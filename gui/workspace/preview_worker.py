"""
Фоновый расчёт задач для Visualise, с кэшем, отменой и прогрессом.

Ключевая деталь: post-задача пишется в ту же папку кэша, что и её
родительский accel. Иначе data_loader не найдёт postprocess рядом
с accel.
"""

from __future__ import annotations
import copy
import time
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from gui.common.log import get_logger
from gui.workspace.preview_cache import task_cache_dir, has_cached


class PreviewWorker(QThread):
    """Считает задачи в фоне, с кэшем, отменой и прогрессом."""

    finished = pyqtSignal(int, list)
    failed = pyqtSignal(int, str)
    progress = pyqtSignal(int, int, str, float, float)
    cancelled = pyqtSignal(int)

    def __init__(
        self,
        plan: dict,
        generation: int,
        max_n: int = 50,
        max_tasks: int = 8,
        max_dps: int = 200,
    ):
        super().__init__()
        self._accel_tasks = [
            copy.deepcopy(t) for t in plan.get("accel", [])[:max_tasks]
        ]
        selected_ids = {t["task_id"] for t in self._accel_tasks}
        self._post_tasks = [
            copy.deepcopy(t) for t in plan.get("post", [])
            if t.get("parent_task_id") in selected_ids
        ]
        self._gen = generation
        self._max_n = max_n
        self._max_dps = max_dps
        self._log = get_logger("preview")

    def run(self):
        """Основной метод потока."""
        try:
            from arbacc.runner.execute import execute_accel, execute_post
            from gui.view_mode.data_loader import list_accel_tasks

            if not self._accel_tasks:
                self.failed.emit(self._gen, "нет accel-задач")
                return

            # Обрезаем dps для preview.
            for task in self._accel_tasks + self._post_tasks:
                prec = task.get("precision", {})
                if isinstance(prec, dict):
                    dps = prec.get("dps")
                    if isinstance(dps, int) and dps > self._max_dps:
                        prec["dps"] = self._max_dps

            # ВАЖНО: обрезаем n_max ДО расчёта ключа кэша. Иначе
            # task_cache_key() считается по n_max из конфига, и после
            # смены N мы попадаем в старую запись кэша с прежним
            # (большим) числом итераций.
            for task in self._accel_tasks:
                accel = task.get("accelerator", {})
                if accel is not None:
                    try:
                        cur_n = int(accel.get("n_max", self._max_n))
                    except (TypeError, ValueError):
                        cur_n = self._max_n
                    accel["n_max"] = min(cur_n, self._max_n)

            parent_cache: dict[str, Path] = {}

            total = len(self._accel_tasks) + len(self._post_tasks)
            done = 0
            t0 = time.time()

            # 1. Accel-задачи.
            for task in self._accel_tasks:
                if self.isInterruptionRequested():
                    self.cancelled.emit(self._gen)
                    return

                done += 1
                tid = task.get("task_id", "?")
                self._emit_progress(done, total, tid, t0)

                cache_root = task_cache_dir(task)
                parent_cache[tid] = cache_root

                if has_cached(task):
                    continue

                cache_root.mkdir(parents=True, exist_ok=True)
                try:
                    r = execute_accel(task, cache_root)
                    if r.get("status") != "ok":
                        self._log.warning(
                            "accel FAILED: %s -> %s",
                            tid, r.get("error", "?"),
                        )
                except Exception:
                    self._log.exception("accel EXC: %s", tid)

            # 2. Post-задачи — в папку родителя.
            for task in self._post_tasks:
                if self.isInterruptionRequested():
                    self.cancelled.emit(self._gen)
                    return

                done += 1
                tid = task.get("task_id", "?")
                self._emit_progress(done, total, tid, t0)

                parent_id = task.get("parent_task_id")
                if parent_id not in parent_cache:
                    continue
                cache_root = parent_cache[parent_id]

                if has_cached_post_in(cache_root, task):
                    continue

                cache_root.mkdir(parents=True, exist_ok=True)
                try:
                    r = execute_post(task, cache_root)
                    if r.get("status") not in ("ok", "skipped"):
                        self._log.warning(
                            "post FAILED: %s -> %s",
                            tid, r.get("error", "?"),
                        )
                except Exception:
                    self._log.exception("post EXC: %s", tid)

            # 3. Разрешённые postprocess/envelopes в текущем плане.
            allowed_pp: set[str] = set()
            allowed_env: set[str] = set()
            for t in self._post_tasks:
                pp = t.get("postprocess")
                if pp is not None:
                    allowed_pp.add(pp["type"])
                env = t.get("envelope")
                if env is not None:
                    allowed_env.add(env["type"])

            # 4. Собираем AccelData из кэша + фильтруем.
            tasks_data = []
            for task in self._accel_tasks:
                if self.isInterruptionRequested():
                    self.cancelled.emit(self._gen)
                    return
                cache_root = parent_cache.get(task.get("task_id"))
                if not cache_root or not cache_root.exists():
                    continue
                found = list_accel_tasks(cache_root)
                if not found:
                    continue
                data = found[0]
                data.filters = {
                    k: v for k, v in data.filters.items()
                    if k in allowed_pp
                }
                data.envelopes = {
                    k: v for k, v in data.envelopes.items()
                    if k in allowed_env
                }
                data.envelope_values = {
                    k: v for k, v in data.envelope_values.items()
                    if k in allowed_env
                }
                data.envelope_upper = {
                    k: v for k, v in data.envelope_upper.items()
                    if k in allowed_env
                }
                data.envelope_lower = {
                    k: v for k, v in data.envelope_lower.items()
                    if k in allowed_env
                }
                data.envelope_indices = {
                    k: v for k, v in data.envelope_indices.items()
                    if k in allowed_env
                }
                tasks_data.append(data)

            if not tasks_data:
                self.failed.emit(self._gen, "preview: пустой результат")
                return
            self.finished.emit(self._gen, tasks_data)
        except Exception as e:
            import traceback
            self._log.error(
                "Preview crashed:\n%s", traceback.format_exc(),
            )
            self.failed.emit(
                self._gen,
                f"{type(e).__name__}: {e}",
            )

    def _emit_progress(self, done, total, task_id, t0):
        """Считает ETA и эмитит progress."""
        elapsed = time.time() - t0
        eta = 0.0
        if done > 0:
            avg = elapsed / done
            eta = avg * (total - done)
        self.progress.emit(done, total, task_id, elapsed, eta)


def has_cached_post_in(cache_root: Path, task: dict) -> bool:
    """
    Проверяет, есть ли КОНКРЕТНАЯ post-задача в кэше.

    Проверяется путь конкретного фильтра или огибающей, а не
    общий manifest.json.
    """
    ids = task.get("ids", {})
    sid = ids.get("series_id")
    nid = ids.get("noise_id")
    aid = ids.get("accel_id")
    if not (sid and nid and aid):
        return False

    base = cache_root / "postprocess" / sid / nid / aid

    pp = task.get("postprocess")
    if pp is not None:
        return (base / "filters" / pp["type"] / "summary.json").exists()

    env = task.get("envelope")
    if env is not None:
        return (base / "envelopes" / env["type"] / "summary.json").exists()

    return False