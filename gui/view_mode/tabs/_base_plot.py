"""
BasePlotTab — общая основа для вкладок Overview и Residual.

Возможности:
    - linear / log / symlog шкала Y (переопределяется наследником),
    - в log-режиме отрицательные y берутся по модулю,
    - подписи оси Y в научном формате (1e-3, 1e-300),
    - crosshair со snap,
    - ROI: числа X min/max, Y min/max + Auto,
    - сворачиваемая панель управления,
    - чекбоксы слоёв,
    - Reset view,
    - экспорт в PNG,
    - экспорт видимых линий в plot_viewer.py.
"""

from __future__ import annotations
import math
from pathlib import Path

import pyqtgraph as pg
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox,
    QComboBox, QFileDialog, QMessageBox, QDoubleSpinBox, QToolButton,
)
from PyQt6.QtCore import Qt, QObject, QEvent

from gui.common.log import get_logger
from gui.view_mode.tabs._crosshair import Crosshair
from gui.view_mode.plot_viewer_export import (
    build_plot_viewer_data, save_to_json, launch_plot_viewer,
    find_plot_viewer,
)


def _to_symlog(y: float, linthresh: float) -> float:
    if y == 0:
        return 0.0
    if not math.isfinite(y):
        return y
    return math.copysign(math.log10(1.0 + abs(y) / linthresh), y)


def _from_symlog(y_disp: float, linthresh: float) -> float:
    if y_disp == 0:
        return 0.0
    if not math.isfinite(y_disp):
        return y_disp
    return math.copysign((10.0 ** abs(y_disp) - 1.0) * linthresh, y_disp)


def _format_tick(x: float) -> str:
    if x == 0:
        return "0"
    if not math.isfinite(x):
        return str(x)
    a = abs(x)
    if 1e-3 <= a < 1e5:
        return f"{x:g}"
    s = f"{x:.2e}"
    mant, exp = s.split("e")
    mant = mant.rstrip("0").rstrip(".")
    sign = ""
    if exp and exp[0] in "+-":
        sign = exp[0]
        exp = exp[1:]
    exp = exp.lstrip("0") or "0"
    return f"{mant}e{sign}{exp}"


