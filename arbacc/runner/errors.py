"""
Лог ошибок — errors.log.

Зачем нужен:
    Раннер не падает на первой ошибке — он логирует её и идёт дальше.
    Все ошибки собираются в errors.log с контекстом:
      - task_id,
      - тип ошибки,
      - traceback (если есть).

Как расширять:
    Если понадобится структурированный JSON-лог — переделай на jsonl.
"""

from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ErrorLog:
    """
    Лог ошибок с записью в файл.
    """

    def __init__(self, path: Path):
        """
        Принимает:
            path — путь к errors.log
        """
        self.path = path
        self.count = 0

    def log(self, task: dict[str, Any], error: str, tb: str | None = None) -> None:
        """
        Записывает ошибку.

        Принимает:
            task  — задача
            error — краткое описание
            tb    — traceback (опционально)

        Возвращает:
            None.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).isoformat()
        task_id = task.get("task_id", "?")
        with self.path.open("a", encoding="utf-8") as f:
            f.write(f"[{ts}] task_id={task_id}\n")
            f.write(f"  error: {error}\n")
            if tb:
                for line in tb.splitlines():
                    f.write(f"  {line}\n")
            f.write("\n")
        self.count += 1