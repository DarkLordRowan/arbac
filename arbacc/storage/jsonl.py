"""
Чтение/запись JSONL с числами в виде строк.

Зачем:
    Числа в arb prec нельзя писать как float. Пишем строки через
    backend.to_str. Читаем через backend.from_str.

    Формат: одна JSON-строка на строку файла.
        {"n": 0, "value": "1.20205..."}

    Поддерживает gzip через параметр compress.

Как расширять:
    Другие форматы (parquet, msgpack) — отдельные модули.
"""

from __future__ import annotations
import gzip
import json
from pathlib import Path
from typing import Any, Iterable

from arbacc.core.context import Context


def _open_write(path: Path, compress: bool):
    """Открывает файл для записи."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if compress:
        return gzip.open(path, "wt", encoding="utf-8")
    return path.open("w", encoding="utf-8")


def _open_read(path: Path):
    """Открывает файл для чтения (gzip или обычный)."""
    if str(path).endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8")
    return path.open("r", encoding="utf-8")


def write_jsonl(
    path: Path,
    records: Iterable[dict[str, Any]],
    compress: bool = False,
) -> None:
    """
    Записывает список словарей в JSONL.

    Принимает:
        path     — путь к файлу.
        records  — итерируемое по словарям.
        compress — сжимать gzip (имя файла должно оканчиваться .gz).
    """
    with _open_write(path, compress) as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False))
            f.write("\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """
    Читает JSONL-файл.

    Принимает:
        path — путь (может оканчиваться .gz, или .jsonl без .gz
               при наличии .jsonl.gz рядом).

    Возвращает:
        список словарей.
    """
    if not str(path).endswith(".gz"):
        alt = Path(str(path) + ".gz")
        if alt.exists() and not path.exists():
            path = alt
    out: list[dict[str, Any]] = []
    with _open_read(path) as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def stream_to_jsonl(
    stream,
    path: Path,
    ctx: Context,
    n_values: int,
    label: str = "value",
    compress: bool = False,
) -> None:
    """
    Сохраняет первые n_values элементов Stream в JSONL.

    Принимает:
        stream   — Stream.
        path     — путь к файлу.
        ctx      — контекст.
        n_values — сколько элементов сохранить.
        label    — имя поля значения.
        compress — сжимать gzip.
    """
    stream.extend_to(n_values - 1)
    records = []
    for n in range(n_values):
        v = stream.get(n)
        records.append({
            "n": n,
            label: ctx.backend.to_str(v, ctx.dps),
        })
    write_jsonl(path, records, compress=compress)