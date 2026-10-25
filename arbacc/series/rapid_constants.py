"""Two rapidly convergent series whose C++ references had only eight digits.

For n>=1, both magnitudes decrease and the alternating remainder is bounded
by the first omitted term. For n!/n^n the ratio is (n/(n+1))^n <= 1/2.
Independent reference identities used by tests follow from Euler's gamma
integral and the differentiated geometric series (DLMF 5.9 and 4.6):
 sum (-1)^n n!/n^n = integral_0^1 log(t)/(1-t*log(t))^2 dt;
 sum (-1)^n/n^n = -integral_0^1 t^t dt (the sophomore's dream).
"""
from arbacc.core.registry import register
from arbacc.series.taylor import _Taylor


class _AlternatingRapid(_Taylor):
    reference_kind='ordinary_sum_with_alternating_tail_bound'
    factorial=False

    def magnitude(self,k,backend,dps):
        numerator=backend.factorial(k,dps) if self.factorial else backend.number(1,dps)
        return backend.div(numerator,backend.pow(backend.number(k,dps),backend.number(k,dps),dps),dps)

    def generate(self,n,ctx):
        if n<0: raise IndexError('negative term index')
        b,d=ctx.backend,ctx.dps
        value=self.magnitude(n+1,b,d)
        if n%2==0: value=b.neg(value,d)
        return b.mul(self.argument(ctx),value,d)

    def analytic_sum(self,ctx):
        b,d=ctx.backend,ctx.dps
        scale=self.argument(ctx)
        if b.sign(scale,d)==0: return ctx.number(0)
        work=d+20
        total=b.number(0,work)
        threshold=b.number('1e-'+str(d+12),work)
        for k in range(1,8*(work+1)):
            term=self.magnitude(k,b,work)
            total=b.add(total,b.neg(term,work) if k%2 else term,work)
            tail=self.magnitude(k+1,b,work)
            if b.sign(b.sub(threshold,tail,work),work)>0:
                # Tail bound is attached as an interval radius in Arb.
                bounded=b.with_error(total,tail,work)
                value=b.mul(bounded,b.number(scale,work),work)
                result=b.number(value,d)
                b.activate(d)
                return result
        b.activate(d)
        raise ArithmeticError('reference tail did not reach requested precision')


@register('series','minus_one_n_fact_n_in_n')
class AlternatingFactorial(_AlternatingRapid):
    name=display_name='minus_one_n_fact_n_in_n'
    factorial=True


@register('series','minus_one_ned_in_n')
class AlternatingSophomore(_AlternatingRapid):
    name=display_name='minus_one_ned_in_n'
