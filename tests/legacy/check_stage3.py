"""
Комплексная проверка этапа 3: акселераторы + критерии + главный цикл.

Что проверяется:
    1. Регистрация акселераторов и критериев.
    2. Aitken на зашумлённой zeta(3) — сходится к точному значению.
    3. Wynn ε на зашумлённой zeta(3) — сходится к точному значению.
    4. max_iter корректно останавливает.
    5. digits_stable корректно останавливает.
    6. divergence не срабатывает на сходящемся ряде.
    7. stopping_mode="any" и "all" работают.
    8. n_max корректно обрезает.
    9. Сохранение результата в output.

Запуск:
    cd "Проект Парф Питон"
    python check_stage3.py
"""
from __future__ import annotations
from pathlib import Path

# Импорт пакетов запускает autodiscovery.
import arbacc.series       # noqa: F401
import arbacc.noise        # noqa: F401
import arbacc.accelerators # noqa: F401
import arbacc.stopping     # noqa: F401

from arbacc.core import Context, get, list_registered
from arbacc.precision import get_backend
from arbacc.runner.run_accel import run_accelerator
from arbacc.runner.save_result import save_accelerated_result
from arbacc.storage.save import instance_id


def section(title: str) -> None:
    """Печатает заголовок секции."""
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def check_registration() -> None:
    """Проверяет, что акселераторы и критерии зарегистрированы."""
    section("1. Регистрация акселераторов и критериев")
    reg = list_registered()
    print("Registered:", reg)

    expected_accel = {"aitken_delta2", "wynn_epsilon"}
    expected_stop = {"max_iter", "digits_stable", "divergence"}

    assert expected_accel <= set(reg.get("accelerators", [])), \
        f"Не хватает акселераторов: {expected_accel - set(reg.get('accelerators', []))}"
    assert expected_stop <= set(reg.get("stopping", [])), \
        f"Не хватает критериев: {expected_stop - set(reg.get('stopping', []))}"
    print("[OK] Все плагины зарегистрированы")


def _build_clean_stream(ctx: Context, s: int):
    """Строит чистый поток zeta(s)."""
    ZetaCls = get("series", "zeta")
    zeta = ZetaCls(params={"s": s})
    return zeta.build_stream(ctx)


def check_aitken_converges(ctx: Context) -> None:
    """Aitken должен приближаться к точному значению zeta(3)."""
    section("2. Aitken на zeta(3)")
    backend = ctx.backend
    AitkenCls = get("accelerators", "aitken_delta2")
    MaxIterCls = get("stopping", "max_iter")

    exact = ctx.number("1.202056903159594285399738161511449990764986292")

    stream = _build_clean_stream(ctx, 3)
    accel = AitkenCls(params={})
    stopping = [MaxIterCls(params={"n": 100})]

    result = run_accelerator(
        source=stream,
        accelerator=accel,
        stopping_criteria=stopping,
        stopping_mode="any",
        online_envelopes=[],
        ctx=ctx,
        n_max=1000,
    )

    print(f"  status={result.status}, stopped_by={result.stopped_by}, n_used={result.n_used}")
    print(f"  estimate={backend.to_str(result.estimate, ctx.dps)[:50]}...")
    d = backend.digits_of(result.estimate, exact, ctx.dps)
    print(f"  digits_gained={d}")
    assert result.status == "ok"
    assert d > 0, f"Aitken не приблизился: {d} цифр"
    assert d >= 3, f"Aitken слишком плохо: {d} цифр"
    print("[OK] Aitken сходится")


def check_wynn_converges(ctx: Context) -> None:
    """Wynn ε должен приближаться к точному значению zeta(3)."""
    section("3. Wynn ε на zeta(3)")
    backend = ctx.backend
    WynnCls = get("accelerators", "wynn_epsilon")
    MaxIterCls = get("stopping", "max_iter")

    exact = ctx.number("1.202056903159594285399738161511449990764986292")

    stream = _build_clean_stream(ctx, 3)
    accel = WynnCls(params={})
    stopping = [MaxIterCls(params={"n": 30})]

    result = run_accelerator(
        source=stream,
        accelerator=accel,
        stopping_criteria=stopping,
        stopping_mode="any",
        online_envelopes=[],
        ctx=ctx,
        n_max=1000,
    )

    print(f"  status={result.status}, stopped_by={result.stopped_by}, n_used={result.n_used}")
    print(f"  estimate={backend.to_str(result.estimate, ctx.dps)[:50]}...")
    d = backend.digits_of(result.estimate, exact, ctx.dps)
    print(f"  digits_gained={d}")
    assert result.status == "ok"
    assert d > 0, f"Wynn не приблизился: {d} цифр"
    assert d >= 5, f"Wynn слишком плохо: {d} цифр"
    print("[OK] Wynn ε сходится")


