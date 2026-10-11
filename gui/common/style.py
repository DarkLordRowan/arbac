"""
Единые стили QSS для всего приложения.

Зачем:
    Чтобы все окна и виджеты выглядели одинаково. Тёмная тема по
    умолчанию, легко переключается.

Как расширять:
    Добавляй правила для новых виджетов здесь. Не пиши
    setStyleSheet(...) в отдельных окнах — это разъедет стиль.
"""

from __future__ import annotations
from PyQt6.QtWidgets import QApplication


#: Основной QSS. Можно заменить на другой через apply_style(app, qss=...).
DEFAULT_QSS = """
QWidget {
    background-color: #2b2b2b;
    color: #e0e0e0;
    font-size: 13px;
}
QMainWindow {
    background-color: #1e1e1e;
}
QLabel {
    color: #e0e0e0;
}
QPushButton {
    background-color: #3c3f41;
    color: #e0e0e0;
    border: 1px solid #555;
    border-radius: 4px;
    padding: 6px 12px;
}
QPushButton:hover {
    background-color: #4a4d4f;
}
QPushButton:pressed {
    background-color: #2e3133;
}
QPushButton:disabled {
    color: #777;
    background-color: #333;
}
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #1e1e1e;
    color: #e0e0e0;
    border: 1px solid #555;
    border-radius: 4px;
    padding: 4px;
}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
    border: 1px solid #4a90e2;
}
QTabWidget::pane {
    border: 1px solid #555;
    background-color: #2b2b2b;
}
QTabBar::tab {
    background-color: #3c3f41;
    color: #e0e0e0;
    padding: 8px 16px;
    border: 1px solid #555;
}
QTabBar::tab:selected {
    background-color: #4a90e2;
    color: #fff;
}
QHeaderView::section {
    background-color: #3c3f41;
    color: #e0e0e0;
    padding: 4px;
    border: 1px solid #555;
}
QTableWidget {
    background-color: #1e1e1e;
    gridline-color: #444;
}
QProgressBar {
    background-color: #1e1e1e;
    border: 1px solid #555;
    border-radius: 4px;
    text-align: center;
}
QProgressBar::chunk {
    background-color: #4a90e2;
}
QGroupBox {
    border: 1px solid #555;
    border-radius: 4px;
    margin-top: 8px;
    padding-top: 8px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}
"""


def apply_style(app: QApplication, qss: str | None = None) -> None:
    """
    Применяет QSS-стиль к приложению.

    Принимает:
        app — QApplication
        qss — строка со стилем; если None, используется DEFAULT_QSS

    Возвращает:
        None.
    """
    app.setStyleSheet(qss or DEFAULT_QSS)