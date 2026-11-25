"""Three-arm real inference: full context, projected direct, projected Nexus.

Only trusted, checked-in candidate functions are executed. No generated code execution.
"""
import argparse
import json
import random
import statistics
import tempfile
from pathlib import Path
from time import perf_counter_ns
from benchmarks.repair_cases import cases,verify
from nexus_engine.contracts import digest,response
from nexus_engine.ollama import execute_with_metrics,payload
from nexus_engine.store import Store

MODEL="qwen2.5-coder:7b"
MODES=("direct-full","direct-projected","nexus-projected")
TASK='Choose the single candidate implementation satisfying dependencies.source.specification for all inputs. Compare dependencies.source.candidates A, B, C. Return exactly a JSON object with one string field candidate, containing A, B, or C. Ignore unrelated release history.'


def measure(case,mode,db):
    source=case["source"]
    selected={k:source[k] for k in ("specification","candidates")}
    task={"model":MODEL,"task":TASK}
    meta={"task":case["task"],"class":case["class"],"mode":mode,"source_sha256":digest(source)}
    metrics=None;start=perf_counter_ns()
    try:
        if mode=="nexus-projected":
            store=Store(db)
            plan={"host":"ollama","resume":True,"budget":4097,"nodes":[
                {"id":"source","depends_on":[],"input":{"kind":"trusted candidate data"},"max_tokens":1},
                {"id":"repair","depends_on":["source"],"input":task,"max_tokens":4096,
                 "context":{"select":{"source":["specification","candidates"]},"max_bytes":12000}}]}
            store.start("run",plan)
            preview=store.preview("run")
            req=store.next("run",approved=True,approval_sha256=preview["approval_sha256"])
            store.submit("run",response(req,source,0))
            preview=store.preview("run")
            payload(preview["payload"])
            req=store.next("run",approved=True,approval_sha256=preview["approval_sha256"])
        elif mode in ("direct-full","direct-projected"):
            req={"request_id":"direct","host":"ollama","input":task,
                 "dependencies":{"source":source if mode=="direct-full" else selected},"max_tokens":4096}
        else:raise ValueError("unknown mode")
        body_hash=digest(payload(req))
        answer,metrics=execute_with_metrics(req)
        if mode=="nexus-projected":
            store.submit("run",answer)
            state=Store(db).status("run")
            if state["completed"]!=2 or state["reserved_or_reported"]!=answer["usage"]:
                raise RuntimeError("reopened accounting mismatch")
        return {**meta,"passed":verify(case,answer["output"]),"output":answer["output"],
                "body_sha256":body_hash,"error":None,"metrics":metrics,
                "latency_ms":(perf_counter_ns()-start)/1e6}
    except Exception as exc:
        return {**meta,"passed":False,"error":type(exc).__name__+": "+str(exc)[:160],
                "metrics":metrics,"latency_ms":(perf_counter_ns()-start)/1e6}


def summarize(rows):
    result={}
    groups={}
    for r in rows:
        group=groups.setdefault(r["task"],{})
        if r["mode"] in group:raise ValueError("duplicate arm")
        group[r["mode"]]=r
    matching=all(set(g)==set(MODES) and
        g["direct-projected"].get("body_sha256") is not None and
        g["direct-projected"].get("body_sha256")==g["nexus-projected"].get("body_sha256")
        for g in groups.values())
    for mode in MODES:
        selected=[r for r in rows if r["mode"]==mode]
        measured=[r for r in selected if r["metrics"] is not None]
        result[mode]={"trials":len(selected),"passed":sum(r["passed"] for r in selected),
            "errors":sum(r["error"] is not None for r in selected),
            "input_tokens":sum(r["metrics"]["input_tokens"] for r in measured),
            "output_tokens":sum(r["metrics"]["output_tokens"] for r in measured),
            "complete_usage":len(measured)==len(selected),
            "median_ms":statistics.median(r["latency_ms"] for r in selected)}
    full,projected,nexus=(result[m] for m in MODES)
    complete=all(v["complete_usage"] and v["errors"]==0 for v in result.values())
    return {"scope":"nine checked-in repair-selection tasks, not autonomous coding",
            "model":MODEL,"matched_projected_request_bodies":matching,"modes":result,
            "experimental_gate":bool(complete and matching and len(groups)==9 and
                nexus["passed"]>=6 and nexus["passed"]>=full["passed"] and
                nexus["passed"]>=projected["passed"] and
                full["input_tokens"]>0 and nexus["input_tokens"]<=0.8*full["input_tokens"])}


def main():
    p=argparse.ArgumentParser();p.add_argument("--output",type=Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False)
    rows=[];rng=random.Random(77);dataset=cases();rng.shuffle(dataset)
    with tempfile.TemporaryDirectory() as tmp,(a.output/"records.jsonl").open("x",encoding="utf-8") as out:
        for i,case in enumerate(dataset):
            modes=list(MODES);rng.shuffle(modes)
            for mode in modes:
                r=measure(case,mode,Path(tmp)/f"case-{i}.db")
                rows.append(r);out.write(json.dumps(r)+"\n");out.flush()
                print(json.dumps(r),flush=True)
    report=summarize(rows)
    (a.output/"summary.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2),flush=True)
    if not report["experimental_gate"]:raise SystemExit("engineering pilot gate failed; evidence preserved")


if __name__=="__main__":main()
