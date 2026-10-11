"""
Accelerator — алгоритм ускорения сходимости.

Зачем:
    Единственный узел, который расширяет источник. На каждой итерации
    вызывает required_input и step.

Как расширять:
    Новый алгоритм = один файл accelerators/my_algo.py:
        @register("accelerators", "my_algo")
        class MyAlgo(AcceleratorBase):
            name = "my_algo"
            display_name = "mya"
            PARAM_SPEC = {"order": {"type": "int", "default": 3,
                                    "short": "o"}}
            def required_input(self, state): ...
            def step(self, source, state, ctx): ...
"""

from __future__ import annotations
from abc import abstractmethod
from dataclasses import dataclass, field
from typing import Any

from arbacc.core.context import Context
from arbacc.core.plugin import PluginBase
from arbacc.core.stream import Stream


@dataclass
class AlgoState:
    """Состояние акселератора между итерациями."""

    iteration: int = 0
    estimate: Any = None
    history: list[Any] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    def with_estimate(self, new_estimate: Any) -> "AlgoState":
        """Возвращает новое состояние с обновлённой оценкой и историей."""
        return AlgoState(
            iteration=self.iteration + 1,
            estimate=new_estimate,
            history=self.history + [new_estimate],
            extra=dict(self.extra),
        )


class AcceleratorBase(PluginBase):
    """Базовый класс акселераторов."""

    @abstractmethod
    def required_input(self, state: AlgoState) -> int:
        """Сколько членов исходного ряда нужно на следующей итерации."""
        ...

    @abstractmethod
    def step(self, source: Stream, state: AlgoState, ctx: Context) -> AlgoState:
        """Одна итерация."""
        ...

    def suggested_criteria(self) -> list[str]:
        """Имена критериев остановки, разумных по умолчанию."""
        return []