"""
Консолидация output в единые parquet-файлы для массового анализа.

Зачем:
    Output разложен по директориям задач (accel/.../result.json,
    iterations.parquet, postprocess/.../summary.json и т.д.). Для
    массового анализа удобнее иметь три сводных файла:

        all_results.parquet     — по одной строке на accel-задачу
        all_iterations.parquet  — все iterations всех задач
        all_values.parquet      — все values фильтров
        all_envelopes.parquet   — все огибающие с метаданными

    По ним можно делать group_by / min / median в одну строку.

Как расширять:
    Новые сводки — новая функция по образцу export_results.
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any

try:
    import pyarrow as pa
    import pyarrow.parquet as pq
except ImportError as e:
    raise ImportError(
        "pyarrow не установлен. Установи: pip install pyarrow"
    ) from e


# --- Схемы -----------------------------------------------------------

RESULTS_SCHEMA = pa.schema([
    ("task_id", pa.string()),
    ("series_id", pa.string()),
    ("noise_id", pa.string()),
    ("accel_id", pa.string()),
    ("backend", pa.string()),
    ("dps", pa.int32()),
    ("accelerator", pa.string()),
    ("estimate", pa.string()),
    ("estimate_f64", pa.float64()),
    ("exact_sum", pa.string()),
    ("n_used", pa.int32()),
    ("n_max", pa.int32()),
    ("stopped_by", pa.string()),
    ("status", pa.string()),
    ("error", pa.string()),
    ("digits_gained", pa.int32()),
])

ENVELOPES_SCHEMA = pa.schema([
    ("task_id", pa.string()),
    ("series_id", pa.string()),
    ("noise_id", pa.string()),
    ("accel_id", pa.string()),
    ("envelope", pa.string()),
    ("suggested_stop_at", pa.int32()),
    ("window", pa.int32()),
    ("threshold", pa.float64()),
    ("n_values", pa.int32()),
    ("envelope_length", pa.int32()),
    ("digits_at_suggestion", pa.int32()),
    ("digits_at_actual", pa.int32()),
    ("envelope_was_right", pa.bool_()),
    ("digits_lost", pa.int32()),
])


def _safe_float(s: Any) -> float | None:
    """Строка → float без исключения."""
    if s is None:
        return None
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _safe_int(s: Any) -> int | None:
    """Значение → int без исключения."""
    if s is None:
        return None
    try:
        return int(s)
    except (ValueError, TypeError):
        return None


# --- Results ---------------------------------------------------------

def _read_result_row(accel_dir: Path) -> dict[str, Any] | None:
    """
    Читает result.json + manifest.json одной accel-задачи.

    Принимает:
        accel_dir — путь accel/{sid}/{nid}/{aid}.

    Возвращает:
        словарь с колонками RESULTS_SCHEMA или None.
    """
    result_path = accel_dir / "result.json"
    manifest_path = accel_dir / "manifest.json"
    if not (result_path.exists() and manifest_path.exists()):
        return None

    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    inp = manifest.get("input", {}) or {}
    prec = inp.get("precision", {}) or {}
    series = inp.get("series", {}) or {}

    sid = accel_dir.parent.parent.name
    nid = accel_dir.parent.name
    aid = accel_dir.name

    exact_str = (
        series.get("exact_sum")
        or (series.get("params", {}) or {}).get("exact_sum")
    )

    return {
        "task_id": f"{sid}__{nid}__{aid}",
        "series_id": sid,
        "noise_id": nid,
        "accel_id": aid,
        "backend": prec.get("backend", ""),
        "dps": _safe_int(prec.get("dps")),
        "accelerator": result.get("accelerator", ""),
        "estimate": result.get("estimate"),
        "estimate_f64": _safe_float(result.get("estimate")),
        "exact_sum": str(exact_str) if exact_str else None,
        "n_used": _safe_int(result.get("n_used")),
        "n_max": _safe_int(result.get("n_max")),
        "stopped_by": result.get("stopped_by", ""),
        "status": result.get("status", ""),
        "error": result.get("error"),
        "digits_gained": _safe_int(result.get("digits_gained")),
    }


def export_results(output_root: Path, out_path: Path) -> int:
    """
    Собирает все accel/*/*/*/result.json в один parquet.

    Принимает:
        output_root — корень output.
        out_path    — путь к all_results.parquet.

    Возвращает:
        число строк.
    """
    accel_dir = output_root / "accel"
    if not accel_dir.exists():
        out_path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(pa.Table.from_pylist([], schema=RESULTS_SCHEMA), out_path)
        return 0

    rows = []
    for sid_dir in sorted(accel_dir.iterdir()):
        if not sid_dir.is_dir():
            continue
        for nid_dir in sorted(sid_dir.iterdir()):
            if not nid_dir.is_dir():
                continue
            for aid_dir in sorted(nid_dir.iterdir()):
                if not aid_dir.is_dir():
                    continue
                row = _read_result_row(aid_dir)
                if row is not None:
                    rows.append(row)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist(rows, schema=RESULTS_SCHEMA)
    pq.write_table(table, out_path, compression="zstd")
    return len(rows)


# --- Iterations ------------------------------------------------------

def export_iterations(output_root: Path, out_path: Path) -> int:
    """
    Собирает все accel/*/*/*/iterations.parquet в один parquet.

    Если файл в формате jsonl — пропускается (надо сначала пересохранить).

    Возвращает:
        число строк.
    """
    accel_dir = output_root / "accel"
    tables = []
    if accel_dir.exists():
        for sid_dir in sorted(accel_dir.iterdir()):
            if not sid_dir.is_dir():
                continue
            for nid_dir in sorted(sid_dir.iterdir()):
                if not nid_dir.is_dir():
                    continue
                for aid_dir in sorted(nid_dir.iterdir()):
                    if not aid_dir.is_dir():
                        continue
                    p = aid_dir / "iterations.parquet"
                    if p.exists():
                        tables.append(pq.read_table(p))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    if not tables:
        # Пустая таблица со схемой из parquet.py.
        from arbacc.storage.parquet import ITER_SCHEMA
        pq.write_table(
            pa.Table.from_pylist([], schema=ITER_SCHEMA), out_path,
        )
        return 0

    combined = pa.concat_tables(tables, promote_options="default")
    pq.write_table(combined, out_path, compression="zstd")
    return combined.num_rows


# --- Values (postprocess) -------------------------------------------

def export_values(output_root: Path, out_path: Path) -> int:
    """
    Собирает все postprocess/*/*/*/filters/*/values.parquet.

    Возвращает:
        число строк.
    """
    pp_dir = output_root / "postprocess"
    tables = []
    if pp_dir.exists():
        for sid_dir in sorted(pp_dir.iterdir()):
            if not sid_dir.is_dir():
                continue
            for nid_dir in sorted(sid_dir.iterdir()):
                if not nid_dir.is_dir():
                    continue
                for aid_dir in sorted(nid_dir.iterdir()):
                    if not aid_dir.is_dir():
                        continue
                    filters_dir = aid_dir / "filters"
                    if not filters_dir.exists():
                        continue
                    for f_sub in sorted(filters_dir.iterdir()):
                        p = f_sub / "values.parquet"
                        if p.exists():
                            tables.append(pq.read_table(p))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    if not tables:
        from arbacc.storage.parquet import VALUES_SCHEMA
        pq.write_table(
            pa.Table.from_pylist([], schema=VALUES_SCHEMA), out_path,
        )
        return 0

    combined = pa.concat_tables(tables, promote_options="default")
    pq.write_table(combined, out_path, compression="zstd")
    return combined.num_rows


# --- Envelopes -------------------------------------------------------

def export_envelopes(output_root: Path, out_path: Path) -> int:
    """
    Собирает все postprocess/*/*/*/envelopes/*/summary.json.

    Возвращает:
        число строк.
    """
    pp_dir = output_root / "postprocess"
    rows = []
    if pp_dir.exists():
        for sid_dir in sorted(pp_dir.iterdir()):
            if not sid_dir.is_dir():
                continue
            for nid_dir in sorted(sid_dir.iterdir()):
                if not nid_dir.is_dir():
                    continue
                for aid_dir in sorted(nid_dir.iterdir()):
                    if not aid_dir.is_dir():
                        continue
                    env_dir = aid_dir / "envelopes"
                    if not env_dir.exists():
                        continue
                    for e_sub in sorted(env_dir.iterdir()):
                        sp = e_sub / "summary.json"
                        if not sp.exists():
                            continue
                        try:
                            data = json.loads(
                                sp.read_text(encoding="utf-8")
                            )
                        except (OSError, json.JSONDecodeError):
                            continue
                        env = data.get("envelope", {}) or {}
                        comp = data.get("comparison", {}) or {}
                        rows.append({
                            "task_id": (
                                f"{sid_dir.name}__{nid_dir.name}"
                                f"__{aid_dir.name}__{e_sub.name}"
                            ),
                            "series_id": sid_dir.name,
                            "noise_id": nid_dir.name,
                            "accel_id": aid_dir.name,
                            "envelope": env.get("envelope", e_sub.name),
                            "suggested_stop_at": _safe_int(
                                env.get("suggested_stop_at")
                            ),
                            "window": _safe_int(env.get("window")),
                            "threshold": _safe_float(env.get("threshold")),
                            "n_values": _safe_int(env.get("n_values")),
                            "envelope_length": _safe_int(
                                env.get("envelope_length")
                            ),
                            "digits_at_suggestion": _safe_int(
                                comp.get("digits_at_suggestion")
                            ),
                            "digits_at_actual": _safe_int(
                                comp.get("digits_at_actual")
                            ),
                            "envelope_was_right": comp.get(
                                "envelope_was_right"
                            ),
                            "digits_lost": _safe_int(
                                comp.get("digits_lost")
                            ),
                        })

    out_path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist(rows, schema=ENVELOPES_SCHEMA)
    pq.write_table(table, out_path, compression="zstd")
    return len(rows)


# --- Главная функция -------------------------------------------------

def export_all(
    output_root: Path,
    out_dir: Path | None = None,
) -> dict[str, int]:
    """
    Собирает все сводные parquet-файлы.

    Принимает:
        output_root — корень output.
        out_dir     — куда писать (по умолчанию — в output_root).

    Возвращает:
        {"results": N, "iterations": N, "values": N, "envelopes": N}.
    """
    output_root = Path(output_root)
    out_dir = Path(out_dir) if out_dir else output_root
    out_dir.mkdir(parents=True, exist_ok=True)

    return {
        "results": export_results(output_root, out_dir / "all_results.parquet"),
        "iterations": export_iterations(output_root, out_dir / "all_iterations.parquet"),
        "values": export_values(output_root, out_dir / "all_values.parquet"),
        "envelopes": export_envelopes(output_root, out_dir / "all_envelopes.parquet"),
    }