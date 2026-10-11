"""
Метрики для оценки постобработок и огибающих.

Зачем нужен:
    После постобработки нужно понять, стало ли лучше:
      - digits_gained: сколько верных цифр в финальном значении
        относительно exact_sum.
      - envelope_was_right: если огибающая предлагала остановиться раньше,
        был бы алгоритм ближе к пределу в этой точке?

    Эти метрики позволяют автоматически ранжировать эксперименты.

Как расширять:
    Новые метрики — новые функции здесь.
"""

from __future__ import annotations
from typing import Any

from arbacc.core.context import Context


def digits_gained(value: Any, exact: Any, ctx: Context) -> int:
    """
    Считает число верных десятичных цифр в value относительно exact.

    Принимает:
        value — приближение
        exact — эталон
        ctx   — контекст

    Возвращает:
        целое число цифр.
    """
    if value is None or exact is None:
        return 0
    return ctx.backend.digits_of(value, exact, ctx.dps)


def envelope_was_right(
    iterations: list[Any],
    suggested_stop_at: int | None,
    actual_stop_at: int,
    exact: Any,
    ctx: Context,
) -> dict[str, Any]:
    """
    Оценивает, была ли огибающая права, предложив остановиться раньше.

    Принимает:
        iterations       — траектория оценок акселератора
        suggested_stop_at — индекс, где огибающая предлагала остановиться
        actual_stop_at   — индекс фактической остановки
        exact            — эталон
        ctx              — контекст

    Возвращает:
        словарь с метриками:
          - digits_at_suggestion: цифр в suggested_stop_at
          - digits_at_actual:     цифр в actual_stop_at
          - envelope_was_right:   было бы лучше остановиться раньше?
          - digits_lost:          сколько цифр потеряли, не остановившись
    """
    if exact is None:
        return {"skipped": "no exact_sum"}
    if suggested_stop_at is None or suggested_stop_at >= len(iterations):
        return {"skipped": "no suggestion"}

    d_sugg = digits_gained(iterations[suggested_stop_at], exact, ctx)
    d_act = digits_gained(iterations[actual_stop_at], exact, ctx)

    return {
        "suggested_stop_at": suggested_stop_at,
        "actual_stop_at": actual_stop_at,
        "digits_at_suggestion": d_sugg,
        "digits_at_actual": d_act,
        "envelope_was_right": d_sugg >= d_act,
        "digits_lost": max(0, d_act - d_sugg),
    }