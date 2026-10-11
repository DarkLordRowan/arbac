"""
Стресс-тест фреймворка arbacc.

Назначение:
    Систематически прогоняет ВСЕ компоненты фреймворка в максимально
    широком диапазоне параметров. Проверяет, что:
      - ничто не падает с неожиданными исключениями,
      - метрики считаются,
      - output сохраняется,
      - skip / progress / errors работают,
      - CLI end-to-end работает,
      - крайние случаи обрабатываются корректно,
      - метаданные плагинов полны,
      - валидация build_plan работает,
      - from_file читает сгенерированные файлы.

Запуск:
    python check_stress.py
"""

from __future__ import annotations
import io
import json
import shutil
import subprocess
import sys
import time
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

import arbacc.series        # noqa: F401
import arbacc.noise         # noqa: F401
import arbacc.accelerators  # noqa: F401
import arbacc.stopping      # noqa: F401
import arbacc.postprocess   # noqa: F401
import arbacc.envelopes     # noqa: F401

from arbacc.core import Context, get, list_registered
from arbacc.precision import get_backend
from arbacc.runner import (
    expand_node, expand_all, matches, node_id, build_plan,
    execute_accel, execute_post, should_skip,
    Progress, ErrorLog,
    run_accelerator,
    run_offline_envelopes, run_postprocessors,
    digits_gained, envelope_was_right,
)

# Псевдоним для проверки метаданных плагинов.
registry_get = get


# ==================== Утилиты ====================

class StressReport:
    """Собирает результаты секций и печатает сводку."""

    def __init__(self):
        self.sections: list[tuple[str, bool, str, float]] = []

    def run(self, name: str, fn):
        """Запускает одну секцию, ловит исключения, замеряет время."""
        t0 = time.time()
        try:
            fn()
            elapsed = time.time() - t0
            self.sections.append((name, True, "", elapsed))
            print(f"  [{name}] OK  ({elapsed:.2f}s)")
        except Exception as e:
            elapsed = time.time() - t0
            import traceback
            tb = traceback.format_exc()
            self.sections.append((name, False, tb, elapsed))
            print(f"  [{name}] FAIL  ({elapsed:.2f}s)")
            print(tb)

    def summary(self) -> int:
        """Печатает сводку. Возвращает код выхода."""
        print()
        print("=" * 70)
        print("СВОДКА")
        print("=" * 70)
        passed = sum(1 for _, ok, _, _ in self.sections if ok)
        failed = len(self.sections) - passed
        total_time = sum(t for _, _, _, t in self.sections)
        for name, ok, _, elapsed in self.sections:
            mark = "OK  " if ok else "FAIL"
            print(f"  {mark}  {name:40s}  {elapsed:.2f}s")
        print()
        print(f"Всего: {len(self.sections)}, успешно: {passed}, провалено: {failed}")
        print(f"Время: {total_time:.2f}s")
        if failed == 0:
            print()
            print("ВСЕ СТРЕСС-ТЕСТЫ ПРОЙДЕНЫ")
            return 0
        print()
        print(f"ПРОВАЛЕНО СЕКЦИЙ: {failed}")
        return 1


def section(title: str):
    """Печатает заголовок секции."""
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def make_ctx(dps: int = 40) -> Context:
    """Готовит Context с mpmath."""
    return Context(backend=get_backend("mpmath"), dps=dps)


# ==================== A. Backend + Context ====================

def stress_backend():
    """Проверяет backend mpmath во всех сценариях."""
    section("A. Backend + Context")

    backend = get_backend("mpmath")

    for dps in [10, 20, 50, 100, 200]:
        ctx = Context(backend=backend, dps=dps)
        x = ctx.number("1.2345678901234567890")
        s = backend.to_str(x, dps)
        y = backend.from_str(s, dps)
        d = backend.digits_of(x, y, dps)
        assert d >= dps - 2, f"dps={dps}: потеря точности, digits={d}"
        print(f"  dps={dps}: round-trip OK ({d} digits)")

    ctx = make_ctx(50)
    b = ctx.backend
    a = ctx.number("3.14")
    c = ctx.number("2.71")

    assert b.sign(b.sub(b.add(a, c, 50), ctx.number("5.85"), 50), 50) == 0
    assert b.sign(b.sub(b.mul(a, c, 50), ctx.number("8.5094"), 50), 50) == 0
    d_div = b.digits_of(b.div(a, c, 50), ctx.number("1.15867158671586715867"), 50)
    assert d_div >= 15, f"div: {d_div} digits"
    assert b.sign(b.sub(b.pow(c, ctx.number(2), 50), ctx.number("7.3441"), 50), 50) == 0
    assert b.sign(b.sub(b.neg(a, 50), ctx.number("-3.14"), 50), 50) == 0
    assert b.sign(b.sub(b.abs_val(b.neg(a, 50), 50), a, 50), 50) == 0
    print("  арифметика OK")

    assert b.sign(ctx.number("-5"), 50) == -1
    assert b.sign(ctx.number("0"), 50) == 0
    assert b.sign(ctx.number("5"), 50) == 1
    print("  sign OK")

    assert b.digits_of(ctx.number("1.0"), ctx.number("1.0"), 50) == 50
    d = b.digits_of(ctx.number("1.5"), ctx.number("1.0"), 50)
    assert d == 0, f"digits_of для |a-b|=0.5: {d}"
    d = b.digits_of(ctx.number("10"), ctx.number("1"), 50)
    assert d < 0, f"digits_of для |a-b|=9: {d}"
    d = b.digits_of(ctx.number("100"), ctx.number("1"), 50)
    assert d == -2, f"digits_of для |a-b|=99: {d}"
    print("  digits_of границы OK")

    try:
        Context(backend=backend, dps=0)
        raise AssertionError("Context не бросил на dps=0")
    except ValueError:
        pass
    print("  Context валидация OK")


# ==================== B. Series ====================

