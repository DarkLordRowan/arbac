"""
Тесты логирования по сессиям.
"""

from __future__ import annotations
import pytest


def _reset_log_module(monkeypatch, logs_root):
    """Сбрасывает глобальное состояние log.py и указывает новый root."""
    from gui.common import log as L
    monkeypatch.setattr(L, "LOGS_ROOT", logs_root)
    monkeypatch.setattr(L, "_configured", False)
    monkeypatch.setattr(L, "_session_dir", None)
    return L


def test_setup_creates_session_dir(tmp_path, monkeypatch):
    """setup() создаёт logs/session_.../gui.log."""
    L = _reset_log_module(monkeypatch, tmp_path / "logs")
    session = L.setup()
    assert session.exists()
    assert session.parent.name == "logs"
    assert session.name.startswith("session_")
    assert (session / "gui.log").exists()


def test_get_logger_writes_to_session_file(tmp_path, monkeypatch):
    """get_logger().info() попадает в gui.log этой сессии."""
    L = _reset_log_module(monkeypatch, tmp_path / "logs")
    session = L.setup()
    log = L.get_logger("test_module")
    log.info("hello world")
    # Дадим FileHandler'у сбросить буфер.
    for h in log.parent.handlers:
        h.flush()
    content = (session / "gui.log").read_text(encoding="utf-8")
    assert "hello world" in content
    assert "test_module" in content


def test_get_session_dir_returns_current(tmp_path, monkeypatch):
    """get_session_dir() возвращает ту же папку, что вернул setup()."""
    L = _reset_log_module(monkeypatch, tmp_path / "logs")
    session = L.setup()
    assert L.get_session_dir() == session


def test_cleanup_removes_old_sessions(tmp_path, monkeypatch):
    """_cleanup_old_sessions оставляет только MAX_SESSIONS."""
    L = _reset_log_module(monkeypatch, tmp_path / "logs")
    logs_root = tmp_path / "logs"
    logs_root.mkdir()
    for i in range(25):
        d = logs_root / f"session_2026-01-01_00-00-{i:02d}"
        d.mkdir()
        (d / "gui.log").write_text("x", encoding="utf-8")

    monkeypatch.setattr(L, "MAX_SESSIONS", 20)
    n = L._cleanup_old_sessions()
    assert n == 5

    remaining = sorted(
        p.name for p in logs_root.iterdir() if p.is_dir()
    )
    assert len(remaining) == 20
    # Удалены самые ранние.
    assert "session_2026-01-01_00-00-00" not in remaining
    assert "session_2026-01-01_00-00-24" in remaining


def test_two_setups_dont_duplicate_handlers(tmp_path, monkeypatch):
    """Повторный setup не плодит handler'ы (иначе лог задваивается)."""
    L = _reset_log_module(monkeypatch, tmp_path / "logs")
    L.setup()
    import logging
    n1 = len(logging.getLogger("arbacc.gui").handlers)
    # Форсируем повторный setup.
    monkeypatch.setattr(L, "_configured", False)
    L.setup()
    n2 = len(logging.getLogger("arbacc.gui").handlers)
    assert n2 == n1, f"handlers дублируются: {n1} → {n2}"