"""
Критерий остановки: расхождение.

Зачем:
    Если оценки начали расти (|estimate| резко увеличивается),
    алгоритм разошёлся — считать дальше опасно.

Как расширять:
    Для другого определения расхождения — новый класс.
"""

from __future__ import annotations

from arbacc.core.accelerator import AlgoState
from arbacc.core.context import Context
from arbacc.core.registry import register
from arbacc.core.stopping import StoppingBase


@register("stopping", "divergence")
class Divergence(StoppingBase):
    """
    Останавливается, если |last| > factor * mean(|recent|) за
    последние `window` итераций.
    """

    name = "divergence"
    display_name = "dvg"

    PARAM_SPEC = {
        "window": {
            "type": "int",
            "min": 1,
            "required": True,
            "default": 5,
            "short": "w",
            "hint": "окно усреднения",
        },
        "factor": {
            "type": "float",
            "min": 1,
            "required": True,
            "default": "100",
            "short": "fc",
            "hint": "во сколько раз |last| должен превысить среднее",
        },
    }

    def should_stop(self, state: AlgoState, ctx: Context) -> bool:
        """
        Проверяет расхождение.

        Принимает:
            state — состояние.
            ctx   — контекст.

        Возвращает:
            True, если |last| > factor * mean(|recent|).
        """
        window = int(self.params["window"])
        factor = ctx.number(self.params["factor"])
        b = ctx.backend

        history = state.history
        if len(history) < window + 1:
            return False

        recent = history[-window - 1:-1]
        last = history[-1]

        # Среднее |recent|.
        total = ctx.number(0)
        for v in recent:
            total = b.add(total, b.abs_val(v, ctx.dps), ctx.dps)
        mean_abs = b.div(total, ctx.number(len(recent)), ctx.dps)

        # Порог: factor * mean_abs.
        threshold = b.mul(factor, mean_abs, ctx.dps)

        # Сравниваем |last| и threshold через sign.
        last_abs = b.abs_val(last, ctx.dps)
        diff = b.sub(last_abs, threshold, ctx.dps)

        if b.sign(diff, ctx.dps) > 0:
            self._reason = (
                f"divergence(window={window}, factor={self.params['factor']})"
            )
            return True
        return False