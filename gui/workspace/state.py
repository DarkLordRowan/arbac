"""
Расширенное состояние приложения для Workspace.

Зачем:
    Нужно больше полей, чем было в AppState: режим работы (edit/analysis),
    статус Visualise, кэш предпросмотра и кэш сохранённого результата.

    Разделяем preview_data (результат быстрого расчёта для живой
    визуализации) и saved_data (результат полного Run, прочитанный
    из output). Правые вкладки смотрят на одно из них в зависимости
    от режима.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class AppState:
    """
    Общее состояние между виджетами Workspace.

    Поля:
        current_config_path — путь к последнему сохранённому JSON-конфигу
        last_output_root    — путь к последнему output (для Analysis)
        config_dict         — текущий конфиг, собранный из формы
        mode                — "edit" | "analysis"
        visualise_on        — включён ли живой предпросмотр
        preview_data        — AccelData последнего предпросмотра
        saved_data          — AccelData последнего сохранённого Run
    """
    current_config_path: Path | None = None
    last_output_root: Path | None = None
    config_dict: dict = field(default_factory=dict)

    mode: str = "edit"
    visualise_on: bool = False
    preview_data: Any = None
    saved_data: Any = None