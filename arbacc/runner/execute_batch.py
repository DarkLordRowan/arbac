"""
Параллельное выполнение задач через ProcessPoolExecutor.

Зачем:
    Для большого конфига последовательный execute_accel — часы.
    Многопроцессность даёт ×N на N ядрах.

    Особенности:
      - Один ProcessPoolExecutor на весь прогон (accel + post).
        Это критично: spawn на Windows — ~500 мс на воркер.
      - Chunking: один submit = пачка задач, чтобы оверхед
        не превышал полезную работу.
      - Каждый процесс импортирует плагины через initializer.

Как расширять:
    Если понадобится shared-контекст — multiprocessing.Manager.
"""

from __future__ import annotations
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable

from arbacc.settings import PARALLEL_WORKERS


def _import_plugins() -> None:
    """Импортирует все пакеты плагинов — заполняет реестр."""
    import arbacc.series        # noqa: F401
    import arbacc.noise         # noqa: F401
    import arbacc.accelerators  # noqa: F401
    import arbacc.stopping      # noqa: F401
    import arbacc.postprocess   # noqa: F401
    import arbacc.envelopes     # noqa: F401


def _worker_init() -> None:
    """Initializer для каждого воркера: один раз импортирует плагины."""
    _import_plugins()


def _accel_worker_chunk(args: tuple) -> list[dict]:
    """
    Воркер для пачки accel-задач.

    Принимает:
        args — (list_tasks, output_root_str).

    Возвращает:
        список результатов.
    """
    tasks, output_root_str = args
    from arbacc.runner.execute import execute_accel
    out = Path(output_root_str)
    return [execute_accel(t, out) for t in tasks]


def _post_worker_chunk(args: tuple) -> list[dict]:
    """Воркер для пачки post-задач."""
    tasks, output_root_str = args
    from arbacc.runner.execute import execute_post
    out = Path(output_root_str)
    return [execute_post(t, out) for t in tasks]


def execute_batch(
    plan: dict,
    output_root: Path,
    workers: int = 0,
    skip_existing: bool = False,
    on_result: Callable[[dict], None] | None = None,
    on_progress: Callable[[int, int, str], None] | None = None,
    is_stopped: Callable[[], bool] | None = None,
) -> dict:
    """
    Выполняет план параллельно, ОДНИМ пулом для accel и post.

    Принимает:
        plan, output_root, workers, skip_existing, on_result,
        on_progress, is_stopped — см. предыдущие версии.

    Возвращает:
        {
            "accel_ok": int, "accel_failed": int,
            "post_ok": int, "post_failed": int, "post_skipped": int,
            "elapsed": float, "stopped": bool,
        }
    """
    if workers <= 0:
        workers = PARALLEL_WORKERS or (os.cpu_count() or 1)

    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    stats = {
        "accel_ok": 0, "accel_failed": 0,
        "post_ok": 0, "post_failed": 0,
        "skipped": 0,
        "stopped": False,
    }

    _import_plugins()
    from arbacc.runner.progress import Progress
    from arbacc.runner.errors import ErrorLog

    # Подготовка задач.
    accel_tasks = list(plan.get("accel", []))
    post_tasks = list(plan.get("post", []))
    n_skipped = 0
    if skip_existing:
        from arbacc.runner.skip import should_skip, should_skip_post

        def _announce_skip(task: dict) -> None:
            if on_result:
                on_result({
                    "status": "skipped",
                    "task_id": task["task_id"],
                })

        kept = []
        for t in accel_tasks:
            if should_skip(t, output_root):
                n_skipped += 1
                _announce_skip(t)
            else:
                kept.append(t)
        accel_tasks = kept

        kept = []
        for t in post_tasks:
            if should_skip_post(t, output_root):
                n_skipped += 1
                _announce_skip(t)
            else:
                kept.append(t)
        post_tasks = kept

    total = len(accel_tasks) + len(post_tasks) + n_skipped
    progress = Progress(total=total)
    progress.skipped = n_skipped
    stats["skipped"] = n_skipped
    errors = ErrorLog(output_root / "errors.log")

    def _consume_result(task: dict, r: dict) -> None:
        status = r.get("status", "failed")
        if status == "ok":
            key = "accel_ok" if task.get("kind") == "accel" else "post_ok"
            stats[key] += 1
            progress.done += 1
        elif status == "skipped":
            stats["skipped"] += 1
            progress.skipped += 1
        else:
            key = ("accel_failed" if task.get("kind") == "accel"
                   else "post_failed")
            stats[key] += 1
            progress.failed += 1
            errors.log(task, r.get("error", "?"), r.get("traceback"))

        progress.last_task = r.get("task_id", "?")
        progress.last_status = status
        progress.save(output_root / "progress.json")

        if on_result:
            on_result(r)

    def _task_cost(t: dict) -> float:
        """
        Грубая оценка стоимости задачи. Нужна для балансировки:
        тяжёлые задачи отправляем первыми, чтобы они распределились
        по всем воркерам, а не сгруппировались в одном чанке.
        """
        prec = t.get("precision", {}) or {}
        dps = int(prec.get("dps", 50) or 50)
        accel = t.get("accelerator", {}) or {}
        n_max = int(accel.get("n_max", 1000) or 1000)
        name = str(accel.get("type", ""))
        # Wynn ε — O(n²) по таблице, Aitken — O(n).
        factor = 4 if "wynn" in name else 1
        return float(dps) * float(n_max) * factor

    def _run_tasks(tasks: list[dict], worker_fn: Callable,
                   pool: ProcessPoolExecutor) -> bool:
        """Запускает список задач в готовом пуле."""
        if not tasks:
            return True

        # Тяжёлые — вперёд. Чанки получаются примерно равными
        # по стоимости, если задачи кластеризуются по имени.
        sorted_tasks = sorted(tasks, key=_task_cost, reverse=True)

        n = len(sorted_tasks)
        # Мелкие чанки = лучше балансировка. Оверхед одного submit
        # через ProcessPool — ~0.1 мс, что пренебрежимо на фоне
        # задачи в 100+ мс.
        # Целевое число чанков ≈ 4 × workers, минимум по 1 задаче.
        target_chunks = max(1, 4 * workers)
        chunk_size = max(1, (n + target_chunks - 1) // target_chunks)
        chunks = [sorted_tasks[i:i + chunk_size]
                  for i in range(0, n, chunk_size)]

        completed = 0
        stopped = False
        futures = {}
        for chunk in chunks:
            if is_stopped and is_stopped():
                stopped = True
                break
            fut = pool.submit(worker_fn, (chunk, str(output_root)))
            futures[fut] = chunk

        for fut in as_completed(futures):
            chunk = futures[fut]
            try:
                results = fut.result()
            except Exception as e:
                results = [{
                    "status": "failed",
                    "task_id": t.get("task_id", "?"),
                    "error": f"{type(e).__name__}: {e}",
                } for t in chunk]

            for task, r in zip(chunk, results):
                _consume_result(task, r)
                completed += 1
                if on_progress:
                    on_progress(
                        completed, total, r.get("task_id", "?"),
                    )

        return not stopped

    # ОДИН пул на весь прогон.
    pool = ProcessPoolExecutor(
        max_workers=workers,
        initializer=_worker_init,
    )
    try:
        ok = _run_tasks(accel_tasks, _accel_worker_chunk, pool)
        if not ok:
            stats["stopped"] = True
        else:
            ok = _run_tasks(post_tasks, _post_worker_chunk, pool)
            if not ok:
                stats["stopped"] = True
    finally:
        pool.shutdown(wait=True)

    stats["elapsed"] = time.time() - t0
    return stats