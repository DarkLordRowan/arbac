"""
AcceleratedResult — итог работы акселератора.

Зачем нужен:
    Акселератор возвращает не только финальную оценку, но и всю траекторию
    итераций + метаданные (сколько членов использовано, почему остановился).
    Эти данные нужны:
      - для постобработки (она читает iterations),
      - для метрик (digits_gained),
      - для сохранения и последующего анализа.

Как расширять:
    Если понадобится хранить больше (например, промежуточные таблицы),
    добавь поля сюда — это dataclass, легко расширяется.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class IterationRecord:
    """
    Одна запись об итерации акселератора.

    Поля:
        k        — номер итерации
        estimate — оценка предела на этой итерации
        n_used   — сколько членов источника использовано к этому моменту
    """
    k: int
    estimate: Any
    n_used: int


@dataclass
class AcceleratedResult:
    """
    Полный результат работы акселератора.

    Поля:
        accelerator   — имя акселератора
        params        — параметры, с которыми он запускался
        iterations    — список IterationRecord
        estimate      — финальная оценка (последний элемент iterations)
        n_used        — сколько членов источника реально использовано
        n_max         — верхняя граница, если была задана
        stopped_by    — причина остановки ("digits_stable", "max_iter", ...)
        status        — "ok" | "failed"
        error         — текст ошибки, если status == "failed"
        exact_sum     — точная сумма, если известна
        digits_gained — число верных цифр (если exact_sum известен)
        meta          — произвольные доп. метаданные
    """
    accelerator: str
    params: dict[str, Any]
    iterations: list[IterationRecord] = field(default_factory=list)
    estimate: Any = None
    n_used: int = 0
    n_max: Optional[int] = None
    stopped_by: str = ""
    status: str = "ok"
    error: Optional[str] = None
    exact_sum: Any = None
    digits_gained: Optional[int] = None
    meta: dict[str, Any] = field(default_factory=dict)