"""
Критерий остановки: стабилизация значащих цифр.

Зачем:
    Основной критерий сходимости. Смотрим на последние `window`
    оценок: если они совпадают в первых `min_digits` знаках —
    считаем, что алгоритм сошёлся.

Как расширять:
    Для другого определения стабилизации — новый класс.
"""

from __future__ import annotations

from arbacc.core.accelerator import AlgoState
from arbacc.core.context import Context
from arbacc.core.registry import register
from arbacc.core.stopping import StoppingBase


@register("stopping", "digits_stable")
class DigitsStable(StoppingBase):
    """
    Останавливается, когда последние `window` оценок совпадают
    в первых `min_digits` знаках.
    """

    name = "digits_stable"
    display_name = "dstab"

    PARAM_SPEC = {
        "window": {
            "type": "int",
            "min": 1,
            "required": True,
            "default": 3,
            "short": "w",
            "hint": "сколько последних оценок сравнивать",
        },
        "min_digits": {
            "type": "int",
            "min": 1,
            "required": True,
            "default": 8,
            "short": "mdig",
            "hint": "сколько совпадающих цифр считать стабилизацией",
        },
    }

    def should_stop(self, state: AlgoState, ctx: Context) -> bool:
        """
        Проверяет стабильность цифр.

        Принимает:
            state — состояние.
            ctx   — контекст.

        Возвращает:
            True, если последние `window` оценок совпадают в `min_digits`.
        """
        window = int(self.params["window"])
        min_digits = int(self.params["min_digits"])

        history = state.history
        if len(history) < window:
            return False

        last = history[-1]
        recent = history[-window:]
        for prev in recent[:-1]:
            d = ctx.backend.digits_of(prev, last, ctx.dps)
            if d < min_digits:
                return False

        self._reason = (
            f"digits_stable(window={window}, min_digits={min_digits})"
        )
        return True