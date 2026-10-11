"""
Smoke-тесты Workspace: создание, сигналы, кнопки — без открытия окна.
"""

from __future__ import annotations
import json

import pytest


@pytest.fixture
def workspace(qapp, no_messagebox):
    """Свежий Workspace с отключёнными диалогами."""
    from gui.workspace import Workspace
    from gui.workspace.state import AppState
    ws = Workspace(AppState())
    yield ws
    ws.window.close()


def test_workspace_instantiates(workspace):
    """Workspace создаётся, все кнопки на месте."""
    for attr in (
        "_btn_open", "_btn_save", "_btn_save_as", "_btn_validate",
        "_btn_plan", "_btn_visualise", "_btn_run", "_btn_analysis",
        "_btn_clear_cache",
    ):
        assert hasattr(workspace, attr), f"нет кнопки {attr}"


def test_right_panel_has_five_tabs(workspace):
    """Правая панель — 5 вкладок: JSON, Overview, Residual, Tables, Analysis."""
    rp = workspace._right
    assert rp.count() == 5
    titles = [rp.tabText(i) for i in range(rp.count())]
    assert "JSON" in titles
    assert "Overview" in titles
    assert "Analysis" in titles


def test_analysis_tab_uses_state(workspace):
    """AnalysisTab получает тот же AppState, что и Workspace."""
    assert workspace._right.analysis._state is workspace.state


def test_clear_cache_button(workspace):
    """Кнопка Clear cache не падает."""
    workspace._btn_clear_cache.click()
    assert workspace._status.text().startswith("Кэш очищен")


def test_json_tab_roundtrip(workspace):
    """Правка JSON обновляет state.config_dict."""
    cfg = {
        "run_id": "t", "output": "out",
        "precision": {"backend": "mpmath", "dps": 30},
        "series": [{"type": "zeta", "params": {"s": 3}}],
        "noise": [],
        "accelerators": [{"type": "aitken_delta2", "params": {}}],
    }
    workspace._on_json_edited(cfg)
    assert workspace.state.config_dict == cfg


def test_validate_button_works(workspace, tmp_path):
    """Кнопка Validate не падает на валидном конфиге."""
    workspace._on_json_edited({
        "run_id": "t", "output": "out",
        "precision": {"backend": "mpmath", "dps": 30},
        "series": [{"type": "zeta", "params": {"s": 3}}],
        "noise": [],
        "accelerators": [{"type": "aitken_delta2", "params": {}}],
    })
    workspace._btn_validate.click()


def test_plan_button_works(workspace):
    """Кнопка Plan не падает."""
    workspace._on_json_edited({
        "run_id": "t", "output": "out",
        "precision": {"backend": "mpmath", "dps": 30},
        "series": [{"type": "zeta", "params": {"s": 3}}],
        "noise": [],
        "accelerators": [{"type": "aitken_delta2", "params": {}}],
    })
    workspace._btn_plan.click()


def test_analysis_toggle(workspace):
    """Переключение в Analysis и обратно не падает."""
    workspace._btn_analysis.click()
    assert workspace.state.mode == "analysis"
    workspace._btn_analysis.click()
    assert workspace.state.mode == "edit"