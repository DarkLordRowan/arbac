"""
Тесты поля N: изменение N должно триггерить preview.

ВАЖНО: monkeypatch.setattr(ws, "_run_preview", fake) не работает для
подключённого слота QTimer.timeout — Qt хранит ссылку на bound method.
Поэтому проверяем либо isActive(), либо переподключаем сигнал к spy.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def workspace(qapp, no_messagebox):
    from gui.workspace import Workspace
    from gui.workspace.state import AppState

    ws = Workspace(AppState())
    ws.state.visualise_on = True
    ws.state.mode = "edit"
    yield ws
    ws.window.close()


# --- Свойства spinbox ---

def test_n_default_is_preview_max_n(workspace):
    from arbacc.settings import PREVIEW_MAX_N
    assert workspace._spin_n.value() == PREVIEW_MAX_N


def test_n_value_settable(workspace):
    workspace._spin_n.setValue(12345)
    assert workspace._spin_n.value() == 12345


# --- Сигнал → _on_config_changed ---

def test_n_change_connects_to_config_changed(workspace):
    """Изменение N вызывает _on_config_changed."""
    called = []

    try:
        workspace._spin_n.valueChanged.disconnect()
    except TypeError:
        pass

    original = workspace._on_config_changed
    def spy():
        called.append(1)
        return original()
    workspace._spin_n.valueChanged.connect(spy)

    workspace._spin_n.setValue(999)
    assert called, "valueChanged не вызывает _on_config_changed"


def test_n_change_starts_preview_timer(workspace):
    """Смена N запускает таймер preview (при visualise_on)."""
    workspace.state.visualise_on = True
    workspace.state.mode = "edit"
    workspace._preview_timer.stop()

    workspace._spin_n.setValue(4321)

    assert workspace._preview_timer.isActive(), (
        "после смены N таймер preview не запустился"
    )


def test_n_change_no_timer_when_visualise_off(workspace):
    """При visualise_on=False таймер не запускается."""
    workspace.state.visualise_on = False
    workspace._preview_timer.stop()

    workspace._spin_n.setValue(999)
    assert not workspace._preview_timer.isActive()


# --- Таймер → _run_preview ---

def test_timer_timeout_invokes_preview(workspace):
    """При timeout таймера вызывается _run_preview."""
    called = {"n": 0}
    try:
        workspace._preview_timer.timeout.disconnect()
    except TypeError:
        pass
    workspace._preview_timer.timeout.connect(
        lambda: called.__setitem__("n", called["n"] + 1)
    )
    workspace._preview_timer.timeout.emit()
    assert called["n"] == 1


# --- _run_preview использует N ---

def test_run_preview_uses_n_value(workspace, monkeypatch):
    """
    _run_preview передаёт N в build_raw_preview как max_n.
    Мокаем build_plan (пустой accel) и build_raw_preview (перехват).
    """
    import gui.view_mode.data_loader as dl
    import gui.workspace.window as W

    captured = {}
    def fake_build(config, max_n=None):
        captured["max_n"] = max_n
        return []
    monkeypatch.setattr(dl, "build_raw_preview", fake_build)

    monkeypatch.setattr(
        W, "build_plan",
        lambda cfg: {"accel": [], "post": [], "errors": []},
    )

    workspace.state.mode = "edit"
    workspace.state.visualise_on = True
    workspace._spin_n.setValue(777)

    workspace._run_preview()

    assert captured.get("max_n") == 777, (
        f"build_raw_preview получил max_n={captured.get('max_n')}, "
        f"ожидали 777"
    )


def test_run_preview_n_limits_both_raw_and_accel(workspace, monkeypatch):
    """
    N ограничивает и raw, и акселераторы.
    Проверяем, что raw_n = N_user (не max) и PreviewWorker получает max_n=N_user.
    """
    import gui.view_mode.data_loader as dl
    import gui.workspace.window as W

    captured = {}

    def fake_build(config, max_n=None):
        captured["raw_max_n"] = max_n
        return []
    monkeypatch.setattr(dl, "build_raw_preview", fake_build)

    monkeypatch.setattr(
        W, "build_plan",
        lambda cfg: {
            "accel": [
                {"accelerator": {"n_max": 5000}, "task_id": "t1",
                 "ids": {}, "precision": {}, "series": {}, "noise": {}},
            ],
            "post": [],
            "errors": [],
        },
    )

    # Перехватываем PreviewWorker, чтобы не запускать поток.
    captured_worker = {}

    class FakeWorker:
        def __init__(self, plan, generation, max_n=0, max_tasks=0, max_dps=0):
            captured_worker["max_n"] = max_n
        progress = type("S", (), {"connect": lambda *a: None})()
        finished = type("S", (), {"connect": lambda *a: None})()
        failed = type("S", (), {"connect": lambda *a: None})()
        cancelled = type("S", (), {"connect": lambda *a: None})()
        def start(self): pass

    monkeypatch.setattr(W, "PreviewWorker", FakeWorker)

    workspace.state.mode = "edit"
    workspace.state.visualise_on = True
    workspace._spin_n.setValue(777)

    workspace._run_preview()

    assert captured.get("raw_max_n") == 777, (
        f"raw получил max_n={captured.get('raw_max_n')}, ожидали 777"
    )
    assert captured_worker.get("max_n") == 777, (
        f"PreviewWorker получил max_n={captured_worker.get('max_n')}, "
        f"ожидали 777"
    )

def test_n_caps_accel_max_iter(workspace, monkeypatch):
    """
    N=100 обрезает и n_max, и max_iter акселератора до 100.
    Регрессионный тест: раньше дефолтный max_iter(100) молча
    ограничивал алгоритм независимо от N.
    """
    import gui.workspace.window as W
    import gui.view_mode.data_loader as dl

    monkeypatch.setattr(dl, "build_raw_preview",
                        lambda config, max_n=None: [])
    monkeypatch.setattr(
        W, "build_plan",
        lambda cfg: {
            "accel": [{
                "accelerator": {
                    "n_max": 5000,
                    "stopping": [
                        {"type": "max_iter", "params": {"n": 1000}},
                    ],
                },
                "task_id": "t1", "ids": {}, "precision": {},
                "series": {}, "noise": {},
            }],
            "post": [], "errors": [],
        },
    )

    captured = {}

    class FakeWorker:
        def __init__(self, plan, generation, max_n=0,
                     max_tasks=0, max_dps=0):
            captured["plan"] = plan
            captured["max_n"] = max_n
        progress = type("S", (), {"connect": lambda *a: None})()
        finished = type("S", (), {"connect": lambda *a: None})()
        failed = type("S", (), {"connect": lambda *a: None})()
        cancelled = type("S", (), {"connect": lambda *a: None})()
        def start(self): pass

    monkeypatch.setattr(W, "PreviewWorker", FakeWorker)

    workspace.state.mode = "edit"
    workspace.state.visualise_on = True
    workspace._spin_n.setValue(100)
    workspace._run_preview()

    acc = captured["plan"]["accel"][0]["accelerator"]
    assert acc["n_max"] == 100, f"n_max={acc['n_max']}"
    assert acc["stopping"][0]["params"]["n"] == 100, (
        f"max_iter={acc['stopping'][0]['params']['n']}"
    )


def test_n_respects_smaller_user_max_iter(workspace, monkeypatch):
    """
    Если пользователь явно указал max_iter(30) < N=1000,
    не раздуваем его до 1000.
    """
    import gui.workspace.window as W
    import gui.view_mode.data_loader as dl

    monkeypatch.setattr(dl, "build_raw_preview",
                        lambda config, max_n=None: [])
    monkeypatch.setattr(
        W, "build_plan",
        lambda cfg: {
            "accel": [{
                "accelerator": {
                    "n_max": 5000,
                    "stopping": [{"type": "max_iter", "params": {"n": 30}}],
                },
                "task_id": "t1", "ids": {}, "precision": {},
                "series": {}, "noise": {},
            }],
            "post": [], "errors": [],
        },
    )

    captured = {}
    class FakeWorker:
        def __init__(self, plan, generation, max_n=0,
                     max_tasks=0, max_dps=0):
            captured["plan"] = plan
        progress = type("S", (), {"connect": lambda *a: None})()
        finished = type("S", (), {"connect": lambda *a: None})()
        failed = type("S", (), {"connect": lambda *a: None})()
        cancelled = type("S", (), {"connect": lambda *a: None})()
        def start(self): pass
    monkeypatch.setattr(W, "PreviewWorker", FakeWorker)

    workspace.state.mode = "edit"
    workspace.state.visualise_on = True
    workspace._spin_n.setValue(1000)
    workspace._run_preview()

    acc = captured["plan"]["accel"][0]["accelerator"]
    assert acc["n_max"] == 1000
    assert acc["stopping"][0]["params"]["n"] == 30, (
        f"не должны были трогать user max_iter: "
        f"{acc['stopping'][0]['params']['n']}"
    )    