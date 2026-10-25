"""
Главный цикл акселератора.

Зачем нужен:
    Связывает вместе Stream, Accelerator, StoppingCriterion и Envelope.
    Управляет дотягиванием источника, вызывает step, проверяет критерии,
    обрабатывает онлайн-огибающие, останавливается.

    Это единственное место, где акселератор "крутится". Всё остальное —
    подготовка входа и сохранение выхода.

Как расширять:
    Для новых режимов (например, чекпоинтов) — добавлять хуки сюда.
    Интерфейсы Accelerator/Stopping/Envelope не меняются.
"""

from __future__ import annotations
from typing import Any

from arbacc.core.accelerator import AcceleratorBase, AlgoState
from arbacc.core.context import Context
from arbacc.core.envelope import EnvelopeBase
from arbacc.core.result import AcceleratedResult, IterationRecord
from arbacc.core.stopping import StoppingBase
from arbacc.core.stream import Stream


def run_accelerator(
    source: Stream,
    accelerator: AcceleratorBase,
    stopping_criteria: list[StoppingBase],
    stopping_mode: str,
    online_envelopes: list[EnvelopeBase],
    ctx: Context,
    n_max: int,
) -> AcceleratedResult:
    """
    Прогоняет акселератор по источнику до срабатывания критериев.

    Принимает:
        source             — источник (series + noise)
        accelerator        — акселератор
        stopping_criteria  — список критериев
        stopping_mode      — "any" | "all"
        online_envelopes   — огибающие с run_mode="during"
        ctx                — контекст
        n_max              — максимальное число членов источника

    Возвращает:
        AcceleratedResult с траекторией и финальной оценкой.
    """
    state = AlgoState(iteration=0, estimate=None, history=[], extra={})
    records: list[IterationRecord] = []
    stopped_by = ""
    status = "ok"

    while True:
        need = accelerator.required_input(state)
        if need > n_max:
            stopped_by = f"n_max({n_max})"
            break

        # Дотягиваем источник.

        # Один шаг акселератора.
        try:
            source.extend_to(need - 1)
            state = accelerator.step(source, state, ctx)
        except Exception as e:
            status = "failed"
            stopped_by = f"exception: {type(e).__name__}"
            result = AcceleratedResult(
                accelerator=accelerator.name,
                params=dict(accelerator.params),
                iterations=records,
                estimate=records[-1].estimate if records else None,
                n_used=len(source),
                n_max=n_max,
                stopped_by=stopped_by,
                status=status,
                error=str(e),
            )
            return result

        records.append(IterationRecord(
            k=state.iteration - 1,
            estimate=state.estimate,
            n_used=need,
        ))

        # Проверяем критерии остановки.
        if _should_stop(stopping_criteria, stopping_mode, state, ctx):
            # reason берём у последнего, который сработал.
            for c in stopping_criteria:
                if c._reason:
                    stopped_by = c._reason
                    break
            break

        # Онлайн-огибающие.
        env_stopped = False
        for env in online_envelopes:
            env.push(state.estimate)
            if env.says_stop():
                stopped_by = f"envelope:{env.name}"
                env_stopped = True
                break
        if env_stopped:
            break

    estimate = records[-1].estimate if records else None
    result = AcceleratedResult(
        accelerator=accelerator.name,
        params=dict(accelerator.params),
        iterations=records,
        estimate=estimate,
        n_used=len(source),
        n_max=n_max,
        stopped_by=stopped_by,
        status=status,
    )

    # Записываем метаданные огибающих (для observer-режима).
    for env in online_envelopes:
        result.meta[f"envelope:{env.name}"] = env.result()

    return result


def _should_stop(
    criteria: list[StoppingBase],
    mode: str,
    state: AlgoState,
    ctx: Context,
) -> bool:
    """
    Проверяет, сработали ли критерии остановки.

    Принимает:
        criteria — список критериев
        mode     — "any" | "all"
        state    — состояние
        ctx      — контекст

    Возвращает:
        True, если нужно остановиться.

    Примечание:
        Каждый критерий сохраняет _reason при возврате True.
        Перед вызовом сбрасываем reason, чтобы не было stale.
    """
    if not criteria:
        return False
    results = []
    for c in criteria:
        c._reason = ""
        results.append(c.should_stop(state, ctx))
    if mode == "all":
        return all(results)
    return any(results)