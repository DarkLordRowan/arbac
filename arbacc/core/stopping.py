"""
StoppingCriterion — критерий остановки акселератора.

Зачем:
    Остановка вынесена из акселератора, чтобы переиспользовать
    критерии и комбинировать их через stopping_mode.

Как расширять:
    Новый критерий = один файл stopping/my_criterion.py:
        @register("stopping", "my_criterion")
        class MyCriterion(StoppingBase):
            name = "my_criterion"
            display_name = "mc"
            PARAM_SPEC = {"n": {"type": "int", "required": True,
                                "default": 100, "short": "n"}}
            def should_stop(self, state, ctx): ...
"""

from __future__ import annotations
from abc import abstractmethod

from arbacc.core.accelerator import AlgoState
from arbacc.core.context import Context
from arbacc.core.plugin import PluginBase


class StoppingBase(PluginBase):
    """Базовый класс критериев остановки."""

    def __init__(self, params: dict | None = None):
        super().__init__(params)
        self._reason: str = ""

    @abstractmethod
    def should_stop(self, state: AlgoState, ctx: Context) -> bool:
        """
        Проверяет, нужно ли остановиться.

        При возврате True ОБЯЗАН выставить self._reason.
        """
        ...

    @property
    def reason(self) -> str:
        """Причина последней остановки."""
        return self._reason