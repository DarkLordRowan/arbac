"""
Тест легенды в BasePlotTab: после redraw она не должна пропадать.

Замечание по pyqtgraph:
    addLegend() вешает легенду через legend.setParentItem(self.vb),
    поэтому в plotItem.items она не лежит — там только items графика.
    Признак «легенда на сцене» — legend.scene() is not None.
"""

from __future__ import annotations
import pytest


@pytest.fixture
def overview(qapp):
    from gui.view_mode.tabs import OverviewTab
    tab = OverviewTab()
    yield tab
    tab.deleteLater()


def test_legend_exists_after_init(overview):
    """Легенда есть сразу после создания вкладки."""
    assert overview._plot.plotItem.legend is not None
    assert overview._plot.plotItem.legend.scene() is not None


def test_legend_survives_redraw(overview):
    """После redraw легенда снова привязана к сцене."""
    overview._redraw()
    legend = overview._plot.plotItem.legend
    assert legend is not None
    assert legend.scene() is not None, "легенда оторвана от сцены"


def test_legend_survives_multiple_redraws(overview):
    """5 redraw подряд — легенда не пропадает."""
    for i in range(5):
        overview._redraw()
        legend = overview._plot.plotItem.legend
        assert legend is not None, f"legend None после redraw #{i}"
        assert legend.scene() is not None, f"legend off-scene после redraw #{i}"


def test_legend_after_scale_switch(overview):
    """Переключение шкалы Y не теряет легенду."""
    overview._scale.setCurrentText("log")
    assert overview._plot.plotItem.legend is not None
    assert overview._plot.plotItem.legend.scene() is not None

    overview._scale.setCurrentText("linear")
    assert overview._plot.plotItem.legend is not None
    assert overview._plot.plotItem.legend.scene() is not None


def test_legend_picks_up_new_lines(overview, ctx):
    """
    Кривая, добавленная после redraw, попадает в легенду.

    Это ключевая проверка фикса: без _recreate_legend() после
    _plot.clear() новые кривые регистрировались в «оторванной» легенде.
    """
    # Один redraw — легенда пересоздана, пустая.
    overview._redraw()
    legend = overview._plot.plotItem.legend

    # Добавляем кривую.
    overview._add_line(
        label="test_curve",
        xs=[0, 1, 2],
        ys=[0.0, 0.5, 1.0],
        color="#4a90e2",
    )

    # В легенде теперь должна быть одна запись.
    assert len(legend.items) == 1, (
        f"после add_line в легенде {len(legend.items)} записей"
    )