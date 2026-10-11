"""
Упрощённая скользящая EMD-огибающая.

Зачем:
    Эмпирическая модовая декомпозиция (EMD) раскладывает сигнал
    на IMF. Первая IMF — шумовые колебания, остаток — тренд.

    Классический EMD требует весь сигнал. Здесь — упрощение:
    остаток = x_n - скользящее среднее, амплитуда = размах остатка
    в окне.

    ВАЖНО: работает не с самими оценками, а с остатком после
    удаления тренда. Иначе амплитуда не падает.

Как расширять:
    Для настоящего EMD — подключить PyEMD.
"""

from __future__ import annotations
from typing import Any, Literal

from arbacc.core.envelope import EnvelopeBase
from arbacc.core.registry import register


@register("envelopes", "emd")
class EMDSliding(EnvelopeBase):
    """Упрощённая скользящая EMD-огибающая."""

    name = "emd"
    display_name = "emd"
    run_mode: Literal["during", "after"] = "after"
    used_as: Literal["stopping_criterion", "observer"] = "observer"

    PARAM_SPEC = {
        "window": {
            "type": "int",
            "min": 3,
            "required": True,
            "default": 15,
            "short": "w",
            "hint": "окно для оценки размаха остатка",
        },
        "detrend_window": {
            "type": "int",
            "min": 3,
            "default": 11,
            "short": "dw",
            "hint": "окно скользящего среднего для удаления тренда",
        },
        "threshold": {
            "type": "float",
            "min": 0,
            "max": 1,
            "default": 0.5,
            "short": "th",
            "hint": "доля от пика амплитуды, ниже которой стоп",
        },
        "min_history": {
            "type": "int",
            "min": 1,
            "default": 20,
            "short": "mh",
            "hint": "минимум значений до срабатывания",
        },
        "run_mode": {
            "type": "enum",
            "values": ["during", "after"],
            "default": "after",
            "short": "rm",
            "short_values": {"during": "du", "after": "af"},
        },
        "used_as": {
            "type": "enum",
            "values": ["observer", "stopping_criterion"],
            "default": "observer",
            "short": "ua",
            "short_values": {
                "observer": "obs",
                "stopping_criterion": "sc",
            },
        },
    }

    def __init__(self, params: dict[str, Any] | None = None):
        super().__init__(params)
        params = params or {}
        self._window = int(params.get("window", 15))
        self._detrend_window = int(params.get("detrend_window", 11))
        self._threshold = float(params.get("threshold", 0.5))
        self._min_history = int(params.get("min_history", self._window))
        if "run_mode" in params:
            self.run_mode = params["run_mode"]
        if "used_as" in params:
            self.used_as = params["used_as"]

        self._values: list[float] = []
        self._residual: list[float] = []
        self._amplitudes: list[float] = []
        self._signal_at_env: list[float] = []
        self._stop_at: int | None = None

    def _detrend(self, values: list[float]) -> list[float]:
        """Убирает локальный тренд скользящим средним."""
        w = self._detrend_window
        out: list[float] = []
        for i, v in enumerate(values):
            lo = max(0, i - w + 1)
            window_vals = values[lo:i + 1]
            m = sum(window_vals) / len(window_vals)
            out.append(v - m)
        return out

    def push(self, value: Any) -> None:
        """Добавляет очередное значение траектории."""
        try:
            v = float(value)
        except (TypeError, ValueError):
            v = 0.0
        self._values.append(v)
        self._residual = self._detrend(self._values)

        if len(self._residual) >= self._window:
            recent = self._residual[-self._window:]
            amp = max(recent) - min(recent)
            self._amplitudes.append(amp)
            self._signal_at_env.append(self._values[-1])

        if (
            self._stop_at is None
            and len(self._values) >= self._min_history
            and len(self._amplitudes) >= 5
        ):
            peak = max(self._amplitudes)
            if peak > 0:
                rel = self._amplitudes[-1] / peak
                if rel < self._threshold:
                    self._stop_at = len(self._values) - 1

    def says_stop(self) -> bool:
        return (
            self._stop_at is not None
            and self.used_as == "stopping_criterion"
        )

    def result(self) -> dict[str, Any]:
        """Метаданные огибающей."""
        n_amps = len(self._amplitudes)
        n_sig = len(self._signal_at_env)
        n = min(n_amps, n_sig)
        upper = [self._signal_at_env[i] + self._amplitudes[i] for i in range(n)]
        lower = [self._signal_at_env[i] - self._amplitudes[i] for i in range(n)]
        start_k = max(0, self._window - 1)
        indices = list(range(start_k, start_k + n))

        return {
            "envelope": "emd",
            "suggested_stop_at": self._stop_at,
            "window": self._window,
            "detrend_window": self._detrend_window,
            "threshold": self._threshold,
            "n_values": len(self._values),
            "n_amplitudes": n,
            "last_amplitude": self._amplitudes[-1] if self._amplitudes else None,
            "peak_amplitude": max(self._amplitudes) if self._amplitudes else None,
            "envelope_values": list(self._amplitudes[:n]),
            "envelope_indices": indices,
            "envelope_upper": upper,
            "envelope_lower": lower,
        }