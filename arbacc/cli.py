"""
CLI для arbacc.

Зачем:
    Позволяет запускать эксперименты из JSON-конфига одной командой.
    Три подкоманды:
      - run      — выполнить все задачи из конфига
      - plan     — построить план, но не выполнять
      - validate — проверить конфиг на корректность без запуска

Как расширять:
    Новые подкоманды — добавляй через argparse subparsers.
    Логика выполнения — в runner/.

Примеры:
    py -3 -m arbacc.cli plan examples/config_full.json
    py -3 -m arbacc.cli run examples/config_full.json
    py -3 -m arbacc.cli run examples/config_full.json --only-series zeta3
    py -3 -m arbacc.cli validate examples/config_full.json
"""

from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Импорт пакетов запускает autodiscovery и регистрирует плагины.
import arbacc.series        # noqa: F401
import arbacc.noise         # noqa: F401
import arbacc.accelerators  # noqa: F401
import arbacc.stopping      # noqa: F401
import arbacc.postprocess   # noqa: F401
import arbacc.envelopes     # noqa: F401

from arbacc.runner import (
    build_plan,
    execute_accel,
    execute_post,
    should_skip,
    Progress,
    ErrorLog,
)
from arbacc.storage.jsonl import write_jsonl


def load_config(path: Path) -> dict[str, Any]:
    """
    Загружает JSON-конфиг.

    Принимает:
        path — путь к конфигу

    Возвращает:
        словарь.
    """
    text = path.read_text(encoding="utf-8-sig")
    return json.loads(text)


def cmd_plan(args: argparse.Namespace) -> int:
    """Строит план и сохраняет его. НЕ выполняет задачи."""
    config = load_config(Path(args.config))
    plan = build_plan(config)

    for e in plan.get("errors", []):
        print(f"[WARN] {e}", file=sys.stderr)

    accel_tasks = plan["accel"]
    post_tasks = plan["post"]

    print(f"Plan: {len(accel_tasks)} accel tasks, {len(post_tasks)} post tasks")
    for i, task in enumerate(accel_tasks[:10]):
        print(f"  A[{i}] {task['task_id']}")
    if len(accel_tasks) > 10:
        print(f"  ... and {len(accel_tasks) - 10} more accel tasks")
    for i, task in enumerate(post_tasks[:10]):
        print(f"  P[{i}] {task['task_id']}")
    if len(post_tasks) > 10:
        print(f"  ... and {len(post_tasks) - 10} more post tasks")

    output_root = Path(
        args.output
        or (config.get("output", "out") + "/" + config.get("run_id", "run"))
    )
    output_root.mkdir(parents=True, exist_ok=True)

    records = (
        [{"kind": "accel", "task_id": t["task_id"]} for t in accel_tasks]
        + [{"kind": "post", "task_id": t["task_id"]} for t in post_tasks]
    )
    write_jsonl(output_root / "plan.jsonl", records)
    print(f"Saved plan to {output_root / 'plan.jsonl'}")
    return 0

def cmd_validate(args: argparse.Namespace) -> int:
    """Проверяет конфиг."""
    try:
        config = load_config(Path(args.config))
    except Exception as e:
        print(f"[FAIL] cannot load config: {e}", file=sys.stderr)
        return 1

    errors: list[str] = []
    if "series" not in config:
        errors.append("no 'series' section")
    if "noise" not in config:
        errors.append("no 'noise' section")
    if "accelerators" not in config:
        errors.append("no 'accelerators' section")
    if "precision" not in config:
        errors.append("no 'precision' section")

    try:
        plan = build_plan(config)
        if not plan["accel"]:
            errors.append("plan has no accel tasks")
        # Ошибки валидации параметров.
        errors.extend(plan.get("errors", []))
    except Exception as e:
        errors.append(f"build_plan failed: {type(e).__name__}: {e}")

    if errors:
        for e in errors:
            print(f"[FAIL] {e}", file=sys.stderr)
        return 1

    print(f"[OK] config valid, {len(plan['accel'])} accel + {len(plan['post'])} post tasks")
    return 0

