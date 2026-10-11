"""
Вкладка Tables — summary + детальная таблица для одной задачи.

Значения в таблицах берутся из сохранённых строк (result.json,
iterations.parquet) — полная точность backend'а.

Колонка |diff| и log10|diff| считаются через backend.digits_of,
а не через float(est - exact), иначе при dps > 15 всё обнулялось бы.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QLabel,
)
from PyQt6.QtCore import Qt

from gui.view_mode.data_loader import AccelData


class TablesTab(QWidget):
    """Вкладка с таблицами."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self._summary_label = QLabel("Summary:")
        self._summary = _make_table(
            ["series", "noise", "accel", "dps", "estimate",
             "digits", "stopped_by", "n_used"]
        )
        self._summary.setMaximumHeight(150)
        layout.addWidget(self._summary_label)
        layout.addWidget(self._summary)

        self._detail_label = QLabel("Detail (первая задача):")
        layout.addWidget(self._detail_label)

        self._sub = QTabWidget()
        self._values = _make_table(["k", "n_used", "estimate (full)"])
        self._errors = _make_table(
            ["k", "|diff|", "log10 |diff|", "digits_gained"]
        )
        self._events = _make_table(["when", "event", "details"])
        self._sub.addTab(self._values, "Значения (values)")
        self._sub.addTab(self._errors, "Ошибки (errors)")
        self._sub.addTab(self._events, "События (events)")

        self._sub.setTabToolTip(0, "k, n_used, estimate — полная строка")
        self._sub.setTabToolTip(
            1, "k, |diff|, log10|diff|, digits — точная арифметика backend",
        )
        self._sub.setTabToolTip(
            2, "stopped_by, envelope suggestions, filters",
        )

        layout.addWidget(self._sub, stretch=1)

        self._set_summary_visible(False)

    def clear_data(self):
        self._summary.setRowCount(0)
        self._values.setRowCount(0)
        self._errors.setRowCount(0)
        self._events.setRowCount(0)
        self._set_summary_visible(False)

    def show_data(self, data: AccelData) -> None:
        self.show_data_list([data])

    def show_data_list(self, tasks: list[AccelData]) -> None:
        if not tasks:
            self.clear_data()
            return

        if len(tasks) > 1:
            self._set_summary_visible(True)
            self._fill_summary(tasks)
            self._summary_label.setText(f"Summary ({len(tasks)} задач):")
        else:
            self._set_summary_visible(False)

        first = tasks[0]
        self._detail_label.setText(
            f"Detail: {first.short_label} (первая из {len(tasks)})"
            if len(tasks) > 1 else f"Detail: {first.short_label}"
        )
        self._fill_values(first)
        self._fill_errors(first)
        self._fill_events(first)

    def _set_summary_visible(self, visible: bool) -> None:
        self._summary_label.setVisible(visible)
        self._summary.setVisible(visible)

    def _fill_summary(self, tasks: list[AccelData]) -> None:
        # Отключаем сортировку, иначе QT переставит строки прямо в момент
        # setItem и item(i, j) вернёт None.
        self._summary.setSortingEnabled(False)
        try:
            self._summary.setRowCount(len(tasks))
            for i, t in enumerate(tasks):
                prec = t.input_payload.get("precision")
                dps = prec.get("dps") if isinstance(prec, dict) else "?"
                self._summary.setItem(i, 0, QTableWidgetItem(t.series_id))
                self._summary.setItem(i, 1, QTableWidgetItem(t.noise_id))
                self._summary.setItem(i, 2, QTableWidgetItem(t.accel_id))
                self._summary.setItem(i, 3, QTableWidgetItem(str(dps)))
                self._summary.setItem(i, 4, QTableWidgetItem(str(t.estimate)))
                self._summary.setItem(
                    i, 5, QTableWidgetItem(str(t.digits_gained)),
                )
                self._summary.setItem(i, 6, QTableWidgetItem(t.stopped_by))
                self._summary.setItem(i, 7, QTableWidgetItem(str(t.n_used)))
        finally:
            self._summary.setSortingEnabled(True)

    def _fill_values(self, data: AccelData) -> None:
        """estimate как строка — полная точность сохраняется."""
        self._values.setSortingEnabled(False)
        try:
            rows = data.iterations
            self._values.setRowCount(len(rows))
            for i, rec in enumerate(rows):
                self._values.setItem(
                    i, 0, QTableWidgetItem(str(rec.get("k", ""))),
                )
                self._values.setItem(
                    i, 1, QTableWidgetItem(str(rec.get("n_used", ""))),
                )
                self._values.setItem(
                    i, 2,
                    QTableWidgetItem(str(rec.get("estimate", ""))),
                )
        finally:
            self._values.setSortingEnabled(True)

    def _fill_errors(self, data: AccelData) -> None:
        """
        Считает |diff| и digits_gained через backend — точная
        арифметика, работает для любой dps.
        """
        rows = data.iterations

        backend_name = "mpmath"
        dps = 30
        prec = data.input_payload.get("precision")
        if isinstance(prec, dict):
            backend_name = prec.get("backend", "mpmath")
            d = prec.get("dps")
            if isinstance(d, int):
                dps = d

        ctx = None
        try:
            from arbacc.precision import get_backend
            from arbacc.core.context import Context
            rounding = "nearest"
            if isinstance(prec, dict):
                rounding = prec.get("rounding", "nearest")
            ctx = Context(
                backend=get_backend(backend_name),
                dps=dps,
                rounding=rounding,
            )
        except Exception:
            ctx = None

        exact_num = None
        if data.exact_sum and ctx is not None:
            try:
                exact_num = ctx.backend.from_str(str(data.exact_sum), dps)
            except Exception:
                exact_num = None

        self._errors.setSortingEnabled(False)
        try:
            self._errors.setRowCount(len(rows))

            for i, rec in enumerate(rows):
                self._errors.setItem(
                    i, 0, QTableWidgetItem(str(rec.get("k", ""))),
                )

                if (exact_num is None or ctx is None
                        or rec.get("estimate") is None):
                    for col in (1, 2, 3):
                        self._errors.setItem(
                            i, col, QTableWidgetItem("—"),
                        )
                    continue

                try:
                    est = ctx.backend.from_str(rec["estimate"], dps)
                    diff = ctx.backend.abs_diff(est, exact_num, dps)
                    digits = ctx.backend.digits_of(est, exact_num, dps)
                except Exception:
                    for col in (1, 2, 3):
                        self._errors.setItem(
                            i, col, QTableWidgetItem("—"),
                        )
                    continue

                try:
                    diff_s = _short_num(ctx, diff, dps)
                except Exception:
                    diff_s = "?"

                log10_s = f"{-digits}"

                self._errors.setItem(i, 1, QTableWidgetItem(diff_s))
                self._errors.setItem(i, 2, QTableWidgetItem(log10_s))
                self._errors.setItem(i, 3, QTableWidgetItem(str(digits)))
        finally:
            self._errors.setSortingEnabled(True)

    def _fill_events(self, data: AccelData) -> None:
        events: list[tuple[str, str, str]] = []
        last_k = data.iterations[-1].get("k") if data.iterations else "?"
        events.append((f"k={last_k}", "stopped_by", data.stopped_by))

        for env_name, env_data in data.envelopes.items():
            envelope = env_data.get("envelope", {})
            sug = envelope.get("suggested_stop_at")
            comp = env_data.get("comparison", {})
            details = f"suggested_stop_at={sug}"
            if "envelope_was_right" in comp:
                details += f", right={comp['envelope_was_right']}"
            if "digits_lost" in comp:
                details += f", digits_lost={comp['digits_lost']}"
            events.append((f"k={sug}", f"envelope:{env_name}", details))

        for filter_name, filter_data in data.filters.items():
            details = (
                f"window={filter_data.get('params', {}).get('window')}, "
                f"passes={filter_data.get('params', {}).get('passes', '-')}, "
                f"final_digits={filter_data.get('digits_gained')}"
            )
            events.append(("post", f"filter:{filter_name}", details))

        if data.error:
            events.append(("—", "error", data.error))

        self._events.setSortingEnabled(False)
        try:
            self._events.setRowCount(len(events))
            for i, (when, event, details) in enumerate(events):
                self._events.setItem(i, 0, QTableWidgetItem(when))
                self._events.setItem(i, 1, QTableWidgetItem(event))
                self._events.setItem(i, 2, QTableWidgetItem(details))
        finally:
            self._events.setSortingEnabled(True)


def _make_table(headers: list[str]) -> QTableWidget:
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    t.setSortingEnabled(True)
    return t


def _short_num(ctx, value, dps: int) -> str:
    """
    Короткое представление числа backend'а для колонки |diff|.
    """
    s = ctx.backend.to_str(value, dps)
    if "e" in s or "E" in s:
        return s
    try:
        f = float(s)
    except (ValueError, TypeError):
        return s
    if f == 0:
        return "0"
    import math
    e = int(math.floor(math.log10(abs(f))))
    m = f / (10 ** e)
    return f"{m:.3g}e{e}"