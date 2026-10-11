"""
Применение постобработок и огибающих после акселератора.

Зачем:
    После прогона акселератора есть траектория оценок. Нужно:
      1. Прогнать offline-огибающие (run_mode="after").
      2. Применить постобработки (KZ, SG, median).
      3. Посчитать метрики относительно exact_sum.
      4. Сохранить всё в output.

    Поддерживает любой формат сохранения (parquet/jsonl.gz/jsonl)
    через settings.STORAGE_FORMAT.

Как расширять:
    Новые типы постобработок подхватываются автоматически через
    реестр. Логика та же.
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from arbacc.core.context import Context
from arbacc.core.envelope import EnvelopeBase
from arbacc.core.postprocess import PostprocessorBase
from arbacc.core.result import AcceleratedResult
from arbacc.runner.metrics import digits_gained, envelope_was_right
from arbacc.storage import save_values
from arbacc.storage.manifest import build_manifest


def _write_json(path: Path, obj: dict[str, Any]) -> None:
    """Атомарная запись JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, default=str)
    tmp.replace(path)


def run_offline_envelopes(
    result: AcceleratedResult,
    envelopes: list[EnvelopeBase],
    ctx: Context,
) -> dict[str, dict[str, Any]]:
    """
    Прогоняет offline-огибающие по траектории.

    Принимает:
        result    — результат акселератора.
        envelopes — список огибающих с run_mode="after".
        ctx       — контекст.

    Возвращает:
        {env_name: {envelope, comparison}}.
    """
    estimates = [rec.estimate for rec in result.iterations]
    actual_stop_at = len(estimates) - 1
    exact = result.exact_sum
    out: dict[str, dict[str, Any]] = {}

    for env in envelopes:
        for v in estimates:
            env.push(v)
        env_result = env.result()

        comparison = envelope_was_right(
            iterations=estimates,
            suggested_stop_at=env_result.get("suggested_stop_at"),
            actual_stop_at=actual_stop_at,
            exact=exact,
            ctx=ctx,
        )
        out[env.name] = {
            "envelope": env_result,
            "comparison": comparison,
        }
    return out


def run_postprocessors(
    result: AcceleratedResult,
    postprocessors: list[PostprocessorBase],
    ctx: Context,
) -> dict[str, dict[str, Any]]:
    """
    Применяет постобработки к траектории.

    Принимает:
        result         — результат акселератора.
        postprocessors — список постобработок.
        ctx            — контекст.

    Возвращает:
        {post_name: {params, final, digits_gained, meta, _values_obj}}.
    """
    estimates = [rec.estimate for rec in result.iterations]
    exact = result.exact_sum
    out: dict[str, dict[str, Any]] = {}

    for pp in postprocessors:
        post_result = pp.apply(estimates, ctx)
        d = (
            digits_gained(post_result.final, exact, ctx)
            if exact is not None else None
        )
        out[pp.name] = {
            "params": dict(pp.params),
            "final": (
                ctx.backend.to_str(post_result.final, ctx.dps)
                if post_result.final is not None else None
            ),
            "digits_gained": d,
            "meta": post_result.meta,
            "_values_obj": post_result.values,
        }
    return out


def save_postprocess_results(
    output_root: Path,
    series_id: str,
    noise_id: str,
    accel_id: str,
    postprocess_out: dict[str, dict[str, Any]],
    envelope_out: dict[str, dict[str, Any]],
    ctx: Context,
    input_payload: dict[str, Any],
) -> Path:
    """
    Сохраняет результаты постобработок и огибающих.

    Принимает:
        output_root       — корень output.
        series_id, noise_id, accel_id — идентификаторы пути.
        postprocess_out   — выход run_postprocessors.
        envelope_out      — выход run_offline_envelopes.
        ctx               — контекст.
        input_payload     — входные данные (для манифеста).

    Возвращает:
        путь к директории постобработки.
    """
    dir_path = output_root / "postprocess" / series_id / noise_id / accel_id
    dir_path.mkdir(parents=True, exist_ok=True)

    task_meta_base = {
        "backend": ctx.backend.name,
        "dps": ctx.dps,
        "series_id": series_id,
        "noise_id": noise_id,
        "accel_id": accel_id,
    }

    # --- Фильтры ---
    for name, data in postprocess_out.items():
        sub = dir_path / "filters" / name
        sub.mkdir(parents=True, exist_ok=True)

        # values.* — своя локальная переменная records для каждого фильтра.
        values_obj = data.get("_values_obj", [])
        task_meta = {
            **task_meta_base,
            "task_id": f"{series_id}__{noise_id}__{accel_id}__{name}",
        }
        records = []
        for k, v in enumerate(values_obj):
            records.append({
                "k": k,
                "value": (
                    ctx.backend.to_str(v, ctx.dps)
                    if v is not None else None
                ),
                "_task_meta": task_meta,
            })
        save_values(sub / "values", records)

        # summary.json
        summary = {k: v for k, v in data.items() if k != "_values_obj"}
        _write_json(sub / "summary.json", summary)

    # --- Огибающие ---
    for name, data in envelope_out.items():
        sub = dir_path / "envelopes" / name
        sub.mkdir(parents=True, exist_ok=True)
        _write_json(sub / "summary.json", data)

    # --- Общий манифест ---
    _write_json(dir_path / "manifest.json", build_manifest(input_payload))
    return dir_path