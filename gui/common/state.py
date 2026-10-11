"""
Общее состояние приложения, разделяемое между окнами.

Зачем:
    Когда пользователь открывает Run, строит конфиг, запускает прогон —
    результат сохраняется в output. При переходе в View мы хотим, чтобы
    последний output был уже подставлен как путь по умолчанию.

    Также здесь хранится текущий конфиг, чтобы не терять его между
    окнами.

Как расширять:
    Добавляй поля по мере необходимости.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AppState:
    """
    Общее состояние между окнами.

    Поля:
        current_config_path — путь к текущему открытому JSON-конфигу
        last_output_root    — путь к последнему output (для View)
        config_dict         — словарь текущего конфига (для быстрого
                              доступа без повторного чтения файла)
    """
    current_config_path: Path | None = None
    last_output_root: Path | None = None
    config_dict: dict = field(default_factory=dict)
    
    # Новое:
    mode: str = "edit"                # "edit" | "analysis"
    visualise_on: bool = False        # живой предпросмотр
    preview_task: dict | None = None  # задача для предпросмотра
    preview_data: Any = None          # AccelData после предпросмотра