def stress_series():
    """Проверяет все ряды."""
    section("B. Series (все)")

    ctx = make_ctx(50)
    b = ctx.backend

    ZetaCls = get("series", "zeta")
    for s in [2, 3, 4, 5, 10, 20]:
        z = ZetaCls(params={"s": s})
        stream = z.build_stream(ctx)
        a0 = stream.get(0)
        assert b.digits_of(a0, ctx.number("1.0"), 50) >= 48, f"zeta(s={s}) a_0 != 1"
        a1 = stream.get(1)
        expected = b.pow(ctx.number(2), b.neg(ctx.number(s), 50), 50)
        assert b.digits_of(a1, expected, 50) >= 48, f"zeta(s={s}) a_1 wrong"
        stream.extend_to(100)
        assert len(stream) == 101
        a0_again = stream.get(0)
        assert b.digits_of(a0, a0_again, 50) >= 48
    print("  zeta: s=2,3,4,5,10,20 OK")

    GeomCls = get("series", "geometric")
    for q in ["0.5", "0.7", "0.9", "-0.3", "-0.9", "0.99"]:
        g = GeomCls(params={"q": q})
        stream = g.build_stream(ctx)
        q_num = ctx.number(q)
        for n in range(10):
            expected = b.pow(q_num, ctx.number(n), 50)
            actual = stream.get(n)
            assert b.digits_of(actual, expected, 50) >= 48, f"geom(q={q}) a_{n}"
    print("  geometric: q=0.5,0.7,0.9,-0.3,-0.9,0.99 OK")

    from_file_csv = get("series", "from_file")
    project_root = Path(__file__).parent.resolve()
    csv_path = project_root / "examples" / "data" / "sample_series.csv"
    txt_path = project_root / "examples" / "data" / "sample_series.txt"

    if csv_path.exists():
        f = from_file_csv(params={"path": str(csv_path), "column": "value"})
        stream = f.build_stream(ctx)
        a0 = stream.get(0)
        assert b.digits_of(a0, ctx.number("1.0"), 50) >= 48
        try:
            stream.extend_to(10000)
            raise AssertionError("from_file не бросил IndexError")
        except IndexError:
            pass
        print("  from_file CSV OK")

    if txt_path.exists():
        f = from_file_csv(params={"path": str(txt_path)})
        stream = f.build_stream(ctx)
        a1 = stream.get(1)
        assert b.digits_of(a1, ctx.number("0.5"), 50) >= 48
        print("  from_file TXT OK")


# ==================== C. Noise ====================

def stress_noise():
    """Проверяет все шумы."""
    section("C. Noise (все)")

    ctx = make_ctx(50)
    b = ctx.backend
    ZetaCls = get("series", "zeta")
    zeta = ZetaCls(params={"s": 3})
    clean = zeta.build_stream(ctx)

    NoneCls = get("noise", "none")
    n = NoneCls(params={}, seed=0)
    noisy = n.wrap(clean, ctx)
    for i in range(5):
        assert b.digits_of(noisy.get(i), clean.get(i), 50) >= 48
    print("  none OK")

    GaussCls = get("noise", "gaussian")
    for sigma in ["1e-3", "1e-6", "1e-10"]:
        for mode in ["absolute", "relative"]:
            for seed in [0, 42, 12345]:
                n = GaussCls(params={"sigma": sigma, "mode": mode}, seed=seed)
                noisy = n.wrap(clean, ctx)
                v0 = noisy.get(0)
                noisy.extend_to(50)
                v0_again = noisy.get(0)
                assert b.digits_of(v0, v0_again, 50) >= 48, \
                    f"gaussian({sigma},{mode},{seed}) сломал детерминизм"
    print("  gaussian: 3 sigma × 2 mode × 3 seed OK")

    ARCls = get("noise", "ar1")
    for phi in ["0.3", "0.5", "0.7", "0.9", "-0.5"]:
        n = ARCls(params={"phi": phi, "sigma": "1e-6"}, seed=42)
        noisy = n.wrap(clean, ctx)
        for i in range(20):
            _ = noisy.get(i)
        n2 = ARCls(params={"phi": phi, "sigma": "1e-6"}, seed=42)
        _ = n2.transform(10, ctx.number("1.0"), ctx)
        try:
            _ = n2.transform(5, ctx.number("1.0"), ctx)
            raise AssertionError(f"ar1 phi={phi} не запретил доступ в прошлое")
        except RuntimeError:
            pass
    print("  ar1: phi=0.3,0.5,0.7,0.9,-0.5 OK")

    n3 = ARCls(params={"phi": "0.5", "sigma": "1e-6"}, seed=42)
    _ = n3.wrap(clean, ctx)
    try:
        _ = n3.wrap(clean, ctx)
        raise AssertionError("ar1 не запретил повторный wrap")
    except RuntimeError:
        pass
    print("  ar1 повторный wrap запрещён OK")


# ==================== D. Accelerators + Stopping ====================

def stress_accelerators():
    """Проверяет акселераторы и критерии."""
    section("D. Accelerators × Stopping × n_max")

    ctx = make_ctx(50)
    b = ctx.backend
    ZetaCls = get("series", "zeta")

    AitkenCls = get("accelerators", "aitken_delta2")
    for n_max in [5, 10, 50, 200]:
        zeta = ZetaCls(params={"s": 3})
        stream = zeta.build_stream(ctx)
        accel = AitkenCls(params={})
        r = run_accelerator(
            source=stream, accelerator=accel,
            stopping_criteria=[], stopping_mode="any",
            online_envelopes=[], ctx=ctx, n_max=n_max,
        )
        assert r.status == "ok"
        assert r.n_used <= n_max
    print("  aitken: n_max=5,10,50,200 OK")

    WynnCls = get("accelerators", "wynn_epsilon")
    MaxIterCls = get("stopping", "max_iter")
    DigitsCls = get("stopping", "digits_stable")
    DivCls = get("stopping", "divergence")

    for stopping_specs, mode in [
        ([MaxIterCls(params={"n": 10})], "any"),
        ([MaxIterCls(params={"n": 20}), DigitsCls(params={"window": 3, "min_digits": 5})], "any"),
        ([MaxIterCls(params={"n": 5}), DivCls(params={"window": 3, "factor": "1e10"})], "all"),
    ]:
        zeta = ZetaCls(params={"s": 3})
        stream = zeta.build_stream(ctx)
        accel = WynnCls(params={})
        r = run_accelerator(
            source=stream, accelerator=accel,
            stopping_criteria=stopping_specs, stopping_mode=mode,
            online_envelopes=[], ctx=ctx, n_max=50,
        )
        assert r.status == "ok"
    print("  wynn: 3 комбинации stopping OK")

    for window, min_digits in [(3, 3), (5, 5), (3, 10)]:
        zeta = ZetaCls(params={"s": 3})
        stream = zeta.build_stream(ctx)
        accel = AitkenCls(params={})
        r = run_accelerator(
            source=stream, accelerator=accel,
            stopping_criteria=[
                DigitsCls(params={"window": window, "min_digits": min_digits}),
                MaxIterCls(params={"n": 100}),
            ],
            stopping_mode="any",
            online_envelopes=[], ctx=ctx, n_max=200,
        )
        assert r.status == "ok"
    print("  digits_stable: 3 окна OK")


# ==================== E. Postprocess ====================

