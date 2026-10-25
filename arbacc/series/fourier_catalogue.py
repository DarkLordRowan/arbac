"""Real Fourier expansions with explicit intervals and endpoint conventions.

Sources: https://dlmf.nist.gov/1.8 and /24.8 (Bernoulli Fourier series),
https://dlmf.nist.gov/4.22 and /4.36 (sine/sinh product and partial fractions).
Piecewise linear/quadratic formulae follow by integrating these Fourier series.
A table entry includes both its convergence interval and closed form.
"""
from arbacc.core.registry import register
from arbacc.series.taylor import _Taylor
from arbacc.series.rational_catalogue import _Arithmetic


class _TrigArithmetic(_Arithmetic):
    def sin(self,x): return self.backend.sin(self.ctx.number(x),self.dps)
    def cos(self,x): return self.backend.cos(self.ctx.number(x),self.dps)
    def exp(self,x): return self.backend.exp(self.ctx.number(x),self.dps)
    def absolute(self,x): return self.backend.abs_val(self.ctx.number(x),self.dps)
    def sign(self,x): return self.backend.sign(self.ctx.number(x),self.dps)


def _coth_remainder(x,a):
    if a.sign(x)==0: return a.ctx.number(0)
    z=a.mul(a.pi,x)
    exponential=a.exp(a.mul(2,z))
    return a.sub(a.mul(z,a.div(a.add(exponential,1),a.sub(exponential,1))),1)


