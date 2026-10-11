"""
Загрузка готовой последовательности из CSV или TXT.

Зачем:
    Иногда ряд не сгенерировать формулой — он получен извне. Здесь
    читаем его один раз, кэшируем и отдаём как обычный Stream.

    Формат CSV: одна колонка с числами (первая строка — заголовок).
    Формат TXT: по одному числу в строке.

    Числа должны быть записаны как строки — иначе float потеряет
    точность ещё до того, как мы их прочитаем.

Как расширять:
    Если нужен другой формат (JSON, Parquet) — новый класс
    и @register под новым именем. Ядро менять не нужно.
"""

from __future__ import annotations
import csv
from pathlib import Path
from typing import Any

from arbacc.core.context import Context
from arbacc.core.registry import register
from arbacc.core.series import SeriesBase


@register("series", "from_file")
class FromFileSeries(SeriesBase):
    """Ряд, загружаемый из CSV или TXT."""

    name = "from_file"
    display_name = "file"

    PARAM_SPEC = {
        "path": {
            "type": "file",
            "required": True,
            "default": "",
            "short": "pth",
            "hint": "CSV или TXT",
        },
        "column": {
            "type": "str",
            "default": "",
            "short": "col",
            "hint": "имя колонки для CSV (если есть заголовок)",
        },
        "skip_rows": {
            "type": "int",
            "min": 0,
            "default": 0,
            "short": "sk",
            "hint": "сколько первых строк пропустить",
        },
        "encoding": {
            "type": "enum",
            "values": ["utf-8-sig", "utf-8", "cp1251"],
            "default": "utf-8-sig",
            "short": "enc",
            "short_values": {
                "utf-8-sig": "u8s",
                "utf-8": "u8",
                "cp1251": "cp1251",
            },
            "hint": "utf-8-sig — надёжно для Windows",
        },
    }

    def __init__(self, params: dict[str, Any], exact_sum: str | None = None):
        """
        Принимает:
            params    — параметры ряда.
            exact_sum — точная сумма (для from_file обычно задаётся явно).
        """
        super().__init__(params, exact_sum)
        # Ленивая загрузка: файл читается при первом generate.
        self._values_str: list[str] | None = None

    def _load(self) -> list[str]:
        """
        Загружает значения из файла один раз.

        Возвращает:
            список строк с числами.
        """
        if self._values_str is not None:
            return self._values_str

        path = Path(self.params["path"])
        if not path.exists():
            raise FileNotFoundError(f"Series file not found: {path}")

        skip = int(self.params.get("skip_rows", 0))
        column = self.params.get("column") or None
        encoding = self.params.get("encoding", "utf-8-sig")
        suffix = path.suffix.lower()
        values: list[str] = []

        if suffix == ".csv":
            with path.open("r", encoding=encoding) as f:
                reader = csv.reader(f)
                header: list[str] | None = None
                idx: int = 0
                for i, row in enumerate(reader):
                    if i < skip:
                        continue
                    # Если задана колонка — первая непустая строка
                    # считается заголовком.
                    if i == skip and column is not None and header is None:
                        header = row
                        if column not in header:
                            raise KeyError(
                                f"Column {column!r} not found in {path}. "
                                f"Available: {header}"
                            )
                        idx = header.index(column)
                        continue
                    if not row:
                        continue
                    values.append(row[idx].strip())
        else:
            # TXT: одна строка = одно число.
            with path.open("r", encoding=encoding) as f:
                for i, line in enumerate(f):
                    if i < skip:
                        continue
                    s = line.strip()
                    if s:
                        values.append(s)

        self._values_str = values
        return values

    def generate(self, n: int, ctx: Context) -> Any:
        """
        Возвращает n-й элемент из файла.

        Принимает:
            n   — индекс.
            ctx — контекст.

        Возвращает:
            число backend'а.

        Бросает:
            IndexError — если n выходит за пределы файла.
        """
        values = self._load()
        if n >= len(values):
            raise IndexError(
                f"from_file: index {n} out of range "
                f"(file has {len(values)} values)"
            )
        return ctx.number(values[n])