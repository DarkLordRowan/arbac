"""
Скользящая огибающая Гильберта.

Зачем:
    Преобразование Гильберта даёт аналитический сигнал, модуль
    которого — амплитудная огибающая.

    ВАЖНО: огибающая считается не от самих оценок, а от их отклонений
    от локального тренда. Иначе сигнал стремится к константе (пределу),
    а огибающая — к той же константе, а не к нулю, и порог никогда
    не сработает.

    Схема:
        x_n = estimate_n
        m_n = скользящее среднее x по окну `detrend_window`
        r_n = x_n - m_n (остаток)
        Hilbert(r) через FIR → envelope_n (амплитуда колебаний)

Как расширять:
    Для других FIR-окон — параметр `window_type`.
"""

from __future__ import annotations
import math
from typing import Any, Literal

from arbacc.core.envelope import EnvelopeBase
from arbacc.core.registry import register


@register("envelopes", "hilbert")
class HilbertSliding(EnvelopeBase):
    """Скользящая огибающая Гильберта с удалением тренда."""

    name = "hilbert"
    display_name = "hilb"
    run_mode: Literal["during", "after"] = "after"
    used_as: Literal["stopping_criterion", "observer"] = "observer"

    PARAM_SPEC = {
        "window": {
            "type": "int",
            "min": 5,
            "required": True,
            "default": 11,
            "short": "w",
            "hint": "длина FIR-фильтра, нечётная",
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
            "hint": "during — в цикле акселератора; after — после",
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
            "hint": "может ли остановить акселератор",
        },
    }

    def __init__(self, params: dict[str, Any] | None = None):
        super().__init__(params)
        params = params or {}
        self._window = int(params.get("window", 11))
        self._detrend_window = int(params.get("detrend_window", 11))
        self._threshold = float(params.get("threshold", 0.5))
        self._min_history = int(params.get("min_history", self._window))
        # Переопределяем run_mode / used_as из params, если заданы.
        if "run_mode" in params:
            self.run_mode = params["run_mode"]
        if "used_as" in params:
            self.used_as = params["used_as"]

        self._h = self._build_hilbert_fir(self._window)
        self._values: list[float] = []
        self._residual: list[float] = []
        self._envelope: list[float] = []
        self._signal_at_env: list[float] = []
        self._stop_at: int | None = None

    @staticmethod
    def _build_hilbert_fir(window: int) -> list[float]:
        """Коэффициенты FIR-Гильберта с окном Хэмминга."""
        if window % 2 == 0:
            window += 1
        half = window // 2
        h = [0.0] * window
        for i in range(window):
            k = i - half
            if k == 0:
                h[i] = 0.0
            elif k % 2 != 0:
                h[i] = 2.0 / (math.pi * k)
            else:
                h[i] = 0.0
        for i in range(window):
            h[i] *= 0.54 - 0.46 * math.cos(2 * math.pi * i / (window - 1))
        return h

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

        w = self._window
        if len(self._residual) >= w:
            recent = self._residual[-w:]
            h_comp = sum(recent[i] * self._h[i] for i in range(w))
            x = recent[w // 2]
            amp = math.sqrt(x * x + h_comp * h_comp)
            self._envelope.append(amp)
            self._signal_at_env.append(self._values[-1])

        if (
            self._stop_at is None
            and len(self._values) >= self._min_history
            and len(self._envelope) >= 5
        ):
            peak = max(self._envelope)
            if peak > 0:
                rel = self._envelope[-1] / peak
                if rel < self._threshold:
                    self._stop_at = len(self._values) - 1

    def says_stop(self) -> bool:
        return (
            self._stop_at is not None
            and self.used_as == "stopping_criterion"
        )

    def result(self) -> dict[str, Any]:
        """Метаданные огибающей, включая верхнюю и нижнюю границы."""
        n_amps = len(self._envelope)
        n_sig = len(self._signal_at_env)
        n = min(n_amps, n_sig)
        upper = [self._signal_at_env[i] + self._envelope[i] for i in range(n)]
        lower = [self._signal_at_env[i] - self._envelope[i] for i in range(n)]
        start_k = max(0, self._window - 1)
        indices = list(range(start_k, start_k + n))

        return {
            "envelope": "hilbert",
            "suggested_stop_at": self._stop_at,
            "window": self._window,
            "detrend_window": self._detrend_window,
            "threshold": self._threshold,
            "n_values": len(self._values),
            "envelope_length": n,
            "last_amplitude": self._envelope[-1] if self._envelope else None,
            "peak_amplitude": max(self._envelope) if self._envelope else None,
            "envelope_values": list(self._envelope[:n]),
            "envelope_indices": indices,
            "envelope_upper": upper,
            "envelope_lower": lower,
        }