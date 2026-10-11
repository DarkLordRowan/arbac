"""
Реализация PrecisionBackend через python-flint (arb).

Зачем:
    arb — интервальная арифметика произвольной точности. Честнее mpmath:
    результат возвращается как интервал [значение ± погрешность].

    Это второй независимый backend, что позволяет:
      - сравнивать mpmath и arb в реальных экспериментах;
      - проверять согласованность результатов;
      - использовать arb, когда важна честная оценка точности.

Замечания:
    - dps (десятичные значащие) переводится в биты: bits ≈ dps * 3.32 + 20.
    - str(arb) возвращает "[val +/- err]" — извлекаем центр.
    - Все методы — статические или обычные, оборачивают тело в установку
      flint_ctx.prec.
    - Конвертация не-arb значений: см. _to_arb. Для mpmath.mpf используем
      mpmath.nstr(value, dps+10), а не str(value) — иначе теряем точность
      до 15 знаков (дефолт mpmath для str).
"""

from __future__ import annotations
import math
from typing import Any

try:
    from flint import arb, ctx as flint_ctx
except ImportError as e:
    raise ImportError(
        "python-flint не установлен. Установи: pip install python-flint"
    ) from e

from arbacc.precision.base import PrecisionBackend, register_backend


#: Коэффициент перевода десятичных значащих цифр в биты.
_LOG2_10 = math.log2(10)


