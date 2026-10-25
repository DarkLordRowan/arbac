"""
PrecisionBackend — абстрактный интерфейс над библиотекой длинной арифметики.

Зачем:
    Переключаться между mpmath, python-flint и другими без изменения ядра.

Как расширять:
    Унаследуйся и реализуй все абстрактные методы, зарегистрируй в
    precision/__init__.py.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any


class PrecisionBackend(ABC):
    """Абстрактный backend длинной арифметики."""

    name: str = "abstract"

    def activate(self, dps: int) -> None:
        """
        Устанавливает глобальный контекст backend'а на dps.

        По умолчанию — no-op. Backend'ы, у которых точность хранится
        в глобальном состоянии (mpmath — mp.mp.dps), переопределяют.

        Вызывается автоматически из Context.__post_init__.
        """
        return None

    # --- Преобразования ---

    @abstractmethod
    def number(self, value: Any, dps: int) -> Any:
        """value → число backend'а с точностью dps."""
        ...

    @abstractmethod
    def to_str(self, value: Any, dps: int) -> str:
        """Сериализация в строку."""
        ...

    @abstractmethod
    def from_str(self, s: str, dps: int) -> Any:
        """Десериализация из строки."""
        ...

    # --- Арифметика ---

    @abstractmethod
    def add(self, a: Any, b: Any, dps: int) -> Any: ...
    @abstractmethod
    def sub(self, a: Any, b: Any, dps: int) -> Any: ...
    @abstractmethod
    def mul(self, a: Any, b: Any, dps: int) -> Any: ...
    @abstractmethod
    def div(self, a: Any, b: Any, dps: int) -> Any: ...
    @abstractmethod
    def pow(self, base: Any, exponent: Any, dps: int) -> Any: ...
    @abstractmethod
    def neg(self, a: Any, dps: int) -> Any: ...
    @abstractmethod
    def abs_val(self, a: Any, dps: int) -> Any: ...

    # --- Метрики ---

    @abstractmethod
    def abs_diff(self, a: Any, b: Any, dps: int) -> Any:
        """|a - b| в точности dps."""
        ...

    @abstractmethod
    def digits_of(self, value: Any, reference: Any, dps: int) -> int:
        """Сколько верных десятичных цифр в value относительно reference."""
        ...

    @abstractmethod
    def sign(self, a: Any, dps: int) -> int:
        """
        Возвращает знак числа: -1, 0 или +1.

        Принимает:
            a   — число backend'а
            dps — точность

        Возвращает:
            -1 | 0 | +1.
        """
        ...        

    @abstractmethod
    def factorial(self, n: int, dps: int) -> Any:
        """n! в точности dps."""
        ...

    @abstractmethod
    def sin(self, x: Any, dps: int) -> Any:
        """sin(x)."""
        ...

    @abstractmethod
    def cos(self, x: Any, dps: int) -> Any:
        """cos(x)."""
        ...

    @abstractmethod
    def exp(self, x: Any, dps: int) -> Any:
        """exp(x)."""
        ...

    @abstractmethod
    def log(self, x: Any, dps: int) -> Any:
        """ln(x)."""
        ...

    @abstractmethod
    def zeta(self, s: Any, dps: int) -> Any:
        """ζ(s)."""
        ...

    @abstractmethod
    def gamma(self, x: Any, dps: int) -> Any:
        """Γ(x)."""
        ...

    def pi(self, dps):
        raise NotImplementedError("pi is unavailable for this backend")

    def euler_constant(self, dps):
        raise NotImplementedError("euler_constant is unavailable for this backend")

    def erf(self, x, dps):
        raise NotImplementedError("erf is unavailable for this backend")

    def si(self, x, dps):
        raise NotImplementedError("si is unavailable for this backend")

    def ci(self, x, dps):
        raise NotImplementedError("ci is unavailable for this backend")

    def bessel_j(self, alpha, x, dps):
        raise NotImplementedError("bessel_j is unavailable for this backend")

    def gamma_lower(self, alpha, x, dps):
        raise NotImplementedError("gamma_lower is unavailable for this backend")

    def lambertw(self, x, dps):
        raise NotImplementedError("lambertw is unavailable for this backend")

    def ellipk(self, m, dps):
        raise NotImplementedError("ellipk is unavailable for this backend")

    def ellipe(self, m, dps):
        raise NotImplementedError("ellipe is unavailable for this backend")

    def legendre(self, n, x, dps):
        raise NotImplementedError("legendre is unavailable for this backend")

    def with_error(self,value,error,dps):
        """Attach an absolute error bound when supported by the backend."""
        return value

    def is_finite(self, x: Any, dps: int) -> bool:
        """Whether x is finite in the selected backend."""
        raise NotImplementedError(f"{self.name}: is_finite is unavailable")

    def atan(self, x: Any, dps: int) -> Any:
        """Real arctangent; https://dlmf.nist.gov/4.23."""
        raise NotImplementedError(f"{self.name}: atan is unavailable")

    def asin(self, x: Any, dps: int) -> Any:
        """Real arcsine; https://dlmf.nist.gov/4.23."""
        raise NotImplementedError(f"{self.name}: asin is unavailable")

    # Supported semantic rounding modes; backends may override.
    SUPPORTED_ROUNDING: tuple[str, ...] = (
        "nearest", "floor", "ceiling",
        "toward_zero", "away_from_zero",
    )

    def set_rounding(self, mode: str) -> None:
        """
        Устанавливает режим округления/извлечения.

        Принимает:
            mode — семантическое имя ("nearest", "floor", ...).

        Бросает:
            ValueError — если backend не поддерживает режим.

        По умолчанию — no-op (эквивалент "nearest"). Backend'ы
        переопределяют.
        """
        if mode not in self.SUPPORTED_ROUNDING:
            raise ValueError(
                f"{self.name}: rounding mode {mode!r} not supported. "
                f"Available: {list(self.SUPPORTED_ROUNDING)}"
            )
        return None



# --- Реестр backend'ов -------------------------------------------------------

#: Реестр: имя → класс. Заполняется через @register_backend.
_BACKENDS: dict[str, type["PrecisionBackend"]] = {}


def register_backend(name: str):
    """
    Декоратор регистрации backend'а под именем name.

    Принимает:
        name — имя для JSON-конфига ("mpmath", "arb", ...).

    Возвращает:
        декоратор.

    Пример:
        @register_backend("mpmath")
        class MpmathBackend(PrecisionBackend):
            ...
    """
    def decorator(cls):
        if not issubclass(cls, PrecisionBackend):
            raise TypeError(f"{cls} must subclass PrecisionBackend")
        _BACKENDS[name] = cls
        return cls
    return decorator


def get_backend(name: str) -> "PrecisionBackend":
    """Возвращает экземпляр backend'а по имени."""
    if name not in _BACKENDS:
        raise KeyError(
            f"Unknown precision backend: {name!r}. "
            f"Available: {sorted(_BACKENDS)}"
        )
    return _BACKENDS[name]()


def list_backends() -> list[str]:
    """Список доступных имён backend'ов."""
    return sorted(_BACKENDS.keys())        