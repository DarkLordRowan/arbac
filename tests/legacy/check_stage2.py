"""
Комплексная проверка этапа 2.

Что проверяется:
    1. Регистрация всех плагинов (series, noise).
    2. Корректность генерации каждого синтетического ряда.
    3. Корректность загрузки из CSV и TXT.
    4. Работа каждого шума (none, gaussian absolute/relative, ar1).
    5. Детерминизм counter-based RNG (досоздание не ломает значения).
    6. Forward-only ограничение AR(1).
    7. Сохранение series и noise в output.
    8. Round-trip: сохранили -> прочитали -> числа совпали.

Запуск:
    cd "Проект Парф Питон"
    python check_stage2.py
"""
from __future__ import annotations
from pathlib import Path

# Импорт пакетов запускает autodiscovery и регистрирует плагины.
import arbacc.series  # noqa: F401
import arbacc.noise   # noqa: F401

from arbacc.core import Context, get, list_registered
from arbacc.precision import get_backend
from arbacc.storage.save import save_series, save_noise, instance_id
from arbacc.storage.jsonl import read_jsonl


def section(title: str) -> None:
    """Печатает заголовок секции."""
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def check_registration() -> None:
    """Проверяет, что все ожидаемые плагины зарегистрированы."""
    section("1. Регистрация плагинов")
    reg = list_registered()
    print("Registered:", reg)

    expected_series = {"zeta", "geometric", "from_file"}
    expected_noise = {"none", "gaussian", "ar1"}

    assert expected_series <= set(reg.get("series", [])), \
        f"Не хватает рядов: {expected_series - set(reg.get('series', []))}"
    assert expected_noise <= set(reg.get("noise", [])), \
        f"Не хватает шумов: {expected_noise - set(reg.get('noise', []))}"
    print("[OK] Все плагины зарегистрированы")


def check_zeta(ctx: Context) -> None:
    """Проверяет генерацию zeta для s=2,3,4."""
    section("2. ZetaSeries")
    ZetaCls = get("series", "zeta")
    backend = ctx.backend

    for s in (2, 3, 4):
        zeta = ZetaCls(params={"s": s})
        stream = zeta.build_stream(ctx)
        a0 = backend.to_str(stream.get(0), ctx.dps)
        a1 = backend.to_str(stream.get(1), ctx.dps)
        print(f"  zeta(s={s}): a_0={a0}, a_1={a1}")
        assert a0.startswith("1.0"), f"zeta(s={s}) a_0 != 1"
        expected_a1 = ctx.backend.pow(
            ctx.number(2),
            ctx.backend.neg(ctx.number(s), ctx.dps),
            ctx.dps,
        )
        d = backend.digits_of(stream.get(1), expected_a1, ctx.dps)
        assert d >= ctx.dps - 2, f"zeta(s={s}) a_1 wrong: {d} digits"
    print("[OK] zeta корректна для s=2,3,4")


def check_geometric(ctx: Context) -> None:
    """Проверяет генерацию geometric для разных q."""
    section("3. GeometricSeries")
    GeomCls = get("series", "geometric")
    backend = ctx.backend

    for q in ["0.5", "0.7", "0.9", "-0.3"]:
        geom = GeomCls(params={"q": q})
        stream = geom.build_stream(ctx)
        q_num = ctx.number(q)
        for n in range(5):
            expected = ctx.backend.pow(q_num, ctx.number(n), ctx.dps)
            d = backend.digits_of(stream.get(n), expected, ctx.dps)
            assert d >= ctx.dps - 2, f"geometric(q={q}) a_{n} wrong: {d} digits"
        print(f"  geometric(q={q}): первые 5 членов OK")
    print("[OK] geometric корректна")


