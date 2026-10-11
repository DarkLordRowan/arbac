"""
Развёртка массивов параметров в декартово произведение.

Зачем нужен:
    В JSON-конфиге любой параметр может быть либо скаляром, либо массивом.
    Например:
        "dps": [10, 20, 100]
        "params": {"sigma": ["1e-3", "1e-6"], "mode": "absolute"}
    Нужно развернуть это в плоский список конкретных инстансов
    (в данном случае 3 * 2 = 6 инстансов).

    Правило: если значение — список, оно раскрывается в декартово
    произведение со всеми остальными списками в этом узле. Если скаляр —
    считается списком из одного элемента.

    Вложенные словари (например, params внутри узла) разворачиваются
    рекурсивно.

    ИСКЛЮЧЕНИЕ: некоторые поля не подлежат развёртке, потому что
    семантически являются предикатами, а не параметрами. Например,
    `applies_to: ["zeta3", "geom"]` означает «к любому из этих рядов»,
    а не «два варианта параметра». Такие поля перечислены в
    _NON_EXPANDABLE.

Как расширять:
    Если понадобятся другие не-разворачиваемые поля — добавь их в
    _NON_EXPANDABLE.
"""

from __future__ import annotations
from itertools import product
from typing import Any


#: Поля, которые НЕ разворачиваются:
#:   - applies_to — предикат области действия
#:   - stopping   — массив критериев остановки (обрабатывается акселератором)
_NON_EXPANDABLE = frozenset({"applies_to", "stopping"})


def expand_node(node: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Разворачивает один узел конфига во все возможные комбинации.

    Принимает:
        node — словарь, например {"id": "gauss", "params": {...}}

    Возвращает:
        список словарей — каждая комбинация параметров.

    Пример:
        >>> expand_node({"id": "gauss", "params": {"sigma": ["1e-3","1e-6"], "mode": "abs"}})
        [
            {"id": "gauss", "params": {"sigma": "1e-3", "mode": "abs"}},
            {"id": "gauss", "params": {"sigma": "1e-6", "mode": "abs"}},
        ]
    """
    keys: list[str] = []
    value_lists: list[list[Any]] = []

    for k, v in node.items():
        keys.append(k)
        if k in _NON_EXPANDABLE:
            # Поле не разворачивается — берём как есть.
            value_lists.append([v])
        else:
            value_lists.append(_expand_value(v))

    result: list[dict[str, Any]] = []
    for combo in product(*value_lists):
        result.append(dict(zip(keys, combo)))
    return result


def _expand_value(v):
    if isinstance(v, list):
        if all(isinstance(x, (str, int, float, bool, type(None))) for x in v):
            return v
        # Список словарей — массив под-узлов.
        # Для каждого под-узла получаем список вариантов.
        per_item_variants = [expand_node(item) for item in v]
        # Декартово произведение даёт варианты всего списка.
        # Каждый вариант — список из len(v) элементов.
        result = []
        for combo in product(*per_item_variants):
            result.append(list(combo))
        return result
    if isinstance(v, dict):
        return expand_node(v)
    return [v]


def expand_all(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Разворачивает список узлов верхнего уровня.

    Принимает:
        nodes — список узлов (например, все series из конфига)

    Возвращает:
        плоский список всех комбинаций.
    """
    out: list[dict[str, Any]] = []
    for node in nodes:
        out.extend(expand_node(node))
    return out