"""
Комплексная проверка этапа 5.

Что проверяется:
    1. expand_node, expand_all — развёртка параметров.
    2. matches — scope.
    3. instance_id — детерминированность.
    4. build_plan на config_full.json — правильное число задач.
    5. execute на минимальной задаче.
    6. skip_existing — после прогона задача скипается.
    7. Progress, ErrorLog — запись файлов.
    8. CLI — plan, validate, run end-to-end.

Запуск:
    cd "Проект Парф Питон"
    py -3 check_stage5.py
"""
from __future__ import annotations
import json
import shutil
import subprocess
import sys
from pathlib import Path

import arbacc.series        # noqa: F401
import arbacc.noise         # noqa: F401
import arbacc.accelerators  # noqa: F401
import arbacc.stopping      # noqa: F401
import arbacc.postprocess   # noqa: F401
import arbacc.envelopes     # noqa: F401

from arbacc.runner import (
    expand_node, expand_all, matches, instance_id, build_plan,
    execute_accel, should_skip, Progress, ErrorLog,
)


def section(title: str) -> None:
    """Печатает заголовок."""
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def check_expand() -> None:
    """Проверяет развёртку параметров."""
    section("1. expand_node / expand_all")
    node = {
        "id": "gauss",
        "type": "gaussian",
        "params": {"sigma": ["1e-3", "1e-6"], "mode": "absolute"},
        "seed": [42, 43],
    }
    combos = expand_node(node)
    print(f"  combinations: {len(combos)} (expected 4)")
    assert len(combos) == 4, f"expand дал {len(combos)} вместо 4"
    # Проверим, что все 4 разные.
    sigmas = sorted(set(c["params"]["sigma"] for c in combos))
    seeds = sorted(set(c["seed"] for c in combos))
    print(f"  sigmas={sigmas}, seeds={seeds}")
    assert sigmas == ["1e-3", "1e-6"]
    assert seeds == [42, 43]

    # expand_all на списке узлов.
    nodes = [
        {"id": "a", "params": {"x": [1, 2]}},
        {"id": "b", "params": {"y": [3, 4, 5]}},
    ]
    all_combos = expand_all(nodes)
    print(f"  expand_all: {len(all_combos)} (expected 5 = 2 + 3)")
    assert len(all_combos) == 5
    print("[OK] expand работает")


def check_matches() -> None:
    """Проверяет scope."""
    section("2. matches (scope)")
    ctx = {"series": "zeta3", "noise": "clean", "accelerator": "aitken"}

    assert matches("all", ctx)
    assert matches(None, ctx)
    assert matches(["zeta3"], ctx)
    assert matches(["zeta3", "other"], ctx)
    assert not matches(["other"], ctx)
    assert matches({"series": "zeta3"}, ctx)
    assert matches({"series": "zeta3", "noise": "clean"}, ctx)
    assert not matches({"series": "zeta3", "noise": "other"}, ctx)
    print("[OK] matches работает")


def check_instance_id() -> None:
    """Проверяет детерминированность id."""
    section("3. instance_id")
    id1 = instance_id("noise", "gaussian", {"sigma": "1e-6"}, {"seed": 42})
    id2 = instance_id("noise", "gaussian", {"sigma": "1e-6"}, {"seed": 42})
    id3 = instance_id("noise", "gaussian", {"sigma": "1e-3"}, {"seed": 42})
    print(f"  id1={id1}")
    print(f"  id3={id3}")
    assert id1 == id2, "instance_id не детерминирован"
    assert id1 != id3, "instance_id не различает параметры"
    print("[OK] instance_id работает")


def check_build_plan(project_root: Path) -> dict:
    """Строит план по config_full.json."""
    section("4. build_plan на config_full.json")
    cfg_path = project_root / "examples" / "config_full.json"
    config = json.loads(cfg_path.read_text(encoding="utf-8-sig"))
    plan = build_plan(config)
    print(f"  accel tasks: {len(plan['accel'])}")
    print(f"  post tasks:  {len(plan['post'])}")
    for i, t in enumerate(plan["accel"][:5]):
        print(f"    A[{i}] {t['task_id']}")
    for i, t in enumerate(plan["post"][:5]):
        print(f"    P[{i}] {t['task_id']}")

    # 2 (dps) × 5 (series,noise,accel) = 10 accel-задач.
    assert len(plan["accel"]) == 10, f"accel: ожидалось 10, получено {len(plan['accel'])}"
    # На каждую accel-задачу: kz + hilbert_obs = 2 post-задачи.
    assert len(plan["post"]) == 20, f"post: ожидалось 20, получено {len(plan['post'])}"

    # Детерминированность.
    plan2 = build_plan(config)
    assert [t["task_id"] for t in plan["accel"]] == [t["task_id"] for t in plan2["accel"]]
    assert [t["task_id"] for t in plan["post"]] == [t["task_id"] for t in plan2["post"]]
    print("[OK] build_plan работает")
    return config


def check_execute(project_root: Path) -> None:
    """Выполняет одну минимальную задачу."""
    section("5. execute_accel")
    cfg_path = project_root / "examples" / "config_minimal.json"
    config = json.loads(cfg_path.read_text(encoding="utf-8-sig"))
    plan = build_plan(config)
    assert len(plan["accel"]) == 1

    out_root = project_root / "out" / "check_stage5"
    if out_root.exists():
        shutil.rmtree(out_root)
    out_root.mkdir(parents=True)

    result = execute_accel(plan["accel"][0], out_root)
    print(f"  status={result['status']}")
    print(f"  n_used={result.get('n_used')}")
    print(f"  stopped_by={result.get('stopped_by')}")
    assert result["status"] == "ok", f"execute_accel упал: {result.get('error')}"
    assert Path(result["accel_dir"]).exists()
    print("[OK] execute_accel работает")


