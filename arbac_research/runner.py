"""Direct Arbac experiment runner -> compressed Parquet, without intermediate JSON.

Implements the verified GitHub Magister plugin contracts but deliberately does
not modify existing arbacc code. It handles accelerator tasks only; postprocess
must be run with the original Arbac CLI until its separate Parquet adapter lands.
"""
from __future__ import annotations
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
from hashlib import sha256
from pathlib import Path
import json
import os
import subprocess
import time
import traceback

from .storage import write_trace, VERSION


def _canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _hash(obj):
    return sha256(_canon(obj).encode("utf-8")).hexdigest()


def init_plugins():
    from arbacc.runner.execute_batch import _import_plugins
    _import_plugins()


def _worker_one(task):
    """No disk writes inside workers; return raw trace with backend-preserved decimals."""
    from arbacc.core.context import Context
    from arbacc.core.registry import get
    from arbacc.precision import get_backend
    from arbacc.runner.run_accel import run_accelerator
    from arbacc.core.stream import partial_value
    from .profiling import ProfilingAccelerator

    p = task["precision"]
    backend_name = p["backend"]
    dps = int(p["dps"])
    ids = task["ids"]
    accel_cfg = task["accelerator"]
    base = {
        "task_id": task["task_id"], "series_id": ids["series_id"],
        "class_id": str(task.get("research_class") or task["series"].get("class_id", "")),
        "noise_id": ids["noise_id"], "method_id": accel_cfg["type"],
        "accel_id": ids["accel_id"], "backend": backend_name, "dps": dps,
        "params_json": _canon({"series":task["series"],"accelerator":accel_cfg,"precision":p}),
    }
    started = time.perf_counter()
    try:
        ctx = Context(backend=get_backend(backend_name), dps=dps,
                      rounding=p.get("rounding", "nearest"))
        b=ctx.backend
        ser=task["series"]
        Series = get("series", ser["type"])
        series=Series(params=ser.get("params", {}), exact_sum=ser.get("exact_sum"))
        src=series.build_stream(ctx)
        noise_cfg=task["noise"]
        Noise=get("noise", noise_cfg["type"])
        src=Noise(params=noise_cfg.get("params", {}), seed=int(noise_cfg.get("seed",0))).wrap(src,ctx)
        Accel=get("accelerators",accel_cfg["type"])
        original_accel=Accel(params=accel_cfg.get("params",{}))
        accel=ProfilingAccelerator(original_accel,
             count_backend_ops=bool(task.get("research_profile_backend_ops", False)))
        stopping=[]
        for c in accel_cfg.get("stopping",[]):
            Stop=get("stopping",c["type"])
            stopping.append(Stop(params=c.get("params",{})))
        nmax=int(accel_cfg.get("n_max",100))
        result=run_accelerator(source=src,accelerator=accel,
                               stopping_criteria=stopping,
                               stopping_mode=accel_cfg.get("stopping_mode","any"),
                               online_envelopes=[],ctx=ctx,n_max=nmax)
        elapsed=(time.perf_counter()-started)*1000
        reference_failure=None
        try:
            limit=series.exact_sum(ctx)
        except Exception as e:
            # Failure of the oracle/reference is not an accelerator failure.
            limit=None
            reference_failure=f"{type(e).__name__}: {e}"
        strval=lambda x: b.to_str(x, dps) if x is not None else None
        limit_str=strval(limit)
        # Evaluate baseline through the declared study budget, even if the
        # accelerator stops early. Otherwise base_first_epsilon_n is censored
        # and the quoted savings are often wrong.
        max_used=max((int(r.n_used) for r in result.iterations),default=0)
        budget=max(max_used,min(nmax,int(task.get("research_baseline_budget") or nmax)))
        baseline=[]
        baseline_failure=None
        for n in range(budget):
            try:
                prev=baseline[-1] if baseline else None
                baseline.append(partial_value(src,n,prev,ctx))
            except Exception as e:
                baseline_failure=f"{type(e).__name__}: {e}"
                break
        rows=[]
        for j, value in enumerate(baseline,1):
            rows.append(dict(base,row_type="baseline",n_used=j,k=None,
                             value=strval(value),base_value=None,exact_sum=limit_str,
                             status=result.status,failure=result.error,
                             baseline_failure=baseline_failure,reference_failure=reference_failure,elapsed_ms=elapsed))
        for step_index, r in enumerate(result.iterations):
            m=int(r.n_used)
            measure=accel.measurements[step_index] if step_index < len(accel.measurements) else {}
            rows.append(dict(base,row_type="accel",n_used=m,k=int(r.k),
                             step_elapsed_ms=measure.get("step_elapsed_ms"),
                             op_add=measure.get("op_add"),op_mul=measure.get("op_mul"),
                             op_div=measure.get("op_div"),op_neg=measure.get("op_neg"),
                             op_special=measure.get("op_special"),op_total=measure.get("op_total"),
                             op_mode=measure.get("op_mode"),
                             value=strval(r.estimate),
                             base_value=strval(baseline[m-1]) if 1<=m<=len(baseline) else None,
                             exact_sum=limit_str,status=result.status,
                             failure=result.error,baseline_failure=baseline_failure,reference_failure=reference_failure,elapsed_ms=elapsed))
        # Structured events are independent of numerical sample rows and may
        # be inspected even when a failed step produced no estimate.
        for event in accel.failures:
            rows.append(dict(base,row_type="event",n_used=event["n_used"],k=event["k"],
                             value=None,base_value=None,exact_sum=limit_str,
                             status=result.status,failure=result.error,
                             baseline_failure=baseline_failure,reference_failure=reference_failure,
                             elapsed_ms=elapsed,event_type="step_failure",
                             event_message=f"{event['failure_class']}: {event['failure_message']}",
                             step_elapsed_ms=event.get("step_elapsed_ms"),
                             op_add=event.get("op_add"),op_mul=event.get("op_mul"),
                             op_div=event.get("op_div"),op_neg=event.get("op_neg"),
                             op_special=event.get("op_special"),op_total=event.get("op_total"),
                             op_mode=event.get("op_mode")))
        if result.status == "failed" and not accel.failures:
            rows.append(dict(base,row_type="event",n_used=int(result.n_used),k=None,
                             value=None,base_value=None,exact_sum=limit_str,
                             status=result.status,failure=result.error,
                             baseline_failure=baseline_failure,reference_failure=reference_failure,
                             elapsed_ms=elapsed,event_type="runner_failure",
                             event_message=str(result.error or result.stopped_by)))
        if result.stopped_by:
            rows.append(dict(base,row_type="event",n_used=int(result.n_used),k=None,
                             value=None,base_value=None,exact_sum=limit_str,
                             status=result.status,failure=result.error,
                             baseline_failure=baseline_failure,reference_failure=reference_failure,
                             elapsed_ms=elapsed,event_type="runner_stop",
                             event_message=str(result.stopped_by)))
        # Preserve a failed/no-trajectory task so resume never hides it.
        if not rows:
            rows.append(dict(base,row_type="accel",n_used=0,k=0,value=None,
                             base_value=None,exact_sum=limit_str,status=result.status,
                             failure=result.error,baseline_failure=baseline_failure,reference_failure=reference_failure,elapsed_ms=elapsed))
        return rows
    except Exception as exc:
        return [dict(base,row_type="accel",n_used=0,k=0,value=None,
                     base_value=None,exact_sum=None,status="failed",
                     failure=f"{type(exc).__name__}: {exc}",
                     elapsed_ms=(time.perf_counter()-started)*1000)]


