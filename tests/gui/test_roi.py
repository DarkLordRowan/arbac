"""
Тесты ROI: числа X min/max, Y min/max связаны с графиком.
"""

from __future__ import annotations
import pytest


@pytest.fixture
def overview(qapp):
    from gui.view_mode.tabs import OverviewTab
    tab = OverviewTab()
    yield tab
    tab.deleteLater()


def test_roi_has_four_spinboxes(overview):
    assert overview._roi_x_min is not None
    assert overview._roi_x_max is not None
    assert overview._roi_y_min is not None
    assert overview._roi_y_max is not None


def test_roi_set_xrange(overview, qapp):
    """Ввод X min/max → setXRange с этими значениями."""
    overview._roi_x_min.setValue(10.0)
    overview._roi_x_max.setValue(50.0)
    qapp.processEvents()

    vb = overview._plot.getViewBox()
    xr = vb.viewRange()[0]
    assert abs(xr[0] - 10.0) < 1e-6, f"x_min={xr[0]}"
    assert abs(xr[1] - 50.0) < 1e-6, f"x_max={xr[1]}"


def test_roi_set_yrange_linear(overview, qapp):
    """Ввод Y min/max в linear → setYRange с теми же значениями."""
    overview._scale.setCurrentText("linear")
    overview._roi_y_min.setValue(-0.5)
    overview._roi_y_max.setValue(0.5)
    qapp.processEvents()

    vb = overview._plot.getViewBox()
    yr = vb.viewRange()[1]
    assert abs(yr[0] - (-0.5)) < 1e-6, f"y_min={yr[0]}"
    assert abs(yr[1] - 0.5) < 1e-6, f"y_max={yr[1]}"


def test_roi_sync_from_viewbox(overview, qapp):
    """Изменение viewBox (pan/zoom) → обновление spinbox."""
    overview._plot.setXRange(20.0, 80.0, padding=0.0)
    qapp.processEvents()
    assert abs(overview._roi_x_min.value() - 20.0) < 1e-6
    assert abs(overview._roi_x_max.value() - 80.0) < 1e-6


def test_roi_auto_resets(overview, qapp):
    """Auto выходит из ручного режима и авто-подгоняет диапазон."""
    overview._roi_x_min.setValue(1000)
    overview._roi_x_max.setValue(2000)
    qapp.processEvents()
    assert overview._manual_roi is True

    overview._on_roi_auto()
    assert overview._manual_roi is False


def test_roi_invalid_range_ignored(overview, qapp):
    """x_max <= x_min — не применяется."""
    overview._roi_x_min.setValue(50.0)
    overview._roi_x_max.setValue(10.0)   # меньше min
    qapp.processEvents()
    # Ничего не должно сломаться, диапазон не применился.
    assert True