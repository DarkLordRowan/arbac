"""
Noise — искажатель последовательности.

Зачем:
    Noise оборачивает Stream и возвращает новый Stream с шумом.
    Для независимых шумов — counter-based RNG, детерминированный
    по (seed, index). Для коррелированных — access_mode =
    "forward_only".

    Ядро ничего не знает про конкретные шумы. Оно знает только
    абстракцию NoiseBase: transform(n, value, ctx) и wrap(source, ctx).

Как расширять:
    Новый шум = один файл noise/my_noise.py:
        @register("noise", "my_noise")
        class MyNoise(NoiseBase):
            name = "my_noise"
            display_name = "mn"
            PARAM_SPEC = {"sigma": {"type": "float", "required": True,
                                     "default": "1e-6", "short": "sig"}}
            def transform(self, n, value, ctx): ...

    Больше ничего менять не нужно.
"""

from __future__ import annotations
from abc import abstractmethod
from typing import Any, Literal

from arbacc.core.context import Context
from arbacc.core.plugin import PluginBase
from arbacc.core.stream import Stream


class NoiseBase(PluginBase):
    """
    Базовый класс шумов.

    Наследники определяют:
        access_mode  — "random" | "forward_only".
        PARAM_SPEC   — специфичные параметры.
        transform()  — преобразование значения.

    Конструктор принимает seed. Для коррелированных шумов
    переопределяют wrap() с защитой от повторного использования.
    """

    #: "random" — произвольный доступ, "forward_only" — только вперёд.
    access_mode: Literal["random", "forward_only"] = "random"

    def __init__(
        self,
        params: dict[str, Any] | None = None,
        seed: int = 0,
    ):
        """
        Принимает:
            params — параметры шума.
            seed   — seed для RNG.
        """
        super().__init__(params)
        self.seed = int(seed)

    @abstractmethod
    def transform(self, n: int, value: Any, ctx: Context) -> Any:
        """
        Возвращает зашумлённое значение n-го элемента.

        Принимает:
            n     — индекс элемента.
            value — исходное значение.
            ctx   — контекст.

        Возвращает:
            зашумлённое значение.

        Требование:
            Для access_mode == "random" результат — чистая функция
            от (n, value, params, seed). Порядок вызовов не влияет.
        """
        ...

    def wrap(self, source: Stream, ctx: Context) -> Stream:
        """
        Оборачивает source в Stream с шумом.

        Принимает:
            source — исходный Stream.
            ctx    — контекст.

        Возвращает:
            Stream-совместимый объект.
        """
        return _NoisyStream(source, self, ctx)


class _NoisyStream:
    """
    Внутренний Stream, применяющий шум к source.

    Кэширует зашумлённые значения. При extend_to(n) досоздаёт source
    и применяет transform к новым элементам.
    """

    def __init__(self, source: Stream, noise: NoiseBase, ctx: Context):
        self._source = source
        self._noise = noise
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
            raw = self._source.get(idx)
            self._cache.append(self._noise.transform(idx, raw, self._ctx))

    def __len__(self) -> int:
        return len(self._cache)