def _worker_chunk(tasks):
    return [row for task in tasks for row in _worker_one(task)]


def _repo_version():
    try:
        from arbacc import __file__ as init_file
        root=Path(init_file).resolve().parent.parent
        sha=subprocess.run(["git","-C",str(root),"rev-parse","HEAD"],capture_output=True,text=True,timeout=3)
        dirty=subprocess.run(["git","-C",str(root),"status","--porcelain"],capture_output=True,text=True,timeout=3)
        return {"commit":sha.stdout.strip() if sha.returncode==0 else None,
                "dirty": bool(dirty.stdout.strip()) if dirty.returncode==0 else None}
    except Exception:
        return {"commit":None,"dirty":None}


def _source_hash():
    """Hash local .py source bytes so dirty local code cannot silently resume."""
    try:
        import arbacc
        root=Path(arbacc.__file__).resolve().parent
        h=sha256()
        for file in sorted(root.rglob("*.py")):
            h.update(str(file.relative_to(root)).encode("utf-8"))
            h.update(file.read_bytes())
        return h.hexdigest()
    except Exception:
        return None


def _research_hash():
    root=Path(__file__).resolve().parent
    h=sha256()
    for file in sorted(root.rglob("*.py")):
        h.update(str(file.relative_to(root)).encode("utf-8"))
        h.update(file.read_bytes())
    return h.hexdigest()


