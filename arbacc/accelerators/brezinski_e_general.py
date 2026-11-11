"""Brezinski generalized E-algorithm with explicit auxiliary sequences.

A. Fdil, 'Some results on convergence acceleration for the E-algorithm',
Applicationes Mathematicae 24(4) (1997) 393-413, Section 1 recurrence:
https://matwbn.icm.edu.pl/ksiazki/zm/zm24/zm2443.pdf
Also Encyclopedia of Mathematics, 'Extrapolation algorithm'.

Unlike blind methods, E requires the user to provide the error basis.
This is a MODEL-ASSISTED method and MUST be benchmarked separately from
black-box accelerators that do not know the asymptotic remainder.

Basis syntax (comma separated, no eval):
  pow:1,pow:2       (n+beta)**(-1), (n+beta)**(-2)
  geom:0.7          (0.7)**n
  altpow:0.5        (-1)**n/(n+beta)**0.5
  log:1             1/log(n+beta)**1 (n+beta must be >1)

"""
from __future__ import annotations
from arbacc.core.accelerator import AcceleratorBase
from arbacc.core.registry import register
from arbacc.core.stream import extend_partials


def _parse_basis(value):
    entries=[]
    for token in value.split(','):
        token=token.strip()
        if not token:continue
        if ':' not in token: raise ValueError('Expected basis type:parameter, got '+token)
        kind,param=(z.strip().lower() for z in token.split(':',1))
        if kind not in {'pow','geom','altpow','log'}:
            raise ValueError(f'Unsupported E auxiliary basis: {kind}')
        if not param or any(z in param for z in ('(',')','[',']',';')):
            raise ValueError('Invalid basis numeric parameter')
        entries.append((kind,param))
    if not entries: raise ValueError('E basis must not be empty')
    return entries


@register('accelerators','brezinski_e')
class BrezinskiE(AcceleratorBase):

    # Bibliographic provenance, not a claim of numerical equivalence.
    LITERATURE = {'citation': 'Fdil, Some results on convergence acceleration for the E-algorithm, Applicationes Mathematicae 24(4) (1997)', 'url': 'https://matwbn.icm.edu.pl/ksiazki/zm/zm24/zm2443.pdf', 'locator': 'section 1 recurrence', 'relation': 'model_assisted', 'implementation_note': 'Requires explicit auxiliary/error basis; compare separately from black-box methods.'}
    name=display_name='brezinski_e'
    PARAM_SPEC={
        'order':{'type':'int','min':1,'default':2,'short':'k'},
        'basis':{'type':'str','default':'pow:1,pow:2','short':'g'},
        'beta':{'type':'str','default':'2','short':'beta'},
        'pivot_rel_tol':{'type':'str','default':'auto','short':'ptol'},
    }
    def __init__(self,params=None):
        super().__init__(params)
        self.order=self.params.get('order',2)
        if type(self.order) is not int or not (1<=self.order<=20):
            raise ValueError('E order must be integer in 1..20')
        self.basis=_parse_basis(self.params.get('basis','pow:1,pow:2'))
        if self.order != len(self.basis):
            raise ValueError('E order must equal number of auxiliary sequences in basis')

    def required_input(self,state):
        return state.iteration+self.order+1

    def _g(self,index,spec,ctx):
        b,d=ctx.backend,ctx.dps
        kind,param=spec
        power=ctx.number(param)
        if not b.is_finite(power,d): raise ValueError('Nonfinite E basis parameter')
        beta=ctx.number(self.params.get('beta','2'))
        if not b.is_finite(beta,d) or b.sign(beta,d)<=0:
            raise ValueError('E beta must be positive and finite')
        x=b.add(ctx.number(index),beta,d)
        if kind=='geom':
            # n is an EXACT integer, power may be negative or fractional.
            return b.pow(power,ctx.number(index),d)
        if b.sign(x,d)<=0:raise ValueError('E grid n+beta must be positive')
        if kind=='log':
            log=b.log(x,d)
            if b.sign(log,d)<=0:raise ValueError('E log basis requires log(n+beta)>0')
            return b.div(ctx.number(1),b.pow(log,power,d),d)
        term=b.div(ctx.number(1),b.pow(x,power,d),d)
        if kind=='altpow' and index%2:term=b.neg(term,d)
        return term

    def step(self,source,state,ctx):
        b,d,n,k=ctx.backend,ctx.dps,state.iteration,self.order
        s=extend_partials(source,state.extra.get('partials',[]),ctx,self.required_input(state))
        rows=[s[n:n+k+1]]
        auxiliary={i:[self._g(j,self.basis[i],ctx) for j in range(n,n+k+1)] for i in range(k)}
        # Eliminate basis components using the *published E recurrence*.
        current=rows[0]
        for level in range(k):
            g=auxiliary[level]
            following=[]
            transformed={i:[] for i in range(level+1,k)}
            for j in range(len(current)-1):
                a,bb=g[j],g[j+1]
                denom=b.sub(bb,a,d)
                abs_a=b.abs_val(a,d); abs_bb=b.abs_val(bb,d)
                scale=abs_a if b.sign(b.sub(abs_a,abs_bb,d),d)>=0 else abs_bb
                tol_text=self.params.get('pivot_rel_tol','auto')
                tol=ctx.number(f'1e-{max(12,d//2)}') if tol_text=='auto' else ctx.number(tol_text)
                if not b.is_finite(tol,d) or b.sign(tol,d)<0:
                    raise ValueError('E pivot_rel_tol must be finite and nonnegative')
                threshold=b.mul(tol,scale,d)
                if b.sign(denom,d)==0 or b.sign(b.sub(b.abs_val(denom,d),threshold,d),d)<=0:
                    raise ArithmeticError(f'E singular/ill-conditioned auxiliary difference, level={level+1}, j={j}')
                next_value=b.div(b.sub(b.mul(bb,current[j],d),b.mul(a,current[j+1],d),d),denom,d)
                if not b.is_finite(next_value,d):
                    raise ArithmeticError('E non-finite transformed value')
                following.append(next_value)
                for i in range(level+1,k):
                    h=auxiliary[i]
                    num=b.sub(b.mul(bb,h[j],d),b.mul(a,h[j+1],d),d)
                    transformed[i].append(b.div(num,denom,d))
            auxiliary.update(transformed)
            current=following
        result=state.with_estimate(current[0])
        result.extra.update(partials=s,math_status='full_order',assistance='known_error_basis',basis=self.basis[:])
        return result
