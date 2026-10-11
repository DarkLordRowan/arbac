"""
Series — источник последовательности (синтетический или из файла).

Зачем:
    Series — описание "что за ряд обрабатываем". Знает параметры,
    умеет построить Stream по требованию, может знать точную сумму.

    Series НЕ хранит значения — он лишь фабрика Stream'ов.

Как расширять:
    Новый ряд = один файл series/my_series.py:
        @register("series", "my_series")
        class MySeries(SeriesBase):
            name = "my_series"
            display_name = "mys"
            PARAM_SPEC = {"x": {"type": "float", "required": True,
                                "default": 0.6, "short": "x"}}
            def generate(self, n, ctx): ...
            def analytic_sum(self, ctx): ...   # опционально
"""

from __future__ import annotations
from abc import abstractmethod
from typing import Any, Optional

from arbacc.core.context import Context
from arbacc.core.plugin import PluginBase
from arbacc.core.stream import Stream


class SeriesBase(PluginBase):
    """
    Базовый класс рядов.

    Автоматически добавляет к PARAM_SPEC два общих параметра:
        exact_sum — явная точная сумма (перебивает analytic_sum),
        n_raw     — сколько шагов рисовать в сыром виде.
    """

    #: Общие параметры всех рядов.
    BASE_PARAM_SPEC = {
        "exact_sum": {"type": "str", "hidden": True,
                      "hint": "точная сумма; если пусто — аналитически"},
        "n_raw": {"type": "int", "min": 1, "default": 100, "hidden": True,
                  "hint": "шагов для сырого графика"},
    }

    def __init__(self, params: dict[str, Any], exact_sum: str | None = None):
        """
        Принимает:
            params    — параметры ряда.
            exact_sum — явная сумма (перебивает params["exact_sum"]).
        """
        super().__init__(params)
        self._exact_sum_str = exact_sum or params.get("exact_sum")
        self.n_raw = int(params.get("n_raw", 100))

    # ------------------------------------------------------------------

    @abstractmethod
    def generate(self, n: int, ctx: Context) -> Any:
        """n-й член ряда (0-based)."""
        ...

    def analytic_sum(self, ctx: Context) -> Optional[Any]:
        """
        Аналитическое значение суммы (независимо от ряда).

        По умолчанию None. Серии с формулой переопределяют.
        """
        return None

    def exact_sum(self, ctx: Context):
        """
        Точная сумма: явная или analytic_sum.

        Приоритет: params.exact_sum > analytic_sum.
        """
        if self._exact_sum_str is not None:
            return ctx.number(self._exact_sum_str)
        return self.analytic_sum(ctx)

    def build_stream(self, ctx: Context) -> Stream:
        """Создаёт Stream, лениво генерирующий члены."""
        return _SeriesStream(self, ctx)


class _SeriesStream:
    """Внутренний Stream для SeriesBase."""

    def __init__(self, series: SeriesBase, ctx: Context):
        self._series = series
        self._ctx = ctx
        self._cache: list[Any] = []

    def get(self, n: int) -> Any:
        if n < 0:
            raise IndexError(f"negative index: {n}")
        self.extend_to(n)
        return self._cache[n]

    def extend_to(self, n: int) -> None:
        if n < 0:
            raise IndexError(f"negative index: {n}")
        while len(self._cache) <= n:
            idx = len(self._cache)
            self._cache.append(self._series.generate(idx, self._ctx))

    def __len__(self) -> int:
        return len(self._cache)