def run(config_path: str, output: str, workers: int = 1, chunk_tasks: int = 32,
        resume: bool = True, max_tasks: int | None = None, profile_ops: bool = False):
    """Resume at Parquet-shard granularity; refuse reusing output for changed config."""
    from .storage import _arrow
    _arrow()  # fail before scheduling expensive computations
    init_plugins()
    from arbacc.runner.plan import build_plan
    cfg=json.loads(Path(config_path).read_text(encoding="utf-8"))
    if profile_ops:
        cfg.setdefault("research", {})["profile_backend_ops"] = True
    plan=build_plan(cfg)
    if plan.get("errors"):
        raise ValueError("Invalid config: " + "; ".join(plan["errors"]))
    if plan.get("post"):
        raise ValueError("Parquet research runner v1 supports accelerator tasks only; "
                         "use standard arbacc CLI for postprocess/envelopes")
    tasks=plan["accel"]
    class_map=cfg.get("research", {}).get("class_by_series_id", {})
    for task in tasks:
        task["research_class"]=class_map.get(task["ids"]["series_id"], "")
        task["research_baseline_budget"]=int(cfg.get("research",{}).get("baseline_budget") or task["accelerator"].get("n_max",100))
        task["research_profile_backend_ops"]=bool(cfg.get("research",{}).get("profile_backend_ops",False))
    # Prevent data corruption when plan creates duplicate IDs.
    if len({x["task_id"] for x in tasks}) != len(tasks):
        raise ValueError("duplicate task_id; choose distinct accelerator/series parameters")
    if max_tasks is not None:
        tasks=tasks[:int(max_tasks)]
    if not tasks:
        raise ValueError("no accelerator tasks")
    output=Path(output)
    output.mkdir(parents=True,exist_ok=True)
    (output/"trace").mkdir(exist_ok=True)
    version=_repo_version()
    identity={"schema":VERSION,"runner_version":3,"config_sha256":_hash(cfg),
              "source_commit":version["commit"],"source_dirty":version["dirty"],
              "source_tree_sha256":_source_hash(),
              "research_tree_sha256":_research_hash(),
              "chunk_tasks":int(chunk_tasks),"max_tasks":max_tasks}
    marker=output/"manifest.json"
    if marker.exists():
        existing=json.loads(marker.read_text(encoding="utf-8"))
        if any(existing.get(k)!=v for k,v in identity.items()):
            raise ValueError("Output belongs to a different config / code revision; use another directory")
        if not resume:
            raise FileExistsError("output exists; use a new directory or --resume")
    else:
        tmp=marker.with_suffix(".tmp")
        tmp.write_text(json.dumps(identity,indent=2,ensure_ascii=False),encoding="utf-8")
        tmp.replace(marker)
        (output/"config.json").write_text(json.dumps(cfg,indent=2,ensure_ascii=False),encoding="utf-8")
    chunks=[tasks[i:i+chunk_tasks] for i in range(0,len(tasks),chunk_tasks)]
    pending=[]
    skipped=0
    _, pq = _arrow()
    for chunk in chunks:
        # Chunk name includes task specs, not only chunk number.
        digest=_hash(chunk)[:20]
        path=output/"trace"/f"part-{digest}.parquet"
        if resume and path.exists():
            try:
                pf=pq.ParquetFile(path)
                if pf.metadata.num_rows < len(chunk):
                    raise ValueError("too few rows")
                if pf.schema_arrow.metadata.get(b"arbac_research_version") != str(VERSION).encode():
                    raise ValueError("incompatible trace schema version")
            except Exception as exc:
                raise ValueError(f"Corrupt/incompatible Parquet shard {path}: {exc}") from exc
            skipped+=len(chunk)
        else:
            pending.append((chunk,path))
    print(f"Plan: {len(tasks)} tasks; skipped {skipped}; pending {sum(len(c) for c,_ in pending)}")
    completed=0
    def save(chunk,path,rows):
        nonlocal completed
        write_trace(path,rows)
        completed+=len(chunk)
        print(f"{completed}/{sum(len(c) for c,_ in pending)} tasks committed to ZSTD Parquet ({path.name})",flush=True)
    if workers<=1:
        for chunk,path in pending:
            save(chunk,path,_worker_chunk(chunk))
    else:
        # Keep at most 2*workers futures alive to bound memory of large results.
        iterator=iter(pending)
        with ProcessPoolExecutor(max_workers=workers,initializer=init_plugins) as pool:
            inflight={}
            def schedule():
                try:chunk,path=next(iterator)
                except StopIteration:return False
                inflight[pool.submit(_worker_chunk,chunk)]=(chunk,path)
                return True
            for _ in range(2*workers): schedule()
            while inflight:
                done,_=wait(inflight,return_when=FIRST_COMPLETED)
                for future in done:
                    chunk,path=inflight.pop(future)
                    save(chunk,path,future.result())
                    schedule()
    # Precompute one compact summary so GUI can open a large run instantly.
    # The summary is a cache; users may recompute it for a different epsilon.
    from .analysis import analyze
    epsilon=cfg.get("research",{}).get("epsilon","1e-8")
    if pending or not (output/"summary.parquet").exists():
        print("Preparing offline summary.parquet...",flush=True)
        analyze(output,epsilon=epsilon,save_path=output/"summary.parquet")
    return {"tasks":len(tasks),"skipped":skipped,"completed":completed,
            "output":str(output),"summary_epsilon":epsilon}
