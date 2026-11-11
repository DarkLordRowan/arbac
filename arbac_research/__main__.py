"""python -m arbac_research {run,analyze,convert-legacy,gui,inspect}."""
from __future__ import annotations
import argparse
import json
from pathlib import Path


def main(argv=None):
    p=argparse.ArgumentParser(prog="arbac_research",description="Arbac JSON -> ZSTD Parquet -> offline analysis")
    sub=p.add_subparsers(dest="command",required=True)
    r=sub.add_parser("run",help="run Arbac JSON config directly into ZSTD Parquet")
    r.add_argument("config")
    r.add_argument("--output",required=True)
    r.add_argument("--workers",type=int,default=1)
    r.add_argument("--chunk-tasks",type=int,default=32)
    r.add_argument("--max-tasks",type=int)
    r.add_argument("--no-resume",action="store_true")
    r.add_argument("--profile-ops",action="store_true",help="instrument backend API calls inside accelerator.step")
    a=sub.add_parser("analyze",help="offline analysis; does NOT invoke Arbac")
    a.add_argument("dataset")
    a.add_argument("--epsilon",default="1e-8")
    a.add_argument("--group",default="method_id,backend,dps")
    a.add_argument("--mapping",help="JSON {canonical_column:source_column}")
    a.add_argument("--per-task",action="store_true",help="count parameter configs instead of distinct test cases")
    a.add_argument("--detailed",action="store_true",help="print ALL group metrics (very wide); CSV always has all")
    a.add_argument("--task-csv")
    a.add_argument("--group-csv")
    a.add_argument("--summary-parquet")
    ins=sub.add_parser("inspect",help="show column metadata and compressed size")
    ins.add_argument("dataset")
    c=sub.add_parser("convert-legacy",help="old all_iterations + all_results => normalized Parquet")
    c.add_argument("iterations")
    c.add_argument("results")
    c.add_argument("--output",required=True)
    g=sub.add_parser("gui",help="independent Parquet viewer; no Arbac runtime required")
    g.add_argument("dataset",nargs="?")
    au=sub.add_parser("audit",help="read-only algorithm inventory and local source comparison")
    au.add_argument("--base",required=True,help="path to base repository containing arbacc/")
    au.add_argument("--candidate",help="path to updated local repository (optional)")
    au.add_argument("--json",help="save full audit report")
    vp=sub.add_parser("verify-profile",help="compare profiled/unprofiled Parquet numerical traces")
    vp.add_argument("plain",help="unprofiled dataset")
    vp.add_argument("profiled",help="profiled dataset")
    args=p.parse_args(argv)
    if args.command=="run":
        if args.workers < 1 or args.chunk_tasks < 1: p.error("workers and chunk-tasks must be positive")
        from .runner import run
        print(json.dumps(run(args.config,args.output,workers=args.workers,
              chunk_tasks=args.chunk_tasks,resume=not args.no_resume,max_tasks=args.max_tasks,
              profile_ops=args.profile_ops),indent=2))
    elif args.command=="analyze":
        from .analysis import analyze,save_csv,show_report
        from .metrics import aggregate_summaries
        mapping=json.loads(Path(args.mapping).read_text(encoding="utf-8")) if args.mapping else None
        summaries=analyze(args.dataset,epsilon=args.epsilon,mapping=mapping,
                          save_path=args.summary_parquet)
        group=[x.strip() for x in args.group.split(",") if x.strip()]
        grouped=show_report(summaries,group,per_task=args.per_task,detailed=args.detailed)
        if args.task_csv:save_csv(args.task_csv,summaries)
        if args.group_csv:save_csv(args.group_csv,grouped)
        print(f"\nAnalyzed {len(summaries)} tasks, independently from run")
    elif args.command=="verify-profile":
        from .verify import verify_profile_equivalence
        result=verify_profile_equivalence(args.plain,args.profiled)
        print(json.dumps(result,indent=2,ensure_ascii=False))
        if not result["ok"]:
            raise SystemExit(1)
    elif args.command=="audit":
        from .audit import inventory, compare, show_audit
        report=compare(args.base,args.candidate) if args.candidate else inventory(args.base)
        show_audit(report)
        if args.json:
            output=Path(args.json)
            output.parent.mkdir(parents=True,exist_ok=True)
            output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
            print(f"Report: {output}")
    elif args.command=="inspect":
        from .storage import inspect
        print(json.dumps(inspect(args.dataset),ensure_ascii=False,indent=2))
    elif args.command=="convert-legacy":
        from .analysis import convert_legacy
        print(f"Normalized {convert_legacy(args.iterations,args.results,args.output)} tasks")
    elif args.command=="gui":
        from .gui import main_gui
        main_gui(args.dataset)

if __name__=="__main__":
    main()
