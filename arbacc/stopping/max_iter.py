"""
Критерий остановки: максимальное число итераций.

Зачем:
    Предохранитель. Даже если алгоритм не сошёлся и не разошёлся,
    нужно остановиться. Используется как fallback.

Как расширять:
    Скопируй как шаблон для нового критерия.
"""

from __future__ import annotations

from arbacc.core.accelerator import AlgoState
from arbacc.core.context import Context
from arbacc.core.registry import register
from arbacc.core.stopping import StoppingBase


@register("stopping", "max_iter")
class MaxIter(StoppingBase):
    """Останавливается после N итераций."""

    name = "max_iter"
    display_name = "maxi"

    PARAM_SPEC = {
        "n": {
            "type": "int",
            "min": 1,
            "required": True,
            "default": 100,
            "short": "n",
            "hint": "максимальное число итераций",
        },
    }

    def should_stop(self, state: AlgoState, ctx: Context) -> bool:
        """
        Проверяет лимит итераций.

        Принимает:
            state — состояние.
            ctx   — контекст.

        Возвращает:
            True, если iteration >= n.
        """
        limit = int(self.params["n"])
        if state.iteration >= limit:
            self._reason = f"max_iter({limit})"
            return True
        return False