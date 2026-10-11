"""
Виджет прогресса и лога прогона.

Зачем:
    Отдельный виджет, который встраивается в окно Run. Содержит
    прогресс-бар, метку статуса, лог-поле.

    Логика запуска вынесена сюда — окно Run только собирает конфиг
    и передаёт его.

    Прогресс-бар обновляется, читая progress.json из output каждую
    секунду. По завершении делается финальный поллинг, чтобы значение
    дошло до 100%.

Как расширять:
    Если нужно отображать прогресс по задачам (а не только по счётчику) —
    добавить таблицу с задачами.
"""

from __future__ import annotations
import json
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QTextEdit,
)
from PyQt6.QtCore import QTimer, pyqtSignal

from gui.common.threads import RunWorker


class RunnerWidget(QWidget):
    """
    Прогресс + лог + кнопки Run / Stop.

    Сигналы:
        run_requested() — пользователь нажал Run. Внешний код
                          (RunWindow) должен вызвать start() с нужным
                          конфигом.
    """

    run_requested = pyqtSignal()

    def __init__(self, parent=None):
        """
        Принимает:
            parent — родительский виджет
        """
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Статус + кнопки.
        top = QHBoxLayout()
        self._status = QLabel("Idle")
        self._btn_run = QPushButton("Run")
        self._btn_stop = QPushButton("Stop")
        self._btn_stop.setEnabled(False)
        top.addWidget(self._status)
        top.addStretch()
        top.addWidget(self._btn_run)
        top.addWidget(self._btn_stop)
        layout.addLayout(top)

        # Прогресс.
        self._progress = QProgressBar()
        self._progress.setValue(0)
        self._progress.setMaximum(100)
        layout.addWidget(self._progress)

        # Лог.
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(150)
        layout.addWidget(self._log)

        self._worker: RunWorker | None = None
        self._output_root: Path | None = None
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(1000)
        self._poll_timer.timeout.connect(self._poll_progress)

        # Run — эмитим сигнал наружу.
        self._btn_run.clicked.connect(self.run_requested.emit)
        # Stop — обрабатываем локально.
        self._btn_stop.clicked.connect(self.stop)

    def start(self, config_path: str, output_root: str | None = None) -> None:
        """
        Запускает прогон.

        Принимает:
            config_path — путь к конфигу
            output_root — путь к output (если None, вычисляется из конфига)

        Возвращает:
            None.
        """
        # Если output_root не задан — вычисляем из конфига.
        if output_root is None:
            try:
                cfg = json.loads(
                    Path(config_path).read_text(encoding="utf-8-sig")
                )
                output_root = str(
                    Path(cfg.get("output", "out")) / cfg.get("run_id", "run")
                )
            except Exception:
                output_root = None

        self._log.clear()
        self._status.setText("Running…")
        self._progress.setMaximum(100)
        self._progress.setValue(0)
        self._btn_run.setEnabled(False)
        self._btn_stop.setEnabled(True)

        self._worker = RunWorker(
            config_path=config_path,
            output_root=output_root,
        )
        self._worker.finished_ok.connect(self._on_ok)
        self._worker.finished_stopped.connect(self._on_stopped)
        self._worker.finished_fail.connect(self._on_fail)
        self._worker.log_line.connect(self._log.append)

        # Запускаем polling progress.json.
        if output_root:
            self._output_root = Path(output_root)
            self._poll_timer.start()

    def _on_stopped(self) -> None:
        """Пользователь остановил прогон."""
        self._poll_progress()
        self._status.setText("Stopped")
        self._log.append("Run stopped by user.")
        self._btn_run.setEnabled(True)
        self._btn_stop.setEnabled(False)
        self._poll_timer.stop()

    def stop(self) -> None:
        """
        Просит остановиться.

        Возвращает:
            None.
        """
        if self._worker:
            self._worker.request_stop()

    def _on_ok(self) -> None:
        """Успешное завершение."""
        # Финальный поллинг, чтобы прогресс дошёл до максимума.
        self._poll_progress()
        self._progress.setValue(self._progress.maximum())
        self._status.setText("Done")
        self._log.append("Run finished OK.")
        self._btn_run.setEnabled(True)
        self._btn_stop.setEnabled(False)
        self._poll_timer.stop()

    def _on_fail(self, message: str) -> None:
        """Ошибка."""
        self._poll_progress()
        self._status.setText("Failed")
        self._log.append(f"Run failed: {message}")
        self._btn_run.setEnabled(True)
        self._btn_stop.setEnabled(False)
        self._poll_timer.stop()

    def _poll_progress(self) -> None:
        """
        Читает progress.json и обновляет прогресс-бар.

        Возвращает:
            None.
        """
        if not self._output_root:
            return
        p = self._output_root / "progress.json"
        if not p.exists():
            return
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return

        total = data.get("total", 0)
        done = data.get("done", 0)
        failed = data.get("failed", 0)
        skipped = data.get("skipped", 0)

        if total > 0:
            self._progress.setMaximum(total)
            self._progress.setValue(done + failed + skipped)
            self._status.setText(
                f"Running… done={done} failed={failed} "
                f"skipped={skipped} / total={total}"
            )
        else:
            self._progress.setMaximum(100)
            self._progress.setValue(0)