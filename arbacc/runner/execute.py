"""
Выполнение задач акселерации и постобработки.

Разделены на два этапа:
    - execute_accel — прогон series → noise → accel, сохранение.
    - execute_post  — чтение сохранённого результата и применение
                      постобработки/огибающей.

Акселератор считается один раз. Постобработок может быть много,
каждая читает готовый результат.

Поддерживает любой формат сохранения iterations: parquet, jsonl.gz,
jsonl (см. settings.STORAGE_FORMAT).
"""

from __future__ import annotations
import json
import traceback
from pathlib import Path
from typing import Any

from arbacc.core.context import Context
from arbacc.core.registry import get
from arbacc.precision import get_backend
from arbacc.runner.metrics import digits_gained
from arbacc.runner.run_accel import run_accelerator
from arbacc.runner.run_postprocess import (
    run_offline_envelopes,
    run_postprocessors,
    save_postprocess_results,
)
from arbacc.runner.save_result import save_accelerated_result
from arbacc.runner.skip import build_input_payload
from arbacc.storage import load_iterations


def execute_accel(task: dict[str, Any], output_root: Path) -> dict[str, Any]:
    """
    Выполняет задачу акселерации.

    Принимает:
        task        — задача из plan["accel"].
        output_root — корень output.

    Возвращает:
        {"status", "task_id", "n_used", "stopped_by", "digits_gained",
         "accel_dir", "error"?}
    """
    try:
        # 1. Context. Создание Context'а автоматически активирует
        #    глобальный контекст backend'а на нужный dps
        #    (см. Context.__post_init__).
        backend_name = task["precision"]["backend"]
        dps = int(task["precision"]["dps"])
        backend = get_backend(backend_name)
        rounding = task["precision"].get("rounding", "nearest")
        ctx = Context(backend=backend, dps=dps, rounding=rounding)
        # (удалена строка: import mpmath as mp; mp.mp.dps = dps —
        #  теперь это делает Context.__post_init__)

        # Для mpmath устанавливаем глобальный dps.
        if backend_name == "mpmath":
            import mpmath as mp
            mp.mp.dps = dps

        # 2. Series.
        SeriesCls = get("series", task["series"]["type"])
        series_params = task["series"].get("params", {})
        exact_sum_str = task["series"].get("exact_sum")
        series = SeriesCls(params=series_params, exact_sum=exact_sum_str)
        source = series.build_stream(ctx)

        # 3. Noise.
        NoiseCls = get("noise", task["noise"]["type"])
        noise_params = task["noise"].get("params", {})
        seed = int(task["noise"].get("seed", 0))
        noise = NoiseCls(params=noise_params, seed=seed)
        noisy = noise.wrap(source, ctx)

        # 4. Accelerator.
        AccelCls = get("accelerators", task["accelerator"]["type"])
        accelerator = AccelCls(params=task["accelerator"].get("params", {}))

        # 5. Stopping.
        stopping = []
        for spec in task["accelerator"].get("stopping", []):
            SCls = get("stopping", spec["type"])
            stopping.append(SCls(params=spec.get("params", {})))
        stopping_mode = task["accelerator"].get("stopping_mode", "any")

        # 6. Online envelopes — пока не поддерживаются в accel.
        online_envelopes: list = []

        # 7. n_max.
        n_max = int(task["accelerator"].get("n_max", 100000))

        # 8. Запуск.
        result = run_accelerator(
            source=noisy,
            accelerator=accelerator,
            stopping_criteria=stopping,
            stopping_mode=stopping_mode,
            online_envelopes=online_envelopes,
            ctx=ctx,
            n_max=n_max,
        )
        result.exact_sum = series.exact_sum(ctx)
        if result.exact_sum is not None and result.estimate is not None:
            result.digits_gained = digits_gained(
                result.estimate, result.exact_sum, ctx
            )

        # 9. Сохранение.
        input_payload = build_input_payload(task)
        accel_dir = save_accelerated_result(
            output_root=output_root,
            series_id=task["ids"]["series_id"],
            noise_id=task["ids"]["noise_id"],
            accel_id=task["ids"]["accel_id"],
            result=result,
            ctx=ctx,
            input_payload=input_payload,
        )

        return {
            "status": result.status,
            "task_id": task["task_id"],
            "n_used": result.n_used,
            "stopped_by": result.stopped_by,
            "digits_gained": result.digits_gained,
            "accel_dir": str(accel_dir),
        }

    except Exception as e:
        return {
            "status": "failed",
            "task_id": task["task_id"],
            "error": f"{type(e).__name__}: {e}",
            "traceback": traceback.format_exc(),
        }


