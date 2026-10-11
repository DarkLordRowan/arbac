"""
Прогресс выполнения — progress.json.

Зачем нужен:
    После каждой задачи раннер обновляет progress.json. Это позволяет:
      - видеть, где он находится,
      - возобновлять после падения,
      - строить отчёты.

    Запись атомарная (tmp + rename), чтобы Ctrl+C не оставил битый файл.

Как расширять:
    Если понадобится больше полей (например, среднее время на задачу),
    добавь их в Progress.
"""

from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class Progress:
    """
    Прогресс выполнения.

    Поля:
        total       — всего задач
        done        — успешно посчитано
        failed      — упало
        skipped     — пропущено
        started_at  — время старта
        last_task   — последняя обработанная задача
        last_status — её статус
    """

    def __init__(self, total: int):
        """
        Принимает:
            total — общее число задач
        """
        self.total = total
        self.done = 0
        self.failed = 0
        self.skipped = 0
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.last_task: str | None = None
        self.last_status: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Возвращает словарь для JSON."""
        return {
            "total": self.total,
            "done": self.done,
            "failed": self.failed,
            "skipped": self.skipped,
            "started_at": self.started_at,
            "last_task": self.last_task,
            "last_status": self.last_status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def save(self, path: Path) -> None:
        """
        Атомарно сохраняет прогресс.

        Принимает:
            path — путь к progress.json

        Возвращает:
            None.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        tmp.replace(path)