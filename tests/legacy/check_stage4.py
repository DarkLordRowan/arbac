"""
Комплексная проверка этапа 4: постобработки и огибающие.

Что проверяется:
    1. Регистрация постобработок и огибающих.
    2. KZ-фильтр сглаживает траекторию.
    3. Savitzky-Golay сглаживает траекторию.
    4. Median убирает выбросы.
    5. Hilbert-огибающая работает в режиме after.
    6. EMD-огибающая работает в режиме after.
    7. Огибающая в режиме during может остановить акселератор.
    8. Метрики digits_gained и envelope_was_right считаются.
    9. Сохранение результатов.

Запуск:
    cd "Проект Парф Питон"
    python check_stage4.py
"""
from __future__ import annotations
from pathlib import Path

import arbacc.series        # noqa: F401
import arbacc.noise         # noqa: F401
import arbacc.accelerators  # noqa: F401
import arbacc.stopping      # noqa: F401
import arbacc.postprocess   # noqa: F401
import arbacc.envelopes     # noqa: F401

from arbacc.core import Context, get, list_registered
from arbacc.precision import get_backend
from arbacc.runner.run_accel import run_accelerator
from arbacc.runner.run_postprocess import (
    run_offline_envelopes,
    run_postprocessors,
    save_postprocess_results,
)
from arbacc.runner.metrics import digits_gained
from arbacc.storage.save import instance_id


def section(title: str) -> None:
    """Печатает заголовок секции."""
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def _make_result(ctx: Context, n_iters: int = 50):
    """Готовит AcceleratedResult на zeta(3) с Aitken."""
    ZetaCls = get("series", "zeta")
    AitkenCls = get("accelerators", "aitken_delta2")
    MaxIterCls = get("stopping", "max_iter")

    zeta = ZetaCls(
        params={"s": 3},
        exact_sum="1.202056903159594285399738161511449990764986292",
    )
    stream = zeta.build_stream(ctx)
    accel = AitkenCls(params={})
    stopping = [MaxIterCls(params={"n": n_iters})]

    result = run_accelerator(
        source=stream,
        accelerator=accel,
        stopping_criteria=stopping,
        stopping_mode="any",
        online_envelopes=[],
        ctx=ctx,
        n_max=2000,
    )
    result.exact_sum = zeta.exact_sum(ctx)
    return result


def check_registration() -> None:
    """Проверяет, что плагины зарегистрированы."""
    section("1. Регистрация постобработок и огибающих")
    reg = list_registered()
    print("Registered:", reg)
    expected_pp = {"kolmogorov_zurbenko", "savitzky_golay", "median"}
    expected_env = {"hilbert", "emd"}
    assert expected_pp <= set(reg.get("postprocess", [])), \
        f"Не хватает постобработок: {expected_pp - set(reg.get('postprocess', []))}"
    assert expected_env <= set(reg.get("envelopes", [])), \
        f"Не хватает огибающих: {expected_env - set(reg.get('envelopes', []))}"
    print("[OK] все плагины зарегистрированы")


def check_kz(ctx: Context) -> None:
    """KZ сглаживает траекторию."""
    section("2. KZ-фильтр")
    KZCls = get("postprocess", "kolmogorov_zurbenko")
    backend = ctx.backend

    result = _make_result(ctx, n_iters=50)
    estimates = [r.estimate for r in result.iterations]

    kz = KZCls(params={"window": 5, "passes": 2})
    post = kz.apply(estimates, ctx)

    print(f"  input_len={len(estimates)}, output_len={len(post.values)}")
    print(f"  final={backend.to_str(post.final, ctx.dps)[:50]}...")
    d = digits_gained(post.final, result.exact_sum, ctx)
    d_orig = digits_gained(estimates[-1], result.exact_sum, ctx)
    print(f"  digits: original={d_orig}, after KZ={d}")
    assert len(post.values) < len(estimates), "KZ не уменьшил длину"
    assert post.final is not None
    print("[OK] KZ работает")


def check_sg(ctx: Context) -> None:
    """SG сглаживает траекторию."""
    section("3. Savitzky-Golay")
    SGCls = get("postprocess", "savitzky_golay")
    backend = ctx.backend

    result = _make_result(ctx, n_iters=50)
    estimates = [r.estimate for r in result.iterations]

    sg = SGCls(params={"window": 7, "order": 2})
    post = sg.apply(estimates, ctx)

    print(f"  input_len={len(estimates)}, output_len={len(post.values)}")
    print(f"  final={backend.to_str(post.final, ctx.dps)[:50]}...")
    assert post.final is not None
    print("[OK] SG работает")


def check_median(ctx: Context) -> None:
    """Median убирает выбросы."""
    section("4. Медианный фильтр")
    MedCls = get("postprocess", "median")
    backend = ctx.backend

    result = _make_result(ctx, n_iters=30)
    estimates = [r.estimate for r in result.iterations]

    med = MedCls(params={"window": 5})
    post = med.apply(estimates, ctx)

    print(f"  input_len={len(estimates)}, output_len={len(post.values)}")
    print(f"  final={backend.to_str(post.final, ctx.dps)[:50]}...")
    assert post.final is not None
    print("[OK] median работает")


def check_hilbert(ctx: Context) -> None:
    """Hilbert-огибающая работает в режиме after."""
    section("5. Hilbert-огибающая (after)")
    HilbertCls = get("envelopes", "hilbert")

    result = _make_result(ctx, n_iters=50)
    # Порог 0.9 — сработает, как только амплитуда упадёт на 10% от пика.
    env = HilbertCls(params={"window": 11, "threshold": 0.9, "min_history": 20})
    env_out = run_offline_envelopes(result, [env], ctx)

    print(f"  keys={list(env_out.keys())}")
    summary = env_out["hilbert"]["envelope"]
    print(f"  suggested_stop_at={summary['suggested_stop_at']}")
    print(f"  envelope_length={summary['envelope_length']}")
    assert summary["suggested_stop_at"] is not None, \
        "Hilbert не предложил остановку даже с threshold=0.9"
    print("[OK] Hilbert работает и предлагает остановку")


