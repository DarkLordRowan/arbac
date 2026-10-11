"""
Массовый анализ: min / median / mean / max по группам.

Зачем:
    По сводному all_results.parquet нужно быстро отвечать:
      - какой алгоритм даёт больше всего цифр на этом ряду;
      - как backend влияет на качество;
      - где фильтры помогают, а где мешают.

    Анализ через polars — быстрый (миллион строк за секунды).

Как расширять:
    Новые агрегации — добавь в AGG_DEFAULTS.
"""

from __future__ import annotations
from pathlib import Path
from typing import Any

try:
    import polars as pl
except ImportError as e:
    raise ImportError(
        "polars не установлен. Установи: pip install polars"
    ) from e


#: Агрегации по умолчанию для колонки digits_gained.
AGG_DEFAULTS = [
    pl.col("digits_gained").count().alias("count"),
    pl.col("digits_gained").min().alias("min"),
    pl.col("digits_gained").median().alias("median"),
    pl.col("digits_gained").mean().round(2).alias("mean"),
    pl.col("digits_gained").max().alias("max"),
]


def _apply_filters(df: pl.DataFrame, filter_str: str | None) -> pl.DataFrame:
    """
    Применяет фильтры вида "key=value,key2=value2".

    Принимает:
        df         — исходный DataFrame.
        filter_str — строка фильтров.

    Возвращает:
        отфильтрованный DataFrame.
    """
    if not filter_str:
        return df
    for part in filter_str.split(","):
        part = part.strip()
        if not part:
            continue
        k, _, v = part.partition("=")
        k = k.strip()
        v = v.strip()
        if k not in df.columns:
            raise ValueError(f"unknown column in filter: {k!r}")
        # Приводим к строке обе стороны — работает для int/float/str.
        df = df.filter(pl.col(k).cast(pl.Utf8) == v)
    return df


def analyze(
    results_path: Path,
    by: list[str],
    filter_str: str | None = None,
) -> pl.DataFrame:
    """
    Читает all_results.parquet, группирует, агрегирует.

    Принимает:
        results_path — путь к all_results.parquet.
        by           — список колонок для группировки.
        filter_str   — строка фильтров.

    Возвращает:
        polars.DataFrame с колонками by + count, min, median, mean, max.
    """
    df = pl.read_parquet(results_path)
    df = _apply_filters(df, filter_str)

    # Отбрасываем строки без digits_gained.
    df = df.filter(pl.col("digits_gained").is_not_null())

    if not by:
        # Без группировки — одна строка.
        return df.select(AGG_DEFAULTS)

    return df.group_by(by).agg(AGG_DEFAULTS).sort(by)


def format_table(df: pl.DataFrame) -> str:
    """
    Форматирует DataFrame в читаемую таблицу.

    Принимает:
        df — polars DataFrame.

    Возвращает:
        строку для печати в консоль.
    """
    cols = df.columns
    rows = df.to_dicts()

    # Вычисляем ширины столбцов.
    widths = {}
    for c in cols:
        w = len(str(c))
        for r in rows:
            w = max(w, len(str(r.get(c, ""))))
        widths[c] = w

    # Заголовок.
    header = "  ".join(str(c).ljust(widths[c]) for c in cols)
    sep = "  ".join("-" * widths[c] for c in cols)

    lines = [header, sep]
    for r in rows:
        line = "  ".join(
            str(r.get(c, "")).ljust(widths[c]) for c in cols
        )
        lines.append(line)
    return "\n".join(lines)