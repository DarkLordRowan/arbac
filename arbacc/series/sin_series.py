"""
Ряд Тейлора для sin(x).

Зачем:
    Аналог cos, но с нечётными степенями. Часто используется в паре.

    sin(x) = Σ_{n=0}^∞ (-1)^n * x^(2n+1) / (2n+1)!

Как расширять:
    Аналогично cos, см. cos_series.py.
"""

from __future__ import annotations
from typing import Any

from arbacc.core.context import Context
from arbacc.core.registry import register
from arbacc.core.series import SeriesBase


@register("series", "sin")
class SinSeries(SeriesBase):
    """sin(x) = Σ (-1)^n * x^(2n+1) / (2n+1)!"""

    name = "sin"
    display_name = "sin"

    PARAM_SPEC = {
        "x": {
            "type": "str",
            "required": True,
            "default": "0.6",
            "short": "x",
            "hint": "радианы, например 0.6",
        },
    }

    def generate(self, n: int, ctx: Context) -> Any:
        """
        n-й член: a_n = (-1)^n * x^(2n+1) / (2n+1)!.

        Принимает:
            n   — индекс (0-based).
            ctx — контекст.

        Возвращает:
            число backend'а.
        """
        b = ctx.backend
        x = ctx.number(self.params["x"])
        two_n_plus_1 = ctx.number(2 * n + 1)
        power = b.pow(x, two_n_plus_1, ctx.dps)
        fact = b.factorial(2 * n + 1, ctx.dps)
        term = b.div(power, fact, ctx.dps)
        if n % 2 == 1:
            term = b.neg(term, ctx.dps)
        return term

    def analytic_sum(self, ctx: Context) -> Any:
        """
        Точное sin(x) через backend.

        Принимает:
            ctx — контекст.

        Возвращает:
            число backend'а.
        """
        b = ctx.backend
        x = ctx.number(self.params["x"])
        return b.sin(x, ctx.dps)