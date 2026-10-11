"""Фильтр Савицкого–Голея (SG).

Зачем:
    SG-фильтр — локальная полиномиальная аппроксимация. В отличие
    от скользящего среднего сохраняет форму пиков и трендов.

    Реализация: для каждой точки строим полином степени `order`
    по окну `window` через нормальные уравнения и берём значение
    полинома в центральной точке.

Замечание о backend'ах:
    Веса фильтра — рациональные числа. Считаем их ТОЧНО через
    fractions.Fraction (Гауссово исключение + Крамер), затем
    конвертируем в числа backend'а через ctx.number. Никаких
    прямых import'ов mpmath/arb — фильтр полностью backend-agnostic.

Как расширять:
    Если понадобится другой фильтр этого семейства — новый класс.
"""

from __future__ import annotations
from fractions import Fraction
from typing import Any

from arbacc.core.context import Context
from arbacc.core.postprocess import PostprocessorBase, PostResult
from arbacc.core.registry import register


def _det(matrix: list[list[Fraction]]) -> Fraction:
    """
    Определитель квадратной матрицы (метод Гаусса).

    Принимает:
        matrix — список строк из Fraction.

    Возвращает:
        Fraction.
    """
    n = len(matrix)
    M = [row[:] for row in matrix]
    det = Fraction(1)
    for i in range(n):
        pivot = i
        while pivot < n and M[pivot][i] == 0:
            pivot += 1
        if pivot == n:
            return Fraction(0)
        if pivot != i:
            M[i], M[pivot] = M[pivot], M[i]
            det = -det
        det *= M[i][i]
        for j in range(i + 1, n):
            factor = M[j][i] / M[i][i]
            for k in range(i, n):
                M[j][k] -= factor * M[i][k]
    return det


def _solve_weights_rational(window: int, order: int) -> list[Fraction]:
    """
    Веса SG для центральной точки окна — точные рациональные числа.

    Решаем (A^T A) X = A^T методом Крамера: первая строка X — веса.

    Принимает:
        window — длина окна (нечётная, ≥ 3).
        order  — степень полинома (0 ≤ order ≤ window-2).

    Возвращает:
        список Fraction длины window.
    """
    half = window // 2
    m = order + 1

    # A: (window × m), A[i][j] = (i - half)^j.
    A = [[Fraction((i - half) ** j) for j in range(m)]
         for i in range(window)]

    # AtA: (m × m).
    AtA = [
        [sum(A[i][r] * A[i][c] for i in range(window))
         for c in range(m)]
        for r in range(m)
    ]
    det = _det(AtA)
    if det == 0:
        raise ValueError(
            f"singular normal-equations matrix for "
            f"window={window}, order={order}"
        )

    # Первая строка (AtA)^-1 * A^T. По Крамеру: для каждого k
    # заменяем строку 0 на A^T[k][*] = [A[k][0], ..., A[k][order]].
    weights: list[Fraction] = []
    for k in range(window):
        M = [row[:] for row in AtA]
        for r in range(m):
            M[0][r] = A[k][r]
        weights.append(_det(M) / det)
    return weights


@register("postprocess", "savitzky_golay")
class SavitzkyGolay(PostprocessorBase):
    """Фильтр Савицкого–Голея."""

    name = "savitzky_golay"
    display_name = "sg"
    consumes = "iterations"

    PARAM_SPEC = {
        "window": {
            "type": "int",
            "min": 3,
            "required": True,
            "default": 7,
            "short": "w",
            "hint": "нечётное, ≥ order+2",
        },
        "order": {
            "type": "int",
            "min": 0,
            "required": True,
            "default": 2,
            "short": "ord",
            "hint": "степень полинома, < window-1",
        },
    }

    def apply(self, estimates: list[Any], ctx: Context) -> PostResult:
        """
        Применяет SG-фильтр к траектории оценок.

        Принимает:
            estimates — список оценок.
            ctx       — контекст.

        Возвращает:
            PostResult со сглаженной последовательностью.
        """
        window = int(self.params.get("window", 7))
        order = int(self.params.get("order", 2))
        b = ctx.backend

        if window < 3 or window % 2 == 0:
            raise ValueError(
                f"SG window must be odd and >= 3, got {window}"
            )
        if order < 0 or order >= window - 1:
            raise ValueError(
                f"SG order must be in [0, window-2], got {order}"
            )

        n = len(estimates)
        if n < window:
            return PostResult(
                name=self.name,
                params=dict(self.params),
                values=list(estimates),
                final=estimates[-1] if estimates else None,
                meta={
                    "input_len": n,
                    "output_len": n,
                    "degenerate": True,
                },
            )

        # Веса — точные дроби, конвертируем в числа backend'а.
        weights_frac = _solve_weights_rational(window, order)
        w = [
            b.div(
                ctx.number(fr.numerator),
                ctx.number(fr.denominator),
                ctx.dps,
            )
            for fr in weights_frac
        ]

        half = window // 2
        smoothed: list[Any] = []
        for i in range(half, n - half):
            total = ctx.number(0)
            for k, j in enumerate(range(i - half, i + half + 1)):
                total = b.add(
                    total,
                    b.mul(w[k], estimates[j], ctx.dps),
                    ctx.dps,
                )
            smoothed.append(total)

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
                "order": order,
            },
        )