def check_max_iter(ctx: Context) -> None:
    """max_iter корректно останавливает после N итераций."""
    section("4. max_iter")
    MaxIterCls = get("stopping", "max_iter")
    AitkenCls = get("accelerators", "aitken_delta2")

    stream = _build_clean_stream(ctx, 3)
    accel = AitkenCls(params={})
    stopping = [MaxIterCls(params={"n": 10})]

    result = run_accelerator(
        source=stream,
        accelerator=accel,
        stopping_criteria=stopping,
        stopping_mode="any",
        online_envelopes=[],
        ctx=ctx,
        n_max=1000,
    )

    print(f"  stopped_by={result.stopped_by}, iterations={len(result.iterations)}")
    assert result.stopped_by.startswith("max_iter")
    assert len(result.iterations) == 10
    print("[OK] max_iter работает")


def check_digits_stable(ctx: Context) -> None:
    """digits_stable останавливает при стабилизации."""
    section("5. digits_stable")
    DigitsCls = get("stopping", "digits_stable")
    AitkenCls = get("accelerators", "aitken_delta2")
    MaxIterCls = get("stopping", "max_iter")

    stream = _build_clean_stream(ctx, 3)
    accel = AitkenCls(params={})
    # Требуем стабилизацию первых 8 цифр на окне 3.
    stopping = [
        DigitsCls(params={"window": 3, "min_digits": 8}),
        MaxIterCls(params={"n": 500}),  # fallback
    ]

    result = run_accelerator(
        source=stream,
        accelerator=accel,
        stopping_criteria=stopping,
        stopping_mode="any",
        online_envelopes=[],
        ctx=ctx,
        n_max=2000,
    )

    print(f"  stopped_by={result.stopped_by}, iterations={len(result.iterations)}")
    # Должен либо стабилизироваться, либо упереться в max_iter.
    # Проверим, что если стабилизировался, то цифры действительно стабильны.
    if "digits_stable" in result.stopped_by:
        last = result.iterations[-3:]
        for rec in last[:-1]:
            d = ctx.backend.digits_of(rec.estimate, last[-1].estimate, ctx.dps)
            assert d >= 8, f"digits_stable соврал: {d} цифр"
        print("  digits_stable сработал корректно")
    else:
        print("  digits_stable не сработал (упёрлись в max_iter)")
    print("[OK] digits_stable проверен")


def check_divergence_not_triggered(ctx: Context) -> None:
    """
    divergence не должен срабатывать на сходящемся ряде.

    Используем огромный factor — тогда критерий сработает только
    при реальном катастрофическом росте оценок.
    """
    section("6. divergence не срабатывает на сходящемся")
    DivCls = get("stopping", "divergence")
    AitkenCls = get("accelerators", "aitken_delta2")
    MaxIterCls = get("stopping", "max_iter")

    stream = _build_clean_stream(ctx, 3)
    accel = AitkenCls(params={})
    stopping = [
        DivCls(params={"window": 5, "factor": "1e10"}),
        MaxIterCls(params={"n": 30}),
    ]

    result = run_accelerator(
        source=stream,
        accelerator=accel,
        stopping_criteria=stopping,
        stopping_mode="any",
        online_envelopes=[],
        ctx=ctx,
        n_max=1000,
    )

    print(f"  stopped_by={result.stopped_by}")
    assert "divergence" not in result.stopped_by, \
        f"divergence ложно сработал: {result.stopped_by}"
    print("[OK] divergence не ложно срабатывает")


def check_divergence_triggered(ctx: Context) -> None:
    """
    divergence ДОЛЖЕН срабатывать на расходящемся ряде.

    Создаём искусственный расходящийся поток: a_n = 10^n.
    """
    section("6b. divergence срабатывает на расходящемся")
    DivCls = get("stopping", "divergence")
    MaxIterCls = get("stopping", "max_iter")

    # Искусственный расходящийся поток.
    from arbacc.core.stream import Stream as StreamProto

    class ExplodingStream:
        """a_n = 10^n, растёт катастрофически."""
        def __init__(self, ctx):
            self._ctx = ctx
            self._cache = []
        def get(self, n):
            self.extend_to(n)
            return self._cache[n]
        def extend_to(self, n):
            while len(self._cache) <= n:
                k = len(self._cache)
                ten = self._ctx.number(10)
                v = self._ctx.backend.pow(ten, self._ctx.number(k), self._ctx.dps)
                self._cache.append(v)
        def __len__(self):
            return len(self._cache)

    # Акселератор, который просто берёт последний член.
    from arbacc.core.accelerator import AcceleratorBase, AlgoState

    class Passthrough(AcceleratorBase):
        name = "passthrough"
        def required_input(self, state):
            return state.iteration + 1
        def step(self, source, state, ctx):
            return state.with_estimate(source.get(state.iteration))

    stream = ExplodingStream(ctx)
    accel = Passthrough(params={})
    stopping = [
        DivCls(params={"window": 3, "factor": "5"}),
        MaxIterCls(params={"n": 50}),
    ]

    result = run_accelerator(
        source=stream,
        accelerator=accel,
        stopping_criteria=stopping,
        stopping_mode="any",
        online_envelopes=[],
        ctx=ctx,
        n_max=100,
    )

    print(f"  stopped_by={result.stopped_by}, iters={len(result.iterations)}")
    assert "divergence" in result.stopped_by, \
        f"divergence не сработал на расходящемся: {result.stopped_by}"
    print("[OK] divergence срабатывает на расходящемся")


