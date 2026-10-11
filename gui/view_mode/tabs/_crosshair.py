"""
Универсальный crosshair с snap для Overview и Residual.

Snap — по 2D-расстоянию в display-пространстве. Точки в _snap_points
хранятся в РЕАЛЬНЫХ значениях, преобразование в display делается
через to_display (переданный из BasePlotTab).
"""

from __future__ import annotations
import math
from typing import Callable

import pyqtgraph as pg
from PyQt6.QtCore import Qt


#: Радиус притяжения в display-единицах.
SNAP_RADIUS = 20.0


class Crosshair:
    """Перекрестие с подписью и snap к ближайшей точке."""

    def __init__(self, plot: pg.PlotWidget):
        self._plot = plot
        self._enabled = True
        #: Список (x, y_real, item).
        self._snap_points: list[tuple[float, float, object]] = []

        self._vline = pg.InfiniteLine(
            angle=90, movable=False,
            pen=pg.mkPen("#f0c674", width=1, style=Qt.PenStyle.DotLine),
        )
        self._hline = pg.InfiniteLine(
            angle=0, movable=False,
            pen=pg.mkPen("#f0c674", width=1, style=Qt.PenStyle.DotLine),
        )
        self._label = pg.TextItem(color="#f0c674", anchor=(0, 1))
        plot.addItem(self._vline, ignoreBounds=True)
        plot.addItem(self._hline, ignoreBounds=True)
        plot.addItem(self._label, ignoreBounds=True)

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, on: bool):
        self._enabled = on
        self._vline.setVisible(on)
        self._hline.setVisible(on)
        self._label.setVisible(on)

    def clear_points(self):
        self._snap_points = []

    def add_point(self, x: float, y_real: float, item):
        """
        Регистрирует точку для snap.

        y_real — РЕАЛЬНОЕ значение (не display). Преобразование
        в display делается в on_mouse_moved через to_display.
        """
        self._snap_points.append((x, y_real, item))

    def recreate(self):
        """Пересоздаёт элементы после plot.clear()."""
        self._vline = pg.InfiniteLine(
            angle=90, movable=False,
            pen=pg.mkPen("#f0c674", width=1, style=Qt.PenStyle.DotLine),
        )
        self._hline = pg.InfiniteLine(
            angle=0, movable=False,
            pen=pg.mkPen("#f0c674", width=1, style=Qt.PenStyle.DotLine),
        )
        self._label = pg.TextItem(color="#f0c674", anchor=(0, 1))
        self._plot.addItem(self._vline, ignoreBounds=True)
        self._plot.addItem(self._hline, ignoreBounds=True)
        self._plot.addItem(self._label, ignoreBounds=True)
        self.set_enabled(self._enabled)

    def on_mouse_moved(
        self,
        pos,
        from_display: Callable[[float], float],
        to_display: Callable[[float], float],
        snap: bool,
    ):
        """
        Обновляет crosshair по позиции мыши.

        snap — по 2D-расстоянию (dx² + dy²) в display-пространстве.
        """
        if not self._enabled:
            return
        try:
            vb = self._plot.getViewBox()
            if not self._plot.sceneBoundingRect().contains(pos):
                return

            mp = vb.mapSceneToView(pos)
            x = mp.x()
            y_disp = mp.y()

            item_label = ""
            if snap and self._snap_points:
                best = None
                best_dist_sq = float("inf")
                radius_sq = SNAP_RADIUS * SNAP_RADIUS
                for px, py_real, item in self._snap_points:
                    # Видимость (PlotDataItem может быть скрыт).
                    try:
                        if not item.isVisible():
                            continue
                    except Exception:
                        pass
                    # py_real → display (единое пространство).
                    try:
                        py_disp = to_display(py_real)
                    except Exception:
                        continue
                    if not math.isfinite(py_disp):
                        continue
                    dx = px - x
                    dy = py_disp - y_disp
                    dist_sq = dx * dx + dy * dy
                    if dist_sq < best_dist_sq:
                        best_dist_sq = dist_sq
                        best = (px, py_real, item, py_disp)

                if best is not None and best_dist_sq < radius_sq:
                    x = best[0]
                    y_disp = best[3]
                    try:
                        item_label = best[2].name() or ""
                    except Exception:
                        item_label = ""

            y_real = from_display(y_disp)

            self._vline.setPos(x)
            self._hline.setPos(y_disp)
            prefix = f"[{item_label}] " if item_label else ""
            self._label.setText(f"{prefix}n={x:.0f}, y={y_real:.6g}")
            self._label.setPos(x, y_disp)
        except Exception:
            pass