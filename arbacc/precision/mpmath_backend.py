"""
Реализация PrecisionBackend через mpmath.

Каждый метод оборачивает тело в with mp.workdps(dps) — это делает
backend самодостаточным: результат не зависит от глобального
mp.mp.dps. Стоимость workdps — сохранение/восстановление одного int,
это пренебрежимо по сравнению с арифметикой mpf.

Без обёртки терялась точность, если глобальный mp.mp.dps не совпадал
с dps конкретного вызова (например, при прямом get_backend("mpmath")
без Context).
"""

from __future__ import annotations
from typing import Any

import mpmath as mp

from arbacc.precision.base import PrecisionBackend, register_backend


@register_backend("mpmath")
class MpmathBackend(PrecisionBackend):
    """Backend на базе mpmath."""

    name = "mpmath"

    def activate(self, dps: int) -> None:
        """Устанавливает mp.mp.dps = dps."""
        mp.mp.dps = int(dps)

    # ------------------------------------------------------------------
    # Преобразования
    # ------------------------------------------------------------------

    def number(self, value: Any, dps: int) -> Any:
        """value → mpf с точностью dps."""
        if isinstance(value, str) and any(ord(c) >= 128 for c in value):
            bad = [c for c in value if ord(c) >= 128]
            raise ValueError(
                f"non-ASCII characters in number: {value!r} "
                f"(bad: {bad!r}). Проверь параметры в конфиге."
            )
        with mp.workdps(dps):
            return mp.mpf(value)

    def to_str(self, value: Any, dps: int) -> str:
        """mpf → строка с dps значащими."""
        with mp.workdps(dps):
            return mp.nstr(mp.mpf(value), dps, strip_zeros=False)

    def from_str(self, s: str, dps: int) -> Any:
        """Строка → mpf."""
        with mp.workdps(dps):
            return mp.mpf(s)

    # ------------------------------------------------------------------
    # Арифметика
    # ------------------------------------------------------------------

    def add(self, a: Any, b: Any, dps: int) -> Any:
        with mp.workdps(dps):
            return a + b

    def sub(self, a: Any, b: Any, dps: int) -> Any:
        with mp.workdps(dps):
            return a - b

    def mul(self, a: Any, b: Any, dps: int) -> Any:
        with mp.workdps(dps):
            return a * b

    def div(self, a: Any, b: Any, dps: int) -> Any:
        with mp.workdps(dps):
            return a / b

    def pow(self, base: Any, exponent: Any, dps: int) -> Any:
        with mp.workdps(dps):
            return base ** exponent

    def neg(self, a: Any, dps: int) -> Any:
        with mp.workdps(dps):
            return -a

    def abs_val(self, a: Any, dps: int) -> Any:
        with mp.workdps(dps):
            return abs(a)

    # ------------------------------------------------------------------
    # Математические функции
    # ------------------------------------------------------------------

    def factorial(self, n: int, dps: int) -> Any:
        with mp.workdps(dps):
            return mp.factorial(int(n))

    def sin(self, x: Any, dps: int) -> Any:
        with mp.workdps(dps):
            return mp.sin(mp.mpf(x))

    def cos(self, x: Any, dps: int) -> Any:
        with mp.workdps(dps):
            return mp.cos(mp.mpf(x))

    def exp(self, x: Any, dps: int) -> Any:
        with mp.workdps(dps):
            return mp.exp(mp.mpf(x))

    def log(self, x: Any, dps: int) -> Any:
        with mp.workdps(dps):
            return mp.log(mp.mpf(x))

    def zeta(self, s: Any, dps: int) -> Any:
        with mp.workdps(dps):
            return mp.zeta(mp.mpf(s))

    def gamma(self, x: Any, dps: int) -> Any:
        with mp.workdps(dps):
            return mp.gamma(mp.mpf(x))

    # ------------------------------------------------------------------
    # Метрики
    # ------------------------------------------------------------------

    def abs_diff(self, a: Any, b: Any, dps: int) -> Any:
        with mp.workdps(dps):
            return abs(a - b)

    def sign(self, a: Any, dps: int) -> int:
        with mp.workdps(dps):
            if a > 0:
                return 1
            if a < 0:
                return -1
            return 0

    def digits_of(self, value: Any, reference: Any, dps: int) -> int:
        with mp.workdps(dps):
            diff = abs(mp.mpf(value) - mp.mpf(reference))
            if diff == 0:
                return dps
            return int(mp.floor(-mp.log10(diff)))

    #: mpmath-код для каждого семантического имени.
    _MPMATH_ROUNDING = {
        "nearest": "n",
        "floor": "f",
        "ceiling": "c",
        "toward_zero": "d",
        "away_from_zero": "u",
    }

    SUPPORTED_ROUNDING = tuple(_MPMATH_ROUNDING.keys())

    def set_rounding(self, mode: str) -> None:
        """
        Устанавливает mp.mp.rounding.

        Семантика:
            nearest         → 'n' (round-half-even)
            floor           → 'f' (toward −∞)
            ceiling         → 'c' (toward +∞)
            toward_zero     → 'd'
            away_from_zero  → 'u'
        """
        if mode not in self._MPMATH_ROUNDING:
            raise ValueError(
                f"mpmath: unknown rounding mode {mode!r}. "
                f"Available: {list(self._MPMATH_ROUNDING)}"
            )
        mp.mp.rounding = self._MPMATH_ROUNDING[mode]        