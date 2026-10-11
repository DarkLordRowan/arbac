"""
Открытие / сохранение JSON-конфига.

Зачем:
    Диалоги выбора файла + обработка ошибок чтения/записи.
"""

from __future__ import annotations
import json
from pathlib import Path

from PyQt6.QtWidgets import QFileDialog, QMessageBox, QWidget


def open_config_dialog(parent: QWidget) -> tuple[Path | None, dict | None]:
    """
    Диалог «открыть конфиг».

    Принимает:
        parent — родительский виджет

    Возвращает:
        (path, config) или (None, None), если отменено.
    """
    path_str, _ = QFileDialog.getOpenFileName(
        parent, "Open config", "", "JSON (*.json);;All (*)"
    )
    if not path_str:
        return None, None
    path = Path(path_str)
    try:
        text = path.read_text(encoding="utf-8-sig")
        config = json.loads(text)
        return path, config
    except Exception as e:
        QMessageBox.critical(parent, "Read error", f"Cannot read {path}:\n{e}")
        return None, None


def save_config_dialog(parent: QWidget, config: dict, current: Path | None) -> Path | None:
    """
    Диалог «сохранить конфиг».

    Принимает:
        parent  — родительский виджет
        config  — словарь конфига
        current — текущий путь (если есть, предлагаем его)

    Возвращает:
        путь или None, если отменено.
    """
    path_str, _ = QFileDialog.getSaveFileName(
        parent, "Save config",
        str(current) if current else "",
        "JSON (*.json)",
    )
    if not path_str:
        return None
    path = Path(path_str)
    try:
        path.write_text(
            json.dumps(config, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        return path
    except Exception as e:
        QMessageBox.critical(parent, "Write error", f"Cannot save {path}:\n{e}")
        return None