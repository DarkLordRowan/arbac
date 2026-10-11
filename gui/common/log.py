"""
Единая точка логирования GUI — по сессиям.

Зачем:
    Каждый запуск GUI пишет свой лог в отдельную папку:
        logs/session_YYYY-MM-DD_HH-MM-SS/gui.log

    Это позволяет:
      - присылать конкретную сессию при отладке,
      - хранить историю запусков,
      - не терять контекст между прогонами.

    Старые сессии (> MAX_SESSIONS) удаляются автоматически при старте.

Как использовать:
    from gui.common.log import get_logger
    log = get_logger("my_module")
    log.info("event")
    try:
        ...
    except Exception:
        log.exception("failed")
"""

from __future__ import annotations
import logging
import shutil
import sys
import traceback
from datetime import datetime
from pathlib import Path


#: Папка для логов — рядом с проектом.
LOGS_ROOT = Path("logs")

#: Сколько последних сессий хранить.
MAX_SESSIONS = 20

_LOGGER_NAME = "arbacc.gui"
_configured = False
_session_dir: Path | None = None


def _make_session_dir() -> Path:
    """
    Создаёт папку для текущей сессии.

    Формат имени: session_YYYY-MM-DD_HH-MM-SS.
    Если папка уже существует (два запуска в одну секунду) — добавляет
    суффикс _2, _3, ...

    Возвращает:
        Path к созданной папке.
    """
    LOGS_ROOT.mkdir(parents=True, exist_ok=True)
    base = "session_" + datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    candidate = LOGS_ROOT / base
    n = 2
    while candidate.exists():
        candidate = LOGS_ROOT / f"{base}_{n}"
        n += 1
    candidate.mkdir(parents=True)
    return candidate


def _cleanup_old_sessions() -> int:
    """
    Удаляет старые сессии, оставляя последние MAX_SESSIONS.

    Возвращает:
        число удалённых папок.
    """
    if not LOGS_ROOT.exists():
        return 0
    sessions = sorted(
        [p for p in LOGS_ROOT.iterdir() if p.is_dir() and p.name.startswith("session_")],
        key=lambda p: p.name,
    )
    if len(sessions) <= MAX_SESSIONS:
        return 0
    to_remove = sessions[: len(sessions) - MAX_SESSIONS]
    for p in to_remove:
        try:
            shutil.rmtree(p, ignore_errors=True)
        except Exception:
            pass
    return len(to_remove)


def setup() -> Path:
    """
    Настраивает логгер на текущую сессию. Идемпотентно.

    Возвращает:
        Path к папке сессии.
    """
    global _configured, _session_dir
    if _configured and _session_dir is not None:
        return _session_dir

    _cleanup_old_sessions()
    _session_dir = _make_session_dir()
    log_file = _session_dir / "gui.log"

    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    # Убираем старые handlers, если setup() вызывается повторно
    # (например, при перезапуске из одного процесса).
    for h in list(logger.handlers):
        logger.removeHandler(h)
        try:
            h.close()
        except Exception:
            pass

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    # File handler — на сессию. Без ротации: каждая сессия короткая.
    try:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(fmt)
        fh.setLevel(logging.DEBUG)
        logger.addHandler(fh)
    except Exception:
        pass

    # stderr — чтобы видеть в консоли.
    sh = logging.StreamHandler(sys.stderr)
    sh.setFormatter(fmt)
    sh.setLevel(logging.INFO)
    logger.addHandler(sh)

    _configured = True
    return _session_dir


def get_session_dir() -> Path | None:
    """Возвращает папку текущей сессии (или None, если setup не вызывался)."""
    return _session_dir


def get_logger(name: str = "") -> logging.Logger:
    """
    Возвращает логгер с указанным суффиксом.

    Принимает:
        name — суффикс (например, "run", "plot", "excepthook").

    Возвращает:
        logging.Logger.
    """
    if not _configured:
        setup()
    full = f"{_LOGGER_NAME}.{name}" if name else _LOGGER_NAME
    return logging.getLogger(full)


def install_excepthook() -> None:
    """
    Глобальный обработчик исключений: логирует + показывает диалог.

    Ставится в gui/main.py до создания QApplication.
    """
    log = get_logger("excepthook")

    def hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        tb_text = "".join(
            traceback.format_exception(exc_type, exc_value, exc_tb)
        )
        log.error("Unhandled exception:\n%s", tb_text)

        try:
            from PyQt6.QtWidgets import QApplication, QMessageBox
            app = QApplication.instance()
            if app is None:
                return
            box = QMessageBox()
            box.setIcon(QMessageBox.Icon.Critical)
            box.setWindowTitle("Ошибка")
            box.setText(f"{exc_type.__name__}: {exc_value}")
            box.setDetailedText(tb_text)
            info = "Полный traceback записан в "
            if _session_dir is not None:
                info += str((_session_dir / "gui.log").resolve())
            else:
                info += "logs/"
            box.setInformativeText(info)
            box.exec()
        except Exception:
            pass

    sys.excepthook = hook


def log_exception(name: str, msg: str) -> None:
    """
    Логирует текущее исключение с полным traceback.
    """
    get_logger(name).error(
        "%s\n%s", msg, traceback.format_exc(),
    )


#: Алиас: некоторые модули импортируют setup_logging.
setup_logging = setup