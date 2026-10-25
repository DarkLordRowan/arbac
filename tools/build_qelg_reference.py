"""Build an OPTIONAL external binary64 QELG oracle (run in Linux/WSL with cc).

Downloads the hash-pinned GSL source to the selected output directory.
The GPL source/license remains there and is NOT vendored in this repository.
Wrapper matches our documented restart/refill policy; QELG itself is unmodified.
Usage: python tools/build_qelg_reference.py --output /tmp/shanks-qelg-reference
Then set SHANKS_QELG_REFERENCE to the printed executable path for pytest.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import urllib.request

URL='https://raw.githubusercontent.com/ampl/gsl/master/integration/qelg.c'
SHA256='57c217594cdb69ec99875820299ea55477694a4fab2e0a5965b44d3bd482cf4a'
DRIVER=r'''#include <stddef.h>
#include <stdio.h>
#include <math.h>
#include <float.h>
#define GSL_DBL_MAX DBL_MAX
#define GSL_DBL_EPSILON DBL_EPSILON
#define GSL_MAX_DBL(a,b) ((a)>(b)?(a):(b))
#include SOURCE
int main(void){
 struct extrapolation_table t;initialise_table(&t);
 double y,result,error,estimate=0;int have=0;
 while(scanf("%lf",&y)==1){
  append_table(&t,y);size_t before=t.nres;int mature=t.n>=3;
  qelg(&t,&result,&error);
  if(mature || !have)estimate=result;
  if(mature)have=1;
  if(mature && before==t.nres){initialise_table(&t);append_table(&t,y);}
  printf("%.17g\n",estimate);
 }
 return 0;
}
'''


def build(output,compiler='cc'):
    output=Path(output).resolve();output.parent.mkdir(parents=True,exist_ok=True)
    source=output.with_name(output.name+'.upstream.c')
    driver=output.with_name(output.name+'.driver.c')
    data=urllib.request.urlopen(URL,timeout=30).read()
    if hashlib.sha256(data).hexdigest()!=SHA256:
        raise RuntimeError('Upstream QELG content changed; inspect it before updating the expected hash')
    source.write_bytes(data)
    driver.write_text(DRIVER.replace('SOURCE',json.dumps(source.name)),encoding='utf-8')
    subprocess.run([compiler,'-std=c99','-O2',str(driver),'-lm','-o',str(output)],check=True)
    return output


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('/tmp/shanks-qelg-reference'))
    parser.add_argument('--compiler',default='cc')
    args=parser.parse_args()
    print(build(args.output,args.compiler))
