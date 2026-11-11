"""Cross implementation: mpmath's Sidi-S factorial recurrence vs Arbac quotient.

mpmath documents method='sidi' as the Sidi-S transformation and implements
an independent triangular recurrence. These are finite numerical regression
checks (not a proof of equality with a printed formula in Sidi 2003).

References: A. Sidi, Practical Extrapolation Methods (2003), §19.3;
mpmath.calculus.extrapolation.levin.factor_sidi and mpmath documentation.
https://mpmath.org/doc/current/calculus/sums_limits.html
"""
import mpmath as mp
import pytest
import arbacc.accelerators  # noqa: F401
from arbacc.core import AlgoState, Context, get
from arbacc.precision import get_backend

class PartialSumSource:
    kind = "sequence"
    def __init__(self, vals):
        self.vals = vals
    def get(self, n):
        return self.vals[n]
    def extend_to(self, n):
        if not 0 <= n < len(self.vals):
            raise IndexError(n)
    def __len__(self):
        return len(self.vals)

@pytest.mark.parametrize("variant", ["t", "u", "v"])
@pytest.mark.parametrize("beta", ["0.5", "1", "2"])
@pytest.mark.parametrize("order", [1, 2, 3, 4, 5])
@pytest.mark.parametrize("case", ["exp_log", "alternating", "mixed"])
def test_sidi_s_matches_independent_mpmath_sidi_evaluator(variant, beta, order, case):
    with mp.workdps(110):
        v = {
           "exp_log": lambda n: mp.mpf("1.7") + mp.power(mp.mpf("0.6"), n) + mp.mpf(1)/(n+5),
           "alternating": lambda n: mp.mpf("1") + (-1)**n/mp.power(n+2, mp.mpf("0.7")),
           "mixed": lambda n: mp.mpf("3") + mp.power(mp.mpf("0.23"),n) + mp.mpf("2")/(n+4),
        }
        samples = [v[case](n) for n in range(18)]
        reference = mp.levin(method="sidi", variant=variant)
        reference.theta = mp.mpf(beta)
        need = order + 2 if variant == "v" else order + 1
        benchmark = reference.update_psum(samples[:need])[0]
        ctx = Context(get_backend("mpmath"), 100)
        algorithm = get("accelerators","levin_sidi_s")({
           "order":order, "beta":beta, "remainder":variant, "evaluation":"direct"})
        output = algorithm.step(PartialSumSource(samples),AlgoState(iteration=0),ctx)
        difference = abs(benchmark-output.estimate)
        assert difference < mp.mpf("1e-75")*max(1,abs(benchmark)), (
           case, variant, beta, order, difference)