def execute_post(task: dict[str, Any], output_root: Path) -> dict[str, Any]:
    """
    Выполняет задачу постобработки.

    Читает результат родительской задачи акселерации, применяет
    постобработку или огибающую. Работает с любым форматом
    iterations (parquet, jsonl.gz, jsonl).

    Принимает:
        task        — задача из plan["post"].
        output_root — корень output.

    Возвращает:
        {"status", "task_id", "post_dir"?, "error"?}
    """
    try:
        ids = task["ids"]

        # Context — создаём сразу, чтобы активировать dps backend'а
        # до чтения чисел и работы фильтров.
        backend_name = task["precision"]["backend"]
        dps = int(task["precision"]["dps"])
        backend = get_backend(backend_name)
        rounding = task["precision"].get("rounding", "nearest")
        ctx = Context(backend=backend, dps=dps, rounding=rounding)

        # Путь к родительскому результату.
        parent_dir = (
            output_root / "accel"
            / ids["series_id"] / ids["noise_id"] / ids["accel_id"]
        )
        result_path = parent_dir / "result.json"

        if not result_path.exists():
            return {
                "status": "skipped",
                "task_id": task["task_id"],
                "error": "parent accel result not found (parent failed)",
            }

        # iterations может быть в .parquet, .jsonl.gz или .jsonl.
        parent_iters = load_iterations(parent_dir / "iterations")
        if not parent_iters:
            return {
                "status": "skipped",
                "task_id": task["task_id"],
                "error": "parent accel iterations not found",
            }

        result = _load_accelerated_result(result_path, parent_dir, ctx)

        # Postprocess.
        postprocessors = []
        offline_envelopes = []
        if task.get("postprocess") is not None:
            PPCls = get("postprocess", task["postprocess"]["type"])
            postprocessors.append(
                PPCls(params=task["postprocess"].get("params", {}))
            )
        if task.get("envelope") is not None:
            EnvCls = get("envelopes", task["envelope"]["type"])
            env_params = dict(task["envelope"].get("params", {}))
            env_params.setdefault("run_mode", "after")
            env_params.setdefault("used_as", "observer")
            offline_envelopes.append(EnvCls(params=env_params))

        env_out = run_offline_envelopes(result, offline_envelopes, ctx)
        pp_out = run_postprocessors(result, postprocessors, ctx)

        input_payload = build_input_payload(task)
        post_dir = save_postprocess_results(
            output_root=output_root,
            series_id=ids["series_id"],
            noise_id=ids["noise_id"],
            accel_id=ids["accel_id"],
            postprocess_out=pp_out,
            envelope_out=env_out,
            ctx=ctx,
            input_payload=input_payload,
        )
        return {
            "status": "ok",
            "task_id": task["task_id"],
            "post_dir": str(post_dir),
        }

    except Exception as e:
        return {
            "status": "failed",
            "task_id": task["task_id"],
            "error": f"{type(e).__name__}: {e}",
            "traceback": traceback.format_exc(),
        }


def _load_accelerated_result(
    result_path: Path,
    parent_dir: Path,
    ctx: Context,
):
    """
    Восстанавливает AcceleratedResult из result.json и iterations.*.

    Принимает:
        result_path — путь к result.json.
        parent_dir  — директория акселератора (в ней iterations.*).
        ctx         — контекст.

    Возвращает:
        AcceleratedResult.
    """
    from arbacc.core.result import AcceleratedResult, IterationRecord

    result_obj = json.loads(result_path.read_text(encoding="utf-8"))
    iter_records = load_iterations(parent_dir / "iterations")

    iterations = []
    for r in iter_records:
        est_str = r.get("estimate")
        if est_str is None:
            continue
        try:
            est = ctx.backend.from_str(est_str, ctx.dps)
        except Exception:
            continue
        iterations.append(
            IterationRecord(
                k=int(r["k"]),
                estimate=est,
                n_used=int(r.get("n_used", 0)),
            )
        )

    estimate = None
    if result_obj.get("estimate") is not None:
        try:
            estimate = ctx.backend.from_str(
                result_obj["estimate"], ctx.dps
            )
        except Exception:
            estimate = None

    return AcceleratedResult(
        accelerator=result_obj.get("accelerator", "?"),
        params=result_obj.get("params", {}),
        iterations=iterations,
        estimate=estimate,
        n_used=int(result_obj.get("n_used", 0)),
        n_max=result_obj.get("n_max"),
        stopped_by=result_obj.get("stopped_by", ""),
        status=result_obj.get("status", "ok"),
        exact_sum=None,
        digits_gained=result_obj.get("digits_gained"),
    )