"""
Медианный фильтр.

Зачем:
    Медиана устойчива к выбросам — в отличие от среднего.
    Если траектория оценок содержит редкие «вылеты» — медиана
    их уберёт, а KZ размажет.

Как расширять:
    Для взвешенной медианы или процентилей — новый класс.
"""

from __future__ import annotations
import functools
from typing import Any

from arbacc.core.context import Context
from arbacc.core.postprocess import PostprocessorBase, PostResult
from arbacc.core.registry import register


@register("postprocess", "median")
class MedianFilter(PostprocessorBase):
    """Скользящая медиана."""

    name = "median"
    display_name = "med"
    consumes = "iterations"

    PARAM_SPEC = {
        "window": {
            "type": "int",
            "min": 3,
            "required": True,
            "default": 5,
            "short": "w",
            "hint": "нечётное, ≥ 3",
        },
    }

    def apply(self, estimates: list[Any], ctx: Context) -> PostResult:
        """
        Применяет медианный фильтр к траектории оценок.

        Принимает:
            estimates — список оценок.
            ctx       — контекст.

        Возвращает:
            PostResult со сглаженной последовательностью.
        """
        window = int(self.params.get("window", 5))

        if window < 3 or window % 2 == 0:
            raise ValueError(f"median window must be odd and >= 3, got {window}")

        n = len(estimates)
        if n < window:
            return PostResult(
                name=self.name,
                params=dict(self.params),
                values=list(estimates),
                final=estimates[-1] if estimates else None,
                meta={"input_len": n, "output_len": n, "degenerate": True},
            )

        half = window // 2
        smoothed: list[Any] = []
        for i in range(half, n - half):
            w = estimates[i - half: i + half + 1]
            sorted_w = _sort_values(w, ctx)
            smoothed.append(sorted_w[half])

        final = smoothed[-1] if smoothed else None
        return PostResult(
            name=self.name,
            params=dict(self.params),
            values=smoothed,
            final=final,
            meta={
                "input_len": n,
                "output_len": len(smoothed),
                "window": window,
            },
        )


def _sort_values(values: list[Any], ctx: Context) -> list[Any]:
    """Сортирует список чисел backend'а через cmp_to_key."""
    def cmp(a, b):
        return ctx.backend.sign(
            ctx.backend.sub(a, b, ctx.dps),
            ctx.dps,
        )
    return sorted(values, key=functools.cmp_to_key(cmp))