def check_from_file(ctx: Context, project_root: Path) -> None:
    """
    Проверяет загрузку из CSV и TXT.

    Автоматически определяет кодировку: utf-8-sig, cp1251, cp866, latin-1.
    """
    section("4. FromFileSeries (CSV и TXT)")
    FFCls = get("series", "from_file")
    backend = ctx.backend

    csv_path = project_root / "examples" / "data" / "sample_series.csv"
    txt_path = project_root / "examples" / "data" / "sample_series.txt"

    def detect_encoding(p: Path) -> str:
        """Определяет кодировку файла, начиная с проверки BOM."""
        data = p.read_bytes()
        if data.startswith(b"\xef\xbb\xbf"):
            return "utf-8-sig"
        for enc in ("utf-8", "cp1251", "cp866", "latin-1"):
            try:
                data.decode(enc)
                return enc
            except UnicodeDecodeError:
                continue
        return "latin-1"

    if not csv_path.exists():
        print(f"[SKIP] {csv_path} не найден")
    else:
        enc = detect_encoding(csv_path)
        print(f"  CSV encoding detected: {enc}")
        ff = FFCls(params={"path": str(csv_path), "column": "value", "encoding": enc})
        stream = ff.build_stream(ctx)
        a0 = backend.to_str(stream.get(0), ctx.dps)
        a1 = backend.to_str(stream.get(1), ctx.dps)
        print(f"  CSV: a_0={a0[:30]}..., a_1={a1[:30]}...")
        assert a0.startswith("1.0"), "CSV a_0 != 1"
        assert a1.startswith("0.5"), "CSV a_1 != 0.5"
        print("  [OK] CSV загружается")

    if not txt_path.exists():
        print(f"[SKIP] {txt_path} не найден")
    else:
        enc = detect_encoding(txt_path)
        print(f"  TXT encoding detected: {enc}")
        ff = FFCls(params={"path": str(txt_path), "encoding": enc})
        stream = ff.build_stream(ctx)
        a0 = backend.to_str(stream.get(0), ctx.dps)
        a1 = backend.to_str(stream.get(1), ctx.dps)
        print(f"  TXT: a_0={a0[:30]}..., a_1={a1[:30]}...")
        assert a0.startswith("1.0"), "TXT a_0 != 1"
        assert a1.startswith("0.5"), "TXT a_1 != 0.5"
        print("  [OK] TXT загружается")


def check_noise_none(ctx: Context) -> None:
    """Проверяет, что none не меняет значения."""
    section("5. Noise none")
    ZetaCls = get("series", "zeta")
    NoneCls = get("noise", "none")
    backend = ctx.backend

    zeta = ZetaCls(params={"s": 3})
    clean = zeta.build_stream(ctx)
    noise = NoneCls(params={}, seed=0)
    noisy = noise.wrap(clean, ctx)

    for n in range(5):
        c = backend.to_str(clean.get(n), ctx.dps)
        z = backend.to_str(noisy.get(n), ctx.dps)
        assert c == z, f"none изменил a_{n}: {c} vs {z}"
    print("[OK] none не меняет значения")


def check_noise_gaussian(ctx: Context) -> None:
    """Проверяет gaussian в absolute и relative режимах + детерминизм."""
    section("6. Noise gaussian (absolute, relative) + детерминизм")
    ZetaCls = get("series", "zeta")
    GaussCls = get("noise", "gaussian")
    backend = ctx.backend

    zeta = ZetaCls(params={"s": 3})
    clean = zeta.build_stream(ctx)

    for mode in ["absolute", "relative"]:
        noise = GaussCls(params={"sigma": "1e-6", "mode": mode}, seed=42)
        noisy = noise.wrap(clean, ctx)

        # Детерминизм: запомним a_0, досоздадим до 100, проверим a_0.
        v0_before = backend.to_str(noisy.get(0), ctx.dps)
        noisy.extend_to(100)
        v0_after = backend.to_str(noisy.get(0), ctx.dps)
        assert v0_before == v0_after, f"gaussian/{mode} сломал детерминизм"
        print(f"  gaussian mode={mode}: a_0={v0_before[:30]}...")

        # Значения должны отличаться от чистых (шум есть).
        c0 = backend.to_str(clean.get(0), ctx.dps)
        assert v0_before != c0, f"gaussian/{mode} не добавил шум"
    print("[OK] gaussian работает и детерминирован")