# (lower bound, upper bound, closed endpoints, nth term with k=n+1, limit).
# None bounds mean all finite real arguments. Bound functions preserve precision.
FOURIER_SPECS={
 'abs_sin_x_minus_2_div_pi': (None,None,True,
    lambda k,x,a:a.div(a.mul(-4,a.cos(a.mul(2*k,x))),a.mul(a.pi,(2*k-1)*(2*k+1))),
    lambda x,a:a.sub(a.absolute(a.sin(x)),a.div(2,a.pi))),
 'half_minus_sinx_multi_pi_4': (lambda a:0,lambda a:a.pi,True,
    lambda k,x,a:a.div(a.cos(a.mul(2*k,x)),(2*k-1)*(2*k+1)),
    lambda x,a:a.sub(a.div(1,2),a.mul(a.div(a.pi,4),a.sin(x)))),
 'half_multi_ln_1div2multi1minuscosx': (lambda a:0,lambda a:a.mul(2,a.pi),False,
    lambda k,x,a:a.div(a.cos(a.mul(k,x)),k),
    lambda x,a:a.div(a.log(a.sub(2,a.mul(2,a.cos(x)))),-2)),
 'minus_3_div_4_or_x_minus_3_div_4': (lambda a:-3,lambda a:3,False,
    lambda k,x,a:a.add(
       a.div(a.mul(-6,a.cos(a.div(a.mul((2*k-1),a.mul(a.pi,x)),3))),a.mul(a.power(a.pi,2),(2*k-1)**2)),
       a.div(a.mul(3*(-1)**(k-1),a.sin(a.div(a.mul(k,a.mul(a.pi,x)),3))),a.mul(a.pi,k))),
    lambda x,a:a.sub(a.div(a.add(a.absolute(x),x),2),a.div(3,4))),
 'minus_x_minus_pi_4_or_minus_pi_4': (lambda a:a.mul(-1,a.pi),lambda a:a.pi,False,
    lambda k,x,a: a.div(a.pi,4) if k==1 else a.add(
        a.div(a.mul((-1)**(k-1)-1,a.cos(a.mul(k-1,x))),a.mul(a.pi,(k-1)**2)),
        a.div(a.mul((-1)**(k-1),a.sin(a.mul(k-1,x))),k-1)),
    lambda x,a:a.div(a.sub(a.absolute(x),x),2)),
 'one_twelfth_3x2_pi2': (lambda a:a.mul(-1,a.pi),lambda a:a.pi,True,
    lambda k,x,a:a.div(a.mul((-1)**k,a.cos(a.mul(k,x))),k*k),
    lambda x,a:a.div(a.sub(a.mul(3,a.power(x,2)),a.power(a.pi,2)),12)),
 'one_twelfth_x2_pi2': (lambda a:a.mul(-1,a.pi),lambda a:a.pi,True,
    lambda k,x,a:a.div(a.mul((-1)**k,a.sin(a.mul(k,x))),k**3),
    lambda x,a:a.div(a.mul(x,a.sub(a.power(x,2),a.power(a.pi,2))),12)),
 'pi_8_cosx_square_minus_1_div_3_cosx': (lambda a:a.div(a.pi,-2),lambda a:a.div(a.pi,2),True,
    lambda k,x,a:a.div(a.mul((-1)**(k-1),a.cos(a.mul(2*k+1,x))),(2*k-1)*(2*k+1)*(2*k+3)),
    lambda x,a:a.sub(a.mul(a.div(a.pi,8),a.power(a.cos(x),2)),a.div(a.cos(x),3))),
 'pi_minus_3pi_4_and_pi_minus_x_minus_3pi_4': (lambda a:a.mul(-1,a.pi),lambda a:a.pi,False,
    lambda k,x,a:a.add(a.div(a.mul(1+(-1)**(k-1),a.cos(a.mul(k,x))),a.mul(a.pi,k*k)),
                      a.div(a.mul((-1)**k,a.sin(a.mul(k,x))),k)),
    lambda x,a:a.sub(a.div(a.pi,4),a.div(a.add(a.absolute(x),x),2))),
 'pi_minus_x_2': (lambda a:0,lambda a:a.mul(2,a.pi),False,
    lambda k,x,a:a.div(a.sin(a.mul(k,x)),k),
    lambda x,a:a.div(a.sub(a.pi,x),2)),
 'pi_x_minus_x_square_square_minus_three_pi_x_plus_two_pi_square':
    (lambda a:0,lambda a:a.mul(2,a.pi),True,
     lambda k,x,a:a.div(a.mul(8,a.sin(a.mul(2*k-1,x))),a.mul(a.pi,(2*k-1)**3)),
     lambda x,a:a.sub(a.mul(a.pi,x),a.power(x,2)) if a.sign(a.sub(a.pi,x))>=0
                else a.add(a.sub(a.power(x,2),a.mul(a.mul(3,a.pi),x)),a.mul(2,a.power(a.pi,2)))),
 'pi_x_multi_e_xpi_plus_e_minusxpi_divided_e_xpi_minus_e_minusxpi':
    (None,None,True, lambda k,x,a:a.div(a.mul(2,a.power(x,2)),a.add(a.power(x,2),k*k)), _coth_remainder),
 'ten_minus_x': (lambda a:5,lambda a:15,False,
    lambda k,x,a:a.div(a.mul(10*(-1)**k,a.sin(a.div(a.mul(k,a.mul(a.pi,x)),5))),a.mul(k,a.pi)),
    lambda x,a:a.sub(10,x)),
 'x': (lambda a:a.mul(-1,a.pi),lambda a:a.pi,False,
    lambda k,x,a:a.div(a.mul(2*(-1)**(k-1),a.sin(a.mul(k,x))),k),
    lambda x,a:x),
}


class _FourierSeries(_Taylor):
    def argument(self,ctx):
        value=super().argument(ctx)
        lower,upper,closed,_,_=self.SPEC
        a=_TrigArithmetic(ctx)
        if lower is not None:
            left=a.sign(a.sub(value,lower(a)))
            right=a.sign(a.sub(upper(a),value))
            if left<0 or right<0 or (not closed and (left==0 or right==0)):
                raise ValueError('Argument outside the specified real Fourier branch')
        return value

    def generate(self,n,ctx):
        if n<0: raise IndexError('negative term index')
        return self.SPEC[3](n+1,self.argument(ctx),_TrigArithmetic(ctx))

    def analytic_sum(self,ctx):
        return self.SPEC[4](self.argument(ctx),_TrigArithmetic(ctx))


for _name,_spec in FOURIER_SPECS.items():
    _class_name=''.join(part.capitalize() for part in _name.split('_'))+'Series'
    _class=type(_class_name,(_FourierSeries,),{
        '__module__':__name__,'name':_name,'display_name':_name,'SPEC':_spec,
        '__doc__':'Fourier expansion; see FOURIER_SPECS, DLMF 1.8 and 24.8.',
    })
    globals()[_class_name]=register('series',_name)(_class)
