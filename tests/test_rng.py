# tests/test_rng.py

def test_counter_rng_distribution():
    """CounterRNG даёт близкое к равномерному распределение."""
    import statistics
    from arbacc.core.rng import CounterRNG
    rng = CounterRNG(seed=42, stream_id="test")
    N = 10_000
    samples = [rng.uniform(n) for n in range(N)]
    assert abs(statistics.mean(samples) - 0.5) < 0.02
    assert abs(statistics.stdev(samples) - 1/12**0.5) < 0.02


def test_counter_rng_determinism():
    """Одинаковый (seed, n) даёт то же число."""
    from arbacc.core.rng import CounterRNG
    r1 = CounterRNG(seed=1, stream_id="x")
    r2 = CounterRNG(seed=1, stream_id="x")
    for n in [0, 1, 100, 10000]:
        assert r1.uniform(n) == r2.uniform(n)