def check_noise_ar1(ctx: Context) -> None:
    """
    Проверяет ar1 + forward-only ограничение.

    Что проверяется:
        1. Последовательный прогон 0..10 работает.
        2. Повторный доступ к посчитанному (из кэша Stream) — OK.
        3. Прямой вызов transform с n < last_n — RuntimeError.
        4. Повторный wrap на одном AR1Noise — RuntimeError.
    """
    section("7. Noise ar1 (forward-only)")
    ZetaCls = get("series", "zeta")
    ARCls = get("noise", "ar1")

    zeta = ZetaCls(params={"s": 3})
    clean = zeta.build_stream(ctx)

    # 7.1. Последовательный прогон.
    noise = ARCls(params={"phi": "0.7", "sigma": "1e-6"}, seed=42)
    noisy = noise.wrap(clean, ctx)
    for n in range(11):
        _ = noisy.get(n)
    print("  ar1: 0..10 посчитаны без ошибок")

    # 7.2. Повторный доступ к уже посчитанному идёт из кэша Stream.
    _ = noisy.get(5)
    print("  ar1: повторный доступ к посчитанному — OK (из кэша)")

    # 7.3. Прямая проверка transform.
    noise2 = ARCls(params={"phi": "0.7", "sigma": "1e-6"}, seed=42)
    _ = noise2.transform(10, ctx.number("1.0"), ctx)
    try:
        _ = noise2.transform(5, ctx.number("1.0"), ctx)
        raise AssertionError("ar1.transform не бросил RuntimeError при n < last_n")
    except RuntimeError:
        print("  ar1: transform запрещает доступ в прошлое")

    # 7.4. Повторный wrap на одном инстансе.
    noise3 = ARCls(params={"phi": "0.7", "sigma": "1e-6"}, seed=42)
    _ = noise3.wrap(clean, ctx)
    try:
        _ = noise3.wrap(clean, ctx)
        raise AssertionError("ar1.wrap не запретил повторное использование")
    except RuntimeError:
        print("  ar1: повторный wrap запрещён")

    print("[OK] ar1 работает")


def check_save_and_load(ctx: Context, project_root: Path) -> None:
    """Проверяет сохранение series/noise и round-trip."""
    section("8. Сохранение и round-trip")
    ZetaCls = get("series", "zeta")
    GaussCls = get("noise", "gaussian")
    backend = ctx.backend

    out_root = project_root / "out" / "check_stage2" / f"dps{ctx.dps}"

    zeta = ZetaCls(params={"s": 3})
    stream = zeta.build_stream(ctx)
    series_id = instance_id("zeta", {"s": 3})

    save_series(
        output_root=out_root,
        series_id=series_id,
        series_params={"s": 3},
        stream=stream,
        ctx=ctx,
        n_values=200,
        series_type="zeta",
    )

    # Round-trip: прочитаем stream.jsonl и сравним с потоком.
    records = read_jsonl(out_root / "series" / series_id / "stream.jsonl")
    assert len(records) == 200, f"Ожидалось 200 записей, получили {len(records)}"
    for n in range(0, 200, 17):  # выборочная проверка
        saved = records[n]["value"]
        live = backend.to_str(stream.get(n), ctx.dps)
        assert saved == live, f"Round-trip сломался на n={n}: {saved} vs {live}"
    print(f"  series round-trip OK ({len(records)} записей)")

    # Аналогично для шума.
    gauss = GaussCls(params={"sigma": "1e-6", "mode": "absolute"}, seed=42)
    noisy = gauss.wrap(stream, ctx)
    noise_id = instance_id(
        "gaussian",
        {"sigma": "1e-6", "mode": "absolute"},
        {"seed": 42},
    )
    save_noise(
        output_root=out_root,
        series_id=series_id,
        noise_id=noise_id,
        noise_params={"sigma": "1e-6", "mode": "absolute"},
        noise_type="gaussian",
        seed=42,
        noisy_stream=noisy,
        ctx=ctx,
        n_values=200,
    )
    records = read_jsonl(out_root / "noise" / series_id / noise_id / "stream.jsonl")
    assert len(records) == 200
    for n in range(0, 200, 17):
        saved = records[n]["value"]
        live = backend.to_str(noisy.get(n), ctx.dps)
        assert saved == live, f"noise round-trip сломался на n={n}"
    print(f"  noise round-trip OK ({len(records)} записей)")

    # Манифесты на месте.
    assert (out_root / "series" / series_id / "manifest.json").exists()
    assert (out_root / "noise" / series_id / noise_id / "manifest.json").exists()
    print("  манифесты на месте")
    print(f"[OK] сохранение работает: {out_root}")


def main() -> None:
    """Точка входа."""
    project_root = Path(__file__).parent.resolve()
    backend = get_backend("mpmath")
    ctx = Context(backend=backend, dps=50)

    check_registration()
    check_zeta(ctx)
    check_geometric(ctx)
    check_from_file(ctx, project_root)
    check_noise_none(ctx)
    check_noise_gaussian(ctx)
    check_noise_ar1(ctx)
    check_save_and_load(ctx, project_root)

    print("\n" + "=" * 70)
    print("ВСЕ ПРОВЕРКИ ЭТАПА 2 ПРОЙДЕНЫ")
    print("=" * 70)


if __name__ == "__main__":
    main()