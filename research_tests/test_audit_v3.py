from pathlib import Path
from arbac_research.audit import inventory, compare


def make_repo(root, code):
    pkg = root / "arbacc"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    sub = pkg / "accelerators"
    sub.mkdir()
    (sub / "__init__.py").write_text("")
    (sub / "one.py").write_text(code,encoding="utf-8")
    return root


def test_audit_without_import_executing_local_code(tmp_path):
    repo=make_repo(tmp_path / "repo", '@register("accelerators", "foo")\nclass Foo:\n pass\n')
    r=inventory(repo)
    assert r["python_files"]==3
    assert [x["name"] for x in r["plugins"]]==["foo"]
    assert not r["syntax_errors"]


def test_audit_compare_added_and_changed(tmp_path):
    base=make_repo(tmp_path / "base", '@register("accelerators", "foo")\nclass Foo:\n pass\n')
    new=make_repo(tmp_path / "new", '@register("accelerators", "bar")\nclass Bar:\n pass\n')
    report=compare(base,new)
    assert report["added_plugins"]==[{"kind":"accelerators","name":"bar"}]
    assert report["removed_plugins"]==[{"kind":"accelerators","name":"foo"}]
    assert report["changed_files"]==["arbacc/accelerators/one.py"]
