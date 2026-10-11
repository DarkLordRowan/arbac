"""
Единая логика id для всех узлов фреймворка.

Зачем:
    id используется в трёх местах:
      - в путях output (out/accel/<series_id>/<noise_id>/<accel_id>/),
      - в task_id (для сортировки и отображения),
      - в applies_to (пользователь пишет "zeta_s3" — матчится по id).

    Один id для всего — проще и последовательнее. Если логика
    поменяется, правится ТОЛЬКО эта функция.

Формат id:
    <type>_<short1><val1><short2><val2>...

    Порядок параметров — как в PARAM_SPEC плагина.
    Числа: short+value без '='.     Пример: dw11, th0p5
    Строки/enum: short+short_value. Пример: rmaf, uaobs
    Спецсимволы убираются: . -> p, - -> m, , = пробел -> удаляются.

    Пример: emd_w11dw11th0p5mh20rmafuaobs

Имя функции:
    'id' использовать нельзя — перекрывает builtin. Но по смыслу
    node_id — это ТОТ САМЫЙ единственный id.
"""

from __future__ import annotations
import json
from typing import Any


#: Значения-дефолты для extra. Если значение равно дефолту — не
#: добавляется в id (чтобы не удлинять без нужды).
_EXTRA_DEFAULTS = {
    "seed": 0,
    "backend": "mpmath",
}


def canonical_json(obj: Any) -> str:
    """
    Канонизирует объект в JSON: сортировка ключей, без пробелов.

    Принимает:
        obj — любой JSON-сериализуемый объект.

    Возвращает:
        строку.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _clean(s: str) -> str:
    """
    Убирает символы, неудобные в путях и id.

    - запятые, знаки равенства, пробелы — удаляются;
    - точка → 'p', минус → 'm';
    - все не-ASCII символы → '_' (защита от случайной кириллицы
      или других юникод-символов в параметрах).
    """
    for ch in (",", "=", " "):
        s = s.replace(ch, "")
    s = s.replace(".", "p")
    s = s.replace("-", "m")
    # Защита от не-ASCII.
    s = "".join(c if ord(c) < 128 else "_" for c in s)
    return s


def node_id(
    kind: str,
    type_name: str,
    params: dict[str, Any],
    extra: dict[str, Any] | None = None,
) -> str:
    """
    Читаемый id узла: '<type>_<short_params>[_<extra>]'.

    Принимает:
        kind      — категория ("series" | "noise" | "accelerators" |
                    "stopping" | "postprocess" | "envelopes").
        type_name — имя типа ("zeta", "gaussian", "aitken_delta2", ...).
        params    — параметры узла.
        extra     — доп. поля (dps, backend, seed). Значения,
                    совпадающие с дефолтом, опускаются.

    Возвращает:
        строку.

    Пример:
        node_id("series", "zeta", {"s": 3})
            = "zeta_s3"
        node_id("series", "cos", {"x": 0.6})
            = "cos_x0p6"
        node_id("noise", "gaussian", {"sigma": "1e-6"},
                {"seed": 42})
            = "gaussian_sig1em6_seed42"
        node_id("accelerators", "aitken_delta2", {},
                {"dps": 50, "backend": "mpmath"})
            = "aitken_delta2_dps50"
    """
    # Короткое представление params — через плагин.
    params_str = ""
    try:
        from arbacc.core.registry import get as _get
        Cls = _get(kind, type_name)
        params_str = Cls.format_short_params(params or {})
    except Exception:
        params_str = ""

    parts = [type_name]
    if params_str:
        parts.append(_clean(params_str))

    if extra:
        for k in sorted(extra.keys()):
            v = extra[k]
            if v is None:
                continue
            if k in _EXTRA_DEFAULTS and v == _EXTRA_DEFAULTS[k]:
                continue
            parts.append(f"{k}{_clean(str(v))}")

    return "_".join(parts)