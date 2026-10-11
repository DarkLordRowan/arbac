"""
Гауссов шум.

Зачем:
    Классическая модель шума: к каждому члену добавляется N(0, sigma).
    Благодаря CounterRNG значение шума для индекса n — чистая функция
    от (seed, n, params), что гарантирует детерминизм при досоздании.

    Режимы:
        mode="absolute" — добавляем sigma * N(0, 1)
        mode="relative" — добавляем sigma * |value| * N(0, 1)

Как расширять:
    Новый шум — унаследуйся от NoiseBase, реализуй transform,
    используй CounterRNG для детерминизма.
"""

from __future__ import annotations
from typing import Any

from arbacc.core.context import Context
from arbacc.core.noise import NoiseBase
from arbacc.core.registry import register
from arbacc.core.rng import CounterRNG


@register("noise", "gaussian")
class GaussianNoise(NoiseBase):
    """Аддитивный гауссов шум."""

    name = "gaussian"
    display_name = "gauss"
    access_mode = "random"

    PARAM_SPEC = {
        "sigma": {
            "type": "float",
            "required": True,
            "default": "1e-6",
            "short": "sig",
            "hint": "стандартное отклонение",
        },
        "mode": {
            "type": "enum",
            "values": ["absolute", "relative"],
            "default": "absolute",
            "short": "md",
            "short_values": {"absolute": "abs", "relative": "rel"},
            "hint": "absolute — фиксированный шум; relative — ∝ |value|",
        },
    }

    def __init__(self, params: dict[str, Any] | None = None, seed: int = 0):
        """
        Принимает:
            params — {sigma, mode}.
            seed   — seed для RNG.
        """
        super().__init__(params, seed)
        sigma_s = str((params or {}).get("sigma", "0"))
        mode = (params or {}).get("mode", "absolute")
        # stream_id формируется из параметров — разные sigma и mode
        # дают разные последовательности при одном seed.
        stream_id = f"gaussian|{sigma_s}|{mode}"
        self._rng = CounterRNG(seed, stream_id)

    def transform(self, n: int, value: Any, ctx: Context) -> Any:
        """
        Добавляет гауссов шум к value.

        Принимает:
            n     — индекс.
            value — исходное значение.
            ctx   — контекст.

        Возвращает:
            value + noise.
        """
        b = ctx.backend
        sigma = ctx.number(self.params.get("sigma", "0"))
        mode = self.params.get("mode", "absolute")

        # Стандартное N(0,1) как float, затем в backend.
        z = self._rng.normal(n)
        z_num = ctx.number(z)

        if mode == "relative":
            abs_v = b.abs_val(value, ctx.dps)
            delta = b.mul(sigma, b.mul(abs_v, z_num, ctx.dps), ctx.dps)
        else:
            delta = b.mul(sigma, z_num, ctx.dps)

        return b.add(value, delta, ctx.dps)