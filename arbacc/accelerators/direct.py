"""Direct sequence transforms, with backend arithmetic throughout.

Shanks: https://dlmf.nist.gov/3.9#iv, Eq. 3.9.9.
Levin/Weniger: https://dlmf.nist.gov/3.9#v, Eqs. 3.9.13-3.9.16.
Richardson here assumes errors in successive powers of 4**(-n), as in
shanks-university; this assumption is not appropriate for arbitrary series.
"""
from math import comb
from arbacc.core.accelerator import AcceleratorBase
from arbacc.core.registry import register
from arbacc.core.stream import extend_partials, series_term


def _partials(source, state, ctx, count):
    return extend_partials(source,state.extra.get("partials",[]),ctx,count)


def _det(matrix, ctx):
    """Gaussian elimination with partial pivoting; None means singular."""
    b, d = ctx.backend, ctx.dps
    a = [row[:] for row in matrix]
    result = ctx.number(1)
    for k in range(len(a)):
        pivot = k
        for i in range(k + 1, len(a)):
            if b.sign(b.sub(b.abs_val(a[i][k], d), b.abs_val(a[pivot][k], d), d), d) > 0:
                pivot = i
        if b.sign(a[pivot][k], d) == 0:
            # An Arb ball containing zero is not necessarily exactly zero.
            return ctx.number(0) if all(a[i][k] == ctx.number(0) for i in range(k,len(a))) else None
        if pivot != k:
            a[pivot], a[k] = a[k], a[pivot]
            result = b.neg(result, d)
        result = b.mul(result, a[k][k], d)
        for i in range(k + 1, len(a)):
            ratio = b.div(a[i][k], a[k][k], d)
            for j in range(k + 1, len(a)):
                a[i][j] = b.sub(a[i][j], b.mul(ratio, a[k][j], d), d)
    return result


class _FixedOrder(AcceleratorBase):
    PARAM_SPEC = {"order": {"type": "int", "min": 0, "default": 2, "short": "k"}}

    def __init__(self, params=None):
        super().__init__(params)
        self.order = self.params.get("order", 2)
        if isinstance(self.order, bool) or not isinstance(self.order, int) or self.order < 0:
            raise ValueError("order must be a nonnegative integer")


@register("accelerators", "shanks")
class Shanks(_FixedOrder):
    name = display_name = "shanks"

    def required_input(self, state):
        return state.iteration + 2 * self.order + 1

    def step(self, source, state, ctx):
        b, d, n, k = ctx.backend, ctx.dps, state.iteration, self.order
        s = _partials(source, state, ctx, self.required_input(state))
        # Same determinant representation as the C++ implementation:
        # rows s_(n+j+r)-s_(n+j), equivalent to successive differences.
        common = [[b.sub(s[n+j+r], s[n+j], d) for j in range(k+1)] for r in range(1, k+1)]
        denominator = _det([[ctx.number(1)] * (k+1)] + common, ctx)
        estimate = s[n+2*k]
        if denominator is not None and b.sign(denominator, d) != 0:
            numerator = _det([s[n:n+k+1]] + common, ctx)
            if numerator is not None:
                estimate = b.div(numerator, denominator, d)
        result = state.with_estimate(estimate)
        result.extra["partials"] = s
        return result


@register("accelerators", "richardson")
class Richardson(AcceleratorBase):
    """Romberg-style extrapolation on a dyadic grid (error ratio 1/4)."""
    name = display_name = "richardson"
    PARAM_SPEC = {}

    def required_input(self, state):
        return state.iteration + 1

    def step(self, source, state, ctx):
        b, d = ctx.backend, ctx.dps
        s = _partials(source, state, ctx, self.required_input(state))
        row = s[:]
        for order in range(1, len(s)):
            factor = ctx.number(4**order)
            row = [b.div(b.sub(b.mul(factor, row[i+1], d), row[i], d), ctx.number(4**order-1), d)
                   for i in range(len(row)-1)]
        result = state.with_estimate(row[0])
        result.extra["partials"] = s
        return result


