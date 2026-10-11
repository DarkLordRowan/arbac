"""
Общие фикстуры и константы для всех тестов.

Зачем:
    Чтобы каждый тестовый файл не создавал Context, не импортировал
    все пакеты плагинов, не настраивал пути вручную. Всё — здесь.

Фикстуры:
    ctx            — Context(mpmath, dps=50).
    ctx_arb        — Context(arb, dps=50). Требует python-flint.
    low_ctx        — Context(mpmath, dps=20) для быстрых тестов.
    tmp_output     — путь к временной папке output.
    config_minimal — минимальный валидный конфиг.
    config_full    — конфиг с 2 dps, 2 сериями, 2 шумами.
"""

from __future__ import annotations
from pathlib import Path

import pytest

# Импорт всех пакетов — заполняет реестр плагинов.
import arbacc.series        # noqa: F401
import arbacc.noise         # noqa: F401
import arbacc.accelerators  # noqa: F401
import arbacc.stopping      # noqa: F401
import arbacc.postprocess   # noqa: F401
import arbacc.envelopes     # noqa: F401

from arbacc.core import Context
from arbacc.precision import get_backend, list_backends


# --- Известные константы ----------------------------------------------------

#: Точные значения для проверки серий и алгоритмов.
KNOWN = {
    "zeta2": "1.6449340668482264364724151666460251892189499012067984377355582",
    "zeta3": "1.2020569031595942853997381615114499907649862923404988817923412",
    "zeta4": "1.0823232337111381915160036965411679027747509519187269076829762",
    "sin_06": "0.5646424733950353572009454456586579071098880849941517710242659",
    "cos_06": "0.8253356149096782972409524989553760388780910391884703813697498",
    "geometric_07": "3.3333333333333333333333333333333333333333333333333333333333",
    "pi": "3.1415926535897932384626433832795028841971693993751058209749446",
    "e": "2.7182818284590452353602874713526624977572470936999595749669676",
}


# --- Фикстуры ---------------------------------------------------------------

@pytest.fixture
def ctx():
    """Context на mpmath с dps=50.

    Function-scoped: каждый тест получает свежий Context, что
    активирует mp.mp.dps=50 (см. Context.__post_init__). Это
    защищает от «утечек» dps из других тестов.
    """
    return Context(backend=get_backend("mpmath"), dps=50)


@pytest.fixture
def low_ctx():
    """Context на mpmath с dps=20 — для быстрых тестов."""
    return Context(backend=get_backend("mpmath"), dps=20)


@pytest.fixture
def ctx_arb():
    """Context на arb (python-flint) с dps=50."""
    if "arb" not in list_backends():
        pytest.skip("arb backend not available (python-flint not installed)")
    return Context(backend=get_backend("arb"), dps=50)


@pytest.fixture
def tmp_output(tmp_path: Path) -> Path:
    """Временная папка output для каждого теста."""
    out = tmp_path / "out"
    out.mkdir(parents=True, exist_ok=True)
    return out


@pytest.fixture
def config_minimal() -> dict:
    """Минимальный валидный конфиг: одна серия, один акселератор."""
    return {
        "precision": {"backend": "mpmath", "dps": 30},
        "series": [{"type": "zeta", "params": {"s": 3}}],
        "noise": [],
        "accelerators": [{
            "type": "aitken_delta2", "params": {},
            "n_max": 50,
            "stopping": [{"type": "max_iter", "params": {"n": 20}}],
        }],
    }


@pytest.fixture
def config_full() -> dict:
    """Конфиг с развёрткой: 2 dps × 2 серии × 2 шума × 2 акселя."""
    return {
        "precision": {"backend": "mpmath", "dps": [30, 50]},
        "series": [
            {"type": "zeta", "params": {"s": 3}},
            {"type": "geometric", "params": {"q": "0.7"}},
        ],
        "noise": [
            {"type": "none", "params": {}, "seed": 0, "applies_to": "all"},
            {"type": "gaussian",
             "params": {"sigma": "1e-6", "mode": "absolute"},
             "seed": 42, "applies_to": ["zeta_s3"]},
        ],
        "accelerators": [
            {"type": "aitken_delta2", "params": {}, "n_max": 50,
             "stopping": [{"type": "max_iter", "params": {"n": 20}}],
             "applies_to": "all"},
            {"type": "wynn_epsilon", "params": {}, "n_max": 30,
             "stopping": [{"type": "max_iter", "params": {"n": 10}}],
             "applies_to": {"series": "zeta_s3"}},
        ],
    }