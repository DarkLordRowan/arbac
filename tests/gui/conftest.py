"""
Конфигурация тестов GUI.

Устанавливает QT_QPA_PLATFORM=offscreen ДО импорта PyQt6, чтобы
тесты работали без реального дисплея. Создаёт одну QApplication
на всю сессию pytest.

Также monkeypatch'ит QMessageBox.* — чтобы вызовы диалогов в GUI-коде
не блокировали тесты.
"""

from __future__ import annotations
import os

# Это должно быть ДО первого импорта PyQt6.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    """Одна QApplication на всю pytest-сессию."""
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def no_messagebox(monkeypatch):
    """
    Отключает все QMessageBox.* — иначе тесты, нажимающие кнопки
    Validate / Run / Save, зависнут на модальном диалоге.
    """
    from PyQt6.QtWidgets import QMessageBox
    monkeypatch.setattr(
        QMessageBox, "information", staticmethod(lambda *a, **k: None),
    )
    monkeypatch.setattr(
        QMessageBox, "warning", staticmethod(lambda *a, **k: None),
    )
    monkeypatch.setattr(
        QMessageBox, "critical", staticmethod(lambda *a, **k: None),
    )
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.No),
    )