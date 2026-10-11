"""
Публичный экспорт модулей storage.

Зачем:
    Единая точка для сохранения/загрузки в любом формате.

    save_iterations / load_iterations работают с:
        - iterations.parquet
        - iterations.jsonl.gz
        - iterations.jsonl
    Формат выбирается по settings.STORAGE_FORMAT.

Как расширять:
    Новые форматы — добавь функцию по образцу save_iterations.
"""

from __future__ import annotations
from pathlib import Path
from typing import Any

from arbacc.storage.jsonl import (
    write_jsonl, read_jsonl, stream_to_jsonl,
)
from arbacc.storage.manifest import build_manifest
from arbacc.storage.save import save_series, save_noise


# --- Сохранение -----------------------------------------------------

def save_iterations(
    path_stem: Path,
    rows: list[dict[str, Any]],
    fmt: str | None = None,
) -> Path:
    """
    Сохраняет iterations в выбранном формате.

    Принимает:
        path_stem — путь без расширения (например, dir/iterations).
        rows      — список словарей.
        fmt       — "jsonl" / "jsonl.gz" / "parquet".
                    None → из settings.STORAGE_FORMAT.

    Возвращает:
        путь к записанному файлу.
    """
    from arbacc.settings import STORAGE_FORMAT, STORAGE_PARQUET_COMPRESSION
    fmt = fmt or STORAGE_FORMAT

    if fmt == "parquet":
        from arbacc.storage.parquet import write_iterations_parquet
        p = path_stem.with_suffix(".parquet")
        write_iterations_parquet(
            p, rows, compression=STORAGE_PARQUET_COMPRESSION,
        )
        return p

    if fmt == "jsonl.gz":
        p = Path(str(path_stem) + ".jsonl.gz")
        write_jsonl(p, rows, compress=True)
        return p

    p = path_stem.with_suffix(".jsonl")
    write_jsonl(p, rows, compress=False)
    return p


def save_values(
    path_stem: Path,
    rows: list[dict[str, Any]],
    fmt: str | None = None,
) -> Path:
    """
    Сохраняет values (после фильтра) в выбранном формате.
    """
    from arbacc.settings import STORAGE_FORMAT, STORAGE_PARQUET_COMPRESSION
    fmt = fmt or STORAGE_FORMAT

    if fmt == "parquet":
        from arbacc.storage.parquet import write_values_parquet
        p = path_stem.with_suffix(".parquet")
        write_values_parquet(
            p, rows, compression=STORAGE_PARQUET_COMPRESSION,
        )
        return p

    if fmt == "jsonl.gz":
        p = Path(str(path_stem) + ".jsonl.gz")
        write_jsonl(p, rows, compress=True)
        return p

    p = path_stem.with_suffix(".jsonl")
    write_jsonl(p, rows, compress=False)
    return p


# --- Загрузка -------------------------------------------------------

def load_iterations(path_stem: Path) -> list[dict[str, Any]]:
    """
    Загружает iterations из любого доступного формата.

    Приоритет: .parquet → .jsonl.gz → .jsonl.

    Принимает:
        path_stem — путь без расширения.

    Возвращает:
        список словарей.
    """
    pq_path = path_stem.with_suffix(".parquet")
    if pq_path.exists():
        from arbacc.storage.parquet import read_iterations_parquet
        return read_iterations_parquet(pq_path)

    gz_path = Path(str(path_stem) + ".jsonl.gz")
    if gz_path.exists():
        return read_jsonl(gz_path)

    jsonl_path = path_stem.with_suffix(".jsonl")
    if jsonl_path.exists():
        return read_jsonl(jsonl_path)

    return []


def load_values(path_stem: Path) -> list[dict[str, Any]]:
    """
    Загружает values из любого доступного формата.
    """
    pq_path = path_stem.with_suffix(".parquet")
    if pq_path.exists():
        from arbacc.storage.parquet import read_values_parquet
        return read_values_parquet(pq_path)

    gz_path = Path(str(path_stem) + ".jsonl.gz")
    if gz_path.exists():
        return read_jsonl(gz_path)

    jsonl_path = path_stem.with_suffix(".jsonl")
    if jsonl_path.exists():
        return read_jsonl(jsonl_path)

    return []


__all__ = [
    "write_jsonl", "read_jsonl", "stream_to_jsonl",
    "build_manifest", "save_series", "save_noise",
    "save_iterations", "save_values",
    "load_iterations", "load_values",
]