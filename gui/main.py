"""
Главная точка входа GUI.

Запускает QApplication и открывает Workspace — единое окно
конструктора и визуализации.

Каждый запуск пишет свой лог в logs/session_.../gui.log
(см. gui/common/log.py).
"""

from __future__ import annotations
import sys

from PyQt6.QtWidgets import QApplication

from gui.common.log import (
    setup_logging, install_excepthook, get_logger, get_session_dir,
)


def main() -> int:
    """Точка входа."""
    setup_logging()
    install_excepthook()

    log = get_logger("main")
    session = get_session_dir()
    log.info("GUI starting, session log: %s", session)

    app = QApplication(sys.argv)

    from gui.common.style import apply_style
    from gui.workspace import Workspace
    from gui.workspace.state import AppState

    apply_style(app)
    state = AppState()
    ws = Workspace(state)
    ws.show()

    rc = app.exec()
    log.info("GUI exited with code %s", rc)
    return rc


if __name__ == "__main__":
    sys.exit(main())