"""
Короткое представление параметров — общее для всех плагинов.

Зачем:
    Единая логика форматирования: плагин задаёт PARAM_SPEC с полями
    short / short_values / hidden, а форматирование строки — здесь.

Порядок параметров:
    В том порядке, в котором они объявлены в PARAM_SPEC. Это даёт
    контроль автору плагина: главные параметры идут первыми,
    второстепенные — позже.

    Параметры, которых нет в PARAM_SPEC (например, добавленные
    вручную в JSON), идут после — по алфавиту.

Как расширять:
    Ничего менять не нужно. Новые поля спека обрабатываются
    автоматически.
"""

from __future__ import annotations


def short_value_repr(v, short_values: dict | None = None) -> str:
    """Короткое представление значения параметра."""
    short_values = short_values or {}
    if isinstance(v, list):
        inner = ",".join(short_value_repr(x, short_values) for x in v[:4])
        if len(v) > 4:
            inner += ",…"
        return f"[{inner}]"
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, float):
        return f"{v:g}"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, str):
        v2 = short_values.get(v, v)
        return v2 if len(v2) <= 16 else v2[:13] + "…"
    return str(v)


def format_short_params(spec: dict, params: dict) -> str:
    """
    Короткое представление params на основе PARAM_SPEC.

    Порядок:
        1) сначала параметры в порядке PARAM_SPEC,
        2) потом оставшиеся (не в spec) — по алфавиту.

    Пропускает:
        - параметры с hidden=True,
        - параметры со значением None или "".

    Принимает:
        spec   — PARAM_SPEC плагина.
        params — словарь параметров.

    Возвращает:
        строку вида 'x=0.6,s=3' или 'w11dw11'.
    """
    spec = spec or {}
    params = params or {}
    parts = []
    seen: set[str] = set()

    # --- 1. Порядок PARAM_SPEC ---
    for k in spec.keys():
        seen.add(k)               # ← помечаем как обработанный
        if k not in params:
            continue
        pspec = spec[k]
        if pspec.get("hidden"):
            continue
        v = params[k]
        if v is None or v == "":
            continue
        sk = pspec.get("short") or k
        sv = short_value_repr(v, pspec.get("short_values"))
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            parts.append(f"{sk}{sv}")
        else:
            parts.append(f"{sk}={sv}")
        seen.add(k)

    # --- 2. Оставшиеся (не в spec) — по алфавиту ---
    for k in sorted(params.keys()):
        if k in seen:
            continue
        v = params[k]
        if v is None or v == "":
            continue
        sv = short_value_repr(v, None)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            parts.append(f"{k}{sv}")
        else:
            parts.append(f"{k}={sv}")

    return ",".join(parts)