def cmd_run(args: argparse.Namespace) -> int:
    """
    Выполняет задачи из конфига.

    Если задан --parallel N (или PARALLEL_ENABLED в settings), идёт
    через execute_batch (ProcessPoolExecutor). Иначе — последовательный
    цикл.
    """
    config = load_config(Path(args.config))
    plan = build_plan(config)

    # Показываем ошибки валидации до запуска.
    for e in plan.get("errors", []):
        print(f"[WARN] {e}", file=sys.stderr)

    accel_tasks = plan["accel"]
    post_tasks = plan["post"]

    if args.only_series:
        wanted = set(args.only_series.split(","))
        accel_tasks = [t for t in accel_tasks
                       if t["ids"]["series_id"] in wanted]
        post_tasks = [t for t in post_tasks
                      if t["ids"]["series_id"] in wanted]
        print(f"Filtered by series: {len(accel_tasks)} accel, "
              f"{len(post_tasks)} post")

    if args.limit:
        accel_tasks = accel_tasks[: args.limit]
        remaining = max(0, args.limit - len(accel_tasks))
        post_tasks = post_tasks[:remaining]
        print(f"Limited to {len(accel_tasks) + len(post_tasks)} tasks")

    output_root = Path(
        args.output
        or (config.get("output", "out") + "/" + config.get("run_id", "run"))
    )
    output_root.mkdir(parents=True, exist_ok=True)

    skip_existing = args.skip_existing or config.get("skip_existing", False)
    abort_on_error = args.abort_on_error or config.get("abort_on_error", False)

    # --- Определяем режим: параллельный или последовательный ---
    import os
    from arbacc.settings import PARALLEL_ENABLED, PARALLEL_WORKERS

    use_parallel = False
    workers = 0
    if getattr(args, "no_parallel", False):
        use_parallel = False
    elif args.parallel is not None:
        use_parallel = True
        workers = args.parallel or (os.cpu_count() or 1)
    elif PARALLEL_ENABLED:
        use_parallel = True
        workers = PARALLEL_WORKERS or (os.cpu_count() or 1)

    # --- Параллельный путь ---
    if use_parallel and (accel_tasks or post_tasks):
        from arbacc.runner.execute_batch import execute_batch

        print(f"Parallel mode: {workers} workers, "
              f"{len(accel_tasks)} accel + {len(post_tasks)} post tasks")

        def _on_result(r: dict) -> None:
            status = r.get("status", "?")
            tid = r.get("task_id", "?")
            if status == "ok":
                print(f"OK    {tid}")
            elif status == "skipped":
                print(f"SKIP  {tid}")
            else:
                print(f"FAIL  {tid} ({r.get('error', '?')})")

        stats = execute_batch(
            {"accel": accel_tasks, "post": post_tasks},
            output_root,
            workers=workers,
            skip_existing=skip_existing,
            on_result=_on_result,
        )
        print()
        print(
            f"Done: {stats['accel_ok'] + stats['post_ok']}, "
            f"Failed: {stats['accel_failed'] + stats['post_failed']}, "
            f"Skipped: {stats['skipped']}, "
            f"Elapsed: {stats['elapsed']:.2f}s"
        )
        failed = stats["accel_failed"] + stats["post_failed"]
        return 0 if failed == 0 else 1

    # --- Последовательный путь ---
    total = len(accel_tasks) + len(post_tasks)
    print(f"Sequential mode: {len(accel_tasks)} accel + "
          f"{len(post_tasks)} post tasks")

    progress = Progress(total=total)
    errors = ErrorLog(output_root / "errors.log")

    idx = 0
    # Этап 1: акселерация.
    for task in accel_tasks:
        idx += 1
        if skip_existing and should_skip(task, output_root):
            progress.skipped += 1
            progress.last_task = task["task_id"]
            progress.last_status = "skipped"
            progress.save(output_root / "progress.json")
            print(f"[{idx}/{total}] SKIP  {task['task_id']}")
            continue
        result = execute_accel(task, output_root)
        if result["status"] == "ok":
            progress.done += 1
            print(
                f"[{idx}/{total}] OK    {task['task_id']} "
                f"(digits={result.get('digits_gained')}, "
                f"stopped={result.get('stopped_by')})"
            )
        else:
            progress.failed += 1
            errors.log(task, result.get("error", "?"),
                       result.get("traceback"))
            print(f"[{idx}/{total}] FAIL  {task['task_id']} "
                  f"({result.get('error', '?')})")
        progress.last_task = task["task_id"]
        progress.last_status = result["status"]
        progress.save(output_root / "progress.json")
        if abort_on_error and result["status"] == "failed":
            print("Aborting on first error", file=sys.stderr)
            return 1

    # Этап 2: постобработка.
    from arbacc.runner.skip import should_skip_post
    for task in post_tasks:
        idx += 1
        if skip_existing and should_skip_post(task, output_root):
            progress.skipped += 1
            progress.last_task = task["task_id"]
            progress.last_status = "skipped"
            progress.save(output_root / "progress.json")
            print(f"[{idx}/{total}] SKIP  {task['task_id']}")
            continue
        result = execute_post(task, output_root)
        if result["status"] == "ok":
            progress.done += 1
            print(f"[{idx}/{total}] OK    {task['task_id']}")
        elif result["status"] == "skipped":
            progress.skipped += 1
            print(f"[{idx}/{total}] SKIP  {task['task_id']}")
        else:
            progress.failed += 1
            errors.log(task, result.get("error", "?"),
                       result.get("traceback"))
            print(f"[{idx}/{total}] FAIL  {task['task_id']} "
                  f"({result.get('error', '?')})")
        progress.last_task = task["task_id"]
        progress.last_status = result["status"]
        progress.save(output_root / "progress.json")
        if abort_on_error and result["status"] == "failed":
            return 1

    print()
    print(f"Done: {progress.done}, Failed: {progress.failed}, "
          f"Skipped: {progress.skipped}")
    return 0 if progress.failed == 0 else 1

    
