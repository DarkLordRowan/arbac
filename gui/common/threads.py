"""
RunWorker — QThread для запуска прогона конфига.

Зачем:
    Прогон может занимать минуты. Делаем в отдельном потоке.
    Поддерживает два режима:
      - последовательный (как было),
      - параллельный (ProcessPoolExecutor).

    Режим выбирается по приоритету:
      1) явный аргумент parallel в конструкторе,
      2) settings.PARALLEL_ENABLED / PARALLEL_WORKERS.

Сигналы:
    progress(int, int, str)  — (done, total, task_id)
    log_line(str)            — строка лога
    finished_ok()            — успешно
    finished_stopped()       — остановлено пользователем
    finished_fail(str)       — ошибка
"""

from __future__ import annotations
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from gui.common.log import get_logger


class RunWorker(QThread):
    """Выполняет прогон в отдельном потоке."""

    progress = pyqtSignal(int, int, str)
    log_line = pyqtSignal(str)
    finished_ok = pyqtSignal()
    finished_stopped = pyqtSignal()
    finished_fail = pyqtSignal(str)

    def __init__(
        self,
        config_path: str,
        output_root: str | None = None,
        skip_existing: bool = False,
        only_series: str | None = None,
        limit: int | None = None,
        parallel: int | None = None,
    ):
        """
        Принимает:
            config_path   — путь к JSON-конфигу.
            output_root   — путь к output (None → из конфига).
            skip_existing — пропускать посчитанное.
            only_series   — фильтр по series_id (через запятую).
            limit         — лимит числа задач.
            parallel      — число процессов.
                            None → из settings.
                            0 → все ядра.
        """
        super().__init__()
        self._config_path = config_path
        self._output_root = output_root
        self._skip_existing = skip_existing
        self._only_series = only_series
        self._limit = limit
        self._parallel = parallel
        self._stop_requested = False
        self._log = get_logger("run_worker")

    def request_stop(self) -> None:
        """Помечает поток как «остановиться после текущей задачи»."""
        self._log.info("Stop requested")
        self._stop_requested = True
        self.log_line.emit("Stop requested…")

    def run(self) -> None:
        """Основной метод потока."""
        from arbacc.settings import PARALLEL_ENABLED, PARALLEL_WORKERS

        try:
            if self._parallel is not None:
                use_parallel = True
                workers = self._parallel
            elif PARALLEL_ENABLED:
                use_parallel = True
                workers = PARALLEL_WORKERS
            else:
                use_parallel = False
                workers = 0

            self._log.info(
                "starting: config=%s, output=%s, parallel=%s, workers=%s",
                self._config_path, self._output_root,
                use_parallel, workers,
            )

            if use_parallel:
                self._run_parallel(workers)
            else:
                self._run_sequential()

        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self._log.error("RunWorker crashed:\n%s", tb)
            self.finished_fail.emit(f"{type(e).__name__}: {e}\n{tb}")

    # ------------------------------------------------------------------
    # Последовательный режим
    # ------------------------------------------------------------------

    def _run_sequential(self) -> None:
        """Последовательный путь — исходная логика."""
        from arbacc.cli import load_config
        from arbacc.runner import (
            build_plan, execute_accel, execute_post, should_skip,
            Progress, ErrorLog,
        )

        config = load_config(Path(self._config_path))
        plan = build_plan(config)

        accel_tasks = plan["accel"]
        post_tasks = plan["post"]

        if self._only_series:
            wanted = set(self._only_series.split(","))
            accel_tasks = [
                t for t in accel_tasks if t["ids"]["series_id"] in wanted
            ]
            post_tasks = [
                t for t in post_tasks if t["ids"]["series_id"] in wanted
            ]

        if self._limit:
            accel_tasks = accel_tasks[: self._limit]
            remaining = max(0, self._limit - len(accel_tasks))
            post_tasks = post_tasks[:remaining]

        total = len(accel_tasks) + len(post_tasks)
        output_root = Path(
            self._output_root
            or (config.get("output", "out") + "/" + config.get("run_id", "run"))
        )
        output_root.mkdir(parents=True, exist_ok=True)

        progress = Progress(total=total)
        errors = ErrorLog(output_root / "errors.log")
        skip_existing = self._skip_existing or config.get("skip_existing", False)
        stopped = False
        idx = 0

        # Accel
        for task in accel_tasks:
            if self._stop_requested:
                stopped = True
                break
            idx += 1
            if skip_existing and should_skip(task, output_root):
                progress.skipped += 1
                progress.last_task = task["task_id"]
                progress.last_status = "skipped"
                progress.save(output_root / "progress.json")
                self.progress.emit(idx, total, task["task_id"])
                self.log_line.emit(f"[{idx}/{total}] SKIP  {task['task_id']}")
                continue
            result = execute_accel(task, output_root)
            self._handle_result(
                idx, total, task, result, progress, errors, output_root,
            )

        # Post
        if not stopped:
            for task in post_tasks:
                if self._stop_requested:
                    stopped = True
                    break
                idx += 1
                result = execute_post(task, output_root)
                self._handle_result(
                    idx, total, task, result, progress, errors, output_root,
                )

        self.log_line.emit(
            f"Done: {progress.done}, Failed: {progress.failed}, "
            f"Skipped: {progress.skipped}"
            + (" [STOPPED]" if stopped else "")
        )
        if stopped:
            self.finished_stopped.emit()
        else:
            self.finished_ok.emit()

    def _handle_result(
        self, idx, total, task, result, progress, errors, output_root: Path,
    ) -> None:
        """Обновляет Progress / ErrorLog / emits по результату."""
        status = result["status"]
        tid = task["task_id"]
        if status == "ok":
            progress.done += 1
            self.log_line.emit(f"[{idx}/{total}] OK    {tid}")
        elif status == "skipped":
            progress.skipped += 1
            self.log_line.emit(
                f"[{idx}/{total}] SKIP  {tid} "
                f"({result.get('error', '?')})"
            )
        else:
            progress.failed += 1
            errors.log(task, result.get("error", "?"),
                       result.get("traceback"))
            self._log.warning(
                "task failed: %s — %s", tid, result.get("error", "?"),
            )
            self.log_line.emit(
                f"[{idx}/{total}] FAIL  {tid} ({result.get('error', '?')})"
            )
        progress.last_task = tid
        progress.last_status = status
        progress.save(output_root / "progress.json")
        self.progress.emit(idx, total, tid)

    # ------------------------------------------------------------------
    # Параллельный режим
    # ------------------------------------------------------------------

    def _run_parallel(self, workers: int) -> None:
        """Параллельный путь через execute_batch."""
        from arbacc.cli import load_config
        from arbacc.runner import build_plan
        from arbacc.runner.execute_batch import execute_batch

        config = load_config(Path(self._config_path))
        plan = build_plan(config)

        accel_tasks = plan["accel"]
        post_tasks = plan["post"]

        if self._only_series:
            wanted = set(self._only_series.split(","))
            accel_tasks = [
                t for t in accel_tasks if t["ids"]["series_id"] in wanted
            ]
            post_tasks = [
                t for t in post_tasks if t["ids"]["series_id"] in wanted
            ]

        if self._limit:
            accel_tasks = accel_tasks[: self._limit]
            remaining = max(0, self._limit - len(accel_tasks))
            post_tasks = post_tasks[:remaining]

        output_root = Path(
            self._output_root
            or (config.get("output", "out") + "/" + config.get("run_id", "run"))
        )
        output_root.mkdir(parents=True, exist_ok=True)

        self.log_line.emit(f"Parallel: {workers or 'all'} workers")

        def _on_result(r: dict) -> None:
            status = r.get("status", "?")
            tid = r.get("task_id", "?")
            if status == "ok":
                self.log_line.emit(f"OK    {tid}")
            elif status == "skipped":
                self.log_line.emit(f"SKIP  {tid}")
            else:
                self._log.warning(
                    "task failed: %s — %s", tid, r.get("error", "?"),
                )
                self.log_line.emit(
                    f"FAIL  {tid} ({r.get('error', '?')})"
                )

        def _on_progress(done: int, total: int, task_id: str) -> None:
            self.progress.emit(done, total, task_id)

        def _is_stopped() -> bool:
            return self._stop_requested

        stats = execute_batch(
            {"accel": accel_tasks, "post": post_tasks},
            output_root,
            workers=workers,
            skip_existing=self._skip_existing
                or config.get("skip_existing", False),
            on_result=_on_result,
            on_progress=_on_progress,
            is_stopped=_is_stopped,
        )

        self.log_line.emit(
            f"Done: {stats['accel_ok'] + stats['post_ok']}, "
            f"Failed: {stats['accel_failed'] + stats['post_failed']}, "
            f"Skipped: {stats.get('skipped', 0)}, "
            f"Elapsed: {stats['elapsed']:.2f}s"
        )

        if stats.get("stopped", False):
            self.finished_stopped.emit()
        else:
            self.finished_ok.emit()