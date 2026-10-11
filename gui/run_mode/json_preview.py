"""
JSON-превью конфига.

Зачем:
    Показывает текущий конфиг в виде JSON. Можно править вручную —
    тогда форма пересобирается из текста (двусторонняя синхронизация).

    Защита от зацикливания: при обновлении из формы выставляем флаг
    _updating_from_form, чтобы сигнал textChanged не пытался пересобрать
    конфиг обратно.

Как расширять:
    Если нужна подсветка синтаксиса — подключить QSyntaxHighlighter.
"""

from __future__ import annotations
import json
from typing import Any

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTextEdit
from PyQt6.QtGui import QFont


class JsonPreview(QWidget):
    """
    Виджет JSON-превью.

    Сигналы:
        user_edited(dict) — пользователь отредактировал JSON вручную,
                            содержимое валидно и распарсено.
    """

    user_edited = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._updating_from_form = False

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("JSON preview (edit to load)"))

        self._edit = QTextEdit()
        self._edit.setFont(QFont("Consolas", 10))
        self._edit.setPlaceholderText("{}")
        self._edit.textChanged.connect(self._on_text_changed)
        layout.addWidget(self._edit)

    def set_config(self, config: dict[str, Any]) -> None:
        """
        Обновляет JSON из формы.

        Принимает:
            config — словарь конфига

        Возвращает:
            None.
        """
        self._updating_from_form = True
        try:
            text = json.dumps(config, ensure_ascii=False, indent=2, default=str)
            # Сохраняем позицию курсора.
            cursor_pos = self._edit.textCursor().position()
            self._edit.blockSignals(True)
            self._edit.setPlainText(text)
            self._edit.blockSignals(False)
            # Восстанавливаем позицию.
            cursor = self._edit.textCursor()
            cursor.setPosition(min(cursor_pos, len(text)))
            self._edit.setTextCursor(cursor)
        finally:
            self._updating_from_form = False

    def get_text(self) -> str:
        """Возвращает текст JSON."""
        return self._edit.toPlainText()

    def _on_text_changed(self):
        """Пользователь изменил текст."""
        if self._updating_from_form:
            return
        text = self._edit.toPlainText().strip()
        if not text:
            return
        try:
            config = json.loads(text)
            if isinstance(config, dict):
                self.user_edited.emit(config)
        except json.JSONDecodeError:
            # Игнорируем невалидный JSON — пользователь ещё печатает.
            pass