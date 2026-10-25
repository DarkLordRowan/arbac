"""
Геометрический ряд Σ q^n.

Зачем:
    Простейший тест с аналитически известной суммой 1/(1-q) для |q| < 1.
    Позволяет проверять метрики без внешних констант.

Как расширять:
    Шаблон для нового ряда: замени generate() и PARAM_SPEC.
"""

from __future__ import annotations
from typing import Any

from arbacc.core.context import Context
from arbacc.core.registry import register
from arbacc.core.series import SeriesBase


@register("series", "geometric")
class GeometricSeries(SeriesBase):
    """Σ q^n = 1/(1-q) при |q| < 1."""

    name = "geometric"
    display_name = "geom"

    PARAM_SPEC = {
        "q": {
            "type": "float",
            "required": True,
            "default": "0.7",
            "short": "q",
            "hint": "|q| < 1 для сходимости",
        },
    }

    def generate(self, n: int, ctx: Context) -> Any:
        """
        Возвращает n-й член: a_n = q^n.

        Принимает:
            n   — индекс (0-based).
            ctx — контекст.

        Возвращает:
            число backend'а.
        """
        q = ctx.number(self.params["q"])
        return ctx.backend.pow(q, ctx.number(n), ctx.dps)

    def analytic_sum(self, ctx: Context) -> Any:
        """
        Точная сумма: 1/(1-q).

        Принимает:
            ctx — контекст.

        Возвращает:
            число backend'а.
        """
        b = ctx.backend
        q = ctx.number(self.params["q"])
        one = ctx.number(1)
        # Geometric sum exists only for |q|<1; /4.6 (binomial series).
        # https://dlmf.nist.gov/4.6
        if not b.is_finite(q, ctx.dps) or b.sign(
            b.sub(one, b.abs_val(q, ctx.dps), ctx.dps), ctx.dps
        ) <= 0:
            raise ValueError("Geometric series sum requires |q| < 1")
        return b.div(one, b.sub(one, q, ctx.dps), ctx.dps)