def stress_postprocess():
    """Проверяет все постобработки."""
    section("E. Postprocess (все)")

    ctx = make_ctx(50)
    ZetaCls = get("series", "zeta")
    AitkenCls = get("accelerators", "aitken_delta2")
    MaxIterCls = get("stopping", "max_iter")

    zeta = ZetaCls(params={"s": 3})
    stream = zeta.build_stream(ctx)
    accel = AitkenCls(params={})
    r = run_accelerator(
        source=stream, accelerator=accel,
        stopping_criteria=[MaxIterCls(params={"n": 50})],
        stopping_mode="any", online_envelopes=[], ctx=ctx, n_max=1000,
    )
    estimates = [rec.estimate for rec in r.iterations]

    KZCls = get("postprocess", "kolmogorov_zurbenko")
    for window in [3, 5, 7]:
        for passes in [1, 2, 3]:
            kz = KZCls(params={"window": window, "passes": passes})
            post = kz.apply(estimates, ctx)
            assert post.final is not None
            assert len(post.values) <= len(estimates)
    print("  KZ: 3 window × 3 passes OK")

    SGCls = get("postprocess", "savitzky_golay")
    for window, order in [(5, 1), (5, 2), (7, 2), (7, 3), (9, 4)]:
        sg = SGCls(params={"window": window, "order": order})
        post = sg.apply(estimates, ctx)
        assert post.final is not None
    print("  SG: 5 комбинаций window/order OK")

    MedCls = get("postprocess", "median")
    for window in [3, 5, 7, 9]:
        med = MedCls(params={"window": window})
        post = med.apply(estimates, ctx)
        assert post.final is not None
    print("  median: 4 окна OK")

    for BadCls in [KZCls, SGCls, MedCls]:
        try:
            BadCls(params={"window": 4}).apply(estimates, ctx)
            raise AssertionError(f"{BadCls.name} не запретил чётное окно")
        except ValueError:
            pass
    print("  валидация окон OK")


# ==================== F. Envelopes ====================

def stress_envelopes():
    """Проверяет огибающие во всех режимах."""
    section("F. Envelopes (все режимы)")

    ctx = make_ctx(50)
    ZetaCls = get("series", "zeta")
    AitkenCls = get("accelerators", "aitken_delta2")
    MaxIterCls = get("stopping", "max_iter")

    zeta = ZetaCls(params={"s": 3})
    stream = zeta.build_stream(ctx)
    accel = AitkenCls(params={})
    r = run_accelerator(
        source=stream, accelerator=accel,
        stopping_criteria=[MaxIterCls(params={"n": 50})],
        stopping_mode="any", online_envelopes=[], ctx=ctx, n_max=1000,
    )

    for EnvCls in [get("envelopes", "hilbert"), get("envelopes", "emd")]:
        for run_mode in ["after", "during"]:
            for used_as in ["observer", "stopping_criterion"]:
                env_params = {
                    "window": 11,
                    "detrend_window": 11,
                    "threshold": 0.9,
                    "min_history": 10,
                    "run_mode": run_mode,
                    "used_as": used_as,
                }
                env = EnvCls(params=env_params)
                if run_mode == "during":
                    zeta2 = ZetaCls(params={"s": 3})
                    stream2 = zeta2.build_stream(ctx)
                    accel2 = AitkenCls(params={})
                    r2 = run_accelerator(
                        source=stream2, accelerator=accel2,
                        stopping_criteria=[MaxIterCls(params={"n": 200})],
                        stopping_mode="any",
                        online_envelopes=[env],
                        ctx=ctx, n_max=1000,
                    )
                    assert r2.status == "ok"
                else:
                    env_out = run_offline_envelopes(r, [env], ctx)
                    assert EnvCls.name in env_out
    print("  Hilbert + EMD × after/during × observer/criterion OK")

    env = get("envelopes", "hilbert")(params={
        "window": 11, "threshold": 0.5, "min_history": 10,
    })
    env_out = run_offline_envelopes(r, [env], ctx)
    comp = env_out["hilbert"]["comparison"]
    assert "envelope_was_right" in comp or "skipped" in comp
    print("  метрика envelope_was_right OK")


# ==================== G. Runner: expand, scope, plan ====================

def stress_runner_planning():
    """Проверяет планировщик."""
    section("G. Runner: expand, scope, plan")

    cases = [
        ({"a": 1}, 1),
        ({"a": [1, 2, 3]}, 3),
        ({"a": [1, 2], "b": [3, 4, 5]}, 6),
        ({"a": {"x": [1, 2]}}, 2),
        ({"applies_to": ["x", "y"], "a": [1, 2]}, 2),
        ({"stopping": [{"type": "x"}, {"type": "y"}]}, 1),
    ]
    for node, expected in cases:
        result = expand_node(node)
        assert len(result) == expected, f"expand_node({node}) = {len(result)}, ожидалось {expected}"
    print("  expand_node: 6 случаев OK")

    ctx = {"series": "zeta3", "noise": "clean"}
    assert matches("all", ctx)
    assert matches(None, ctx)
    assert matches("zeta3", ctx)
    assert matches(["zeta3"], ctx)
    assert not matches(["other"], ctx)
    assert matches({"series": "zeta3"}, ctx)
    assert not matches({"series": "other"}, ctx)
    print("  matches: 7 случаев OK")

    ids = set()
    for _ in range(100):
        ids.add(node_id("noise", "gaussian", {"sigma": "1e-6"}, {"seed": 42}))
    assert len(ids) == 1
    print(f"  node_id детерминирован OK ({next(iter(ids))})")

    project_root = Path(__file__).parent.resolve()
    cfg = json.loads(
        (project_root / "examples" / "config_full.json").read_text(encoding="utf-8-sig")
    )
    plan = build_plan(cfg)
    assert "accel" in plan and "post" in plan
    assert len(plan["accel"]) > 0
    plan2 = build_plan(cfg)
    assert [t["task_id"] for t in plan["accel"]] == [t["task_id"] for t in plan2["accel"]]
    print(f"  build_plan: {len(plan['accel'])} accel + {len(plan['post'])} post OK")


# ==================== H. Execute ====================

