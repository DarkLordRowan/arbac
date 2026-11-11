"""Inject per-method bibliography metadata without replacing mathematical code.

Usage: python tools/apply_algorithm_literature.py [--check]
Keeps original algorithm files, creates backups under docs/_literature_backup.
"""
from __future__ import annotations
import argparse
import ast
from pathlib import Path
import json
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
MOD=ROOT/'arbacc'/'accelerators'
MAN=ROOT/'docs'/'algorithm_literature.json'

def parse_registration(d):
    if not isinstance(d,ast.Call) or not isinstance(d.func,ast.Name) or d.func.id!='register':return None
    try:k,n=[ast.literal_eval(v) for v in d.args[:2]]
    except (ValueError,TypeError):return None
    return n if k=='accelerators' else None

def build_changes(refs,check):
    updates=[];errors=[];discovered={};backups=[]
    for file in sorted(MOD.glob('*.py')):
        src=file.read_text(encoding='utf-8')
        tree=ast.parse(src,filename=str(file))
        additions=[]
        for node in tree.body:
            if not isinstance(node,ast.ClassDef):continue
            for dec in node.decorator_list:
                name=parse_registration(dec)
                if name is None:continue
                if name in discovered:errors.append(f'Duplicate registered name {name}: {file}');continue
                discovered[name]=str(file)
                if name not in refs:
                    errors.append(f'Missing provenance for new algorithm {name} in {file}')
                    continue
                existing=[x for x in node.body if isinstance(x,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='LITERATURE' for t in x.targets)]
                if existing:
                    try:old=ast.literal_eval(existing[0].value)
                    except Exception:errors.append(f'Bad existing LITERATURE: {name}');continue
                    if old!=refs[name]:errors.append(f'Existing LITERATURE differs: {name}; refusing to overwrite it')
                    continue
                if check:
                    errors.append(f'Missing LITERATURE: {name} in {file}')
                    continue
                at=node.body[0].end_lineno if node.body and isinstance(node.body[0],ast.Expr) and isinstance(node.body[0].value,ast.Constant) and isinstance(node.body[0].value.value,str) else node.lineno
                meta=refs[name]
                code='\n    # Bibliographic provenance, not a claim of numerical equivalence.\n    LITERATURE = '+repr(meta)+'\n'
                additions.append((at,code))
        if additions:
            lines=src.splitlines(keepends=True)
            for ln,insert in sorted(additions,reverse=True):lines.insert(ln,insert)
            new=''.join(lines)
            ast.parse(new,filename=str(file))
            updates.append((file,new))
    if len(discovered)==0:errors.append('No registered accelerator classes found')
    extra=set(refs)-set(discovered)
    if extra:errors.append('Manifest references missing in this checkout: '+', '.join(sorted(extra)))
    return updates,errors,discovered

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true',help='audit only; do not change files')
    args=parser.parse_args()
    manifest=json.loads(MAN.read_text(encoding='utf-8'))
    refs=manifest['algorithms']
    changes,errors,ids=build_changes(refs,args.check)
    for e in errors:print('ERROR:',e,file=sys.stderr)
    if errors:return 2
    if not args.check:
        backup=ROOT/'docs'/'_literature_backup'
        for path,new in changes:
            backup.mkdir(parents=True,exist_ok=True)
            copy=backup/path.name
            if not copy.exists():shutil.copy2(path,copy)
            path.write_text(new,encoding='utf-8')
        print(f'Annotated {len(changes)} modules / {len(ids)} registered accelerator classes')
    else:print(f'PASS: {len(ids)} methods have literature provenance')
    return 0

if __name__=='__main__':raise SystemExit(main())
