"""
Шум "none" — отсутствие шума.

Зачем:
    Чтобы в JSON можно было явно указать отсутствие шума, а не
    пропускать поле. Плюс — единообразие: в плане всегда есть noise_id.

Как расширять:
    Тривиальный шаблон. Для нового шума — см. gaussian.py.
"""

from __future__ import annotations
from typing import Any

from arbacc.core.context import Context
from arbacc.core.noise import NoiseBase
from arbacc.core.registry import register


@register("noise", "none")
class NoNoise(NoiseBase):
    """Шум, не меняющий значения."""

    name = "none"
    display_name = "none"
    access_mode = "random"

    #: Параметров нет.
    PARAM_SPEC = {}

    def transform(self, n: int, value: Any, ctx: Context) -> Any:
        """
        Возвращает value без изменений.

        Принимает:
            n     — индекс.
            value — исходное значение.
            ctx   — контекст.

        Возвращает:
            value.
        """
        return value