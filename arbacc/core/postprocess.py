"""
Postprocessor — постобработка результата акселератора.

Зачем:
    Работает по готовому списку estimates. Не расширяет источник.

Как расширять:
    Новый фильтр = один файл postprocess/my_filter.py:
        @register("postprocess", "my_filter")
        class MyFilter(PostprocessorBase):
            name = "my_filter"
            display_name = "mf"
            PARAM_SPEC = {"window": {"type": "int", "required": True,
                                     "default": 5, "short": "w"}}
            def apply(self, estimates, ctx): ...
"""

from __future__ import annotations
from abc import abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal

from arbacc.core.context import Context
from arbacc.core.plugin import PluginBase


@dataclass
class PostResult:
    """Результат постобработки."""

    name: str
    params: dict[str, Any]
    values: list[Any]
    final: Any
    meta: dict[str, Any] = field(default_factory=dict)


class PostprocessorBase(PluginBase):
    """Базовый класс постобработок."""

    #: Что потребляет постобработка. Пока только "iterations".
    consumes: Literal["iterations"] = "iterations"

    @abstractmethod
    def apply(self, estimates: list[Any], ctx: Context) -> PostResult:
        """Применяет постобработку к траектории."""
        ...