"""
Чтение/запись Parquet для крупных прогонов.

Зачем:
    При 10 000+ задач JSONL занимает десятки гигабайт.
    Parquet с колоночным сжатием даёт 10-30× экономии.

    Формат колонок iterations:
        task_id:      str
        k:            int32
        estimate:     str    (полная строка, arb prec)
        estimate_f64: float  (приближение, для аналитики)
        n_used:       int32
        backend:      str
        dps:          int32
        series_id:    str
        noise_id:     str
        accel_id:     str

    Формат колонок values (postprocess):
        task_id:      str
        k:            int32
        value:        str
        value_f64:    float

Как расширять:
    Новые колонки — добавь в схему в ITER_SCHEMA.
    Новые форматы — добавь функцию по образцу.
"""

from __future__ import annotations
import math
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

ITER_SCHEMA = pa.schema([
    ("task_id", pa.string()),
    ("k", pa.int32()),
    ("estimate", pa.string()),
    ("estimate_f64", pa.float64()),
    ("n_used", pa.int32()),
    ("backend", pa.string()),
    ("dps", pa.int32()),
    ("series_id", pa.string()),
    ("noise_id", pa.string()),
    ("accel_id", pa.string()),
])

VALUES_SCHEMA = pa.schema([
    ("task_id", pa.string()),
    ("k", pa.int32()),
    ("value", pa.string()),
    ("value_f64", pa.float64()),
])


# --- Утилиты --------------------------------------------------------

def _safe_float(s: Any) -> float:
    """
    Преобразует строку в float без исключения.

    Принимает:
        s — строка или None.

    Возвращает:
        float или NaN.
    """
    if s is None:
        return float("nan")
    try:
        return float(s)
    except (ValueError, TypeError):
        return float("nan")


# --- Iterations -----------------------------------------------------

def write_iterations_parquet(
    path: Path,
    rows: list[dict[str, Any]],
    compression: str = "zstd",
) -> None:
    """
    Записывает список словарей iterations в Parquet.

    Принимает:
        path        — путь к .parquet.
        rows        — список словарей. Если в записи есть поле
                      "_task_meta" (dict со series_id, noise_id, ...),
                      оно раскладывается в колонки.
        compression — "snappy" | "gzip" | "zstd".
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    # Приводим строки к схеме. Если в записи есть task_id и estimate —
    # просто конвертируем. Если нет — берём из meta.
    prepared = []
    for r in rows:
        meta = r.get("_task_meta", {})
        prep = {
            "task_id": r.get("task_id") or meta.get("task_id", ""),
            "k": int(r.get("k", 0)),
            "estimate": str(r.get("estimate", "")),
            "estimate_f64": _safe_float(r.get("estimate")),
            "n_used": int(r.get("n_used", 0)),
            "backend": meta.get("backend", ""),
            "dps": int(meta.get("dps", 0)),
            "series_id": meta.get("series_id", ""),
            "noise_id": meta.get("noise_id", ""),
            "accel_id": meta.get("accel_id", ""),
        }
        prepared.append(prep)

    table = pa.Table.from_pylist(prepared, schema=ITER_SCHEMA)
    pq.write_table(table, path, compression=compression)


def read_iterations_parquet(path: Path) -> list[dict[str, Any]]:
    """Читает iterations.parquet в список словарей."""
    table = pq.read_table(path)
    return table.to_pylist()


# --- Values (postprocess) ------------------------------------------

def write_values_parquet(
    path: Path,
    rows: list[dict[str, Any]],
    compression: str = "zstd",
) -> None:
    """
    Записывает values.jsonl-совместимый список в Parquet.

    Принимает:
        path        — путь к .parquet.
        rows        — список словарей с полями k, value. Опционально
                      task_id в каждой записи или в meta.
        compression — snappy / gzip / zstd.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    prepared = []
    for r in rows:
        meta = r.get("_task_meta", {})
        prep = {
            "task_id": r.get("task_id") or meta.get("task_id", ""),
            "k": int(r.get("k", 0)),
            "value": str(r.get("value", "")),
            "value_f64": _safe_float(r.get("value")),
        }
        prepared.append(prep)

    table = pa.Table.from_pylist(prepared, schema=VALUES_SCHEMA)
    pq.write_table(table, path, compression=compression)


def read_values_parquet(path: Path) -> list[dict[str, Any]]:
    """Читает values.parquet в список словарей."""
    table = pq.read_table(path)
    return table.to_pylist()