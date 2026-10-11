"""
Глобальный реестр плагинов.

Зачем нужен:
    JSON-конфиг ссылается на все компоненты по имени: ряды, шумы,
    акселераторы, критерии остановки, огибающие, постобработки.
    Реестр — единая точка, где имя → класс.

    Регистрация происходит через декоратор @register(kind, name).
    Это позволяет добавлять новые компоненты без правки ядра:
    достаточно создать файл с классом и декоратором, а затем
    импортировать его (обычно через autodiscovery).

Как расширять:
    Доступные kind:
      - "series"
      - "noise"
      - "accelerators"
      - "stopping"
      - "envelopes"
      - "postprocess"
    Если нужен новый kind — просто начни регистрировать под новым именем;
    реестр не ограничивает набор.
"""

from __future__ import annotations
from typing import Any, Callable, TypeVar

#: Глобальное хранилище: kind → {name → class}.
_REGISTRY: dict[str, dict[str, type]] = {}


T = TypeVar("T", bound=type)


def register(kind: str, name: str) -> Callable[[T], T]:
    """
    Декоратор регистрации класса под именем name в категории kind.

    При регистрации проверяется корректность PARAM_SPEC.

    Принимает:
        kind — категория ("series", "noise", ...).
        name — имя для JSON.

    Возвращает:
        декоратор.
    """
    def decorator(cls: T) -> T:
        _validate_param_spec(cls, kind, name)
        bucket = _REGISTRY.setdefault(kind, {})
        if name in bucket:
            raise ValueError(
                f"Duplicate registration: kind={kind!r}, name={name!r} "
                f"(already registered as {bucket[name].__name__})"
            )
        bucket[name] = cls
        return cls
    return decorator


def _validate_param_spec(cls: type, kind: str, name: str) -> None:
    """
    Проверяет, что PARAM_SPEC у класса корректно оформлен.

    Принимает:
        cls  — класс плагина.
        kind — категория.
        name — имя.

    Возвращает:
        None.

    Бросает:
        ValueError при некорректной спеке.
    """
    spec = getattr(cls, "PARAM_SPEC", None)
    if spec is None:
        return
    if not isinstance(spec, dict):
        raise ValueError(
            f"{kind}/{name}: PARAM_SPEC должен быть dict, "
            f"получен {type(spec).__name__}"
        )
    for k, v in spec.items():
        if not isinstance(v, dict):
            raise ValueError(
                f"{kind}/{name}.PARAM_SPEC[{k}]: должен быть dict"
            )
        t = v.get("type")
        if t == "enum" and not v.get("values"):
            raise ValueError(
                f"{kind}/{name}.PARAM_SPEC[{k}]: enum без values"
            )
        if "min" in v and "max" in v and v["min"] > v["max"]:
            raise ValueError(
                f"{kind}/{name}.PARAM_SPEC[{k}]: min > max"
            )


def get(kind: str, name: str) -> type:
    """
    Возвращает класс, зарегистрированный под (kind, name).

    Принимает:
        kind — категория
        name — имя

    Возвращает:
        класс.

    Бросает:
        KeyError — если имя не найдено.
    """
    if kind not in _REGISTRY:
        raise KeyError(f"Unknown kind: {kind!r}. Available: {sorted(_REGISTRY)}")
    bucket = _REGISTRY[kind]
    if name not in bucket:
        raise KeyError(
            f"Unknown name {name!r} in kind {kind!r}. "
            f"Available: {sorted(bucket)}"
        )
    return bucket[name]


def list_registered(kind: str | None = None) -> dict[str, list[str]]:
    """
    Возвращает список зарегистрированных имён.

    Принимает:
        kind — если задан, вернуть только эту категорию; иначе — все.

    Возвращает:
        {kind: [names...]}.
    """
    if kind is not None:
        return {kind: sorted(_REGISTRY.get(kind, {}))}
    return {k: sorted(v) for k, v in _REGISTRY.items()}


def clear() -> None:
    """
    Очищает реестр. Нужен только для тестов.
    """
    _REGISTRY.clear()