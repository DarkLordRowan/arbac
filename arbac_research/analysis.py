"""Offline analysis from Parquet only. Does not import or run Arbac."""
from __future__ import annotations
from pathlib import Path
import csv
import json
from . import storage
from .metrics import summarize_task, aggregate_summaries, METRICS_SCHEMA_VERSION


def analyze(path, *, epsilon="1e-8", mapping=None, save_path=None, progress=None):
    files=storage.iter_parquet_files(path)
    if not files:
        raise FileNotFoundError(path)
    summaries=[]
    for idx,file in enumerate(files,1):
        if progress:
            progress(idx,len(files),str(file))
        for rows in storage.iterate_tasks(file,mapping=mapping):
            summary=summarize_task(rows, epsilon=epsilon)
            try:
                summary["source_file"]=str(file.relative_to(Path(path))) if Path(path).is_dir() else str(file)
            except ValueError:
                summary["source_file"]=str(file)
            summaries.append(summary)
    if save_path:
        storage.write_summary(save_path,summaries)
    return summaries


def load_or_analyze(path, *, epsilon="1e-8", mapping=None):
    """Load a native cached summary if epsilon and all trace parts match."""
    p=Path(path)
    cache=p/"summary.parquet"
    if p.is_dir() and not mapping and (p/"trace").is_dir() and cache.exists():
        sources=storage.iter_parquet_files(p)
        if sources and all(f.stat().st_mtime_ns <= cache.stat().st_mtime_ns for f in sources):
            rows=storage.load_summary(cache)
            if rows and all(str(r.get("epsilon")) == str(epsilon) and
                            r.get("metrics_schema_version") == METRICS_SCHEMA_VERSION for r in rows):
                return rows
    summaries=analyze(path,epsilon=epsilon,mapping=mapping)
    # Do not overwrite user's arbitrary external data; cache only native folder.
    if p.is_dir() and not mapping and (p/"trace").is_dir():
        storage.write_summary(cache,summaries)
    return summaries


def save_csv(path, rows):
    if not rows:
        raise ValueError("empty report")
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    fields=list(rows[0])
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def show_report(summaries, group, *, per_task=False, detailed=False):
    rows=aggregate_summaries(summaries,group,per_task=per_task)
    if not rows:
        print("нет строк")
        return rows
    heads=list(rows[0]) if detailed else [k for k in list(group)+[
        "tasks","cases","comparable","c1","c5","successful_acceleration_cases",
        "epsilon_reached_cases","failed","median_gain_orders","median_last_gain_orders",
        "median_elapsed_ms"] if k in rows[0]]
    widths={key:max(len(key),*(len(str(r.get(key) if r.get(key) is not None else "—")) for r in rows)) for key in heads}
    print("  ".join(x.ljust(widths[x]) for x in heads))
    print("  ".join("-"*widths[x] for x in heads))
    for r in rows:
        print("  ".join(str(r.get(x) if r.get(x) is not None else "—").ljust(widths[x]) for x in heads))
    return rows


def convert_legacy(iterations_path, results_path, output):
    """Normalize old Arbac all_iterations + all_results to v1 Parquet.

    Old exports lack original baseline trajectories; G/C1/C5 remain UNKNOWN,
    not estimated using wrong baseline nor fabricated as zeros.
    """
    pa,pq=storage._arrow()
    data=pq.read_table(results_path, columns=["task_id","series_id","accel_id","backend",
              "dps","exact_sum","status","error"]).to_pylist()
    ref={str(x["task_id"]):x for x in data}
    output=Path(output)
    output.mkdir(parents=True,exist_ok=True)
    count=0
    for rows in storage.iterate_tasks(iterations_path):
        if not rows: continue
        meta=ref.get(str(rows[0]["task_id"]),{})
        for r in rows:
            r["row_type"]="accel"
            r["exact_sum"]=meta.get("exact_sum")
            r["status"]=meta.get("status") or "unknown"
            r["failure"]=meta.get("error")
            for k in ("series_id","accel_id","backend","dps"):
                if r.get(k) is None:
                    r[k]=meta.get(k)
        name=f"legacy-{count:08d}.parquet"
        storage.write_trace(output/name,rows)
        count+=1
    (output/"README.txt").write_text(
        "Legacy conversion: original series baselines were not in old exports; "
        "gain_best_orders/C1/C5 are unavailable until original trajectories are added.\n",
        encoding="utf-8")
    return count
