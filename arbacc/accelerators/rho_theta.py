"""Rho and theta: Weniger (1989), Eqs. (6.2-2), (10.1-9).

https://arxiv.org/pdf/math/0306302
order is the number of even transforms: rho_(2*order), theta_(2*order).
Rho uses x_n=n+1. Series terms are not interpolation nodes.
Singular cells are unavailable; fall back to a lower transform or raw sum.
"""
from arbacc.core.registry import register
from arbacc.accelerators.direct import _FixedOrder, _partials


@register("accelerators", "wynn_rho")
class WynnRho(_FixedOrder):
    name = display_name = "wynn_rho"

    def required_input(self, state):
        return state.iteration + 2*self.order + 1

    def step(self, source, state, ctx):
        b, d, n = ctx.backend, ctx.dps, state.iteration
        sums = _partials(source, state, ctx, self.required_input(state))
        current = sums[n:n+2*self.order+1]
        previous = [ctx.number(0)]*(len(current)+1)
        estimate = current[-1]
        for column in range(1, 2*self.order+1):
            following = []
            for j in range(len(current)-1):
                value = None
                if previous[j+1] is not None and current[j] is not None and current[j+1] is not None:
                    difference = b.sub(current[j+1], current[j], d)
                    if b.sign(difference, d) != 0:
                        value = b.add(previous[j+1], b.div(ctx.number(column), difference, d), d)
                following.append(value)
            previous, current = current, following
            if column % 2 == 0 and current[0] is not None:
                estimate = current[0]
        result = state.with_estimate(estimate)
        result.extra["partials"] = sums
        return result


@register("accelerators", "brezinski_theta")
class BrezinskiTheta(_FixedOrder):
    name = display_name = "brezinski_theta"

    def required_input(self, state):
        return state.iteration + 3*self.order + 1

    def step(self, source, state, ctx):
        b, d, n = ctx.backend, ctx.dps, state.iteration
        sums = _partials(source, state, ctx, self.required_input(state))
        even = sums[n:n+3*self.order+1]
        previous_odd = [ctx.number(0)]*len(even)
        estimate = even[-1]
        for _ in range(self.order):
            odd = []
            for j in range(len(even)-1):
                value = None
                if even[j] is not None and even[j+1] is not None and previous_odd[j+1] is not None:
                    difference = b.sub(even[j+1], even[j], d)
                    if b.sign(difference, d) != 0:
                        value = b.add(previous_odd[j+1], b.div(ctx.number(1), difference, d), d)
                odd.append(value)
            following = []
            for j in range(len(even)-3):
                value = None
                if all(x is not None for x in (even[j+1], even[j+2], odd[j], odd[j+1], odd[j+2])):
                    left = b.sub(odd[j+1], odd[j], d)
                    right = b.sub(odd[j+2], odd[j+1], d)
                    second = b.sub(right, left, d)
                    if b.sign(second, d) != 0:
                        numerator = b.mul(b.sub(even[j+2], even[j+1], d), right, d)
                        value = b.add(even[j+1], b.div(numerator, second, d), d)
                following.append(value)
            previous_odd, even = odd, following
            if even[0] is not None:
                estimate = even[0]
        result = state.with_estimate(estimate)
        result.extra["partials"] = sums
        return result
