"""
Вкладка Overview — график траектории оценок.

Использует BasePlotTab: вся инфраструктура (crosshair, snap, шкала,
Reset view, заголовок) — в базовом классе. Здесь только логика
отрисовки.

Метки в легенде:
    s: <series_id>
    a: <series> / <noise> / <accel> [dps=...]
    f: <series> / <noise> / <accel> / <filter>(params)
    e: <series> / <noise> / <accel> / <envelope>(params)
    exact: <series_id>
"""

from __future__ import annotations

import pyqtgraph as pg
from PyQt6.QtCore import Qt

from gui.view_mode.data_loader import (
    AccelData, estimate_floats, load_filter_values,
)
from gui.view_mode.tabs._base_plot import BasePlotTab
from gui.view_mode.tabs._palette import (
    COLORS, FILTER_STYLES,
    series_label, accel_label, filter_label, envelope_label, exact_label,
)


class OverviewTab(BasePlotTab):
    """Вкладка общего графика."""

    DEFAULT_TITLE = "Overview"
    X_LABEL = "Шаг n"
    Y_LABEL = "Значение последовательности"
    DEFAULT_SCALE = "linear"

    def _build_layer_checkboxes(self, layout) -> None:
        """Чекбоксы слоёв."""
        self._add_checkbox(layout, "stops", "Stop", default=True,
                           tooltip="Точки остановки акселератора")
        self._add_checkbox(layout, "envs", "Envelope", default=True,
                           tooltip="Огибающие: upper/lower и suggested_stop_at")
        self._add_checkbox(layout, "exact", "Exact", default=True,
                           tooltip="Горизонтальные линии точной суммы")
        self._add_checkbox(layout, "filters", "Filters", default=True,
                           tooltip="Кривые после фильтров postprocess")

    # ------------------------------------------------------------------

    def _draw_all(self) -> None:
        """Рисует всё содержимое вкладки."""
        if not self._tasks and not self._raw_series:
            self._header.setText("Overview — нет данных")
            return

        show_stops = self._is_checked("stops")
        show_envs = self._is_checked("envs")
        show_exact = self._is_checked("exact")
        show_filters = self._is_checked("filters")

        plotted = 0
        all_xs: list[float] = []
        exact_lines: list[tuple[str, float]] = []

        # --- 1. Сырые partial sums ---
        for i, raw in enumerate(self._raw_series):
            xs = raw.get("xs", [])
            ys_raw = raw.get("ys", [])
            if not xs:
                continue
            # ys_raw — строки полной точности; в float только для графики.
            ys: list[float] = []
            for v in ys_raw:
                try:
                    ys.append(float(v))
                except (ValueError, TypeError):
                    ys.append(float("nan"))
            color = COLORS[(i + 6) % len(COLORS)]
            label = raw.get("label", "raw")
            self._add_line(
                label=series_label(label),
                xs=xs, ys=ys,
                color=color, width=1, style=Qt.PenStyle.DashLine,
            )
            all_xs.extend(xs)
            plotted += 1
            if show_exact and raw.get("exact_sum"):
                try:
                    exact_lines.append(
                        (exact_label(label), float(raw["exact_sum"]))
                    )
                except (ValueError, TypeError):
                    pass

        # --- 2. Accel + фильтры + огибающие ---
        for i, data in enumerate(self._tasks):
            xs, ys = estimate_floats(data)
            if not xs:
                continue
            color = COLORS[i % len(COLORS)]
            # ВАЖНО: имя переменной НЕ совпадает с именем функции.
            alabel = accel_label(data)

            self._add_line(
                label=alabel,
                xs=xs, ys=ys,
                color=color, width=2,
            )
            all_xs.extend(xs)

            # Stop-маркер.
            if show_stops:
                self._add_marker(
                    x=xs[-1], y=ys[-1],
                    color=color, symbol="o", size=12,
                    tooltip=(
                        f"STOP: {alabel}\n"
                        f"k={xs[-1]}, n_used={data.n_used}\n"
                        f"estimate={data.estimate}\n"
                        f"stopped_by={data.stopped_by}"
                    ),
                )

            if show_exact and data.exact_sum:
                try:
                    exact_lines.append(
                        (exact_label(data.series_id), float(data.exact_sum))
                    )
                except (ValueError, TypeError):
                    pass

            # Фильтры.
            if show_filters:
                self._draw_filters(data, color)

            # Огибающие.
            if show_envs:
                self._draw_envelopes(data, color, xs, ys)

            plotted += 1

        # --- 3. Линии exact_sum ---
        if show_exact and exact_lines and all_xs:
            self._draw_exact_lines(exact_lines, all_xs)

        self._header.setText(f"{plotted} кривых")

    # ------------------------------------------------------------------
    # Хелперы
    # ------------------------------------------------------------------

    def _draw_filters(self, data: AccelData, color: str) -> None:
        """Рисует кривые фильтров одной accel-ветки."""
        root = data.output_root()
        if root is None:
            return
        for j, (fname, fdata) in enumerate(data.filters.items()):
            xs_f, ys_f = load_filter_values(
                root, data.series_id, data.noise_id,
                data.accel_id, fname,
            )
            if not xs_f:
                continue
            style = FILTER_STYLES[j % len(FILTER_STYLES)]
            fparams = fdata.get("params", {}) or {}
            # Локальная переменная flabel, а не имя функции.
            flabel = filter_label(data, fname, fparams)
            self._add_line(
                label=flabel,
                xs=xs_f, ys=ys_f,
                color=color, width=2, style=style,
            )

    def _draw_envelopes(
        self,
        data: AccelData,
        color: str,
        xs: list,
        ys: list,
    ) -> None:
        """Рисует верхнюю/нижнюю огибающие + маркер suggested_stop_at."""
        for env_name, env_data in data.envelopes.items():
            env_params = env_data.get("params", {}) or {}
            elabel = envelope_label(data, env_name, env_params)
            upper = data.envelope_upper.get(env_name, [])
            lower = data.envelope_lower.get(env_name, [])
            idxs = data.envelope_indices.get(env_name, [])

            if upper and idxs:
                n = min(len(upper), len(idxs))
                self._add_line(
                    label=f"{elabel} (upper)",
                    xs=idxs[:n], ys=upper[:n],
                    color=color, width=1, style=Qt.PenStyle.DotLine,
                )
            if lower and idxs:
                n = min(len(lower), len(idxs))
                self._add_line(
                    label=f"{elabel} (lower)",
                    xs=idxs[:n], ys=lower[:n],
                    color=color, width=1, style=Qt.PenStyle.DotLine,
                )

            # Маркер suggested_stop_at.
            sug = env_data.get("envelope", {}).get("suggested_stop_at")
            if sug is not None and 0 <= sug < len(xs):
                comp = env_data.get("comparison", {})
                tip_lines = [
                    f"ENVELOPE: {elabel}",
                    f"suggested_stop_at = k={sug}",
                ]
                if comp.get("envelope_was_right") is not None:
                    tip_lines.append(f"was_right = {comp['envelope_was_right']}")
                if comp.get("digits_lost") is not None:
                    tip_lines.append(f"digits_lost = {comp['digits_lost']}")
                self._add_marker(
                    x=xs[sug], y=ys[sug],
                    color=color, symbol="t", size=14,
                    tooltip="\n".join(tip_lines),
                )

    def _draw_exact_lines(
        self,
        exact_lines: list[tuple[str, float]],
        all_xs: list[float],
    ) -> None:
        """Горизонтальные линии exact_sum с дедупом по значению."""
        x_min, x_max = min(all_xs), max(all_xs)
        by_value: dict[float, str] = {}
        for label, val in exact_lines:
            key = round(val, 12)
            if key not in by_value or len(label) < len(by_value[key]):
                by_value[key] = label
        for val, label in by_value.items():
            self._add_hline(
                label=label,
                y=val, x_min=x_min, x_max=x_max,
                color="#6fbf73",
                style=Qt.PenStyle.DashLine,
            )