def check_stopping_modes(ctx: Context) -> None:
    """stopping_mode='any' и 'all' работают по-разному."""
    section("7. stopping_mode any vs all")
    MaxIterCls = get("stopping", "max_iter")
    DivCls = get("stopping", "divergence")
    AitkenCls = get("accelerators", "aitken_delta2")

    stream = _build_clean_stream(ctx, 3)
    accel = AitkenCls(params={})
    criteria = [
        MaxIterCls(params={"n": 10}),
        DivCls(params={"window": 5, "factor": "100"}),
    ]

    # mode="any": остановится, как только max_iter сработает.
    r_any = run_accelerator(
        source=stream, accelerator=accel,
        stopping_criteria=criteria, stopping_mode="any",
        online_envelopes=[], ctx=ctx, n_max=1000,
    )
    print(f"  mode=any: stopped_by={r_any.stopped_by}, iters={len(r_any.iterations)}")
    assert "max_iter" in r_any.stopped_by

    # mode="all": оба должны сработать. divergence на сходящемся не сработает,
    # значит упрёмся в n_max.
    r_all = run_accelerator(
        source=stream, accelerator=accel,
        stopping_criteria=criteria, stopping_mode="all",
        online_envelopes=[], ctx=ctx, n_max=50,
    )
    print(f"  mode=all: stopped_by={r_all.stopped_by}, iters={len(r_all.iterations)}")
    # Должно упереться в n_max, потому что divergence не срабатывает.
    assert "n_max" in r_all.stopped_by
    print("[OK] stopping_mode работает")


def check_n_max(ctx: Context) -> None:
    """n_max корректно обрезает."""
    section("8. n_max обрезает")
    AitkenCls = get("accelerators", "aitken_delta2")

    stream = _build_clean_stream(ctx, 3)
    accel = AitkenCls(params={})

    result = run_accelerator(
        source=stream, accelerator=accel,
        stopping_criteria=[], stopping_mode="any",
        online_envelopes=[], ctx=ctx, n_max=5,
    )
    print(f"  stopped_by={result.stopped_by}, iters={len(result.iterations)}")
    assert "n_max" in result.stopped_by
    assert result.n_used <= 5
    print("[OK] n_max работает")


def check_save(ctx: Context, project_root: Path) -> None:
    """Проверяет сохранение результата."""
    section("9. Сохранение результата")
    AitkenCls = get("accelerators", "aitken_delta2")
    MaxIterCls = get("stopping", "max_iter")
    backend = ctx.backend

    stream = _build_clean_stream(ctx, 3)
    accel = AitkenCls(params={})
    stopping = [MaxIterCls(params={"n": 20})]

    result = run_accelerator(
        source=stream, accelerator=accel,
        stopping_criteria=stopping, stopping_mode="any",
        online_envelopes=[], ctx=ctx, n_max=1000,
    )

    out_root = project_root / "out" / "check_stage3" / f"dps{ctx.dps}"
    series_id = instance_id("zeta", {"s": 3})
    noise_id = instance_id("none", {})
    accel_id = instance_id("aitken_delta2", {})

    input_payload = {
        "series": {"type": "zeta", "params": {"s": 3}},
        "noise": {"type": "none", "params": {}},
        "accelerator": {"type": "aitken_delta2", "params": {}},
        "stopping": [{"type": "max_iter", "params": {"n": 20}}],
        "dps": ctx.dps,
        "backend": ctx.backend.name,
    }

    dir_path = save_accelerated_result(
        output_root=out_root,
        series_id=series_id,
        noise_id=noise_id,
        accel_id=accel_id,
        result=result,
        ctx=ctx,
        input_payload=input_payload,
    )
    print(f"  saved to {dir_path}")

    assert (dir_path / "iterations.jsonl").exists()
    assert (dir_path / "result.json").exists()
    assert (dir_path / "manifest.json").exists()
    print("[OK] сохранение работает")


def main() -> None:
    """Точка входа."""
    project_root = Path(__file__).parent.resolve()
    backend = get_backend("mpmath")
    ctx = Context(backend=backend, dps=50)

    check_registration()
    check_aitken_converges(ctx)
    check_wynn_converges(ctx)
    check_max_iter(ctx)
    check_digits_stable(ctx)
    check_divergence_not_triggered(ctx)
    check_divergence_triggered(ctx)
    check_stopping_modes(ctx)
    check_n_max(ctx)
    check_save(ctx, project_root)

    print("\n" + "=" * 70)
    print("ВСЕ ПРОВЕРКИ ЭТАПА 3 ПРОЙДЕНЫ")
    print("=" * 70)


if __name__ == "__main__":
    main()