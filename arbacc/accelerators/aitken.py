"""
Δ²-процесс Эйткена — простейший акселератор сходимости.

Зачем:
    Классический алгоритм ускорения линейно сходящихся
    последовательностей. Формула:
        A_n = s_n - (s_{n+1} - s_n)^2 / (s_{n+2} - 2*s_{n+1} + s_n)
    где s_n — частичные суммы исходного ряда.

    На итерации k требует минимум k+3 членов.

Как расширять:
    Скопируй как шаблон для нового акселератора. Замени step().
"""

from __future__ import annotations
from typing import Any

from arbacc.core.accelerator import AcceleratorBase, AlgoState
from arbacc.core.context import Context
from arbacc.core.registry import register
from arbacc.core.stream import Stream


@register("accelerators", "aitken_delta2")
class AitkenDelta2(AcceleratorBase):
    """Δ²-процесс Эйткена."""

    name = "aitken_delta2"
    display_name = "aitd2"

    #: У Aitken нет параметров.
    PARAM_SPEC = {}

    def required_input(self, state: AlgoState) -> int:
        """
        На итерации k нужно s_0..s_{k+2} — то есть k+3 членов.

        Принимает:
            state — текущее состояние.

        Возвращает:
            k + 3.
        """
        return state.iteration + 3

    def step(
        self,
        source: Stream,
        state: AlgoState,
        ctx: Context,
    ) -> AlgoState:
        """
        Одна итерация Δ²-процесса.

        Принимает:
            source — источник (дотянут до required_input-1).
            state  — состояние.
            ctx    — контекст.

        Возвращает:
            новое состояние с оценкой A_k.
        """
        b = ctx.backend
        k = state.iteration

        # Восстанавливаем накопленные частичные суммы.
        partials: list[Any] = state.extra.get("partials", [])

        # Дотягиваем partials до s_k.
        while len(partials) <= k:
            idx = len(partials)
            a = source.get(idx)
            if idx == 0:
                partials.append(a)
            else:
                partials.append(b.add(partials[idx - 1], a, ctx.dps))

        # Дотягиваем до s_{k+2}.
        while len(partials) <= k + 2:
            idx = len(partials)
            a = source.get(idx)
            partials.append(b.add(partials[idx - 1], a, ctx.dps))

        s_k = partials[k]
        s_k1 = partials[k + 1]
        s_k2 = partials[k + 2]

        # Числитель: (s_{k+1} - s_k)^2
        d1 = b.sub(s_k1, s_k, ctx.dps)
        numerator = b.mul(d1, d1, ctx.dps)

        # Знаменатель: s_{k+2} - 2*s_{k+1} + s_k
        two = ctx.number(2)
        d2 = b.sub(s_k2, b.mul(two, s_k1, ctx.dps), ctx.dps)
        denominator = b.add(d2, s_k, ctx.dps)

        # Защита от деления на ноль.
        if b.sign(denominator, ctx.dps) == 0:
            estimate = s_k
        else:
            ratio = b.div(numerator, denominator, ctx.dps)
            estimate = b.sub(s_k, ratio, ctx.dps)

        new_state = state.with_estimate(estimate)
        new_state.extra["partials"] = partials
        return new_state