"""
Envelope — скользящая огибающая.

Зачем:
    Анализирует траекторию оценок и:
      - run_mode="during" + used_as="stopping_criterion" — может
        остановить акселератор,
      - run_mode="after" + used_as="observer" — только отмечает
        точку предполагаемой остановки.

Как расширять:
    Новая огибающая = один файл envelopes/my_env.py:
        @register("envelopes", "my_env")
        class MyEnv(EnvelopeBase):
            name = "my_env"
            display_name = "me"
            PARAM_SPEC = {"window": {"type": "int", "required": True,
                                     "default": 11, "short": "w"}}
            def push(self, value): ...
            def says_stop(self): ...
            def result(self): ...
"""

from __future__ import annotations
from abc import abstractmethod
from typing import Any, Literal

from arbacc.core.plugin import PluginBase


class EnvelopeBase(PluginBase):
    """Базовый класс скользящих огибающих."""

    #: "during" — во время акселератора, "after" — после.
    run_mode: Literal["during", "after"] = "after"

    #: "stopping_criterion" — может остановить, "observer" — только отметить.
    used_as: Literal["stopping_criterion", "observer"] = "observer"

    @abstractmethod
    def push(self, value: Any) -> None:
        """Добавляет очередное значение траектории."""
        ...

    @abstractmethod
    def says_stop(self) -> bool:
        """True, если пора остановиться."""
        ...

    @abstractmethod
    def result(self) -> dict[str, Any]:
        """Итоговые метаданные огибающей."""
        ...