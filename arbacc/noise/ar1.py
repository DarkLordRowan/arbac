"""
AR(1) шум — коррелированный шум с памятью.

Зачем:
    e_n = phi * e_{n-1} + sigma * N(0, 1).
    Значение e_n зависит от e_{n-1}, поэтому произвольный доступ
    "в прошлое" невозможен. Это forward-only шум.

    При повторном wrap одного и того же инстанса состояние
    рассинхронизируется — поэтому wrap защищён от повторного вызова.

Как расширять:
    Для AR(p) или ARMA — по аналогии, следи за состоянием.
"""

from __future__ import annotations
from typing import Any

from arbacc.core.context import Context
from arbacc.core.noise import NoiseBase
from arbacc.core.registry import register
from arbacc.core.rng import CounterRNG
from arbacc.core.stream import Stream


@register("noise", "ar1")
class AR1Noise(NoiseBase):
    """AR(1) шум: e_n = phi * e_{n-1} + sigma * eps_n."""

    name = "ar1"
    display_name = "ar1"
    access_mode = "forward_only"

    PARAM_SPEC = {
        "phi": {
            "type": "float",
            "required": True,
            "default": "0.7",
            "min": -1,
            "max": 1,
            "short": "ph",
            "hint": "коэффициент автокорреляции, |phi| < 1",
        },
        "sigma": {
            "type": "float",
            "required": True,
            "default": "1e-6",
            "short": "sig",
            "hint": "стандартное отклонение инновации",
        },
    }

    def __init__(self, params: dict[str, Any] | None = None, seed: int = 0):
        """
        Принимает:
            params — {phi, sigma}.
            seed   — seed для RNG.
        """
        super().__init__(params, seed)
        stream_id = f"ar1|{(params or {}).get('phi')}|{(params or {}).get('sigma')}"
        self._rng = CounterRNG(seed, stream_id)
        self._state: list[Any] = []      # кэш e_n
        self._last_n: int = -1
        self._wrapped: bool = False      # защита от повторного wrap

    def wrap(self, source: Stream, ctx: Context) -> Stream:
        """
        Оборачивает source в Stream с AR(1) шумом.

        Принимает:
            source — исходный Stream.
            ctx    — контекст.

        Возвращает:
            Stream.

        Бросает:
            RuntimeError — если wrap уже вызывался.
        """
        if self._wrapped:
            raise RuntimeError(
                "AR1Noise.wrap already called; "
                "create a new AR1Noise instance for a new stream"
            )
        self._wrapped = True
        return super().wrap(source, ctx)

    def transform(self, n: int, value: Any, ctx: Context) -> Any:
        """
        Добавляет AR(1) шум к value.

        Принимает:
            n     — индекс (должен идти по возрастанию).
            value — исходное значение.
            ctx   — контекст.

        Возвращает:
            value + e_n.

        Бросает:
            RuntimeError — если n < last_n.
        """
        if n < self._last_n:
            raise RuntimeError(
                f"AR1Noise is forward-only: requested n={n}, "
                f"but last computed was {self._last_n}"
            )

        b = ctx.backend
        phi = ctx.number(self.params["phi"])
        sigma = ctx.number(self.params["sigma"])

        # Досоздаём e_0..e_n.
        while len(self._state) <= n:
            k = len(self._state)
            eps = ctx.number(self._rng.normal(k))
            new_part = b.mul(sigma, eps, ctx.dps)
            if k == 0:
                e = new_part
            else:
                e_prev = self._state[k - 1]
                old_part = b.mul(phi, e_prev, ctx.dps)
                e = b.add(old_part, new_part, ctx.dps)
            self._state.append(e)
            self._last_n = k

        e_n = self._state[n]
        return b.add(value, e_n, ctx.dps)