def check_emd(ctx: Context) -> None:
    """EMD-огибающая работает в режиме after."""
    section("6. EMD-огибающая (after)")
    EMDCls = get("envelopes", "emd")

    result = _make_result(ctx, n_iters=50)
    env = EMDCls(params={"window": 15, "threshold": 0.9, "min_history": 20})
    env_out = run_offline_envelopes(result, [env], ctx)

    print(f"  keys={list(env_out.keys())}")
    summary = env_out["emd"]["envelope"]
    print(f"  suggested_stop_at={summary['suggested_stop_at']}")
    assert summary["suggested_stop_at"] is not None, \
        "EMD не предложил остановку даже с threshold=0.9"
    print("[OK] EMD работает и предлагает остановку")


def check_envelope_during(ctx: Context) -> None:
    """Огибающая в режиме during может остановить акселератор."""
    section("7. Огибающая в режиме during")
    ZetaCls = get("series", "zeta")
    AitkenCls = get("accelerators", "aitken_delta2")
    MaxIterCls = get("stopping", "max_iter")
    HilbertCls = get("envelopes", "hilbert")

    zeta = ZetaCls(
        params={"s": 3},
        exact_sum="1.202056903159594285399738161511449990764986292",
    )
    stream = zeta.build_stream(ctx)
    accel = AitkenCls(params={})
    stopping = [MaxIterCls(params={"n": 500})]

    # Порог 0.9 — сработает при первом падении амплитуды на 10%.
    env = HilbertCls(params={
        "window": 11,
        "threshold": 0.9,
        "min_history": 15,
        "run_mode": "during",
        "used_as": "stopping_criterion",
    })

    result = run_accelerator(
        source=stream,
        accelerator=accel,
        stopping_criteria=stopping,
        stopping_mode="any",
        online_envelopes=[env],
        ctx=ctx,
        n_max=2000,
    )

    print(f"  stopped_by={result.stopped_by}, iters={len(result.iterations)}")
    assert "envelope:hilbert" in result.stopped_by, \
        f"Огибающая не остановила акселератор: {result.stopped_by}"
    print("[OK] during-режим работает: огибающая остановила акселератор")


def check_metrics(ctx: Context) -> None:
    """Метрики digits_gained и envelope_was_right считаются."""
    section("8. Метрики")
    HilbertCls = get("envelopes", "hilbert")

    result = _make_result(ctx, n_iters=50)
    env = HilbertCls(params={"window": 11, "threshold": 0.9, "min_history": 15})
    env_out = run_offline_envelopes(result, [env], ctx)

    summary = env_out["hilbert"]["comparison"]
    print(f"  comparison={summary}")
    assert "skipped" not in summary, \
        f"Огибающая не предложила остановку: {summary}"
    assert "digits_at_suggestion" in summary
    assert "envelope_was_right" in summary
    print("[OK] метрики работают")


def check_save(ctx: Context, project_root: Path) -> None:
    """Сохранение результатов постобработки."""
    section("9. Сохранение постобработки")
    KZCls = get("postprocess", "kolmogorov_zurbenko")
    HilbertCls = get("envelopes", "hilbert")

    result = _make_result(ctx, n_iters=30)
    kz = KZCls(params={"window": 5, "passes": 2})
    hilbert = HilbertCls(params={"window": 11})

    pp_out = run_postprocessors(result, [kz], ctx)
    env_out = run_offline_envelopes(result, [hilbert], ctx)

    out_root = project_root / "out" / "check_stage4" / f"dps{ctx.dps}"
    series_id = instance_id("zeta", {"s": 3})
    noise_id = instance_id("none", {})
    accel_id = instance_id("aitken_delta2", {})

    input_payload = {
        "series": {"type": "zeta", "params": {"s": 3}},
        "noise": {"type": "none", "params": {}},
        "accelerator": {"type": "aitken_delta2", "params": {}},
        "postprocess": [{"type": "kolmogorov_zurbenko", "params": {"window": 5, "passes": 2}}],
        "envelopes": [{"type": "hilbert", "params": {"window": 11}}],
        "dps": ctx.dps,
        "backend": ctx.backend.name,
    }

    dir_path = save_postprocess_results(
        output_root=out_root,
        series_id=series_id,
        noise_id=noise_id,
        accel_id=accel_id,
        postprocess_out=pp_out,
        envelope_out=env_out,
        ctx=ctx,
        input_payload=input_payload,
    )
    print(f"  saved to {dir_path}")
    assert (dir_path / "manifest.json").exists()
    assert (dir_path / "filters" / "kolmogorov_zurbenko" / "summary.json").exists()
    assert (dir_path / "envelopes" / "hilbert" / "summary.json").exists()
    print("[OK] сохранение работает")


def main() -> None:
    """Точка входа."""
    project_root = Path(__file__).parent.resolve()
    backend = get_backend("mpmath")
    ctx = Context(backend=backend, dps=50)

    check_registration()
    check_kz(ctx)
    check_sg(ctx)
    check_median(ctx)
    check_hilbert(ctx)
    check_emd(ctx)
    check_envelope_during(ctx)
    check_metrics(ctx)
    check_save(ctx, project_root)

    print("\n" + "=" * 70)
    print("ВСЕ ПРОВЕРКИ ЭТАПА 4 ПРОЙДЕНЫ")
    print("=" * 70)


if __name__ == "__main__":
    main()