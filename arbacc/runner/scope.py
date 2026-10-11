"""
Проверка области действия (applies_to).

Зачем:
    Компонент может применяться:
      - ко всем ("all" или None),
      - к перечисленным id ([...]),
      - к конкретному контексту ({field: value}).

    id — читаемые (см. runner/id.py). Например, "zeta_s3".

    Списки поддерживают ПРЕФИКСНОЕ совпадение:
      applies_to: ["zeta"]     — матчит "zeta_s3", "zeta_s5", ...
      applies_to: ["zeta_s3"]  — матчит только "zeta_s3".

Как расширять:
    Регулярные выражения или wildcards — можно добавить сюда.
"""

from __future__ import annotations
from typing import Any


def matches(applies_to: Any, context: dict[str, str]) -> bool:
    """
    Проверяет, применяется ли компонент к данному контексту.

    Принимает:
        applies_to — "all" | "id" | [id...] | {field: value} | None.
        context    — {field: value} — текущий контекст
                     (например, {"series": "zeta_s3"}).

    Возвращает:
        True, если применяется.
    """
    if applies_to is None or applies_to == "all":
        return True

    # Одиночная строка трактуется как список из одного id.
    if isinstance(applies_to, str):
        return _match_one(applies_to, context)

    if isinstance(applies_to, list):
        for value in applies_to:
            if _match_one(str(value), context):
                return True
        return False

    if isinstance(applies_to, dict):
        for k, v in applies_to.items():
            if context.get(k) != v:
                return False
        return True

    raise ValueError(f"Bad applies_to: {applies_to!r}")


def _match_one(value: str, context: dict[str, str]) -> bool:
    """
    Совпадение одного значения с любым полем контекста.

    Поддерживает префикс: "zeta" матчит "zeta_s3" (с разделителем "_").

    Принимает:
        value   — значение из applies_to.
        context — {field: value}.

    Возвращает:
        bool.
    """
    for cv in context.values():
        if cv == value or cv.startswith(value + "_"):
            return True
    return False