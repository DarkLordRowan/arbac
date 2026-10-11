"""
Вкладка Residual — точность на графике.

Y-режимы:
    symlog10 — symlog применённый к самой разности diff = est - exact.
               Значения уходят к 0 по мере сходимости.
               |·| ON:  Y = symlog10(|diff|)       (все ≥ 0)
               |·| OFF: Y = symlog10(diff)         (±)
               linthresh вычисляется адаптивно от dps.
    linear   — Y = float(diff) (или |diff| по |·|).

Чекбоксы:
    |·|     — abs(diff) перед symlog/linear.
    Stop    — маркеры остановки.
    Env     — огибающие.
    double  — горизонтальная линия 1e-16 (по умолчанию OFF).
    dps     — горизонтальная линия заявленной точности (по умолчанию OFF).

ВАЖНО про crosshair/snap:
    _compute_y возвращает РЕАЛЬНОЕ значение diff (не symlog!).
    Преобразование в symlog делается:
      - _transform_y_for_plot (при отрисовке линии),
      - _to_display_y (для сопоставления точки с мышью).
    Это даёт согласованность: в _snap_points лежат real, crosshair
    сам применяет to_display.
"""

from __future__ import annotations
import math

from PyQt6.QtCore import Qt

from gui.view_mode.data_loader import AccelData
from gui.view_mode.tabs._base_plot import (
    BasePlotTab, _to_symlog, _from_symlog,
)
from gui.view_mode.tabs._palette import (
    COLORS, series_label, accel_label, envelope_label, residual_prefix,
)


