"""
Фильтр Колмогорова–Зурбенко (KZ).

Зачем:
    KZ-фильтр — итеративное скользящее среднее. На каждом проходе
    к последовательности применяется среднее по окну `window`,
    проходов делается `passes`. Хорошо подавляет высокочастотный шум.

    В нашем контексте KZ применяется к траектории оценок акселератора:
    сглаживает колебания, вызванные шумом данных.

    Краевые эффекты: на каждом проходе теряется (window-1) элементов
    с краёв. Мы их просто отбрасываем.

Как расширять:
    Скопируй как шаблон для нового фильтра.
"""

from __future__ import annotations
from typing import Any

from arbacc.core.context import Context
from arbacc.core.postprocess import PostprocessorBase, PostResult
from arbacc.core.registry import register


@register("postprocess", "kolmogorov_zurbenko")
class KolmogorovZurbenko(PostprocessorBase):
    """KZ-фильтр: `passes` проходов скользящего среднего с окном `window`."""

    name = "kolmogorov_zurbenko"
    display_name = "kz"
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
        "passes": {
            "type": "int",
            "min": 1,
            "required": True,
            "default": 2,
            "short": "p",
            "hint": "число проходов сглаживания",
        },
    }

    def apply(self, estimates: list[Any], ctx: Context) -> PostResult:
        """
        Применяет KZ-фильтр к траектории оценок.

        Принимает:
            estimates — список оценок акселератора.
            ctx       — контекст.

        Возвращает:
            PostResult со сглаженной последовательностью.
        """
        window = int(self.params.get("window", 5))
        passes = int(self.params.get("passes", 1))
        b = ctx.backend

        if window < 3 or window % 2 == 0:
            raise ValueError(f"KZ window must be odd and >= 3, got {window}")
        if passes < 1:
            raise ValueError(f"KZ passes must be >= 1, got {passes}")

        current = list(estimates)

        for _ in range(passes):
            if len(current) < window:
                break
            half = window // 2
            smoothed: list[Any] = []
            for i in range(half, len(current) - half):
                total = ctx.number(0)
                for j in range(i - half, i + half + 1):
                    total = b.add(total, current[j], ctx.dps)
                avg = b.div(total, ctx.number(window), ctx.dps)
                smoothed.append(avg)
            current = smoothed

        final = current[-1] if current else None
        return PostResult(
            name=self.name,
            params=dict(self.params),
            values=current,
            final=final,
            meta={
                "input_len": len(estimates),
                "output_len": len(current),
                "window": window,
                "passes": passes,
            },
        )