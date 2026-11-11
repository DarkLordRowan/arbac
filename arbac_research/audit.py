"""Read-only Arbac source/algorithm inventory, with optional directory diff.

No dynamic imports: handles untrusted/unfinished local files without executing
code. A static plugin inventory does NOT certify a method mathematically.
"""
from __future__ import annotations
import ast
from collections import defaultdict
from hashlib import sha256
from pathlib import Path
import json
import subprocess


def root_of(path):
    path = Path(path).expanduser().resolve()
    if (path / "arbacc" / "__init__.py").is_file():
        return path
    if path.name == "arbacc" and (path / "__init__.py").is_file():
        return path.parent
    raise FileNotFoundError(f"Не найден пакет arbacc в {path}")


def _git_version(root):
    def git(*args):
        try:
            result = subprocess.run(["git", "-C", str(root), *args],
                       text=True, capture_output=True, timeout=3)
            return result.stdout.strip() if result.returncode == 0 else None
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None
    dirty = git("status", "--porcelain")
    return {"commit": git("rev-parse", "HEAD"), "dirty": bool(dirty) if dirty is not None else None}


def inventory(path):
    root = root_of(path)
    pyfiles = sorted((root / "arbacc").rglob("*.py"))
    files = {}
    plugins = []
    syntax_errors = []
    h = sha256()
    for file in pyfiles:
        name = file.relative_to(root).as_posix()
        data = file.read_bytes()
        files[name] = sha256(data).hexdigest()
        h.update(name.encode("utf-8"));h.update(data)
        try:
            tree = ast.parse(data, filename=str(file))
        except (SyntaxError, UnicodeDecodeError) as e:
            syntax_errors.append({"path": name, "error": str(e)})
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                if (isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Name) and
                    decorator.func.id == "register" and len(decorator.args) >= 2):
                    try:
                        kind, plugin = [ast.literal_eval(arg) for arg in decorator.args[:2]]
                    except (ValueError, TypeError, SyntaxError):
                        continue
                    if isinstance(kind, str) and isinstance(plugin, str):
                        plugins.append({"kind": kind, "name": plugin, "path": name,
                                        "class": node.name})
    duplicates = defaultdict(list)
    for x in plugins:
        duplicates[(x["kind"], x["name"])].append(x["path"])
    return {"root": str(root), "git": _git_version(root),
            "source_sha256": h.hexdigest(), "python_files": len(pyfiles),
            "files": files, "plugins": sorted(plugins,key=lambda x:(x["kind"],x["name"],x["path"])),
            "duplicate_registrations": [dict(kind=k[0], name=k[1], paths=v)
                         for k,v in duplicates.items() if len(v)>1],
            "syntax_errors": syntax_errors}


def compare(base, candidate):
    a,b=inventory(base),inventory(candidate)
    af,bf=a["files"],b["files"]
    ap = {(x["kind"], x["name"]) for x in a["plugins"]}
    bp = {(x["kind"], x["name"]) for x in b["plugins"]}
    return {"base": {k:v for k,v in a.items() if k != "files"},
            "candidate": {k:v for k,v in b.items() if k != "files"},
            "added_files":sorted(bf.keys()-af.keys()),
            "removed_files":sorted(af.keys()-bf.keys()),
            "changed_files":sorted(x for x in af.keys() & bf.keys() if af[x] != bf[x]),
            "added_plugins":[dict(kind=k[0], name=k[1]) for k in sorted(bp-ap)],
            "removed_plugins":[dict(kind=k[0], name=k[1]) for k in sorted(ap-bp)]}


def show_audit(report):
    if "candidate" not in report:
        print(f"Arbac: {report['root']}")
        print(f"Python: {report['python_files']}; registered plugins: {len(report['plugins'])}; SHA256: {report['source_sha256']}")
        print("Accelerators:", ", ".join(x['name'] for x in report['plugins'] if x['kind']=='accelerators'))
        if report['syntax_errors']:print(f"Syntax errors: {len(report['syntax_errors'])}")
        if report['duplicate_registrations']:print(f"Duplicate registration keys: {len(report['duplicate_registrations'])}")
    else:
        print("Source comparison (read-only):")
        for k in ("added_files","removed_files","changed_files","added_plugins","removed_plugins"):
            print(f"  {k}: {len(report[k])}")
            for item in report[k][:50]:print("    ", item)
    return report