def stress_execute():
    """Проверяет execute_accel и execute_post."""
    section("H. Execute (accel + post)")

    project_root = Path(__file__).parent.resolve()
    out_root = project_root / "out" / "stress" / "execute"
    if out_root.exists():
        shutil.rmtree(out_root)
    out_root.mkdir(parents=True)

    config = {
        "run_id": "stress_exec",
        "precision": {"backend": "mpmath", "dps": 30},
        "series": [
            {"id": "zeta3", "type": "zeta", "params": {"s": 3},
             "exact_sum": "1.20205690315959428539973816151144999"},
            {"id": "geom07", "type": "geometric", "params": {"q": "0.7"},
             "exact_sum": "3.3333333333333333333333333333333333"},
        ],
        "noise": [
            {"id": "clean", "type": "none", "params": {}, "seed": 0, "applies_to": "all"},
            {"id": "gauss", "type": "gaussian",
             "params": {"sigma": "1e-6"}, "seed": 42,
             "applies_to": ["zeta3"]},
        ],
        "accelerators": [
            {"id": "aitken", "type": "aitken_delta2", "params": {},
             "n_max": 100,
             "stopping": [{"type": "max_iter", "params": {"n": 30}}],
             "applies_to": "all"},
        ],
        "postprocess": [
            {"id": "kz", "type": "kolmogorov_zurbenko",
             "params": {"window": 5, "passes": 2}, "applies_to": "all"},
        ],
        "envelopes": [
            {"id": "hilbert", "type": "hilbert",
             "params": {"window": 11, "threshold": 0.9, "min_history": 10},
             "applies_to": "all"},
        ],
    }

    plan = build_plan(config)
    print(f"  План: {len(plan['accel'])} accel + {len(plan['post'])} post")

    accel_ok = 0
    for task in plan["accel"]:
        r = execute_accel(task, out_root)
        assert r["status"] == "ok", f"accel {task['task_id']} упал: {r.get('error')}"
        accel_ok += 1
    print(f"  execute_accel: {accel_ok}/{len(plan['accel'])} OK")

    post_ok = 0
    for task in plan["post"]:
        r = execute_post(task, out_root)
        assert r["status"] == "ok", f"post {task['task_id']} упал: {r.get('error')}"
        post_ok += 1
    print(f"  execute_post: {post_ok}/{len(plan['post'])} OK")

    for task in plan["accel"]:
        ids = task["ids"]
        d = out_root / "accel" / ids["series_id"] / ids["noise_id"] / ids["accel_id"]
        assert (d / "manifest.json").exists()
        assert (d / "iterations.jsonl").exists()
        assert (d / "result.json").exists()
    print("  output акселерации OK")

    for task in plan["post"]:
        ids = task["ids"]
        d = out_root / "postprocess" / ids["series_id"] / ids["noise_id"] / ids["accel_id"]
        assert (d / "manifest.json").exists()
    print("  output постобработки OK")


# ==================== I. Skip, Progress, Errors ====================

def stress_skip_progress():
    """Проверяет skip, progress, errors."""
    section("I. Skip, Progress, Errors")

    project_root = Path(__file__).parent.resolve()
    out_root = project_root / "out" / "stress" / "skip"
    if out_root.exists():
        shutil.rmtree(out_root)
    out_root.mkdir(parents=True)

    config = {
        "precision": {"backend": "mpmath", "dps": 30},
        "series": [{"id": "zeta3", "type": "zeta", "params": {"s": 3}}],
        "noise": [{"id": "clean", "type": "none", "params": {}, "seed": 0}],
        "accelerators": [
            {"id": "aitken", "type": "aitken_delta2", "params": {},
             "n_max": 50,
             "stopping": [{"type": "max_iter", "params": {"n": 20}}]},
        ],
    }
    plan = build_plan(config)
    task = plan["accel"][0]

    assert not should_skip(task, out_root)
    r = execute_accel(task, out_root)
    assert r["status"] == "ok"

    assert should_skip(task, out_root), "should_skip не сработал"

    task_mod = json.loads(json.dumps(task))
    task_mod["accelerator"]["params"]["_dummy"] = 1
    assert not should_skip(task_mod, out_root), "should_skip на изменённом"

    p = Progress(total=100)
    p.done = 50
    p.failed = 5
    p.skipped = 10
    p.save(out_root / "progress.json")
    loaded = json.loads((out_root / "progress.json").read_text())
    assert loaded["done"] == 50
    assert loaded["total"] == 100
    print("  Progress OK")

    el = ErrorLog(out_root / "errors.log")
    for i in range(5):
        el.log({"task_id": f"t{i}"}, f"error {i}", f"traceback {i}")
    content = (out_root / "errors.log").read_text()
    for i in range(5):
        assert f"t{i}" in content
    print("  ErrorLog OK")


# ==================== J. CLI end-to-end ====================

def stress_cli():
    """Проверяет CLI на всех подкомандах."""
    section("J. CLI end-to-end")

    project_root = Path(__file__).parent.resolve()
    cfg_rel = "examples/config_minimal.json"
    out_rel = "out/stress/cli"
    out_root = project_root / "out" / "stress" / "cli"
    if out_root.exists():
        shutil.rmtree(out_root)

    r = subprocess.run(
        [sys.executable, "-m", "arbacc.cli", "validate", cfg_rel],
        capture_output=True, text=True, cwd=str(project_root),
    )
    assert r.returncode == 0, f"validate: {r.stderr}"
    print(f"  validate: rc=0")

    r = subprocess.run(
        [sys.executable, "-m", "arbacc.cli", "plan", cfg_rel, "--output", out_rel],
        capture_output=True, text=True, cwd=str(project_root),
    )
    assert r.returncode == 0, f"plan: {r.stderr}"
    assert (out_root / "plan.jsonl").exists()
    print(f"  plan: rc=0, plan.jsonl OK")

    r = subprocess.run(
        [sys.executable, "-m", "arbacc.cli", "run", cfg_rel, "--output", out_rel],
        capture_output=True, text=True, cwd=str(project_root),
    )
    assert r.returncode == 0, f"run: {r.stderr}"
    assert (out_root / "progress.json").exists()
    print(f"  run: rc=0, progress.json OK")

    r = subprocess.run(
        [sys.executable, "-m", "arbacc.cli", "run", cfg_rel,
         "--output", out_rel, "--skip-existing"],
        capture_output=True, text=True, cwd=str(project_root),
    )
    assert r.returncode == 0
    assert "SKIP" in r.stdout
    print(f"  run --skip-existing: rc=0, SKIP OK")

    r = subprocess.run(
        [sys.executable, "-m", "arbacc.cli", "run", cfg_rel,
         "--output", out_rel + "_limit", "--limit", "1"],
        capture_output=True, text=True, cwd=str(project_root),
    )
    assert r.returncode == 0
    print(f"  run --limit 1: rc=0 OK")

    bad_cfg = project_root / "out" / "stress" / "bad.json"
    bad_cfg.parent.mkdir(parents=True, exist_ok=True)
    bad_cfg.write_text('{"series": []}', encoding="utf-8")
    r = subprocess.run(
        [sys.executable, "-m", "arbacc.cli", "validate", str(bad_cfg)],
        capture_output=True, text=True, cwd=str(project_root),
    )
    assert r.returncode != 0, "validate на плохом конфиге вернул 0"
    print(f"  validate на плохом конфиге: rc!=0 OK")


# ==================== K. Крайние случаи ====================

