"""Explicit legacy C++ Levin–Sidi S *formula* implementation for Arbac.

This reproduces the direct Pochhammer-weight quotient documented in
shanks-university/main/backend/core/include/transformations/levin_sidi_s_algorithm.hpp.
Do NOT claim it is mathematically distinct from Weniger S: with identical
omega_n, beta and order the two direct quotients are the same.  The separate
ID is intentional to compare parameter maps / numerical paths.

WARNING: Legacy C++ cites arXiv:math/0306302 as 'Sidi'; it is Weniger!
This is NOT the complete Sidi S algorithm defined in Sidi (2003) Ch.19 unless
an independent formula-level verification establishes that identification.
"""
from __future__ import annotations
from math import comb

from arbacc.core.accelerator import AcceleratorBase
from arbacc.core.registry import register
from arbacc.accelerators.direct import _partials
from arbacc.core.stream import series_term


@register("accelerators", "levin_sidi_s")
class LevinSidiS(AcceleratorBase):

    # Bibliographic provenance, not a claim of numerical equivalence.
    LITERATURE = {'citation': 'Sidi, Practical Extrapolation Methods (2003)', 'url': 'https://doi.org/10.1017/CBO9780511546815', 'locator': 'sections 6.3.3 and 19.3 (Sidi S; naming comparison still unresolved)', 'relation': 'attribution_pending', 'implementation_note': 'EXPLICIT WARNING: implementation is factorial Weniger S-type quotient; same formula as weniger at equal parameters. Verify exact Sidi ch.19 formula before claiming this identifier identifies Sidi S; see also https://arxiv.org/abs/math/0306302.'}
    name = display_name = "levin_sidi_s"
    PARAM_SPEC = {
        "order": {"type": "int", "min": 0, "default": 2, "short": "k"},
        "beta": {"type": "str", "default": "1", "short": "b"},
        "remainder": {"type": "enum", "values": ["u", "t", "next", "v", "v_shift"],
                      "default": "u", "short": "omega"},
        "evaluation": {"type": "enum", "values": ["direct", "finite_difference"],
                       "default": "direct", "short": "eval"},
    }

    def __init__(self, params=None):
        super().__init__(params)
        self.order = self.params.get("order", 2)
        self.remainder = self.params.get("remainder", "u")
        self.evaluation = self.params.get("evaluation", "direct")
        if type(self.order) is not int or self.order < 0:
            raise ValueError("order must be a nonnegative integer")
        if self.remainder not in self.PARAM_SPEC["remainder"]["values"]:
            raise ValueError("unknown remainder estimator")
        if self.evaluation not in self.PARAM_SPEC["evaluation"]["values"]:
            raise ValueError("unknown evaluation")

    def required_input(self, state):
        ahead = {"t": 0, "u": 0, "next": 1, "v": 1, "v_shift": 2}[self.remainder]
        return state.iteration + self.order + 1 + (ahead if self.order else 0)

    def _beta(self, ctx):
        b = ctx.number(self.params.get("beta", "1"))
        if not ctx.backend.is_finite(b, ctx.dps) or ctx.backend.sign(b, ctx.dps) <= 0:
            raise ValueError("beta must be finite > 0")
        return b

    def _invomega(self, source, j, ctx, beta):
        b, d = ctx.backend, ctx.dps
        off = int(self.remainder in ("next", "v_shift"))
        a = series_term(source, j + off, ctx)
        if self.remainder in ("v", "v_shift"):
            a1 = series_term(source, j + off + 1, ctx)
            denom = b.mul(a, a1, d)
            if b.sign(denom, d) == 0:
                raise ZeroDivisionError("zero v-estimator product")
            return b.div(b.sub(a1, a, d), denom, d)
        if self.remainder == "u":
            a = b.mul(b.add(ctx.number(j), beta, d), a, d)
        if b.sign(a, d) == 0:
            raise ZeroDivisionError("zero remainder estimate")
        return b.div(ctx.number(1), a, d)

    def step(self, source, state, ctx):
        b, d = ctx.backend, ctx.dps
        n, k = state.iteration, self.order
        beta = self._beta(ctx)
        s = _partials(source, state, ctx, n + k + 1)
        if k == 0:
            result = state.with_estimate(s[n])
        else:
            # a_j = (beta+n+j)_{k-1} / omega_{n+j}; common normalization
            # (beta+n+k)_{k-1} cancels in numerator/denominator.
            weight = []
            for j in range(k + 1):
                fac = ctx.number(1)
                for m in range(k - 1):
                    fac = b.mul(fac, b.add(beta, ctx.number(n + j + m), d), d)
                weight.append(b.mul(fac, self._invomega(source, n + j, ctx, beta), d))
            if self.evaluation == "direct":
                numer, denom = ctx.number(0), ctx.number(0)
                for j in range(k + 1):
                    c = (-1) ** j * comb(k, j)
                    w = b.mul(ctx.number(c), weight[j], d)
                    numer = b.add(numer, b.mul(w, s[n + j], d), d)
                    denom = b.add(denom, w, d)
            else:
                # Independently evaluate the SAME quotient by forward differences.
                row_n = [b.mul(weight[j], s[n + j], d) for j in range(k + 1)]
                row_d = weight[:]
                for level in range(k):
                    row_n = [b.sub(row_n[j + 1], row_n[j], d) for j in range(len(row_n) - 1)]
                    row_d = [b.sub(row_d[j + 1], row_d[j], d) for j in range(len(row_d) - 1)]
                numer, denom = row_n[0], row_d[0]
            if b.sign(denom, d) == 0:
                raise ZeroDivisionError("S-transform denominator is zero")
            estimate = b.div(numer, denom, d)
            if not b.is_finite(estimate, d):
                raise ArithmeticError("non-finite S-transform result")
            result = state.with_estimate(estimate)
        result.extra["partials"] = s
        result.extra["math_status"] = "identity_order_zero" if k == 0 else "full_order"
        result.extra["achieved_order"] = k
        result.extra["requested_order"] = k
        result.extra["remainder_estimator"] = self.remainder
        return result