class ResidualTab(BasePlotTab):
    """Вкладка точности (residual)."""

    DEFAULT_TITLE = "Residual"
    X_LABEL = "Шаг n"
    Y_LABEL = "Residual (symlog10)"
    DEFAULT_SCALE = "symlog10"

    Y_MODES = ["symlog10", "linear"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.set_scale_options(self.Y_MODES, label="Y-mode:")
        self._apply_scale(self.Y_MODES[0])

    def _build_layer_checkboxes(self, layout) -> None:
        self._add_checkbox(layout, "abs", "|·|", default=True,
                           tooltip="abs(diff) перед symlog/linear")
        self._add_checkbox(layout, "stops", "Stop", default=True)
        self._add_checkbox(layout, "envs", "Envelopes", default=True)
        self._add_checkbox(layout, "helper_double", "double", default=False,
                           tooltip="Линия 1e-16 (предел double)")
        self._add_checkbox(layout, "helper_dps", "dps", default=False,
                           tooltip="Линия заявленной точности")

    # ------------------------------------------------------------------
    # linthresh — адаптивно от dps
    # ------------------------------------------------------------------

    def _linthresh(self) -> float:
        """linthresh для symlog — на 5 порядков ниже максимального dps."""
        max_dps = 30
        for data in self._tasks:
            prec = data.input_payload.get("precision")
            if isinstance(prec, dict):
                d = prec.get("dps")
                if isinstance(d, int) and d > max_dps:
                    max_dps = d
        for raw in self._raw_series:
            d = raw.get("dps")
            if isinstance(d, int) and d > max_dps:
                max_dps = d
        return 10.0 ** (-max_dps - 5)

    # ------------------------------------------------------------------
    # Шкала
    # ------------------------------------------------------------------

    def _apply_scale(self, mode: str) -> None:
        try:
            if mode == "linear":
                self._y_axis.set_inverse(None)
                self._y_axis.set_custom_formatter(None)
                self._plot.setLogMode(x=False, y=False)
            else:  # symlog10
                lin = self._linthresh()
                self._y_axis.set_inverse(lambda v: _from_symlog(v, lin))
                self._y_axis.set_custom_formatter(None)
                self._plot.setLogMode(x=False, y=False)
        except Exception:
            self._log.exception("_apply_scale(%s) failed", mode)
        self._redraw()
        if self._manual_roi:
            self._apply_roi_from_spinboxes()
        else:
            self._plot.enableAutoRange()
            self._plot.autoRange()

    # ------------------------------------------------------------------
    # Преобразования Y
    # ------------------------------------------------------------------

    def _transform_y_for_plot(self, ys: list) -> list:
        """
        Отрисовка: real diff → display.
        В symlog10 — symlog(y, L). В linear — как есть.
        """
        mode = self._scale.currentText()
        if mode == "symlog10":
            lin = self._linthresh()
            return [_to_symlog(y, lin) for y in ys]
        return list(ys)

    def _to_display_y(self, y_real: float) -> float:
        """
        real → display. Используется crosshair для сопоставления.
        """
        mode = self._scale.currentText()
        if mode == "symlog10":
            return _to_symlog(y_real, self._linthresh())
        return y_real

    def _from_display_y(self, y_disp: float) -> float:
        """display → real. Для подписи y в crosshair."""
        mode = self._scale.currentText()
        if mode == "symlog10":
            return _from_symlog(y_disp, self._linthresh())
        return y_disp

    # ------------------------------------------------------------------
    # Отрисовка
    # ------------------------------------------------------------------

    def _draw_all(self) -> None:
        if not self._tasks and not self._raw_series:
            self._header.setText("Residual — нет данных")
            return

        mode = self._scale.currentText()
        use_abs = self._is_checked("abs")
        show_stops = self._is_checked("stops")
        show_envs = self._is_checked("envs")
        show_help_double = self._is_checked("helper_double")
        show_help_dps = self._is_checked("helper_dps")

        any_plotted = False
        dps_set: set[int] = set()
        backend_used = "mpmath"
        all_xs: list[float] = []

        # 1. Raw partial sums.
        for i, raw in enumerate(self._raw_series):
            if not raw.get("exact_sum"):
                continue
            backend_name = raw.get("backend", "mpmath")
            dps = int(raw.get("dps", 30))
            rx, ry = self._compute_raw(
                raw, mode, use_abs, backend_name, dps,
            )
            if not rx:
                continue
            color = COLORS[(i + 6) % len(COLORS)]
            label = residual_prefix(series_label(raw.get("label", "raw")))
            self._add_line(
                label=label, xs=rx, ys=ry,
                color=color, width=1, style=Qt.PenStyle.DashLine,
            )
            all_xs.extend(rx)
            any_plotted = True

        # 2. Accel.
        for i, data in enumerate(self._tasks):
            if data.exact_sum is None:
                continue
            color = COLORS[i % len(COLORS)]

            prec = data.input_payload.get("precision")
            backend_name, dps = "mpmath", 30
            if isinstance(prec, dict):
                backend_name = prec.get("backend", "mpmath")
                d = prec.get("dps")
                if isinstance(d, int):
                    dps = d
                    dps_set.add(d)
                backend_used = backend_name

            xs_iter, ys_iter = self._compute_data(
                data, mode, use_abs, backend_name, dps,
            )
            if xs_iter:
                label = residual_prefix(accel_label(data))
                self._add_line(
                    label=label, xs=xs_iter, ys=ys_iter,
                    color=color, width=2,
                )
                all_xs.extend(xs_iter)
                any_plotted = True

                if show_stops:
                    self._add_marker(
                        x=xs_iter[-1], y=ys_iter[-1],
                        color=color, symbol="o", size=12,
                        tooltip=(
                            f"STOP: {accel_label(data)}\n"
                            f"k={xs_iter[-1]}, n_used={data.n_used}\n"
                            f"diff={ys_iter[-1]:.4g}"
                        ),
                    )

            if show_envs:
                rx_e = self._draw_envelopes(
                    data, color, mode, use_abs, backend_name, dps,
                )
                if rx_e:
                    all_xs.extend(rx_e)
                    any_plotted = True

        if not any_plotted:
            self._header.setText("Residual — нет exact_sum.")
            return

        # Помощники.
        if all_xs:
            x_min, x_max = min(all_xs), max(all_xs)
            if show_help_double:
                y = 1e-16
                if math.isfinite(y) and y > 0:
                    self._add_hline(
                        label="double (1e-16)", y=y,
                        x_min=x_min, x_max=x_max,
                        color="#888888", style=Qt.PenStyle.DotLine,
                    )
            if show_help_dps and dps_set:
                dps = min(dps_set)
                y = 10.0 ** (-dps)
                if math.isfinite(y) and y > 0:
                    self._add_hline(
                        label=f"заявлено 1e-{dps}", y=y,
                        x_min=x_min, x_max=x_max,
                        color="#f0c674", style=Qt.PenStyle.DotLine,
                    )

        n_accel = sum(1 for t in self._tasks if t.exact_sum)
        n_raw = sum(1 for r in self._raw_series if r.get("exact_sum"))
        abs_mark = " |·|" if use_abs else ""
        self._header.setText(
            f"Residual [{mode}{abs_mark}]: accel={n_accel}, "
            f"raw={n_raw}, backend={backend_used}"
        )

    # ------------------------------------------------------------------
    # Расчёты (возвращают РЕАЛЬНЫЕ diff-значения, не symlog)
    # ------------------------------------------------------------------

    def _make_ctx(self, backend_name: str, dps: int):
        try:
            from arbacc.precision import get_backend
            from arbacc.core.context import Context
            return Context(backend=get_backend(backend_name), dps=dps)
        except Exception:
            return None

    def _compute_y(self, ctx, est, exact, dps, mode, use_abs):
        """
        Возвращает реальный diff (или |diff|). Преобразование в symlog
        делает _transform_y_for_plot при отрисовке.
        """
        diff = ctx.backend.sub(est, exact, dps)
        if use_abs:
            diff = ctx.backend.abs_val(diff, dps)
        try:
            return float(ctx.backend.to_str(diff, dps))
        except Exception:
            return None

    def _compute_data(self, data, mode, use_abs, backend_name, dps):
        if data.exact_sum is None:
            return [], []
        ctx = self._make_ctx(backend_name, dps)
        if ctx is None:
            return [], []
        try:
            exact = ctx.backend.from_str(str(data.exact_sum), dps)
        except Exception:
            return [], []

        xs, ys = [], []
        for rec in data.iterations:
            est_str = rec.get("estimate")
            if est_str is None:
                continue
            try:
                est = ctx.backend.from_str(est_str, dps)
                y = self._compute_y(ctx, est, exact, dps, mode, use_abs)
            except Exception:
                continue
            if y is None or not math.isfinite(y):
                continue
            xs.append(int(rec.get("k", len(xs))))
            ys.append(y)
        return xs, ys

    def _compute_raw(self, raw, mode, use_abs, backend_name, dps):
        if not raw.get("exact_sum"):
            return [], []
        ctx = self._make_ctx(backend_name, dps)
        if ctx is None:
            return [], []
        try:
            exact = ctx.backend.from_str(str(raw["exact_sum"]), dps)
        except Exception:
            return [], []

        xs, ys = [], []
        for k, v in zip(raw.get("xs", []), raw.get("ys", [])):
            try:
                est = ctx.backend.from_str(str(v), dps) \
                    if isinstance(v, str) else ctx.number(v)
                y = self._compute_y(ctx, est, exact, dps, mode, use_abs)
            except Exception:
                continue
            if y is None or not math.isfinite(y):
                continue
            xs.append(int(k))
            ys.append(y)
        return xs, ys

    def _draw_envelopes(
        self, data, color, mode, use_abs, backend_name, dps,
    ):
        if data.exact_sum is None:
            return []
        ctx = self._make_ctx(backend_name, dps)
        if ctx is None:
            return []
        try:
            exact = ctx.backend.from_str(str(data.exact_sum), dps)
        except Exception:
            return []

        all_rx = []
        for env_name in data.envelopes.keys():
            upper = data.envelope_upper.get(env_name, [])
            lower = data.envelope_lower.get(env_name, [])
            idxs = data.envelope_indices.get(env_name, [])
            if not idxs or not upper:
                continue
            env_params = data.envelopes.get(env_name, {}).get("params", {}) or {}
            env_label = envelope_label(data, env_name, env_params)

            n = min(len(upper), len(idxs))
            rx_u, ry_u = self._env_tf(
                ctx, exact, dps, idxs[:n], upper[:n], mode, use_abs,
            )
            if rx_u:
                self._add_line(
                    label=residual_prefix(f"{env_label} (upper)"),
                    xs=rx_u, ys=ry_u,
                    color=color, width=1, style=Qt.PenStyle.DotLine,
                )
                all_rx.extend(rx_u)

            if lower:
                n = min(len(lower), len(idxs))
                rx_l, ry_l = self._env_tf(
                    ctx, exact, dps, idxs[:n], lower[:n], mode, use_abs,
                )
                if rx_l:
                    self._add_line(
                        label=residual_prefix(f"{env_label} (lower)"),
                        xs=rx_l, ys=ry_l,
                        color=color, width=1, style=Qt.PenStyle.DotLine,
                    )
                    all_rx.extend(rx_l)
        return all_rx

    def _env_tf(self, ctx, exact, dps, idxs, values, mode, use_abs):
        xs, ys = [], []
        for k, v in zip(idxs, values):
            try:
                est = ctx.number(v)
                y = self._compute_y(ctx, est, exact, dps, mode, use_abs)
            except Exception:
                continue
            if y is None or not math.isfinite(y):
                continue
            xs.append(int(k))
            ys.append(y)
        return xs, ys