"""
Stream — продуцируемая последовательность чисел.

Зачем нужен:
    Это базовый контракт для всего, что можно "тянуть" по одному элементу:
    ряды, зашумлённые ряды, выход акселератора. Stream умеет:
      - get(n) — вернуть n-й элемент (при необходимости досоздать),
      - extend_to(n) — гарантировать, что элементы [0..n] доступны,
      - __len__ — сколько уже материализовано.

    Ключевое свойство: extend_to идемпотентен — повторный вызов ничего
    не ломает. Это позволяет акселератору свободно запрашивать больше
    элементов, не заботясь о том, что уже запрошено.

Как расширять:
    Stream — Protocol, а не базовый класс. Любой класс с методами
    get/extend_to/__len__ подходит. Конкретные реализации:
      - SeriesStream (в core/series.py)
      - NoisyStream  (в core/noise.py)
    Ничего наследовать не нужно — достаточно структурного соответствия.
"""

from __future__ import annotations
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Stream(Protocol):
    """Продуцируемая последовательность чисел."""

    def get(self, n: int) -> Any:
        """
        Возвращает n-й элемент, при необходимости досоздавая хвост.

        Принимает:
            n — неотрицательный индекс

        Возвращает:
            число в представлении backend'а текущего Context.
        """
        ...

    def extend_to(self, n: int) -> None:
        """
        Гарантирует, что элементы [0..n] доступны.

        Принимает:
            n — неотрицательный индекс

        Возвращает:
            None.

        Примечание:
            Идемпотентна: повторный вызов с тем же или меньшим n — no-op.
        """
        ...

    def __len__(self) -> int:
        """Возвращает количество уже материализованных элементов."""
        ...

def is_sequence(source) -> bool:
    """Optional stream tag; untagged existing streams still contain series terms."""
    return getattr(source,'kind','terms')=='sequence'


def partial_value(source,n,previous,ctx):
    """Return s_n from either raw sequence samples or series terms.

    Do not difference and re-sum a sequence: cancellation would erase the
    precision-sensitive effects studied by Rump (ETNA 52, 2020).
    """
    value=source.get(n)
    if is_sequence(source) or previous is None:
        return value
    return ctx.backend.add(previous,value,ctx.dps)


def series_term(source,n,ctx):
    """a_n=s_n-s_(n-1) for a sequence; s_(-1)=0 by convention."""
    if n<0: raise IndexError('negative term index')
    value=source.get(n)
    if not is_sequence(source) or n==0:
        return value
    return ctx.backend.sub(value,source.get(n-1),ctx.dps)


def extend_partials(source,values,ctx,count):
    """Extend a partial-sum/sequence cache without changing its interpretation."""
    while len(values)<count:
        n=len(values)
        values.append(partial_value(source,n,values[-1] if values else None,ctx))
    return values