def check_skip(project_root: Path) -> None:
    """Проверяет skip_existing."""
    section("6. skip_existing")
    cfg_path = project_root / "examples" / "config_minimal.json"
    config = json.loads(cfg_path.read_text(encoding="utf-8-sig"))
    plan = build_plan(config)
    task = plan["accel"][0]

    out_root = project_root / "out" / "check_stage5"
    # После check_execute задача уже посчитана.
    skip = should_skip(task, out_root)
    print(f"  should_skip={skip}")
    assert skip, "should_skip не сработал после успешного прогона"

    # Меняем параметр — не должна скипаться.
    task_modified = json.loads(json.dumps(task))
    task_modified["accelerator"]["params"]["_dummy"] = 1
    skip2 = should_skip(task_modified, out_root)
    print(f"  should_skip for modified={skip2}")
    assert not skip2, "should_skip сработал на изменённых параметрах"
    print("[OK] skip_existing работает")


def check_progress_errors(project_root: Path) -> None:
    """Проверяет Progress и ErrorLog."""
    section("7. Progress и ErrorLog")
    out_root = project_root / "out" / "check_stage5"

    # Progress.
    p = Progress(total=10)
    p.done = 7
    p.failed = 1
    p.skipped = 2
    p.last_task = "test"
    p.last_status = "ok"
    p.save(out_root / "progress.json")
    loaded = json.loads((out_root / "progress.json").read_text())
    print(f"  progress: {loaded['done']}/{loaded['total']}")
    assert loaded["done"] == 7

    # ErrorLog.
    el = ErrorLog(out_root / "errors.log")
    el.log({"task_id": "test_task"}, "test error", "traceback line")
    log_text = (out_root / "errors.log").read_text()
    assert "test_task" in log_text
    assert "test error" in log_text
    print("[OK] Progress и ErrorLog работают")


def check_cli(project_root: Path) -> None:
    """Проверяет CLI end-to-end."""
    section("8. CLI")
    cfg_rel = "examples/config_minimal.json"
    out_rel = "out/check_stage5_cli"
    out_root = project_root / "out" / "check_stage5_cli"
    if out_root.exists():
        shutil.rmtree(out_root)

    # validate
    print("  --- validate ---")
    r = subprocess.run(
        [sys.executable, "-m", "arbacc.cli", "validate", cfg_rel],
        capture_output=True, text=True, cwd=str(project_root),
    )
    print(f"  rc={r.returncode}")
    print(f"  stdout={r.stdout.strip()}")
    if r.stderr.strip():
        print(f"  stderr={r.stderr.strip()}")
    assert r.returncode == 0, f"validate упал: {r.stderr}"

    # plan
    print("  --- plan ---")
    r = subprocess.run(
        [sys.executable, "-m", "arbacc.cli", "plan", cfg_rel, "--output", out_rel],
        capture_output=True, text=True, cwd=str(project_root),
    )
    print(f"  rc={r.returncode}")
    print(f"  stdout={r.stdout.strip()}")
    if r.stderr.strip():
        print(f"  stderr={r.stderr.strip()}")
    assert r.returncode == 0, f"plan упал: {r.stderr}"
    assert (out_root / "plan.jsonl").exists(), (
        f"plan.jsonl не найден в {out_root}. "
        f"Содержимое папки: {list(out_root.iterdir()) if out_root.exists() else 'папка не существует'}"
    )

    # run
    print("  --- run ---")
    r = subprocess.run(
        [sys.executable, "-m", "arbacc.cli", "run", cfg_rel, "--output", out_rel],
        capture_output=True, text=True, cwd=str(project_root),
    )
    print(f"  rc={r.returncode}")
    print(f"  stdout={r.stdout.strip()}")
    if r.stderr.strip():
        print(f"  stderr={r.stderr.strip()}")
    assert r.returncode == 0, f"run упал: {r.stderr}"
    assert (out_root / "progress.json").exists(), (
        f"progress.json не найден в {out_root}"
    )

    # run again with skip_existing
    print("  --- run again (skip existing) ---")
    r = subprocess.run(
        [sys.executable, "-m", "arbacc.cli", "run", cfg_rel,
         "--output", out_rel, "--skip-existing"],
        capture_output=True, text=True, cwd=str(project_root),
    )
    print(f"  rc={r.returncode}")
    print(f"  stdout={r.stdout.strip()}")
    if r.stderr.strip():
        print(f"  stderr={r.stderr.strip()}")
    assert "SKIP" in r.stdout, f"skip_existing не сработал в CLI. stdout={r.stdout!r}"
    print("[OK] CLI работает")


def main() -> None:
    """Точка входа."""
    project_root = Path(__file__).parent.resolve()

    check_expand()
    check_matches()
    check_instance_id()
    check_build_plan(project_root)
    check_execute(project_root)
    check_skip(project_root)
    check_progress_errors(project_root)
    check_cli(project_root)

    print("\n" + "=" * 70)
    print("ВСЕ ПРОВЕРКИ ЭТАПА 5 ПРОЙДЕНЫ")
    print("=" * 70)


if __name__ == "__main__":
    main()