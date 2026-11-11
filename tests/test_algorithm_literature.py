"""Scientific provenance contract for every registered accelerator.

Run: python -m pytest tests/test_algorithm_literature.py -q
"""
from __future__ import annotations
import ast
from pathlib import Path
import pytest

ACCELS = Path(__file__).resolve().parents[1] / 'arbacc' / 'accelerators'
REQUIRED = {'citation','url','locator','relation','implementation_note'}

def all_registrations():
    for path in sorted(ACCELS.glob('*.py')):
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for cls in tree.body:
            if not isinstance(cls, ast.ClassDef): continue
            for deco in cls.decorator_list:
                if not isinstance(deco, ast.Call) or not isinstance(deco.func,ast.Name) or deco.func.id != 'register': continue
                try: kind,name = [ast.literal_eval(a) for a in deco.args[:2]]
                except (ValueError,TypeError): continue
                if kind == 'accelerators':
                    literature = None
                    for stmt in cls.body:
                        if isinstance(stmt,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='LITERATURE' for t in stmt.targets):
                            literature=ast.literal_eval(stmt.value)
                    yield path.name, cls.name, name, literature

def test_all_accelerators_have_scientific_provenance():
    rows=list(all_registrations())
    assert rows, 'No algorithm registrations found'
    assert len({name for _,_,name,_ in rows})==len(rows), 'Duplicate IDs'
    for file,cls,name,data in rows:
        assert isinstance(data,dict), f'{file}:{cls} ({name}) lacks LITERATURE metadata'
        assert REQUIRED <= data.keys(), f'{name} missing {REQUIRED-data.keys()}'
        for key in REQUIRED:
            assert isinstance(data[key],str) and data[key].strip(),f'{name} missing {key}'
        assert data['url'].startswith('https://'), f'{name}: no HTTPS bibliography link'

def test_sidi_attribution_is_not_claimed_as_verified():
    records={name:data for _,_,name,data in all_registrations()}
    assert records['levin_sidi_s']['relation']=='attribution_pending'
    assert 'Weniger' in records['levin_sidi_s']['implementation_note']
    assert records['levin_sidi_m']['relation']=='legacy_name'
    assert records['weniger_m']['relation']=='alias'