def cmd_export(args: argparse.Namespace) -> int:
    """
    Консолидирует output в parquet-файлы для анализа.

    Принимает:
        args.output_root — путь к корню output.
        args.out_dir     — куда писать.

    Возвращает:
        код выхода.
    """
    from pathlib import Path
    from arbacc.storage.export import export_all

    output_root = Path(args.output_root)
    if not output_root.exists():
        print(f"[FAIL] path not found: {output_root}", file=sys.stderr)
        return 1

    out_dir = Path(args.out_dir) if args.out_dir else None
    stats = export_all(output_root, out_dir)

    print(f"Exported to {output_root}:")
    print(f"  all_results.parquet     {stats['results']} rows")
    print(f"  all_iterations.parquet  {stats['iterations']} rows")
    print(f"  all_values.parquet      {stats['values']} rows")
    print(f"  all_envelopes.parquet   {stats['envelopes']} rows")
    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    """
    Анализирует all_results.parquet: min/median/mean/max.

    Принимает:
        args.output_root — путь к корню output.
        args.by          — колонки для группировки (через запятую).
        args.filter      — строка фильтров.

    Возвращает:
        код выхода.
    """
    from pathlib import Path
    from arbacc.analysis import analyze, format_table

    output_root = Path(args.output_root)
    results_path = output_root / "all_results.parquet"
    if not results_path.exists():
        print(
            f"[FAIL] {results_path} not found. "
            f"Сначала запусти: python -m arbacc export {output_root}",
            file=sys.stderr,
        )
        return 1

    by = [c.strip() for c in args.by.split(",") if c.strip()]

    try:
        df = analyze(results_path, by=by, filter_str=args.filter)
    except Exception as e:
        print(f"[FAIL] {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    print(f"=== Сводка по {', '.join(by) if by else '(все)'} ===")
    if args.filter:
        print(f"    filter: {args.filter}")
    print()
    print(format_table(df))
    return 0

def cmd_experiment_report(args: argparse.Namespace) -> int:
    """Export a precision-preserving report from web experiment JSON."""
    from arbacc.core import Context
    from arbacc.precision import get_backend
    from arbacc.analysis.experiment import build_experiment_matrix, export_experiment_report
    try:
        ctx = Context(backend=get_backend(args.backend), dps=args.dps)
        matrix = build_experiment_matrix(load_config(Path(args.experiment)), ctx, epsilon=args.epsilon)
        export_experiment_report(matrix, Path(args.output), ctx)
    except (ValueError, KeyError, OSError, TypeError) as error:
        print(f"[FAIL] {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    print(f"Report: {len(matrix['cells'])} measurements -> {args.output}")
    return 0


def main() -> int:
    """Точка входа CLI."""
    parser = argparse.ArgumentParser(
        prog="arbacc",
        description="arbacc — framework for convergence acceleration experiments",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_plan = sub.add_parser("plan", help="build plan without running")
    p_plan.add_argument("config", help="path to config.json")
    p_plan.add_argument("--output", help="output root override")
    p_plan.set_defaults(func=cmd_plan)

    p_val = sub.add_parser("validate", help="validate config")
    p_val.add_argument("config", help="path to config.json")
    p_val.set_defaults(func=cmd_validate)

    p_run = sub.add_parser("run", help="run experiments")
    p_run.add_argument("config", help="path to config.json")
    p_run.add_argument("--output", help="output root override")
    p_run.add_argument("--skip-existing", action="store_true",
                       help="skip already computed tasks")
    p_run.add_argument("--retry-failed", action="store_true",
                       help="recompute failed tasks")
    p_run.add_argument("--abort-on-error", action="store_true",
                       help="stop on first failure")
    p_run.add_argument("--only-series", help="comma-separated series ids")
    p_run.add_argument("--limit", type=int, help="limit number of tasks")
    p_run.add_argument("--parallel", type=int, default=None,
                       help="параллельный режим: число процессов "
                            "(0 = все ядра). Без флага — из settings.")
    p_run.add_argument("--no-parallel", action="store_true",
                       help="принудительно последовательный режим, "
                            "игнорирует PARALLEL_ENABLED из settings")
    p_run.set_defaults(func=cmd_run)

    # --- export ---
    p_export = sub.add_parser(
        "export",
        help="консолидировать output в parquet для анализа",
    )
    p_export.add_argument("output_root",
                          help="путь к корню output (например, out/exp_001)")
    p_export.add_argument("--out-dir", default=None,
                          help="куда писать сводные parquet "
                               "(по умолчанию — в output_root)")
    p_export.set_defaults(func=cmd_export)

    # --- analyze ---
    p_analyze = sub.add_parser(
        "analyze",
        help="анализ all_results.parquet: min/median/mean/max",
    )
    p_analyze.add_argument("output_root",
                           help="путь к корню output (там лежит all_results.parquet)")
    p_analyze.add_argument("--by", default="accel_id",
                           help="колонки для группировки через запятую "
                                "(accel_id, series_id, noise_id, backend, dps)")
    p_analyze.add_argument("--filter", default=None,
                           help="фильтр вида 'key=value,key2=value2'")
    p_analyze.set_defaults(func=cmd_analyze)

    p_report = sub.add_parser("experiment-report", help="матрица и рейтинг из JSON веб-эксперимента")
    p_report.add_argument("experiment", help="experiment JSON with seriesList/accelList/seriesAccelList")
    p_report.add_argument("output", help="destination .json or .csv")
    p_report.add_argument("--backend", default="mpmath")
    p_report.add_argument("--dps", type=int, default=80)
    p_report.add_argument("--epsilon", default="1e-10")
    p_report.set_defaults(func=cmd_experiment_report)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())