class _TransformAxis(pg.AxisItem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._inverse = None
        self._custom_formatter = None

    def set_inverse(self, fn):
        self._inverse = fn
        self.picture = None
        self.update()

    def set_custom_formatter(self, fn):
        self._custom_formatter = fn
        self.picture = None
        self.update()

    def tickStrings(self, values, scale, spacing):
        if self._custom_formatter is not None:
            out = []
            for v in values:
                try:
                    out.append(self._custom_formatter(v))
                except Exception:
                    out.append("")
            return out
        if self._inverse is None:
            return super().tickStrings(values, scale, spacing)
        out = []
        for v in values:
            try:
                out.append(_format_tick(self._inverse(v)))
            except Exception:
                out.append("")
        return out


class BasePlotTab(QWidget):
    """Базовая вкладка с графиком, crosshair, ROI, шкалой, PNG, PlotViewer."""

    DEFAULT_TITLE: str = "Plot"
    X_LABEL: str = "Шаг n"
    Y_LABEL: str = "Y"
    DEFAULT_SCALE: str = "linear"

    SYMLOG_LINTHRESH: float = 1e-3
    SCALES = ["linear", "log", "symlog"]

    def __init__(self, parent=None):
        super().__init__(parent)

        self._log = get_logger(f"plot.{self.__class__.__name__}")

        self._tasks: list = []
        self._raw_series: list[dict] = []
        self._exported_lines: list[dict] = []

        self._manual_roi: bool = False
        self._suppress_roi: bool = False

        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        # --- Кнопка-тоггл настроек ---
        head = QHBoxLayout()
        self._header = QLabel(self.DEFAULT_TITLE)
        head.addWidget(self._header)
        head.addStretch()

        self._btn_toggle = QToolButton()
        self._btn_toggle.setText("⚙ Настройки")
        self._btn_toggle.setCheckable(True)
        self._btn_toggle.setChecked(True)
        self._btn_toggle.setArrowType(Qt.ArrowType.DownArrow)
        self._btn_toggle.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        self._btn_toggle.clicked.connect(self._on_toggle_controls)
        head.addWidget(self._btn_toggle)
        root.addLayout(head)

        # --- Сворачиваемая панель управления ---
        self._controls = QWidget()
        controls_layout = QVBoxLayout(self._controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(4)

        top = QHBoxLayout()
        self._scale_label = QLabel("Y-scale:")
        top.addWidget(self._scale_label)
        self._scale = QComboBox()
        self._scale.addItems(self.SCALES)
        self._scale.setCurrentText(self.DEFAULT_SCALE)
        self._scale.currentTextChanged.connect(self._apply_scale)
        top.addWidget(self._scale)
        top.addStretch()

        self._cb: dict[str, QCheckBox] = {}
        self._add_checkbox(top, "cross", "Crosshair", default=True,
                           tooltip="Перекрестие под мышью")
        self._add_checkbox(top, "snap", "Snap", default=True,
                           tooltip="Магнитить crosshair к точке")
        self._build_layer_checkboxes(top)

        controls_layout.addLayout(top)

        # --- ROI ---
        roi = QHBoxLayout()
        roi.setContentsMargins(0, 0, 0, 0)
        roi.setSpacing(4)
        roi.addWidget(QLabel("X:"))
        self._roi_x_min = _make_roi_spin(); self._roi_x_min.setValue(0.0)
        self._roi_x_max = _make_roi_spin(); self._roi_x_max.setValue(100.0)
        self._roi_x_min.valueChanged.connect(self._on_roi_changed)
        self._roi_x_max.valueChanged.connect(self._on_roi_changed)
        roi.addWidget(self._roi_x_min)
        roi.addWidget(QLabel("–"))
        roi.addWidget(self._roi_x_max)
        roi.addSpacing(12)
        roi.addWidget(QLabel("Y:"))
        self._roi_y_min = _make_roi_spin(); self._roi_y_min.setValue(-1.0)
        self._roi_y_max = _make_roi_spin(); self._roi_y_max.setValue(1.0)
        self._roi_y_min.valueChanged.connect(self._on_roi_changed)
        self._roi_y_max.valueChanged.connect(self._on_roi_changed)
        roi.addWidget(self._roi_y_min)
        roi.addWidget(QLabel("–"))
        roi.addWidget(self._roi_y_max)
        btn_auto = QPushButton("Auto")
        btn_auto.setMaximumWidth(60)
        btn_auto.clicked.connect(self._on_roi_auto)
        roi.addWidget(btn_auto)
        roi.addStretch()
        controls_layout.addLayout(roi)

        # --- Экшены ---
        actions = QHBoxLayout()
        btn_png = QPushButton("PNG")
        btn_png.setMaximumWidth(60)
        btn_png.clicked.connect(self._on_export_png)
        actions.addWidget(btn_png)
        btn_pv = QPushButton("To PlotViewer")
        btn_pv.setMaximumWidth(120)
        btn_pv.clicked.connect(self._on_export_plot_viewer)
        actions.addWidget(btn_pv)
        btn_reset = QPushButton("Reset view")
        btn_reset.setMaximumWidth(100)
        btn_reset.clicked.connect(self._reset_view)
        actions.addWidget(btn_reset)
        actions.addStretch()
        controls_layout.addLayout(actions)

        root.addWidget(self._controls)

        # --- График ---
        self._plot = pg.PlotWidget()
        self._plot.setBackground("#1e1e1e")
        self._plot.showGrid(x=True, y=True, alpha=0.3)
        self._plot.setLabel("bottom", self.X_LABEL)

        self._y_axis = _TransformAxis(orientation="left")
        self._plot.plotItem.setAxisItems({"left": self._y_axis})
        self._plot.setLabel("left", self.Y_LABEL)

        self._plot.addLegend(offset=(-10, 10))
        self._legend_filter = None
        self._install_legend_bounds()
        root.addWidget(self._plot, stretch=1)

        self._crosshair = Crosshair(self._plot)
        self._crosshair.set_enabled(self._cb["cross"].isChecked())
        self._cb["cross"].toggled.connect(self._crosshair.set_enabled)
        self._plot.scene().sigMouseMoved.connect(self._on_mouse_moved)

        vb = self._plot.getViewBox()
        vb.sigRangeChanged.connect(self._on_plot_range_changed)

        self._apply_scale(self.DEFAULT_SCALE)

    # ------------------------------------------------------------------

    def _on_toggle_controls(self):
        visible = self._btn_toggle.isChecked()
        self._controls.setVisible(visible)
        self._btn_toggle.setArrowType(
            Qt.ArrowType.DownArrow if visible else Qt.ArrowType.RightArrow
        )

    # ------------------------------------------------------------------
    # Хуки
    # ------------------------------------------------------------------

    def _build_layer_checkboxes(self, layout: QHBoxLayout) -> None:
        pass

    def _draw_all(self) -> None:
        raise NotImplementedError(
            f"{type(self).__name__} должен реализовать _draw_all()"
        )

    # ------------------------------------------------------------------

    def clear_data(self) -> None:
        self._plot.clear()
        self._crosshair.recreate()
        self._crosshair.clear_points()
        self._tasks = []
        self._raw_series = []
        self._exported_lines = []
        self._manual_roi = False
        self._header.setText(f"{self.DEFAULT_TITLE} — нет данных")

    def show_data(self, data) -> None:
        self.show_data_list([data], [])

    def show_data_list(self, tasks, raw_series=None) -> None:
        self._tasks = list(tasks)
        self._raw_series = list(raw_series) if raw_series else []
        self._redraw()

    def set_scale_options(self, options: list[str], label: str = "Y-scale:") -> None:
        try:
            self._scale.blockSignals(True)
            self._scale.clear()
            self._scale.addItems(options)
            if options:
                self._scale.setCurrentText(options[0])
            self._scale.blockSignals(False)
            self._scale_label.setText(label)
        except Exception:
            self._log.exception("set_scale_options failed")

    # ------------------------------------------------------------------

    def _apply_scale(self, scale: str) -> None:
        try:
            if scale == "log":
                self._y_axis.set_inverse(lambda v: 10.0 ** v)
                self._y_axis.set_custom_formatter(None)
                self._plot.setLogMode(x=False, y=True)
            elif scale == "symlog":
                lin = self.SYMLOG_LINTHRESH
                self._y_axis.set_inverse(lambda v: _from_symlog(v, lin))
                self._y_axis.set_custom_formatter(None)
                self._plot.setLogMode(x=False, y=False)
            else:
                self._y_axis.set_inverse(None)
                self._y_axis.set_custom_formatter(None)
                self._plot.setLogMode(x=False, y=False)
        except Exception:
            self._log.exception("_apply_scale failed")

        self._redraw()
        if self._manual_roi:
            self._apply_roi_from_spinboxes()
        else:
            self._plot.enableAutoRange()
            self._plot.autoRange()

    def _transform_y_for_plot(self, ys: list) -> list:
        scale = self._scale.currentText()
        if scale == "log":
            out = []
            for y in ys:
                if y is None or (isinstance(y, float) and not math.isfinite(y)):
                    out.append(y)
                else:
                    out.append(abs(y))
            return out
        if scale == "symlog":
            lin = self.SYMLOG_LINTHRESH
            return [_to_symlog(y, lin) for y in ys]
        return list(ys)

    def _from_display_y(self, y_disp: float) -> float:
        scale = self._scale.currentText()
        if scale == "log":
            try:
                return 10.0 ** y_disp
            except OverflowError:
                return float("inf") if y_disp > 0 else 0.0
        if scale == "symlog":
            return _from_symlog(y_disp, self.SYMLOG_LINTHRESH)
        return y_disp

    def _to_display_y(self, y_real: float) -> float:
        scale = self._scale.currentText()
        if scale == "log":
            return math.log10(y_real) if y_real > 0 else float("nan")
        if scale == "symlog":
            return _to_symlog(y_real, self.SYMLOG_LINTHRESH)
        return y_real

    # ------------------------------------------------------------------
    # ROI
    # ------------------------------------------------------------------

    def _on_roi_changed(self) -> None:
        if self._suppress_roi:
            return
        self._manual_roi = True
        self._apply_roi_from_spinboxes()

    def _apply_roi_from_spinboxes(self) -> None:
        x_min = self._roi_x_min.value()
        x_max = self._roi_x_max.value()
        y_min = self._roi_y_min.value()
        y_max = self._roi_y_max.value()
        if x_max <= x_min or y_max <= y_min:
            return
        y_disp_min = self._to_display_y(y_min)
        y_disp_max = self._to_display_y(y_max)
        if not (math.isfinite(y_disp_min) and math.isfinite(y_disp_max)):
            return
        self._suppress_roi = True
        try:
            self._plot.setXRange(x_min, x_max, padding=0.0)
            self._plot.setYRange(y_disp_min, y_disp_max, padding=0.0)
        finally:
            self._suppress_roi = False

    def _on_roi_auto(self) -> None:
        self._manual_roi = False
        self._plot.enableAutoRange()
        self._plot.autoRange()

    def _on_plot_range_changed(self, *_):
        if self._suppress_roi:
            return
        try:
            vb = self._plot.getViewBox()
            xr = vb.viewRange()[0]
            yr = vb.viewRange()[1]
        except Exception:
            return
        try:
            y_min_real = self._from_display_y(yr[0])
            y_max_real = self._from_display_y(yr[1])
        except Exception:
            return
        if not (math.isfinite(y_min_real) and math.isfinite(y_max_real)):
            return
        self._suppress_roi = True
        try:
            self._roi_x_min.setValue(xr[0])
            self._roi_x_max.setValue(xr[1])
            self._roi_y_min.setValue(y_min_real)
            self._roi_y_max.setValue(y_max_real)
        finally:
            self._suppress_roi = False

    # ------------------------------------------------------------------
    # Вид
    # ------------------------------------------------------------------

    def _reset_view(self) -> None:
        self._manual_roi = False
        self._plot.enableAutoRange()
        self._plot.autoRange()
        self._recreate_legend()

    def _install_legend_bounds(self) -> None:
        try:
            legend = self._plot.plotItem.legend
            if legend is None:
                return
            self._legend_filter = _LegendSnapFilter(self._plot, legend)
            self._plot.scene().installEventFilter(self._legend_filter)
        except Exception:
            self._legend_filter = None

    def _recreate_legend(self) -> None:
        try:
            plot_item = self._plot.plotItem
            old = plot_item.legend
            if old is not None:
                try:
                    old.setParentItem(None)
                    if old.scene() is not None:
                        old.scene().removeItem(old)
                except Exception:
                    pass
                plot_item.legend = None
            self._plot.addLegend(offset=(-10, 10))
            self._install_legend_bounds()
        except Exception:
            self._log.exception("не удалось пересоздать легенду")

    def _on_mouse_moved(self, pos) -> None:
        snap = self._is_checked("snap")
        self._crosshair.on_mouse_moved(
            pos,
            from_display=self._from_display_y,
            to_display=self._to_display_y,
            snap=snap,
        )

    def _redraw(self) -> None:
        try:
            self._plot.clear()
            self._recreate_legend()
            self._crosshair.recreate()
            self._crosshair.clear_points()
            self._exported_lines = []
            self._draw_all()
        except Exception as e:
            self._log.exception("[%s._redraw] ошибка", self.DEFAULT_TITLE)
            self._header.setText(f"Ошибка отрисовки: {e}")

    # ------------------------------------------------------------------
    # Экспорт
    # ------------------------------------------------------------------

    def _on_export_png(self) -> None:
        default_name = f"{self.DEFAULT_TITLE.replace(' ', '_')}.png"
        path, _ = QFileDialog.getSaveFileName(
            self, "Экспорт графика в PNG", default_name, "PNG (*.png)",
        )
        if not path:
            return
        try:
            pix = self._plot.grab()
            ok = pix.save(path, "PNG")
            self._header.setText(
                f"Сохранено: {path}" if ok else "PNG: не удалось"
            )
        except Exception as e:
            self._log.exception("PNG export failed")
            self._header.setText(f"PNG export failed: {e}")

    def _on_export_plot_viewer(self) -> None:
        scale = self._scale.currentText()
        if scale not in ("linear", "symlog"):
            QMessageBox.information(
                self, "Plot Viewer",
                "Plot Viewer поддерживает Linear и Symlog.\n\n"
                "Переключи Y-scale на Symlog.",
            )
            return
        data = build_plot_viewer_data(
            scale=scale,
            symlog_linthresh=self.SYMLOG_LINTHRESH,
            lines=self._exported_lines,
        )
        n_lines = len(data["lines"])
        if n_lines == 0:
            QMessageBox.information(
                self, "Нечего экспортировать", "Нет видимых линий.",
            )
            return
        default_name = f"{self.DEFAULT_TITLE.replace(' ', '_')}_plot.json"
        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить для Plot Viewer",
            default_name, "JSON (*.json)",
        )
        if not path:
            return
        out_path = Path(path)
        try:
            save_to_json(data, out_path)
        except Exception as e:
            self._log.exception("save plot_viewer JSON failed")
            QMessageBox.critical(self, "Ошибка", f"{e}")
            return
        viewer = find_plot_viewer()
        if viewer is None:
            QMessageBox.information(
                self, "Plot Viewer",
                f"Сохранено: {out_path}\nОткрой вручную:\n"
                f"  python plot_viewer.py {out_path.name}",
            )
            return
        if launch_plot_viewer(out_path):
            self._header.setText(f"Plot Viewer: {n_lines} линий")
        else:
            self._header.setText(f"Сохранено: {out_path.name}")

    # ------------------------------------------------------------------
    # Хелперы отрисовки
    # ------------------------------------------------------------------

    def _add_line(
        self,
        label: str,
        xs: list,
        ys: list,
        color: str,
        width: int = 2,
        style: Qt.PenStyle = Qt.PenStyle.SolidLine,
        snap: bool = True,
    ):
        if not xs:
            return None
        ys_plot = self._transform_y_for_plot(ys)
        item = self._plot.plot(
            xs, ys_plot,
            pen=pg.mkPen(color, width=width, style=style),
            name=label,
        )
        if snap:
            for x, y_raw in zip(xs, ys):
                if y_raw is None:
                    continue
                try:
                    if y_raw == y_raw and math.isfinite(y_raw):
                        self._crosshair.add_point(x, y_raw, item)
                except TypeError:
                    continue
        self._exported_lines.append({
            "xs": list(xs),
            "ys_real": list(ys),
            "ys_plot": list(ys_plot),
            "label": label,
            "color": color,
            "width": int(width),
            "style": style,
            "line_item": item,
        })
        return item

    def _add_marker(
        self, x: float, y: float, color: str,
        symbol: str = "o", size: int = 12, tooltip: str | None = None,
    ):
        y_plot = self._transform_y_for_plot([y])[0]
        item = pg.ScatterPlotItem(
            [x], [y_plot], symbol=symbol, size=size,
            brush=pg.mkBrush(color), pen=pg.mkPen(color, width=1),
        )
        if tooltip:
            item.setToolTip(tooltip)
        self._plot.addItem(item)
        if y == y and math.isfinite(y):
            self._crosshair.add_point(x, y, item)
        return item

    def _add_hline(
        self, label: str, y: float, x_min: float, x_max: float,
        color: str = "#6fbf73",
        style: Qt.PenStyle = Qt.PenStyle.DashLine, width: int = 1,
    ) -> None:
        y_plot = self._transform_y_for_plot([y])[0]
        item = self._plot.plot(
            [x_min, x_max], [y_plot, y_plot],
            pen=pg.mkPen(color, width=width, style=style),
            name=label,
        )
        self._exported_lines.append({
            "xs": [float(x_min), float(x_max)],
            "ys_real": [float(y), float(y)],
            "ys_plot": [float(y_plot), float(y_plot)],
            "label": label,
            "color": color,
            "width": int(width),
            "style": style,
            "line_item": item,
        })

    def _add_checkbox(
        self, layout: QHBoxLayout, key: str, label: str,
        default: bool = True, tooltip: str = "",
    ) -> QCheckBox:
        cb = QCheckBox(label)
        cb.setChecked(default)
        cb.toggled.connect(lambda _: self._redraw())
        if tooltip:
            cb.setToolTip(tooltip)
        layout.addWidget(cb)
        self._cb[key] = cb
        return cb

    def _is_checked(self, key: str) -> bool:
        cb = self._cb.get(key)
        return bool(cb and cb.isChecked())


def _make_roi_spin() -> QDoubleSpinBox:
    sp = QDoubleSpinBox()
    sp.setRange(-1e308, 1e308)
    sp.setDecimals(6)
    sp.setKeyboardTracking(False)
    sp.setGroupSeparatorShown(False)
    sp.setMinimumWidth(130)
    sp.setMaximumWidth(180)
    return sp


class _LegendSnapFilter(QObject):
    def __init__(self, plot, legend):
        super().__init__()
        self._plot = plot
        self._legend = legend

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Type.GraphicsSceneMouseRelease:
            self._snap_if_needed()
        return False

    def _snap_if_needed(self) -> None:
        try:
            lr = self._legend.sceneBoundingRect()
            pr = self._plot.sceneBoundingRect()
            inter = pr.intersected(lr)
            total = lr.width() * lr.height()
            if total <= 0:
                return
            if (inter.width() * inter.height()) / total < 0.01:
                self._legend.anchor(
                    itemPos=(0, 0), parentPos=(0, 0), offset=(-10, 10),
                )
        except Exception:
            pass