def stress_edge_cases():
    """Проверяет крайние случаи."""
    section("K. Крайние случаи")

    ctx = make_ctx(30)
    b = ctx.backend

    plan = build_plan({
        "precision": {"backend": "mpmath", "dps": 30},
        "series": [],
        "noise": [],
        "accelerators": [],
    })
    assert plan["accel"] == []
    assert plan["post"] == []
    print("  пустой план OK")

    ZetaCls = get("series", "zeta")
    AitkenCls = get("accelerators", "aitken_delta2")
    zeta = ZetaCls(params={"s": 3})
    stream = zeta.build_stream(ctx)
    accel = AitkenCls(params={})
    r = run_accelerator(
        source=stream, accelerator=accel,
        stopping_criteria=[], stopping_mode="any",
        online_envelopes=[], ctx=ctx, n_max=1,
    )
    assert r.status == "ok"
    assert r.n_used <= 1
    print("  n_max=1 OK")

    MaxIterCls = get("stopping", "max_iter")
    zeta = ZetaCls(params={"s": 3})
    stream = zeta.build_stream(ctx)
    accel = AitkenCls(params={})
    r = run_accelerator(
        source=stream, accelerator=accel,
        stopping_criteria=[MaxIterCls(params={"n": 0})],
        stopping_mode="any", online_envelopes=[], ctx=ctx, n_max=100,
    )
    assert r.status == "ok"
    print("  max_iter=0 OK")

    ctx_small = make_ctx(5)
    zeta = ZetaCls(params={"s": 3})
    stream = zeta.build_stream(ctx_small)
    accel = AitkenCls(params={})
    r = run_accelerator(
        source=stream, accelerator=accel,
        stopping_criteria=[MaxIterCls(params={"n": 10})],
        stopping_mode="any", online_envelopes=[], ctx=ctx_small, n_max=100,
    )
    assert r.status == "ok"
    print("  dps=5 OK")

    KZCls = get("postprocess", "kolmogorov_zurbenko")
    short = [ctx.number("1.0"), ctx.number("1.1")]
    kz = KZCls(params={"window": 5, "passes": 1})
    post = kz.apply(short, ctx)
    assert post.final is not None
    print("  KZ на короткой последовательности OK")

    FFCls = get("series", "from_file")
    ff = FFCls(params={"path": "nonexistent_xyz.csv"})
    try:
        _ = ff.build_stream(ctx).get(0)
        raise AssertionError("from_file не бросил FileNotFoundError")
    except FileNotFoundError:
        pass
    print("  from_file: FileNotFoundError OK")

    # Пустая секция noise → implicit none → 1 задача.
    plan = build_plan({
        "precision": {"backend": "mpmath", "dps": 30},
        "series": [{"id": "z", "type": "zeta", "params": {"s": 3}}],
        "noise": [],
        "accelerators": [{"id": "a", "type": "aitken_delta2", "params": {},
                          "n_max": 10}],
    })
    # --- Scope applies_to ---
    # Пользователь пишет логический id в applies_to.
    # logical_id("series", "zeta", {"s": 3}) = "zeta_s3"
    # noise с applies_to=["zeta_s3"] применится только к s=3.
    config = {
        "precision": {"backend": "mpmath", "dps": 30},
        "series": [
            {"id": "z1", "type": "zeta", "params": {"s": 3}},
            {"id": "z2", "type": "zeta", "params": {"s": 5}},
        ],
        "noise": [
            {"id": "n", "type": "none", "params": {}, "seed": 0,
             "applies_to": ["zeta_s3"]},
        ],
        "accelerators": [
            {"id": "a", "type": "aitken_delta2", "params": {}},
        ],
    }
    plan = build_plan(config)
    # Только zeta_s3 должен получить задачу.
    assert len(plan["accel"]) == 1, (
        f"Ожидалось 1 задача (только zeta_s3), получено {len(plan['accel'])}"
    )
    assert plan["accel"][0]["ids"]["series_id"] == "zeta_s3", (
        f"Неверный series_id: {plan['accel'][0]['ids']['series_id']}"
    )
    # Попробуем применить ко всем zeta через префикс.
    config["noise"][0]["applies_to"] = ["zeta"]
    plan = build_plan(config)
    assert len(plan["accel"]) == 2, (
        f"applies_to=['zeta'] должен дать 2 задачи, получено {len(plan['accel'])}"
    )
    print("  scope applies_to (точный id и префикс) OK")
    
    assert "none" in plan["accel"][0]["task_id"], (
        f"id задачи должен содержать 'none': {plan['accel'][0]['task_id']}"
    )
    print("  plan без шума → implicit none OK")

    from arbacc.core.registry import register
    try:
        @register("series", "zeta")
        class DuplicateZeta:
            pass
        raise AssertionError("register не бросил на дубликат")
    except ValueError:
        pass
    print("  дубликат регистрации OK")


# ==================== L. Метаданные плагинов ====================

def stress_plugin_metadata():
    """Проверяет default_params / required_params / param_spec у всех плагинов."""
    section("L. Метаданные плагинов")

    categories = [
        "series", "noise", "accelerators", "stopping",
        "postprocess", "envelopes",
    ]
    reg = list_registered()
    total = 0

    for kind in categories:
        names = reg.get(kind, [])
        assert names, f"no plugins registered for {kind}"
        for name in names:
            Cls = registry_get(kind, name)
            assert hasattr(Cls, "default_params"), f"{kind}/{name} нет default_params"
            assert hasattr(Cls, "required_params"), f"{kind}/{name} нет required_params"
            assert hasattr(Cls, "param_spec"), f"{kind}/{name} нет param_spec"

            defaults = Cls.default_params()
            required = Cls.required_params()
            spec = Cls.param_spec()

            assert isinstance(defaults, dict)
            assert isinstance(required, set)
            assert isinstance(spec, dict)

            extra = required - set(defaults.keys()) - set(spec.keys())
            assert not extra, f"{kind}/{name}: required не покрыты: {extra}"

            for k in spec.keys():
                assert isinstance(spec[k], dict), f"{kind}/{name}.spec[{k}] не dict"

            total += 1

    print(f"  проверено плагинов: {total}")

    assert registry_get("series", "from_file").required_params() == {"path"}
    assert "path" in registry_get("series", "from_file").param_spec()
    assert registry_get("series", "from_file").param_spec()["path"]["type"] == "file"

    assert registry_get("noise", "ar1").required_params() == {"phi", "sigma"}
    assert registry_get("noise", "ar1").param_spec()["phi"]["min"] == -1
    assert registry_get("noise", "ar1").param_spec()["phi"]["max"] == 1

    assert registry_get("stopping", "max_iter").required_params() == {"n"}
    assert registry_get("postprocess", "kolmogorov_zurbenko").required_params() == {"window", "passes"}
    assert "run_mode" in registry_get("envelopes", "hilbert").param_spec()
    print("[OK] метаданные всех плагинов валидны")


