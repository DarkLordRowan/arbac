"""
Context — контекст вычисления, привязанный к точности и rounding.

Поля:
    backend  — PrecisionBackend
    dps      — десятичные значащие цифры
    rounding — семантический режим округления (см. backend.SUPPORTED_ROUNDING)
    extra    — произвольные доп. параметры
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

from arbacc.precision.base import PrecisionBackend


@dataclass(frozen=True)
class Context:
    backend: PrecisionBackend
    dps: int
    rounding: str = "nearest"
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.dps <= 0:
            raise ValueError(f"dps must be positive, got {self.dps}")
        self.backend.activate(self.dps)
        try:
            self.backend.set_rounding(self.rounding)
        except ValueError as e:
            raise ValueError(f"bad rounding for {self.backend.name}: {e}")

    def number(self, value: Any) -> Any:
        return self.backend.number(value, self.dps)

    def __repr__(self) -> str:
        return (
            f"Context(backend={self.backend.name}, dps={self.dps}, "
            f"rounding={self.rounding})"
        )