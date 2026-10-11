"""
Ряд Тейлора для cos(x).

Зачем:
    Классический знакопеременный ряд с факториальной сходимостью.
    Быстро сходится для умеренных x.

    cos(x) = Σ_{n=0}^∞ (-1)^n * x^(2n) / (2n)!

Как расширять:
    Скопируй как шаблон для другого тригонометрического ряда.
"""

from __future__ import annotations
from typing import Any

from arbacc.core.context import Context
from arbacc.core.registry import register
from arbacc.core.series import SeriesBase


@register("series", "cos")
class CosSeries(SeriesBase):
    """cos(x) = Σ (-1)^n * x^(2n) / (2n)!"""

    name = "cos"
    display_name = "cos"

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
        n-й член: a_n = (-1)^n * x^(2n) / (2n)!.

        Принимает:
            n   — индекс (0-based).
            ctx — контекст.

        Возвращает:
            число backend'а.
        """
        b = ctx.backend
        x = ctx.number(self.params["x"])
        two_n = ctx.number(2 * n)
        power = b.pow(x, two_n, ctx.dps)
        fact = b.factorial(2 * n, ctx.dps)
        term = b.div(power, fact, ctx.dps)
        if n % 2 == 1:
            term = b.neg(term, ctx.dps)
        return term

    def analytic_sum(self, ctx: Context) -> Any:
        """
        Точное cos(x) через backend.

        Принимает:
            ctx — контекст.

        Возвращает:
            число backend'а.
        """
        b = ctx.backend
        x = ctx.number(self.params["x"])
        return b.cos(x, ctx.dps)