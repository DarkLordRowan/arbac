"""
Окно Run-режима.

Зачем:
    Позволяет конструировать конфиг через формы, запускать прогон,
    видеть прогресс и лог, переходить в View.

Как расширять:
    Новые секции — добавляй в _build_sections_panel.
"""

from __future__ import annotations
import json
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QSplitter, QMessageBox, QScrollArea, QFileDialog,
    QListWidget,
)
from PyQt6.QtCore import Qt

from arbacc.cli import load_config, build_plan

from gui.common.state import AppState
from gui.run_mode.config_io import open_config_dialog, save_config_dialog
from gui.run_mode.json_preview import JsonPreview
from gui.run_mode.runner_widget import RunnerWidget
from gui.run_mode.sections import (
    PrecisionSection, SeriesSection, NoiseSection, AccelSection,
    PostprocessSection, EnvelopeSection,
)


class RunWindow:
    """Окно Run-режима."""

    def __init__(self, state: AppState):
        """
        Принимает:
            state — общее состояние приложения
        """
        self.state = state
        self.window = QMainWindow()
        self.window.setWindowTitle("arbacc — Run")
        self.window.resize(1300, 850)

        self._building_json = False

        central = QWidget()
        main_layout = QVBoxLayout(central)

        # Верхняя панель.
        toolbar = QHBoxLayout()
        self._btn_open = QPushButton("Open…")
        self._btn_save = QPushButton("Save")
        self._btn_save_as = QPushButton("Save as…")
        self._btn_validate = QPushButton("Validate")
        self._btn_plan = QPushButton("Plan")
        self._btn_clear = QPushButton("Clear")

        for b in (self._btn_open, self._btn_save, self._btn_save_as,
                  self._btn_validate, self._btn_plan, self._btn_clear):
            toolbar.addWidget(b)
        toolbar.addStretch()
        main_layout.addLayout(toolbar)

        # Основная область — splitter.
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.addWidget(self._build_sections_panel())
        self._splitter.addWidget(self._build_json_panel())
        self._splitter.setSizes([1200, 100])   # JSON скрыт → узкая полоска
        main_layout.addWidget(self._splitter, stretch=1)


        # Прогресс + лог.
        self._runner = RunnerWidget()
        self._runner.run_requested.connect(self._on_run_from_widget)
        main_layout.addWidget(self._runner)

        self.window.setCentralWidget(central)

        # Панель ошибок (изначально скрыта).
        from PyQt6.QtWidgets import QListWidget
        self._errors_panel = QWidget()
        ep_layout = QVBoxLayout(self._errors_panel)
        ep_layout.setContentsMargins(4, 4, 4, 4)
        ep_layout.addWidget(QLabel("<b>Validation errors:</b>"))
        self._errors_list = QListWidget()
        self._errors_list.setMaximumHeight(100)
        ep_layout.addWidget(self._errors_list)
        self._errors_panel.setVisible(False)
        main_layout.addWidget(self._errors_panel)


        # Подключения.
        self._btn_open.clicked.connect(self._on_open)
        self._btn_save.clicked.connect(self._on_save)
        self._btn_save_as.clicked.connect(self._on_save_as)
        self._btn_validate.clicked.connect(self._on_validate)
        self._btn_plan.clicked.connect(self._on_plan)
        self._btn_clear.clicked.connect(self._on_clear)

        # Сигналы секций → пересборка JSON.
        self._precision.changed.connect(self._rebuild_json)
        for sec in self._sections:
            sec.changed.connect(self._rebuild_json)

        # Начальный конфиг.
        self._on_clear()

    # ---------- Построение UI ----------
    
    def _show_errors(self, errs: list[str]) -> None:
        """Показывает ошибки в панели снизу."""
        self._errors_panel.setVisible(True)
        self._errors_list.clear()
        for e in errs:
            self._errors_list.addItem(e)

    def _build_sections_panel(self) -> QWidget:
        """Панель секций с прокруткой (скролл на весь список секций)."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        self._precision = PrecisionSection()
        self._series = SeriesSection()
        self._noise = NoiseSection()
        self._accel = AccelSection()
        self._postprocess = PostprocessSection()
        self._envelope = EnvelopeSection()
        self._sections = [
            self._series, self._noise, self._accel,
            self._postprocess, self._envelope,
        ]

        layout.addWidget(self._precision)
        for sec in self._sections:
            layout.addWidget(sec)
        layout.addStretch()  # всё сверху, не растягивать

        scroll.setWidget(inner)
        return scroll

    def _build_json_panel(self) -> QWidget:
        """Панель JSON-превью — узкая, скрыта по умолчанию."""
        wrapper = QWidget()
        wrapper.setMaximumWidth(500)
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self._btn_toggle_json = QPushButton("◀ JSON")
        self._btn_toggle_json.setCheckable(True)
        self._btn_toggle_json.setChecked(False)
        self._btn_toggle_json.setMaximumHeight(24)
        self._btn_toggle_json.clicked.connect(self._on_toggle_json)
        layout.addWidget(self._btn_toggle_json)

        self._json_preview = JsonPreview()
        self._json_preview.setVisible(False)
        self._json_preview.user_edited.connect(self._on_json_edited)
        layout.addWidget(self._json_preview, stretch=1)

        return wrapper

    def _on_toggle_json(self):
        visible = self._btn_toggle_json.isChecked()
        self._json_preview.setVisible(visible)
        self._btn_toggle_json.setText("▶ JSON" if visible else "◀ JSON")
        # Меняем ширину splitter'а.
        if visible:
            self._splitter.setSizes([900, 400])
        else:
            self._splitter.setSizes([1200, 100])

    # ---------- Синхронизация ----------

    def _rebuild_json(self):
        if self._building_json:
            return
        self._building_json = True
        try:
            config = self._collect_config()
            self._json_preview.set_config(config)
            self.state.config_dict = config
        finally:
            self._building_json = False

    def _on_json_edited(self, config: dict):
        """Пользователь правил JSON — обновляем формы."""
        if self._building_json:
            return
        self._building_json = True
        try:
            if "precision" in config:
                self._precision.from_dict(config["precision"])
            if "series" in config:
                self._series.from_list(config["series"])
            if "noise" in config:
                self._noise.from_list(config["noise"])
            if "accelerators" in config:
                self._accel.from_list(config["accelerators"])
            if "postprocess" in config:
                self._postprocess.from_list(config["postprocess"])
            if "envelopes" in config:
                self._envelope.from_list(config["envelopes"])
            self.state.config_dict = config
        finally:
            self._building_json = False

    # ---------- Обработчики кнопок ----------

    def _on_open(self):
        """Открыть конфиг."""
        path, config = open_config_dialog(self.window)
        if path is None:
            return
        self.state.current_config_path = path
        self._on_json_edited(config)

    def _on_save(self):
        """Сохранить (в текущий путь или спросить)."""
        config = self._collect_config()
        if self.state.current_config_path is None:
            return self._on_save_as()
        try:
            self.state.current_config_path.write_text(
                json.dumps(config, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
            QMessageBox.information(self.window, "Saved",
                                    f"Saved to {self.state.current_config_path}")
        except Exception as e:
            QMessageBox.critical(self.window, "Save error", str(e))

    def _on_save_as(self):
        """Сохранить как."""
        config = self._collect_config()
        path = save_config_dialog(self.window, config, self.state.current_config_path)
        if path:
            self.state.current_config_path = path
            QMessageBox.information(self.window, "Saved", f"Saved to {path}")

    def _on_validate(self):
        """Валидация — показывает ошибки в панели и подсвечивает карточки."""
        config = self._collect_config()
        try:
            plan = build_plan(config)
        except Exception as e:
            QMessageBox.critical(self.window, "Invalid", f"{type(e).__name__}: {e}")
            return

        # Сбрасываем подсветку.
        for sec in [self._series, self._noise, self._accel,
                    self._postprocess, self._envelope]:
            for card in sec._cards():
                card.set_error(False)

        errs = plan.get("errors", [])
        if not errs:
            self._errors_panel.setVisible(False)
            QMessageBox.information(
                self.window, "Valid",
                f"Config valid.\n"
                f"Accel tasks: {len(plan['accel'])}\n"
                f"Post tasks:  {len(plan['post'])}",
            )
            return

        # Подсветка карточек по строке ошибки "kind/id: message".
        for err in errs:
            try:
                prefix = err.split(":", 1)[0]   # "series/new_1"
                kind, node_id = prefix.split("/", 1)
            except ValueError:
                continue
            sec = {
                "series": self._series,
                "noise": self._noise,
                "accelerators": self._accel,
                "postprocess": self._postprocess,
                "envelopes": self._envelope,
            }.get(kind)
            if sec is None:
                continue
            for card in sec._cards():
                if card.to_dict().get("id") == node_id:
                    card.set_error(True)

        self._show_errors(errs)

    def _on_plan(self):
        """Построить план и показать первые задачи."""
        config = self._collect_config()
        try:
            plan = build_plan(config)
        except Exception as e:
            QMessageBox.critical(self.window, "Plan error", str(e))
            return
        lines = [f"Accel tasks: {len(plan['accel'])}",
                 f"Post tasks:  {len(plan['post'])}"]
        errs = plan.get("errors", [])
        if errs:
            lines.append("")
            lines.append(f"Errors: {len(errs)}")
            lines.extend(errs[:10])
        lines.append("")
        for t in plan["accel"][:20]:
            lines.append(f"A  {t['task_id']}")
        for t in plan["post"][:20]:
            lines.append(f"P  {t['task_id']}")
        QMessageBox.information(self.window, "Plan", "\n".join(lines))

    def _on_clear(self):
        """Очистить всё."""
        self.state.current_config_path = None
        self._precision.from_dict({"backend": "mpmath", "dps": 30})
        for sec in self._sections:
            sec.from_list([])
        self._rebuild_json()

    def _on_run_from_widget(self):
        """Пользователь нажал Run — сохраняем во временный файл и запускаем."""
        import tempfile
        config = self._collect_config()
        # Всегда пишем во временный файл — Save не обязателен.
        tmp_path = Path(tempfile.gettempdir()) / "arbacc_last_run.json"
        try:
            tmp_path.write_text(
                json.dumps(config, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
        except Exception as e:
            QMessageBox.critical(self.window, "Write error", str(e))
            return

        output_root = None
        if self.state.last_output_root:
            output_root = str(self.state.last_output_root)
        self._runner.start(str(tmp_path), output_root)

    # ---------- Утилиты ----------

    def _collect_config(self) -> dict:
        """Собирает конфиг из форм."""
        return {
            "run_id": "exp_001",
            "output": "out",
            "precision": self._precision.to_dict(),
            "series": self._series.to_list(),
            "noise": self._noise.to_list(),
            "accelerators": self._accel.to_list(),
            "postprocess": self._postprocess.to_list(),
            "envelopes": self._envelope.to_list(),
        }

    def show(self):
        """Показывает окно."""
        self.window.show()