@register_backend("arb")
class ArbBackend(PrecisionBackend):
    """Backend на базе python-flint (Arb, интервальная арифметика)."""

    name = "arb"

    # ------------------------------------------------------------------
    # Вспомогательные
    # ------------------------------------------------------------------

    @staticmethod
    def _bits(dps: int) -> int:
        """dps → биты (с запасом +20)."""
        return int(math.ceil(dps * _LOG2_10)) + 20

    @staticmethod
    def _extract_center(s: str) -> str:
        """
        Извлекает центр из "[val +/- err]" или "val".

        Если после извлечения строка пустая или не является числом —
        возвращает "0". Защищает от редкого случая, когда arb возвращает
        "[+/- err]" (значение покрывает ноль).
        """
        s = s.strip()
        if s.startswith("["):
            s = s[1:]
        if "+/-" in s:
            s = s.split("+/-")[0].strip()
        s = s.rstrip("]").strip()
        if not s:
            return "0"
        try:
            float(s)
            return s
        except ValueError:
            import re
            m = re.search(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", s)
            return m.group(0) if m else "0"

    def _to_arb(self, value: Any, dps: int) -> "arb":
        """
        Приводит value к arb, сохраняя точность.

        Для arb — как есть. Для mpmath.mpf — через mpmath.nstr(value, dps+10),
        а не через str(value): str(mpf) печатает только 15 знаков и
        уничтожает точность. Для всего остального — через str().
        """
        if isinstance(value, arb):
            return value

        # mpmath.mpf — специальная обработка.
        try:
            import mpmath as _mp
            if isinstance(value, _mp.mpf):
                with _mp.workdps(max(dps, 30) + 10):
                    s = _mp.nstr(
                        value, max(dps, 30) + 10, strip_zeros=False,
                    )
                return arb(s)
        except ImportError:
            pass
        except Exception:
            pass

        return arb(str(value))

    # ------------------------------------------------------------------
    # Активация (no-op для arb)
    # ------------------------------------------------------------------

    def activate(self, dps: int) -> None:
        """arb устанавливает prec на каждый вызов — no-op."""
        return None

    # ------------------------------------------------------------------
    # Преобразования
    # ------------------------------------------------------------------

    def number(self, value: Any, dps: int) -> Any:
        """value → arb."""
        if isinstance(value, str) and any(ord(c) >= 128 for c in value):
            bad = [c for c in value if ord(c) >= 128]
            raise ValueError(
                f"non-ASCII characters in number: {value!r} "
                f"(bad: {bad!r}). Проверь параметры в конфиге."
            )
        flint_ctx.prec = self._bits(dps)
        if isinstance(value, arb):
            return value
        return self._to_arb(value, dps)

    def to_str(self, value: Any, dps: int) -> str:
        """
        arb → строка. Какое поле (mid/lower/upper/rad) — зависит от
        текущего set_rounding.
        """
        flint_ctx.prec = self._bits(dps)
        v = value if isinstance(value, arb) else self._to_arb(value, dps)
        mode = self._extract
        if mode == "mid":
            return self._extract_center(str(v))
        if mode == "lower":
            return self._extract_center(str(v.lower()))
        if mode == "upper":
            return self._extract_center(str(v.upper()))
        if mode == "rad":
            return self._extract_center(str(v.rad()))
        return self._extract_center(str(v))

    def from_str(self, s: str, dps: int) -> Any:
        """Строка → arb."""
        flint_ctx.prec = self._bits(dps)
        if not s or not s.strip():
            return arb(0)
        s = s.strip()
        if s.startswith("[") or "+/-" in s:
            s = self._extract_center(s)
        try:
            return arb(s)
        except ValueError:
            return arb(0)

    # ------------------------------------------------------------------
    # Арифметика
    # ------------------------------------------------------------------

    def add(self, a: Any, b: Any, dps: int) -> Any:
        flint_ctx.prec = self._bits(dps)
        return self._to_arb(a, dps) + self._to_arb(b, dps)

    def sub(self, a: Any, b: Any, dps: int) -> Any:
        flint_ctx.prec = self._bits(dps)
        return self._to_arb(a, dps) - self._to_arb(b, dps)

    def mul(self, a: Any, b: Any, dps: int) -> Any:
        flint_ctx.prec = self._bits(dps)
        return self._to_arb(a, dps) * self._to_arb(b, dps)

    def div(self, a: Any, b: Any, dps: int) -> Any:
        flint_ctx.prec = self._bits(dps)
        return self._to_arb(a, dps) / self._to_arb(b, dps)

    def pow(self, base: Any, exponent: Any, dps: int) -> Any:
        flint_ctx.prec = self._bits(dps)
        return self._to_arb(base, dps) ** self._to_arb(exponent, dps)

    def neg(self, a: Any, dps: int) -> Any:
        flint_ctx.prec = self._bits(dps)
        return -self._to_arb(a, dps)

    def abs_val(self, a: Any, dps: int) -> Any:
        flint_ctx.prec = self._bits(dps)
        return abs(self._to_arb(a, dps))

    # ------------------------------------------------------------------
    # Математические функции
    # ------------------------------------------------------------------

    def factorial(self, n: int, dps: int) -> Any:
        flint_ctx.prec = self._bits(dps)
        result = arb(1)
        for k in range(2, int(n) + 1):
            result = result * k
        return result

    def sin(self, x: Any, dps: int) -> Any:
        flint_ctx.prec = self._bits(dps)
        return self._to_arb(x, dps).sin()

    def cos(self, x: Any, dps: int) -> Any:
        flint_ctx.prec = self._bits(dps)
        return self._to_arb(x, dps).cos()

    def exp(self, x: Any, dps: int) -> Any:
        flint_ctx.prec = self._bits(dps)
        return self._to_arb(x, dps).exp()

    def log(self, x: Any, dps: int) -> Any:
        flint_ctx.prec = self._bits(dps)
        return self._to_arb(x, dps).log()

    def zeta(self, s: Any, dps: int) -> Any:
        flint_ctx.prec = self._bits(dps)
        return self._to_arb(s, dps).zeta()

    def gamma(self, x: Any, dps: int) -> Any:
        flint_ctx.prec = self._bits(dps)
        return self._to_arb(x, dps).gamma()

    # ------------------------------------------------------------------
    # Метрики
    # ------------------------------------------------------------------

    def abs_diff(self, a: Any, b: Any, dps: int) -> Any:
        flint_ctx.prec = self._bits(dps)
        return abs(self._to_arb(a, dps) - self._to_arb(b, dps))

    def sign(self, a: Any, dps: int) -> int:
        flint_ctx.prec = self._bits(dps)
        v = self._to_arb(a, dps)
        if v > 0:
            return 1
        if v < 0:
            return -1
        return 0

    def digits_of(self, value: Any, reference: Any, dps: int) -> int:
        """
        Сколько верных десятичных цифр value относительно reference.

        |value - reference| оценивается сверху как (|mid| + rad)
        интервала разности. Это корректно работает, когда интервал
        содержит 0 (иначе arb.log() даёт NaN). Для очень маленьких
        разностей (dps > 300) считаем log10 через arb, чтобы не
        упасть в underflow float.
        """
        flint_ctx.prec = self._bits(dps)
        a = self._to_arb(value, dps)
        b = self._to_arb(reference, dps)
        diff = abs(a - b)
        if diff == 0:
            return dps

        s = str(diff).strip()
        if s.startswith("["):
            s = s[1:]
        s = s.rstrip("]").strip()
        if "+/-" in s:
            mid_str, err_str = s.split("+/-", 1)
            mid_str = mid_str.strip()
            err_str = err_str.strip()
        else:
            mid_str, err_str = s, "0"

        try:
            mid = abs(float(mid_str)) if mid_str else 0.0
        except (ValueError, TypeError):
            mid = 0.0
        try:
            err = float(err_str) if err_str else 0.0
        except (ValueError, TypeError):
            err = 0.0

        bound = mid + err
        if bound > 0 and math.isfinite(bound):
            try:
                return int(math.floor(-math.log10(bound)))
            except (ValueError, OverflowError):
                pass

        # bound слишком мал (underflow) — считаем через arb.
        try:
            log10_val = diff.log() / arb(10).log()
        except Exception:
            return dps
        s2 = self._extract_center(str(log10_val))
        if not s2 or s2.lower() in ("nan", "inf", "-inf",
                                    "infinity", "-infinity"):
            return dps
        try:
            log10_f = float(s2)
        except (ValueError, TypeError):
            return dps
        if not math.isfinite(log10_f):
            return dps
        return int(math.floor(-log10_f))

    #: Какое поле arb извлекать при to_str.
    #: Хранится как instance-состояние (default = mid).
    SUPPORTED_ROUNDING = (
        "nearest", "floor", "ceiling", "rad",
    )

    def __init__(self) -> None:
        super().__init__()
        self._extract: str = "mid"

    def set_rounding(self, mode: str) -> None:
        """
        Выбирает, какое поле интервала извлекать при to_str.

        nearest → mid()      (значение)
        floor   → lower()    (гарантированный минимум)
        ceiling → upper()    (гарантированный максимум)
        rad     → rad()      (радиус интервала — для диагностики)

        Прочие семантические имена (toward_zero, away_from_zero)
        не поддерживаются — arb всегда интервальный.
        """
        mapping = {
            "nearest": "mid",
            "floor": "lower",
            "ceiling": "upper",
            "rad": "rad",
        }
        if mode not in mapping:
            raise ValueError(
                f"arb: rounding mode {mode!r} not supported. "
                f"Available: {list(mapping)}"
            )
        self._extract = mapping[mode]    