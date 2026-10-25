"""Rump/Muller/Kahan recurrences as sequences, with explicit arithmetic modes.

S. M. Rump, ETNA 52 (2020), 358-369 and 571-575:
https://doi.org/10.1553/etna_vol52s358
https://etna.ricam.oeaw.ac.at/vol.52.2020/pp571-575.dir/pp571-575.pdf

The unperturbed exact recurrences 1,2,4 have poles; their reported zero is
not a limit. Backend arithmetic intentionally exposes finite-precision drift.
"""
from fractions import Fraction
from arbacc.core.registry import register
from arbacc.core.series import SequenceBase

# A + outer*(B + inner*C/u_(n-1))/u_n, followed in this order even when
# algebraic simplification would change floating-point rounding.
RUMP_SPECS={
 1:(Fraction(-1305),Fraction(-1440),Fraction(6496),-1,Fraction(4305920),1,Fraction(19979468800)),
 2:(Fraction(3),Fraction(170),Fraction(-256),1,Fraction(0),1,Fraction(131072)),
 3:(Fraction(11,2),Fraction(61,11),Fraction(111),-1,Fraction(1130),-1,Fraction(3000)),
 4:(Fraction(109225,43691),Fraction(10923,4369),Fraction(113,2),1,Fraction(160),-1,Fraction(1475,2)),
 5:(Fraction(4),Fraction(17,4),Fraction(108),-1,Fraction(815),-1,Fraction(1500)),
 6:(Fraction(-6),Fraction(64),Fraction(82),-1,Fraction(1824),-1,Fraction(6048)),
 7:(Fraction(8),Fraction(-31),Fraction(3,2),1,Fraction(972),1,Fraction(128)),
}


class UndefinedRecurrence(ArithmeticError):
    """The requested recurrence step divides by zero or an unresolved zero ball."""


class RumpSequence(SequenceBase):
    PARAM_SPEC={
        'x':{'type':'str','default':'0','short':'x','hint':'Perturbation of the first initial value'},
        'evaluation':{'type':'enum','values':['backend','exact'],'default':'backend','short':'ev'},
    }

    def __init__(self,params,**kwargs):
        super().__init__(params,**kwargs)
        self.offset=Fraction(self.params.get('x','0'))
        self.evaluation=self.params.get('evaluation','backend')
        if self.evaluation not in ('backend','exact'):
            raise ValueError('evaluation must be backend or exact')

    @property
    def reference_kind(self):
        if self.offset: return 'unavailable_perturbed_sequence'
        return 'undefined_exact_recurrence' if self.index in (1,2,4) else 'exact_arithmetic_sequence_limit'

    @staticmethod
    def _number(value,ctx):
        return ctx.backend.div(ctx.number(value.numerator),ctx.number(value.denominator),ctx.dps)

    def sequence_step(self,n,values,state,ctx):
        u0,u1,a,outer,b,inner,c=RUMP_SPECS[self.index]
        if self.evaluation=='exact':
            exact=state.setdefault('exact_values',[])
            if n==0: value=u0+self.offset
            elif n==1: value=u1
            else:
                left,right=exact[-2:]
                if not left or not right:
                    raise UndefinedRecurrence(f'rump_seq{self.index}: exact pole at index {n}')
                value=a+outer*(b+inner*c/left)/right
            exact.append(value)
            return self._number(value,ctx)
        if n==0: return self._number(u0+self.offset,ctx)
        if n==1: return self._number(u1,ctx)
        backend,dps=ctx.backend,ctx.dps
        left,right=values[-2:]
        if backend.sign(left,dps)==0 or backend.sign(right,dps)==0:
            raise UndefinedRecurrence(f'rump_seq{self.index}: zero or unresolved denominator at index {n}')
        inverse=backend.div(self._number(c,ctx),left,dps)
        middle=(backend.add if inner==1 else backend.sub)(self._number(b,ctx),inverse,dps)
        quotient=backend.div(middle,right,dps)
        value=(backend.add if outer==1 else backend.sub)(self._number(a,ctx),quotient,dps)
        if not backend.is_finite(value,dps): raise UndefinedRecurrence('Non-finite recurrence value')
        return value

    def analytic_sum(self,ctx):
        if self.offset or self.index in (1,2,4): return None
        if self.index in (3,5,6): return ctx.number({3:6,5:5,6:36}[self.index])
        b,d=ctx.backend,ctx.dps
        return b.div(b.sub(ctx.number(-61),b.pow(ctx.number(3657),ctx.number('.5'),d),d),ctx.number(4),d)


for _index in range(1,8):
    _name=f'rump_seq{_index}'
    _class_name=f'RumpSequence{_index}'
    _cls=type(_class_name,(RumpSequence,),{'__module__':__name__,'name':_name,'display_name':_name,'index':_index})
    globals()[_class_name]=register('series',_name)(_cls)
