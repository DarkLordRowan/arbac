"""
ε-алгоритм Винна — мощный акселератор сходимости.

Зачем:
    Универсальный нелинейный акселератор. Строит таблицу ε:
        ε_{-1}^{(n)} = 0
        ε_0^{(n)}    = s_n
        ε_{k+1}^{(n)} = ε_{k-1}^{(n+1)} + 1 / (ε_k^{(n+1)} - ε_k^{(n)})

    Чётные столбцы ε_{2k}^{(n)} — ускоренные оценки.

Реализация — ИНКРЕМЕНТАЛЬНАЯ.

    Наивный вариант строит всю таблицу на каждой итерации: O(N⁴)
    суммарно. Инкрементальный обновляет только одну диагональ:
    O(N²) суммарно. Для N=1000 это разница в 10⁶ операций.

    Хранение — ромбовидная схема. eps[j][n] — ячейка столбца j,
    диагонали n. На итерации k добавляется одна новая ячейка в
    каждый столбец j ≤ k.

Как расширять:
    Скопируй как шаблон для нового акселератора с таблицей.
"""

from __future__ import annotations
from typing import Any

from arbacc.core.accelerator import AcceleratorBase, AlgoState
from arbacc.core.context import Context
from arbacc.core.registry import register
from arbacc.core.stream import Stream


@register("accelerators", "wynn_epsilon")
class WynnEpsilon(AcceleratorBase):
    """ε-алгоритм Винна (инкрементальный)."""

    name = "wynn_epsilon"
    display_name = "wynn"

    PARAM_SPEC = {}

    def required_input(self, state: AlgoState) -> int:
        """
        На итерации k нужно 2k+1 членов (s_0..s_{2k}).

        Принимает:
            state — состояние.

        Возвращает:
            2k + 1.
        """
        return 2 * state.iteration + 1

    def step(
        self,
        source: Stream,
        state: AlgoState,
        ctx: Context,
    ) -> AlgoState:
        """
        Одна итерация ε-алгоритма (инкрементально).

        При diff == 0 ячейка помечается None. При выборе оценки
        пропускаем столбцы с None — берём последний чётный столбец
        с доступной ячейкой. Это защищает от «схлопывания» arb
        при высокой точности.
        """
        b = ctx.backend
        k = state.iteration

        partials: list[Any] = state.extra.get("partials", [])
        eps: list[list[Any]] = state.extra.get("eps", [])
        zero = ctx.number(0)
        one = ctx.number(1)

        # 1. Дотягиваем partials до s_k.
        while len(partials) <= k:
            idx = len(partials)
            a = source.get(idx)
            if idx == 0:
                partials.append(a)
            else:
                partials.append(b.add(partials[idx - 1], a, ctx.dps))

        s_k = partials[k]

        # 2. Убедимся, что eps[0] есть.
        while len(eps) <= k:
            eps.append([])
        if len(eps[0]) == 0:
            eps[0] = [partials[0]]
        while len(eps[0]) <= k:
            eps[0].append(partials[len(eps[0])])

        # 3. Строим столбцы 1..k.
        for j in range(1, k + 1):
            n = k - j
            while len(eps[j]) <= n:
                eps[j].append(None)

            if j == 1:
                prev_prev = zero
            else:
                prev_prev = eps[j - 2][n + 1]

            a_val = eps[j - 1][n + 1]
            b_val = eps[j - 1][n]

            # Если у предыдущих ячеек нет данных — ячейка недоступна.
            if a_val is None or b_val is None:
                eps[j][n] = None
                continue

            diff = b.sub(a_val, b_val, ctx.dps)

            if b.sign(diff, ctx.dps) == 0:
                # Разность не определена — ячейка недоступна.
                # Не пишем 0 (это ложные данные).
                eps[j][n] = None
            else:
                inv = b.div(one, diff, ctx.dps)
                eps[j][n] = b.add(prev_prev, inv, ctx.dps)

        # 4. Оценка — последний доступный чётный столбец.
        estimate = None
        for j in range(min(k, len(eps) - 1), -1, -1):
            if j % 2 != 0:
                continue
            if len(eps[j]) > 0 and eps[j][0] is not None:
                estimate = eps[j][0]
                break

        if estimate is None:
            estimate = s_k

        new_state = state.with_estimate(estimate)
        new_state.extra["partials"] = partials
        new_state.extra["eps"] = eps
        return new_state