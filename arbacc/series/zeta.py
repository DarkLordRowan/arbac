"""
Ряд ζ(s) = Σ_{n=1}^∞ 1/n^s.

Зачем:
    Классический эталон для тестов ускорения сходимости. Для s=3
    сходится медленно, для s=10 — быстро.

Как расширять:
    Этот файл — шаблон для нового ряда. Замени name, display_name,
    PARAM_SPEC, generate и зарегистрируй под новым именем.
"""

from __future__ import annotations
from typing import Any

from arbacc.core.context import Context
from arbacc.core.registry import register
from arbacc.core.series import SeriesBase


@register("series", "zeta")
class ZetaSeries(SeriesBase):
    """ζ(s) = Σ 1/n^s, n от 1 до ∞."""

    #: Стабильный id (используется в путях output).
    name = "zeta"

    #: Короткое имя для легенд.
    display_name = "zeta"

    #: Параметры плагина. Общие (exact_sum, n_raw) добавляются
    #: автоматически из SeriesBase.BASE_PARAM_SPEC.
    PARAM_SPEC = {
        "s": {
            "type": "float",
            "min": 1,
            "required": True,
            "default": 3,
            "short": "s",
            "hint": "s > 1 для сходимости",
        },
    }

    def generate(self, n: int, ctx: Context) -> Any:
        """
        Возвращает n-й член ряда (0-based): a_n = 1/(n+1)^s.

        Принимает:
            n   — индекс.
            ctx — контекст.

        Возвращает:
            число backend'а.
        """
        s = ctx.number(self.params["s"])
        k = ctx.number(n + 1)                       # 1-based индекс
        neg_s = ctx.backend.neg(s, ctx.dps)         # -s
        return ctx.backend.pow(k, neg_s, ctx.dps)   # k^(-s)

    def analytic_sum(self, ctx: Context) -> Any:
        """
        Точное значение ζ(s) через backend (не через ряд).

        Принимает:
            ctx — контекст.

        Возвращает:
            число backend'а.
        """
        s = ctx.number(self.params["s"])
        return ctx.backend.zeta(s, ctx.dps)