"""
Общие модули GUI.

Экспортирует логгер и хук исключений.
"""

from gui.common.log import (
    setup_logging,
    setup,
    install_excepthook,
    get_logger,
    get_session_dir,
    log_exception,
    LOGS_ROOT,
    MAX_SESSIONS,
)

__all__ = [
    "setup_logging",
    "setup",
    "install_excepthook",
    "get_logger",
    "get_session_dir",
    "log_exception",
    "LOGS_ROOT",
    "MAX_SESSIONS",
]