@register("accelerators", "levin")
class Levin(_FixedOrder):
    """Levin transform with explicit beta and remainder estimates.

    Weniger (1989), Sections 7.1 and 7.3:
    https://arxiv.org/pdf/math/0306302
    Default next-term remainder and beta=1 retain the original DLMF form.
    """
    name = display_name = "levin"
    PARAM_SPEC = {
        **_FixedOrder.PARAM_SPEC,
        "beta": {"type": "str", "default": "1", "short": "b"},
        "remainder": {"type": "enum", "values": ["next", "t", "u", "v", "v_shift"],
                      "default": "next", "short": "r"},
    }

    def __init__(self, params=None):
        super().__init__(params)
        self.remainder = self.params.get("remainder", "next")
        if self.remainder not in self.PARAM_SPEC["remainder"]["values"]:
            raise ValueError("Unknown remainder estimate")

    def beta(self, ctx):
        value = ctx.number(self.params.get("beta", "1"))
        if not ctx.backend.is_finite(value, ctx.dps) or ctx.backend.sign(value, ctx.dps) <= 0:
            raise ValueError("beta must be finite and positive")
        return value

    def required_input(self, state):
        lookahead = {"next": 1, "t": 0, "u": 0, "v": 1, "v_shift": 2}[self.remainder]
        return state.iteration + self.order + 1 + (lookahead if self.order else 0)

    def weight(self, index, ctx):
        b, d = ctx.backend, ctx.dps
        return b.pow(b.add(ctx.number(index), self.beta(ctx), d), ctx.number(self.order-1), d)

    def inverse_remainder(self, source, index, ctx):
        b, d = ctx.backend, ctx.dps
        offset = int(self.remainder in ("next", "v_shift"))
        a = series_term(source,index+offset,ctx)
        if self.remainder in ("v", "v_shift"):
            following = series_term(source,index+offset+1,ctx)
            product = b.mul(a, following, d)
            if b.sign(product, d) == 0:
                return None
            return b.div(b.sub(following, a, d), product, d)
        if self.remainder == "u":
            a = b.mul(b.add(ctx.number(index), self.beta(ctx), d), a, d)
        return None if b.sign(a, d) == 0 else b.div(ctx.number(1), a, d)

    def step(self, source, state, ctx):
        b, d, n, k = ctx.backend, ctx.dps, state.iteration, self.order
        self.beta(ctx)
        s = _partials(source, state, ctx, n+k+1)
        numerator, denominator = ctx.number(0), ctx.number(0)
        estimate = s[n+k]
        if k == 0:
            estimate = s[n]
        else:
            for j in range(k+1):
                inverse = self.inverse_remainder(source, n+j, ctx)
                if inverse is None:
                    break
                coefficient = b.mul(ctx.number((-1)**j * comb(k,j)), self.weight(n+j, ctx), d)
                weight = b.mul(coefficient, inverse, d)
                denominator = b.add(denominator, weight, d)
                numerator = b.add(numerator, b.mul(weight, s[n+j], d), d)
            else:
                if b.sign(denominator, d) != 0:
                    estimate = b.div(numerator, denominator, d)
        result = state.with_estimate(estimate)
        result.extra["partials"] = s
        return result


@register("accelerators", "weniger")
class Weniger(Levin):
    """Factorial-series transform with explicit remainder estimates, beta>0.

    https://arxiv.org/pdf/math/0306302, Section 8.2.
    """
    name = display_name = "weniger"

    def weight(self, index, ctx):
        b, d, value = ctx.backend, ctx.dps, ctx.number(1)
        start = b.add(ctx.number(index), self.beta(ctx), d)
        for j in range(self.order-1):
            value = b.mul(value, b.add(start, ctx.number(j), d), d)
        return value


@register("accelerators", "drummond")
class Drummond(Levin):
    """Finite differences of s_n/omega_n and 1/omega_n.

    https://arxiv.org/pdf/math/0306302, Eqs. (9.5-3)-(9.5-4).
    The default remainder is a_(n+1); select t for Drummond's a_n variant.
    """
    name = display_name = "drummond"

    def weight(self, index, ctx):
        return ctx.number(1)
