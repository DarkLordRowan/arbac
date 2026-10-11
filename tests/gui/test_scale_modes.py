"""
Тесты переключения Y-scale: linear / log / symlog.
"""

from __future__ import annotations
import math
import pytest


@pytest.fixture
def overview(qapp):
    from gui.view_mode.tabs import OverviewTab
    tab = OverviewTab()
    yield tab
    tab.deleteLater()


def test_scale_options(overview):
    items = [overview._scale.itemText(i)
             for i in range(overview._scale.count())]
    assert "linear" in items
    assert "log" in items
    assert "symlog" in items


def test_scale_switch_does_not_crash(overview):
    for s in ("linear", "log", "symlog", "linear"):
        overview._scale.setCurrentText(s)


def test_log_mode_takes_abs(overview):
    """
    В log-режиме кривые с отрицательными y не пропадают:
    transform_y берёт модуль.
    """
    overview._scale.setCurrentText("log")
    ys = [-1.0, -10.0, 0.5]
    out = overview._transform_y_for_plot(ys)
    assert out[0] == 1.0
    assert out[1] == 10.0
    assert out[2] == 0.5


def test_symlog_transforms(overview):
    """symlog сжимает большие значения и оставляет маленькие."""
    overview._scale.setCurrentText("symlog")
    ys = [0.0, 1e-3, 1.0, 1e3]
    out = overview._transform_y_for_plot(ys)
    # 0 → 0
    assert out[0] == 0.0
    # Маленькое не сильно меняется
    assert abs(out[1]) < 1.0
    # Большое сжимается, но растёт
    assert out[2] < out[3]


def test_linear_transforms_identity(overview):
    overview._scale.setCurrentText("linear")
    ys = [-1.0, 0.0, 1.0, 1e-30]
    out = overview._transform_y_for_plot(ys)
    assert out == ys


def test_axis_inverse_log(overview):
    """axis.inverse в log = 10^y."""
    overview._scale.setCurrentText("log")
    # Проверим через from_display
    y_real = overview._from_display_y(2.0)   # display 2.0 → 100
    assert abs(y_real - 100.0) < 1e-6


def test_axis_inverse_symlog_roundtrip(overview):
    """symlog: to_display ∘ from_display = identity на типичных значениях."""
    overview._scale.setCurrentText("symlog")
    for v in (1e-6, -1e-4, 0.1, 1.0, 100.0):
        display = overview._to_display_y(v)
        back = overview._from_display_y(display)
        assert abs(back - v) < abs(v) * 1e-6, f"{v} → {back}"

def test_residual_symlog10_crosshair_roundtrip(qapp):
    """
    В Residual roundtrip: to_display → from_display даёт исходное.
    Проверяет, что crosshair покажет реальные значения.
    """
    from gui.view_mode.tabs import ResidualTab
    tab = ResidualTab()
    try:
        tab._scale.setCurrentText("symlog10")
        for v in (1.0, 1e-5, 1e-30, -1e-10):
            display = tab._to_display_y(v)
            back = tab._from_display_y(display)
            assert abs(back - v) < abs(v) * 1e-6, f"{v} → {back}"
    finally:
        tab.deleteLater()        

def test_residual_symlog10_display_roundtrip(qapp):
    """См. выше: symlog10 (to_display ∘ from_display) = identity."""
    from gui.view_mode.tabs import ResidualTab
    tab = ResidualTab()
    try:
        tab._scale.setCurrentText("symlog10")
        for v in (1.0, 1e-5, 1e-30, -1e-10):
            display = tab._to_display_y(v)
            back = tab._from_display_y(display)
            assert abs(back - v) < abs(v) * 1e-6, f"{v} → {back}"
    finally:
        tab.deleteLater()

def test_residual_symlog10_roundtrip_real(qapp):
    """real → display → real возвращает исходное (для crosshair)."""
    from gui.view_mode.tabs import ResidualTab
    tab = ResidualTab()
    try:
        tab._scale.setCurrentText("symlog10")
        for v in (1.0, 1e-5, 1e-30, -1e-10):
            disp = tab._to_display_y(v)
            back = tab._from_display_y(disp)
            assert abs(back - v) < abs(v) * 1e-6, f"{v} → {back}"
    finally:
        tab.deleteLater()


def test_residual_symlog10_transform_applies_symlog(qapp):
    """
    _transform_y_for_plot (для отрисовки) действительно применяет
    symlog: real diff → symlog-значение.
    """
    from gui.view_mode.tabs import ResidualTab
    tab = ResidualTab()
    try:
        tab._scale.setCurrentText("symlog10")
        ys_real = [1.0, 1e-30]
        ys_plot = tab._transform_y_for_plot(ys_real)
        # symlog(1.0, 1e-35) ≈ 35
        assert ys_plot[0] > 30, f"ys_plot[0]={ys_plot[0]}"
        # symlog(1e-30, 1e-35) ≈ 5
        assert 4 < ys_plot[1] < 6, f"ys_plot[1]={ys_plot[1]}"
    finally:
        tab.deleteLater()