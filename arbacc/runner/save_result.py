"""
Сохранение результата акселератора в output.

Зачем:
    После прогона нужно сохранить:
      - manifest.json       — метаданные для skip_existing
      - iterations.*        — траектория (parquet / jsonl.gz / jsonl)
      - result.json         — финал + метрики

    Формат iterations выбирается через settings.STORAGE_FORMAT.

Как расширять:
    Если понадобится сохранять больше (например, ε-таблицу),
    добавь дополнительные файлы рядом.
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from arbacc.core.context import Context
from arbacc.core.result import AcceleratedResult
from arbacc.storage import save_iterations
from arbacc.storage.manifest import build_manifest


def _write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    """Атомарная запись манифеста."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2, default=str)
    tmp.replace(path)


def _write_json(path: Path, obj: dict[str, Any]) -> None:
    """Атомарная запись JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, default=str)
    tmp.replace(path)


def save_accelerated_result(
    output_root: Path,
    series_id: str,
    noise_id: str,
    accel_id: str,
    result: AcceleratedResult,
    ctx: Context,
    input_payload: dict[str, Any],
) -> Path:
    """
    Сохраняет результат акселератора.

    Принимает:
        output_root   — корень output.
        series_id     — id серии.
        noise_id      — id шума.
        accel_id      — id акселератора.
        result        — результат.
        ctx           — контекст.
        input_payload — полное описание входа (для манифеста).

    Возвращает:
        путь к директории акселератора.
    """
    dir_path = output_root / "accel" / series_id / noise_id / accel_id
    dir_path.mkdir(parents=True, exist_ok=True)

    # --- iterations.* (формат из settings) ---
    task_meta = {
        "task_id": f"{series_id}__{noise_id}__{accel_id}",
        "backend": ctx.backend.name,
        "dps": ctx.dps,
        "series_id": series_id,
        "noise_id": noise_id,
        "accel_id": accel_id,
    }
    from arbacc.settings import STORAGE_ITER_STRIDE

    stride = max(1, int(STORAGE_ITER_STRIDE))
    iters = result.iterations
    if stride > 1 and len(iters) > 1:
        # Оставляем каждую stride-ю + последнюю.
        selected = iters[::stride]
        if selected[-1] is not iters[-1]:
            selected = list(selected) + [iters[-1]]
    else:
        selected = list(iters)

    records = []
    for rec in selected:
        records.append({
            "k": rec.k,
            "estimate": (
                ctx.backend.to_str(rec.estimate, ctx.dps)
                if rec.estimate is not None else None
            ),
            "n_used": rec.n_used,
            "_task_meta": task_meta,
        })
    save_iterations(dir_path / "iterations", records)

    # --- result.json ---
    result_obj = {
        "accelerator": result.accelerator,
        "params": result.params,
        "estimate": (
            ctx.backend.to_str(result.estimate, ctx.dps)
            if result.estimate is not None else None
        ),
        "n_used": result.n_used,
        "n_max": result.n_max,
        "stopped_by": result.stopped_by,
        "status": result.status,
        "error": result.error,
        "digits_gained": result.digits_gained,
        "meta": {k: str(v) for k, v in result.meta.items()},
    }
    _write_json(dir_path / "result.json", result_obj)

    # --- manifest.json ---
    _write_manifest(dir_path / "manifest.json", build_manifest(input_payload))
    return dir_path