"""
Workspace — единое окно конструктора и визуализации.

Зачем:
    Заменяет два отдельных окна Run и View. Слева — конструктор
    конфига (в edit-режиме) или список задач (в analysis-режиме).
    Справа — JSON + визуализации.

    Режимы:
      - edit: конструктор + JSON + Visualise / Run
      - analysis: список задач + визуализация из output

    Visualise — живой предпросмотр с debounce 500ms, кэшем и
    отменой предыдущего worker'а.

    Run — полный прогон с сохранением в output.
    Analysis — режим анализа уже сохранённых результатов.

Как расширять:
    Новые кнопки — в _build_top_bar.
"""

from __future__ import annotations
import json
import time
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QMessageBox, QSplitter, QLabel, QStackedWidget,
)

from arbacc.cli import build_plan

from gui.common.log import get_logger
from gui.workspace.state import AppState
from gui.workspace.left_panel import LeftPanel
from gui.workspace.right_panel import RightPanel
from gui.workspace.task_list_panel import TaskListPanel
from gui.workspace.preview_worker import PreviewWorker
from gui.common.threads import RunWorker
from gui.run_mode.config_io import open_config_dialog, save_config_dialog


class Workspace:
    """Единое окно arbacc."""

    def __init__(self, state: AppState | None = None):
        """
        Принимает:
            state — общее состояние или None (создастся новый).
        """
        self._log = get_logger("workspace")
        self.state = state or AppState()

        self.window = QMainWindow()
        self.window.setWindowTitle("arbacc — Workspace")
        self.window.resize(1500, 950)

        self._preview_timer = QTimer(self.window)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(500)
        self._preview_timer.timeout.connect(self._run_preview)

        self._preview_worker: PreviewWorker | None = None
        self._run_worker: RunWorker | None = None
        self._preview_gen: int = 0
        self._last_raw: list = []

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # --- Верхняя панель ---
        layout.addLayout(self._build_top_bar())

        # --- Splitter с левой и правой панелями ---
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._left_stack = QStackedWidget()
        self._left_edit = LeftPanel()
        self._left_analysis = TaskListPanel()
        self._left_stack.addWidget(self._left_edit)
        self._left_stack.addWidget(self._left_analysis)

        self._right = RightPanel(self.state)

        self._splitter.addWidget(self._left_stack)
        self._splitter.addWidget(self._right)
        self._splitter.setSizes([400, 1100])
        layout.addWidget(self._splitter, stretch=1)

        # --- Статус-строка ---
        self._status = QLabel("Готов")
        layout.addWidget(self._status)

        self.window.setCentralWidget(central)

        # Подключения.
        self._left_edit.changed.connect(self._on_config_changed)
        self._left_analysis.task_selected.connect(
            self._on_analysis_task_selected
        )
        self._right.json_view.user_edited.connect(self._on_json_edited)

        # Начальный конфиг.
        self._left_edit.clear()
        self._on_config_changed()

        # Если есть last_output — загружаем в Analysis-панель.
        if self.state.last_output_root and self.state.last_output_root.exists():
            self._left_analysis.load_from(self.state.last_output_root)
            self._right.set_output_root(self.state.last_output_root)

    # ------------------------------------------------------------------
    # Верхняя панель
    # ------------------------------------------------------------------

    def _build_top_bar(self) -> QHBoxLayout:
        """Создаёт верхнюю панель с кнопками."""
        bar = QHBoxLayout()

        self._btn_open = QPushButton("Open…")
        self._btn_save = QPushButton("Save")
        self._btn_save_as = QPushButton("Save as…")
        self._btn_validate = QPushButton("Validate")
        self._btn_plan = QPushButton("Plan")

        self._btn_visualise = QPushButton("Visualise")
        self._btn_visualise.setCheckable(True)
        self._btn_visualise.setStyleSheet(
            "QPushButton:checked { background-color: #4a90e2; color: white; "
            "font-weight: bold; }"
        )

        self._btn_run = QPushButton("Run")

        # Поле N — сколько шагов считать в Visualise.
        from PyQt6.QtWidgets import QSpinBox
        from arbacc.settings import PREVIEW_MAX_N
        self._spin_n = QSpinBox()
        self._spin_n.setRange(1, 10_000_000)
        self._spin_n.setValue(PREVIEW_MAX_N)
        self._spin_n.setMaximumWidth(100)
        self._spin_n.setKeyboardTracking(False)   # эмитит только на Enter/blur
        self._spin_n.setToolTip(
            "N: сколько членов ряда считать в Visualise.\n"
            "Больше — точнее, но дольше.\n"
            "Enter или клик вне поля — применить."
        )
        self._spin_n.valueChanged.connect(self._on_config_changed)


        self._btn_analysis = QPushButton("Analysis")
        self._btn_analysis.setCheckable(True)

        self._btn_clear_cache = QPushButton("Clear cache")
        self._btn_clear_cache.setToolTip(
            "Удалить кэш предпросмотра (%TEMP%/arbacc_preview_cache)"
        )

        for b in (self._btn_open, self._btn_save, self._btn_save_as,
                  self._btn_validate, self._btn_plan):
            bar.addWidget(b)
        bar.addSpacing(20)
        bar.addWidget(self._btn_visualise)
        bar.addWidget(self._btn_run)
        bar.addWidget(QLabel("N:"))
        bar.addWidget(self._spin_n)        
        bar.addSpacing(20)
        bar.addWidget(self._btn_clear_cache)
        bar.addSpacing(20)
        bar.addWidget(self._btn_analysis)
        bar.addStretch()

        self._btn_open.clicked.connect(self._on_open)
        self._btn_save.clicked.connect(self._on_save)
        self._btn_save_as.clicked.connect(self._on_save_as)
        self._btn_validate.clicked.connect(self._on_validate)
        self._btn_plan.clicked.connect(self._on_plan)
        self._btn_visualise.toggled.connect(self._on_visualise_toggled)
        self._btn_run.clicked.connect(self._on_run)
        self._btn_clear_cache.clicked.connect(self._on_clear_cache_clicked)
        self._btn_analysis.toggled.connect(self._on_analysis_toggled)

        return bar

    # ------------------------------------------------------------------
    # Синхронизация
    # ------------------------------------------------------------------

    def _on_config_changed(self):
        """
        Конфиг изменился — обновляем JSON и preview.

        Защищено от вызова до создания _left_edit и _right:
        _build_top_bar запускает setValue(PREVIEW_MAX_N) раньше, чем
        создаются эти виджеты, и его сигнал вылетает сюда.
        """
        if getattr(self, "_left_edit", None) is None:
            return
        if getattr(self, "_right", None) is None:
            return

        try:
            config = self._left_edit.to_config()
        except Exception:
            self._log.exception("_on_config_changed: to_config failed")
            return

        self.state.config_dict = config

        try:
            self._right.show_config(config)
        except Exception:
            self._log.exception("_on_config_changed: show_config failed")

        if self.state.visualise_on and self.state.mode == "edit":
            self._preview_timer.start()
        else:
            try:
                self._right.show_data_list([], raw_series=[])
            except Exception:
                self._log.exception("_on_config_changed: show_data_list failed")

    def _on_json_edited(self, config: dict):
        """Пользователь правил JSON — пересобираем форму."""
        self._left_edit.from_config(config)
        self.state.config_dict = config

    # ------------------------------------------------------------------
    # Кнопки: файл, валидация, план
    # ------------------------------------------------------------------

    def _on_open(self):
        """Открыть конфиг."""
        path, config = open_config_dialog(self.window)
        if path is None:
            return
        self.state.current_config_path = path
        self._left_edit.from_config(config)
        self._status.setText(f"Открыт {path}")

    def _on_save(self):
        """Сохранить в текущий путь или спросить."""
        if self.state.current_config_path is None:
            return self._on_save_as()
        config = self._left_edit.to_config()
        try:
            self.state.current_config_path.write_text(
                json.dumps(config, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
            self._status.setText(
                f"Сохранено в {self.state.current_config_path}"
            )
        except Exception as e:
            self._log.exception("ошибка сохранения конфига")
            QMessageBox.critical(self.window, "Save error", str(e))

    def _on_save_as(self):
        """Сохранить как."""
        config = self._left_edit.to_config()
        path = save_config_dialog(
            self.window, config, self.state.current_config_path
        )
        if path:
            self.state.current_config_path = path
            self._status.setText(f"Сохранено в {path}")

    def _on_validate(self):
        """Валидация через build_plan."""
        config = self._left_edit.to_config()
        try:
            plan = build_plan(config)
        except Exception as e:
            QMessageBox.critical(
                self.window, "Invalid", f"{type(e).__name__}: {e}"
            )
            return
        errs = plan.get("errors", [])
        self._left_edit.highlight_errors(errs)
        if errs:
            QMessageBox.warning(
                self.window, "Validation errors",
                "\n".join(errs[:30]) + ("\n…" if len(errs) > 30 else ""),
            )
            return
        QMessageBox.information(
            self.window, "Valid",
            f"Конфиг валиден.\n"
            f"Accel задач: {len(plan['accel'])}\n"
            f"Post задач:  {len(plan['post'])}",
        )

    def _on_plan(self):
        """Построить план и показать первые задачи."""
        config = self._left_edit.to_config()
        try:
            plan = build_plan(config)
        except Exception as e:
            QMessageBox.critical(self.window, "Plan error", str(e))
            return
        lines = [
            f"Accel задач: {len(plan['accel'])}",
            f"Post задач:  {len(plan['post'])}",
        ]
        for e in plan.get("errors", [])[:10]:
            lines.append(f"ERR: {e}")
        lines.append("")
        for t in plan["accel"][:20]:
            lines.append(f"A  {t['task_id']}")
        for t in plan["post"][:20]:
            lines.append(f"P  {t['task_id']}")
        QMessageBox.information(self.window, "Plan", "\n".join(lines))

    # ------------------------------------------------------------------
    # Visualise
    # ------------------------------------------------------------------

    def _on_visualise_toggled(self, checked: bool):
        """Включает / выключает живой предпросмотр."""
        self.state.visualise_on = checked
        if checked:
            self._btn_visualise.setEnabled(False)
            self._btn_visualise.setText("Visualise ⏳")
            self._status.setText("Visualise — расчёт…")
            self._preview_timer.start()
        else:
            self._btn_visualise.setEnabled(True)
            self._btn_visualise.setText("Visualise")
            self._status.setText("Visualise выключен")
            self.state.preview_data = None
            self._right.show_data_list([], raw_series=[])

    def _run_preview(self):
        """
        Предпросмотр: N ограничивает и ряд, и акселераторы.

        N_user — верхняя граница (поле ввода сверху).
        Ряд рисуется до N_user.
        Каждый акселератор:
            n_max   = min(n_max_из_конфига, N_user)
            max_iter в stopping = min(max_iter_из_конфига, N_user)
        """
        if self.state.mode != "edit":
            return
        config = self._left_edit.to_config()

        from arbacc.settings import (
            PREVIEW_MAX_TASKS, PREVIEW_MAX_DPS, PREVIEW_BACKEND,
        )

        user_n = int(self._spin_n.value())

        if PREVIEW_BACKEND:
            from arbacc.precision import list_backends
            prec = config.get("precision", {})
            if isinstance(prec, dict):
                cur = prec.get("backend")
                if isinstance(cur, str) and PREVIEW_BACKEND in list_backends():
                    prec["backend"] = PREVIEW_BACKEND

        try:
            plan = build_plan(config)
        except Exception as e:
            self._status.setText(f"Preview: plan error — {e}")
            return

        # Ограничиваем n_max и max_iter каждого акселератора.
        for t in plan.get("accel", []):
            acc = t.get("accelerator", {}) or {}
            try:
                nm = int(acc.get("n_max", user_n))
            except (TypeError, ValueError):
                nm = user_n
            new_n = min(nm, user_n)
            acc["n_max"] = new_n

            for crit in acc.get("stopping", []):
                if not isinstance(crit, dict):
                    continue
                if crit.get("type") != "max_iter":
                    continue
                params = crit.get("params") or {}
                try:
                    cn = int(params.get("n", 0))
                except (TypeError, ValueError):
                    cn = 0
                # Обрезаем только если больше N. Пользовательский
                # max_iter меньше N — уважаем.
                if cn == 0 or cn > new_n:
                    params["n"] = new_n
                    crit["params"] = params

        # Отменяем старый worker.
        if self._preview_worker is not None:
            try:
                if self._preview_worker.isRunning():
                    self._preview_worker.requestInterruption()
                    self._preview_worker.wait(200)
            except Exception:
                pass

        # Ряд идёт РОВНО до N_user.
        from gui.view_mode.data_loader import build_raw_preview
        raw = build_raw_preview(config, max_n=user_n)
        self._last_raw = raw

        raw_points_total = sum(len(r.get("xs", [])) for r in raw)
        self._log.info(
            "Preview start: N=%d, raw_series=%d, raw_points=%d",
            user_n, len(raw), raw_points_total,
        )

        if not plan["accel"]:
            self.state.preview_data = []
            self._right.show_data_list([], raw_series=raw)
            self._status.setText(
                f"Preview: {len(raw)} raw (N={user_n}, без accel)"
            )
            return

        self._preview_gen += 1
        gen = self._preview_gen

        worker = PreviewWorker(
            plan, generation=gen,
            max_n=user_n,
            max_tasks=PREVIEW_MAX_TASKS,
            max_dps=PREVIEW_MAX_DPS,
        )
        worker.progress.connect(self._on_preview_progress)
        worker.finished.connect(self._on_preview_ready)
        worker.failed.connect(self._on_preview_failed)
        worker.cancelled.connect(self._on_preview_cancelled)
        worker.start()
        self._preview_worker = worker

    def _on_preview_progress(
        self,
        done: int, total: int, task_id: str,
        elapsed: float, eta: float,
    ):
        """Обновляет статус с прогрессом, временем и ETA."""
        self._status.setText(
            f"Preview: {done}/{total} — {task_id}  |  "
            f"elapsed {_fmt_time(elapsed)}, ETA {_fmt_time(eta)}"
        )

    def _on_preview_ready(self, gen: int, tasks: list):
        if gen != self._preview_gen:
            return
        if not self.state.visualise_on:
            return
        self.state.preview_data = tasks
        raw = getattr(self, "_last_raw", [])
        self._right.show_data_list(tasks, raw_series=raw)

        self._btn_visualise.setEnabled(True)
        self._btn_visualise.setText("Visualise")
        self._status.setText(
            f"Preview готов: {len(tasks)} accel + {len(raw)} raw "
            f"(N={int(self._spin_n.value())})"
        )

    def _on_preview_failed(self, gen: int, message: str):
        """Preview упал."""
        if gen != self._preview_gen:
            return
        self._log.error("Preview failed: %s", message)
        self._btn_visualise.setEnabled(True)
        self._btn_visualise.setText("Visualise")
        self._status.setText(f"Preview failed: {message[:120]}")

    def _on_preview_cancelled(self, gen: int):
        """Worker отменён (устаревшая генерация)."""
        if gen != self._preview_gen:
            return
        self._btn_visualise.setEnabled(True)
        self._btn_visualise.setText("Visualise")
        self._status.setText("Preview: отменён")

    def _on_clear_cache_clicked(self):
        """Очищает кэш preview."""
        from gui.workspace.preview_cache import clear_cache, cache_size_bytes
        size_before = cache_size_bytes()
        n = clear_cache()
        self._status.setText(
            f"Кэш очищен: {n} записей, "
            f"{size_before / 1024 / 1024:.1f} MB освобождено"
        )

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def _on_run(self):
        """Полный прогон конфига."""
        if self.state.current_config_path is None:
            self._status.setText("Сохрани конфиг перед Run")
            return

        try:
            self._on_save()

            self._btn_run.setEnabled(False)
            self._btn_run.setText("Running…")
            self._status.setText("Run запущен…")

            output_root = None
            # Run uses the output path in the current saved configuration.
            # last_output_root belongs to the previous run / analysis selection.

            self._log.info(
                "Starting Run: config=%s, output=%s",
                self.state.current_config_path, output_root,
            )

            self._run_worker = RunWorker(
                config_path=str(self.state.current_config_path),
                output_root=output_root,
            )
            self._run_worker.finished_ok.connect(self._on_run_ok)
            self._run_worker.finished_stopped.connect(self._on_run_stopped)
            self._run_worker.finished_fail.connect(self._on_run_fail)
            self._run_worker.start()
        except Exception:
            self._log.exception("ошибка при запуске Run")
            self._btn_run.setEnabled(True)
            self._btn_run.setText("Run")
            self._status.setText(
                "Run: не удалось запустить (см. gui_errors.log)"
            )

    def _on_run_ok(self):
        """Прогон завершён успешно."""
        try:
            self._btn_run.setEnabled(True)
            self._btn_run.setText("Run")
            self._status.setText("Run завершён")

            config = self._left_edit.to_config()
            output_root = (
                Path(config.get("output", "out"))
                / config.get("run_id", "run")
            )
            self.state.last_output_root = output_root
            self._left_analysis.load_from(output_root)
            self._right.set_output_root(output_root)

            from gui.view_mode.data_loader import (
                list_accel_tasks, build_raw_preview,
            )
            tasks = list_accel_tasks(output_root)
            raw = build_raw_preview(config)

            if tasks:
                self.state.saved_data = tasks
                self._right.show_data_list(tasks[:8], raw_series=raw)
                self._status.setText(
                    f"Run: {len(tasks)} accel + {len(raw)} raw "
                    f"(N={int(self._spin_n.value())})"
                )
            elif raw:
                self._right.show_data_list([], raw_series=raw)
                self._status.setText(f"Run: только raw ({len(raw)})")

            self._log.info(
                "Run completed: %d accel, %d raw, output=%s",
                len(tasks), len(raw), output_root,
            )
        except Exception:
            self._log.exception("ошибка в _on_run_ok")
            self._status.setText(
                "Run: ошибка постобработки (см. gui_errors.log)"
            )

    def _on_run_stopped(self):
        """Run остановлен пользователем."""
        self._btn_run.setEnabled(True)
        self._btn_run.setText("Run")
        self._status.setText("Run остановлен пользователем")

    def _on_run_fail(self, message: str):
        """Run упал."""
        self._log.error("Run failed: %s", message)
        self._btn_run.setEnabled(True)
        self._btn_run.setText("Run")
        first_line = message.splitlines()[0] if message else "?"
        self._status.setText(
            f"Run упал (см. gui_errors.log): {first_line[:120]}"
        )

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------

    def _on_analysis_toggled(self, checked: bool):
        """Переключение между edit и analysis режимами."""
        if checked:
            self.state.mode = "analysis"
            self._left_stack.setCurrentIndex(1)
            self._btn_visualise.setEnabled(False)
            self._btn_run.setEnabled(False)
            self._btn_open.setEnabled(False)
            self._btn_save.setEnabled(False)
            self._btn_save_as.setEnabled(False)
            self._btn_validate.setEnabled(False)
            self._btn_plan.setEnabled(False)
            self._btn_analysis.setText("Exit analysis")
            self._status.setText("Analysis: выбери output и задачу слева")

            if (self.state.last_output_root
                    and self.state.last_output_root.exists()):
                self._left_analysis.load_from(self.state.last_output_root)
                self._right.set_output_root(self.state.last_output_root)
        else:
            self.state.mode = "edit"
            self._left_stack.setCurrentIndex(0)
            self._btn_visualise.setEnabled(True)
            self._btn_run.setEnabled(True)
            self._btn_open.setEnabled(True)
            self._btn_save.setEnabled(True)
            self._btn_save_as.setEnabled(True)
            self._btn_validate.setEnabled(True)
            self._btn_plan.setEnabled(True)
            self._btn_analysis.setText("Analysis")
            self._status.setText("Edit mode")

    def _on_analysis_task_selected(self, data):
        """Пользователь выбрал задачу в analysis-режиме."""
        self.state.saved_data = data
        self._right.show_data_list([data])
        self._status.setText(
            f"Analysis: {data.short_label} "
            f"(digits={data.digits_gained}, stopped={data.stopped_by})"
        )

    # ------------------------------------------------------------------
    # Показать
    # ------------------------------------------------------------------

    def show(self):
        """Показывает окно."""
        self.window.show()


def _fmt_time(sec: float) -> str:
    """Форматирует секунды как '12.3s' или '1m 23s'."""
    if sec < 60:
        return f"{sec:.1f}s"
    m = int(sec // 60)
    s = sec - 60 * m
    return f"{m}m {s:.0f}s"