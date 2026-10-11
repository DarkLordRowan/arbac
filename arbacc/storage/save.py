"""
Сохранение series и noise в output.

Зачем:
    Каждый узел цепочки (series, noise) сохраняется на диск:
      - manifest.json — метаданные для skip_existing,
      - stream.jsonl  — сами значения (как строки).

    Структура output:
        out/{run_id}/{dps}/
            series/{series_id}/
                manifest.json
                stream.jsonl
            noise/{series_id}/{noise_id}/
                manifest.json
                stream.jsonl

Как расширять:
    Для сохранения акселератора — см. runner/save_result.py.
    Для постобработки — см. runner/run_postprocess.py.
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from arbacc.core.context import Context
from arbacc.storage.jsonl import stream_to_jsonl
from arbacc.storage.manifest import build_manifest


def _write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    """Записывает манифест в JSON (атомарно, через tmp+rename)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2, default=str)
    tmp.replace(path)


def save_series(
    output_root: Path,
    series_id: str,
    series_params: dict[str, Any],
    stream,
    ctx: Context,
    n_values: int,
    series_type: str,
) -> Path:
    """
    Сохраняет ряд в output.

    Принимает:
        output_root   — корень output.
        series_id     — id серии (для пути).
        series_params — параметры.
        stream        — Stream серии.
        ctx           — контекст.
        n_values      — сколько значений сохранить.
        series_type   — имя типа ("zeta", "geometric", ...).

    Возвращает:
        путь к директории серии.
    """
    dir_path = output_root / "series" / series_id
    dir_path.mkdir(parents=True, exist_ok=True)

    stream_to_jsonl(stream, dir_path / "stream.jsonl", ctx, n_values)

    payload = {
        "kind": "series",
        "type": series_type,
        "id": series_id,
        "params": series_params,
        "dps": ctx.dps,
        "backend": ctx.backend.name,
        "n_values": n_values,
    }
    _write_manifest(dir_path / "manifest.json", build_manifest(payload))
    return dir_path


def save_noise(
    output_root: Path,
    series_id: str,
    noise_id: str,
    noise_params: dict[str, Any],
    noise_type: str,
    seed: int,
    noisy_stream,
    ctx: Context,
    n_values: int,
) -> Path:
    """
    Сохраняет зашумлённый ряд в output.

    Принимает:
        output_root  — корень output.
        series_id    — id серии (для вложенности пути).
        noise_id     — id шума.
        noise_params — параметры шума.
        noise_type   — имя типа шума.
        seed         — seed.
        noisy_stream — Stream зашумлённой серии.
        ctx          — контекст.
        n_values     — сколько значений сохранить.

    Возвращает:
        путь к директории шума.
    """
    dir_path = output_root / "noise" / series_id / noise_id
    dir_path.mkdir(parents=True, exist_ok=True)

    stream_to_jsonl(noisy_stream, dir_path / "stream.jsonl", ctx, n_values)

    payload = {
        "kind": "noise",
        "type": noise_type,
        "id": noise_id,
        "params": noise_params,
        "seed": seed,
        "series_id": series_id,
        "dps": ctx.dps,
        "backend": ctx.backend.name,
        "n_values": n_values,
    }
    _write_manifest(dir_path / "manifest.json", build_manifest(payload))
    return dir_path