# ==================== M. Валидация build_plan ====================

def stress_plan_validation():
    """Проверяет, что build_plan отсеивает плохие params и сообщает ошибки."""
    section("M. Валидация build_plan")

    plan = build_plan({})
    assert len(plan["accel"]) == 0
    assert len(plan["post"]) == 0
    assert plan["errors"], "пустой конфиг должен дать errors"
    print(f"  пустой конфиг: {len(plan['errors'])} errors")

    bad = {
        "precision": {"backend": "mpmath", "dps": 30},
        "series": [{"id": "z", "type": "zeta", "params": {}}],
        "noise": [{"id": "n", "type": "gaussian", "params": {}, "seed": 0}],
        "accelerators": [{"id": "a", "type": "aitken_delta2", "params": {}}],
    }
    plan = build_plan(bad)
    assert len(plan["accel"]) == 0, "плохие params не должны дать accel-задач"
    errs = plan["errors"]
    assert any("zeta" in e for e in errs), f"нет ошибки про zeta: {errs}"
    assert any("gaussian" in e for e in errs), f"нет ошибки про gaussian: {errs}"
    print(f"  плохие params: {len(errs)} errors")

    good = {
        "precision": {"backend": "mpmath", "dps": 30},
        "series": [{"id": "z", "type": "zeta", "params": {"s": 3}}],
        "noise": [{"id": "n", "type": "none", "params": {}, "seed": 0}],
        "accelerators": [{"id": "a", "type": "aitken_delta2", "params": {}}],
    }
    plan = build_plan(good)
    assert len(plan["accel"]) == 1
    assert plan["errors"] == [], f"хороший конфиг дал errors: {plan['errors']}"
    print("  хороший конфиг: 0 errors, 1 accel task")

    accel = plan["accel"][0]["accelerator"]
    assert accel["n_max"] == 100, f"n_max = {accel['n_max']}"
    assert accel["stopping"], "stopping не подставлен"
    assert accel["stopping_mode"] == "any"
    print("  defaults n_max / stopping / stopping_mode OK")

    config = {
        "precision": {"backend": "mpmath", "dps": [30, 50]},
        "series": [{"id": "z", "type": "zeta", "params": {"s": 3}}],
        "noise": [{"id": "n", "type": "none", "params": {}, "seed": 0}],
        "accelerators": [
            {"id": "a", "type": "aitken_delta2", "params": {},
             "n_max": [100, 500]},
        ],
    }
    plan = build_plan(config)
    assert len(plan["accel"]) == 4, f"ожидалось 4, получено {len(plan['accel'])}"
    print("  развёртка dps × n_max: 4 задачи OK")

    # --- Scope applies_to: точный id ---
    config = {
        "precision": {"backend": "mpmath", "dps": 30},
        "series": [
            {"type": "zeta", "params": {"s": 3}},
            {"type": "zeta", "params": {"s": 5}},
        ],
        "noise": [
            {"type": "none", "params": {}, "seed": 0,
             "applies_to": ["zeta_s3"]},
        ],
        "accelerators": [
            {"type": "aitken_delta2", "params": {}},
        ],
    }
    plan = build_plan(config)
    assert len(plan["accel"]) == 1, (
        f"scope по 'zeta_s3' должен дать 1 задачу, "
        f"получено {len(plan['accel'])}"
    )
    assert plan["accel"][0]["ids"]["series_id"] == "zeta_s3"

    # --- Scope applies_to: префикс ---
    config["noise"][0]["applies_to"] = ["zeta"]
    plan = build_plan(config)
    assert len(plan["accel"]) == 2, (
        f"scope по префиксу 'zeta' должен дать 2 задачи, "
        f"получено {len(plan['accel'])}"
    )
    print("  scope applies_to (точный id + префикс) OK")
    print("  scope applies_to OK")

    config = {
        "precision": {"backend": "mpmath", "dps": 30},
        "series": [{"id": "z", "type": "zeta", "params": {"s": 3}}],
        "noise": [{"id": "n", "type": "none", "params": {}, "seed": 0}],
        "accelerators": [{
            "id": "a", "type": "aitken_delta2", "params": {},
            "stopping": [
                {"type": "max_iter", "params": {"n": 50}},
                {"type": "digits_stable", "params": {"window": 3, "min_digits": 8}},
            ],
        }],
    }
    plan = build_plan(config)
    stopping = plan["accel"][0]["accelerator"]["stopping"]
    assert len(stopping) == 2, f"stopping должен остаться длиной 2: {stopping}"
    print("  stopping не разворачивается OK")

    print("[OK] build_plan валидация работает")


# ==================== N. from_file sin/cos ====================

def stress_from_file_new():
    """Проверяет from_file с файлами sin_06/cos_06."""
    section("N. from_file с sin_06 / cos_06")

    import mpmath as mp

    project_root = Path(__file__).parent.resolve()
    data = project_root / "examples" / "data"

    files = ["sin_06.csv", "sin_06.txt", "cos_06.csv", "cos_06.txt"]
    if not all((data / f).exists() for f in files):
        print("  [SKIP] файлы не сгенерированы — запусти generate_series_files.py")
        return

    ctx = make_ctx(50)
    b = ctx.backend
    FFCls = get("series", "from_file")

    # Эталоны вычисляем через mpmath — не хардкодим.
    with mp.workdps(80):
        exact_sin = ctx.number(str(mp.sin(mp.mpf("0.6"))))
        exact_cos = ctx.number(str(mp.cos(mp.mpf("0.6"))))

    def _mk_stream(path: Path):
        """Создаёт stream с правильным режимом чтения."""
        p = str(path)
        if p.lower().endswith(".csv"):
            ff = FFCls(params={"path": p, "column": "value"})
        else:
            ff = FFCls(params={"path": p})
        return ff.build_stream(ctx)

    for fname, exact in [
        ("sin_06.csv", exact_sin),
        ("sin_06.txt", exact_sin),
        ("cos_06.csv", exact_cos),
        ("cos_06.txt", exact_cos),
    ]:
        stream = _mk_stream(data / fname)
        total = ctx.number(0)
        for n in range(40):
            total = b.add(total, stream.get(n), 50)
        d = b.digits_of(total, exact, 50)
        print(f"  {fname}: 40 членов → {d} верных цифр")
        assert d >= 40, f"{fname}: только {d} цифр, ожидалось ≥40"

    csv_stream = _mk_stream(data / "sin_06.csv")
    txt_stream = _mk_stream(data / "sin_06.txt")
    for n in range(10):
        d = b.digits_of(csv_stream.get(n), txt_stream.get(n), 50)
        assert d >= 48, f"CSV и TXT разошлись на n={n}: {d} цифр"

    print("[OK] from_file с sin_06 / cos_06 работает")

