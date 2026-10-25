"""Wynn epsilon table; https://dlmf.nist.gov/3.9#iv (3.9.11).

Iteration k uses 2k+1 partial sums. Singular cells are unavailable;
the highest available even column is used, without claiming convergence.
"""
from arbacc.core.accelerator import AcceleratorBase, AlgoState
from arbacc.core.registry import register
from arbacc.core.stream import partial_value


@register("accelerators", "wynn_epsilon")
class WynnEpsilon(AcceleratorBase):
    name = "wynn_epsilon"
    display_name = "wynn"
    PARAM_SPEC = {}

    def required_input(self, state: AlgoState) -> int:
        return 2 * state.iteration + 1

    def step(self, source, state, ctx):
        b, dps = ctx.backend, ctx.dps
        partials = state.extra.get("partials", [])
        eps = state.extra.get("eps", [])
        zero, one = ctx.number(0), ctx.number(1)
        target = self.required_input(state)
        # Append each new diagonal once: O(N^2) arithmetic overall.
        while len(partials) < target:
            end = len(partials)
            partials.append(partial_value(source,end,partials[-1] if partials else None,ctx))
            if not eps:
                eps.append([])
            eps[0].append(partials[-1])
            for j in range(1, end + 1):
                if len(eps) <= j:
                    eps.append([])
                n = end - j
                previous = zero if j == 1 else eps[j - 2][n + 1]
                left, right = eps[j - 1][n], eps[j - 1][n + 1]
                value = None
                if previous is not None and left is not None and right is not None:
                    diff = b.sub(right, left, dps)
                    if b.sign(diff, dps) != 0:
                        value = b.add(previous, b.div(one, diff, dps), dps)
                eps[j].append(value)
        estimate = partials[-1]
        for j in range(target - 1, 1, -2):
            if eps[j][0] is not None:
                estimate = eps[j][0]
                break
        new_state = state.with_estimate(estimate)
        new_state.extra.update(partials=partials, eps=eps)
        return new_state