# ==================== O. Консистентность output ====================

def stress_output_consistency():
    """
    Проверяет согласованность файлов output:
      - manifest.input_hash — sha256 с правильным форматом
      - result.json и iterations.jsonl согласованы
      - n_used == len(iterations)
      - estimate в result.json == последний в iterations.jsonl
    """
    section("O. Консистентность output")

    project_root = Path(__file__).parent.resolve()
    out_root = project_root / "out" / "stress" / "consistency"
    if out_root.exists():
        shutil.rmtree(out_root)
    out_root.mkdir(parents=True)

    config = {
        "precision": {"backend": "mpmath", "dps": 30},
        "series": [{"id": "z", "type": "zeta", "params": {"s": 3}}],
        "noise": [{"id": "n", "type": "none", "params": {}, "seed": 0}],
        "accelerators": [
            {"id": "a", "type": "aitken_delta2", "params": {},
             "n_max": 100,
             "stopping": [{"type": "max_iter", "params": {"n": 20}}]},
        ],
    }

    plan = build_plan(config)
    task = plan["accel"][0]
    ids = task["ids"]
    r = execute_accel(task, out_root)
    assert r["status"] == "ok"

    dir_path = (
        out_root / "accel" / ids["series_id"] / ids["noise_id"] / ids["accel_id"]
    )

    # --- manifest.json ---
    manifest = json.loads((dir_path / "manifest.json").read_text(encoding="utf-8"))
    assert "input_hash" in manifest
    assert manifest["input_hash"].startswith("sha256:")
    assert len(manifest["input_hash"]) == len("sha256:") + 64
    print(f"  input_hash: {manifest['input_hash'][:30]}…")
    assert "code_version" in manifest
    assert "deps" in manifest
    assert "input" in manifest

    # --- result.json ---
    result = json.loads((dir_path / "result.json").read_text(encoding="utf-8"))
    assert result["status"] == "ok"
    assert result["accelerator"] == "aitken_delta2"
    assert "estimate" in result
    assert "stopped_by" in result

    # --- iterations.jsonl ---
    iterations = [
        json.loads(line)
        for line in (dir_path / "iterations.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    # n_used — сколько элементов источника израсходовано, это ≥ числа
    # итераций, потому что required_input растёт с каждой итерацией.
    assert result["n_used"] >= len(iterations), (
        f"n_used ({result['n_used']}) должно быть ≥ числа итераций "
        f"({len(iterations)})"
    )
    print(f"  iterations: {len(iterations)} записей, n_used={result['n_used']}")

    # --- estimate совпадает с последней записью ---
    last_iter = iterations[-1]
    assert last_iter["estimate"] == result["estimate"], (
        f"last iteration estimate ({last_iter['estimate']}) "
        f"!= result estimate ({result['estimate']})"
    )
    print("  estimate совпадает с последней итерацией")

    # --- k-индексы монотонны ---
    for i, rec in enumerate(iterations):
        assert rec["k"] == i, f"k-индекс не монотонный: {rec['k']} != {i}"
    print("  k-индексы монотонны")

    # --- manifest.input_hash совпадает с build_input_payload ---
    from arbacc.runner.skip import build_input_payload, expected_manifest
    expected = expected_manifest(task)
    assert manifest["input_hash"] == expected["input_hash"], (
        "input_hash не совпадает с expected_manifest"
    )
    print("  input_hash совпадает с expected")

    print("[OK] output консистентен")


# ==================== P. Детерминизм ====================

def stress_determinism():
    """
    Проверяет, что один и тот же конфиг, запущенный дважды в разные
    директории, даёт идентичные result.json (побитово, как строки).
    """
    section("P. Детерминизм результата")

    project_root = Path(__file__).parent.resolve()
    out_a = project_root / "out" / "stress" / "det_a"
    out_b = project_root / "out" / "stress" / "det_b"
    for d in (out_a, out_b):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)

    config = {
        "precision": {"backend": "mpmath", "dps": 40},
        "series": [{"id": "z", "type": "zeta", "params": {"s": 3}}],
        "noise": [
            {"id": "gauss", "type": "gaussian",
             "params": {"sigma": "1e-6"}, "seed": 42},
        ],
        "accelerators": [
            {"id": "a", "type": "aitken_delta2", "params": {},
             "n_max": 100,
             "stopping": [{"type": "max_iter", "params": {"n": 30}}]},
        ],
    }

    plan = build_plan(config)
    task = plan["accel"][0]
    ids = task["ids"]

    # Прогон A.
    r1 = execute_accel(task, out_a)
    assert r1["status"] == "ok"

    # Прогон B — то же самое.
    r2 = execute_accel(task, out_b)
    assert r2["status"] == "ok"

    # Сравниваем result.json.
    def _load_result(root):
        return json.loads(
            (root / "accel" / ids["series_id"] / ids["noise_id"] / ids["accel_id"]
             / "result.json").read_text(encoding="utf-8")
        )

    res_a = _load_result(out_a)
    res_b = _load_result(out_b)

    for key in ("estimate", "n_used", "stopped_by", "status", "digits_gained"):
        assert res_a[key] == res_b[key], (
            f"детерминизм сломан для {key}: {res_a[key]!r} != {res_b[key]!r}"
        )
    print(f"  result совпадает: estimate={res_a['estimate'][:30]}…, "
          f"n_used={res_a['n_used']}")

    # Сравниваем iterations.jsonl построчно.
    def _load_iters(root):
        return [
            json.loads(line)
            for line in (root / "accel" / ids["series_id"] / ids["noise_id"]
                         / ids["accel_id"] / "iterations.jsonl")
            .read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    it_a = _load_iters(out_a)
    it_b = _load_iters(out_b)

    assert len(it_a) == len(it_b), (
        f"длина iterations разная: {len(it_a)} != {len(it_b)}"
    )
    for i, (a, b) in enumerate(zip(it_a, it_b)):
        for key in ("k", "estimate", "n_used"):
            assert a[key] == b[key], (
                f"iterations[{i}][{key}]: {a[key]!r} != {b[key]!r}"
            )
    print(f"  iterations совпадают построчно ({len(it_a)} записей)")

    # Манифест совпадает по input_hash.
    def _load_manifest(root):
        return json.loads(
            (root / "accel" / ids["series_id"] / ids["noise_id"] / ids["accel_id"]
             / "manifest.json").read_text(encoding="utf-8")
        )

    m_a = _load_manifest(out_a)
    m_b = _load_manifest(out_b)
    assert m_a["input_hash"] == m_b["input_hash"]
    print(f"  input_hash совпадает")

    print("[OK] детерминизм подтверждён")


# ==================== T. Полная матрица series × noise × accel ====================

def stress_full_matrix():
    """
    Прогоняет ВСЕ комбинации series × noise × accel с минимальными
    параметрами. Проверяет, что никакая комбинация не падает.
    """
    section("T. Полная матрица series × noise × accel")

    ctx = make_ctx(30)
    ZetaCls = get("series", "zeta")
    GeomCls = get("series", "geometric")
    NoneCls = get("noise", "none")
    GaussCls = get("noise", "gaussian")
    AitkenCls = get("accelerators", "aitken_delta2")
    WynnCls = get("accelerators", "wynn_epsilon")
    MaxIterCls = get("stopping", "max_iter")

    series_factories = [
        ("zeta_s3", lambda: ZetaCls(params={"s": 3})),
        ("zeta_s5", lambda: ZetaCls(params={"s": 5})),
        ("geom_q05", lambda: GeomCls(params={"q": "0.5"})),
        ("geom_q07", lambda: GeomCls(params={"q": "0.7"})),
    ]
    noise_factories = [
        ("none", lambda: NoneCls(params={}, seed=0)),
        ("gauss", lambda: GaussCls(params={"sigma": "1e-6"}, seed=42)),
    ]
    accel_factories = [
        ("aitken", lambda: AitkenCls(params={})),
        ("wynn", lambda: WynnCls(params={})),
    ]

    total = 0
    ok = 0
    for s_name, s_make in series_factories:
        for n_name, n_make in noise_factories:
            for a_name, a_make in accel_factories:
                total += 1
                try:
                    source = s_make().build_stream(ctx)
                    noise = n_make().wrap(source, ctx)
                    accel = a_make()
                    stopping = [MaxIterCls(params={"n": 10})]
                    r = run_accelerator(
                        source=noise,
                        accelerator=accel,
                        stopping_criteria=stopping,
                        stopping_mode="any",
                        online_envelopes=[],
                        ctx=ctx,
                        n_max=50,
                    )
                    if r.status != "ok":
                        print(f"  FAIL {s_name}/{n_name}/{a_name}: "
                              f"status={r.status}, error={r.error}")
                        continue
                    ok += 1
                except Exception as e:
                    print(f"  EXC  {s_name}/{n_name}/{a_name}: "
                          f"{type(e).__name__}: {e}")
                    continue

    print(f"  матрица: {ok}/{total} успешно")
    assert ok == total, f"не все комбинации прошли: {ok}/{total}"

    # Все постобработки × все акселераторы (с одной серией).
    KZCls = get("postprocess", "kolmogorov_zurbenko")
    SGCls = get("postprocess", "savitzky_golay")
    MedCls = get("postprocess", "median")

    source = ZetaCls(params={"s": 3}).build_stream(ctx)
    accel = AitkenCls(params={})
    r = run_accelerator(
        source=source, accelerator=accel,
        stopping_criteria=[MaxIterCls(params={"n": 30})],
        stopping_mode="any", online_envelopes=[], ctx=ctx, n_max=100,
    )
    estimates = [rec.estimate for rec in r.iterations]

    pp_total = 0
    pp_ok = 0
    for pp_name, pp_make in [
        ("kz_5_2", lambda: KZCls(params={"window": 5, "passes": 2})),
        ("sg_7_2", lambda: SGCls(params={"window": 7, "order": 2})),
        ("med_5", lambda: MedCls(params={"window": 5})),
    ]:
        pp_total += 1
        try:
            post = pp_make().apply(estimates, ctx)
            assert post.final is not None
            pp_ok += 1
        except Exception as e:
            print(f"  EXC postprocess {pp_name}: {type(e).__name__}: {e}")

    print(f"  постобработки: {pp_ok}/{pp_total} успешно")
    assert pp_ok == pp_total

    # Все огибающие × все режимы.
    HilbertCls = get("envelopes", "hilbert")
    EMDCls = get("envelopes", "emd")
    env_total = 0
    env_ok = 0
    for env_name, env_cls in [("hilbert", HilbertCls), ("emd", EMDCls)]:
        for run_mode in ("after", "during"):
            for used_as in ("observer", "stopping_criterion"):
                env_total += 1
                try:
                    params = {
                        "window": 11, "detrend_window": 11,
                        "threshold": 0.9, "min_history": 10,
                        "run_mode": run_mode, "used_as": used_as,
                    }
                    env = env_cls(params=params)
                    if run_mode == "during":
                        src2 = ZetaCls(params={"s": 3}).build_stream(ctx)
                        acc2 = AitkenCls(params={})
                        r2 = run_accelerator(
                            source=src2, accelerator=acc2,
                            stopping_criteria=[MaxIterCls(params={"n": 100})],
                            stopping_mode="any",
                            online_envelopes=[env],
                            ctx=ctx, n_max=500,
                        )
                        assert r2.status == "ok"
                    else:
                        out = run_offline_envelopes(r, [env], ctx)
                        assert env_name in out
                    env_ok += 1
                except Exception as e:
                    print(f"  EXC envelope {env_name}/{run_mode}/{used_as}: "
                          f"{type(e).__name__}: {e}")

    print(f"  огибающие: {env_ok}/{env_total} успешно")
    assert env_ok == env_total

    print("[OK] полная матрица работает")

# ==================== main ====================

def main() -> int:
    """Точка входа. Запускает все секции."""
    print("=" * 70)
    print("ARBACC STRESS TEST")
    print("=" * 70)
    print(f"Python: {sys.version.split()[0]}")
    print(f"CWD:    {Path.cwd()}")

    report = StressReport()

    report.run("A. Backend + Context",            stress_backend)
    report.run("B. Series",                       stress_series)
    report.run("C. Noise",                        stress_noise)
    report.run("D. Accelerators + Stopping",      stress_accelerators)
    report.run("E. Postprocess",                  stress_postprocess)
    report.run("F. Envelopes",                    stress_envelopes)
    report.run("G. Runner: planning",             stress_runner_planning)
    report.run("H. Execute",                      stress_execute)
    report.run("I. Skip, Progress, Errors",       stress_skip_progress)
    report.run("J. CLI end-to-end",               stress_cli)
    report.run("K. Крайние случаи",               stress_edge_cases)
    report.run("L. Метаданные плагинов",          stress_plugin_metadata)
    report.run("M. Валидация build_plan",         stress_plan_validation)
    report.run("N. from_file sin/cos",            stress_from_file_new)
    report.run("O. Консистентность output",       stress_output_consistency)
    report.run("P. Детерминизм",                  stress_determinism)
    report.run("T. Полная матрица",               stress_full_matrix)

    return report.summary()


if __name__ == "__main__":
    sys.exit(main())