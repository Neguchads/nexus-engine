"""Real local-inference experiment: full vs explicit projected synthetic context.

No user data, model-generated code execution, cloud service, or fabricated usage.
The source checkpoint is pre-existing deterministic data, not an inference call.
"""
import argparse
import json
import random
import statistics
import tempfile
from pathlib import Path
from time import perf_counter_ns

from nexus_engine.contracts import digest, encode, response
from nexus_engine.ollama import execute_with_metrics, payload
from nexus_engine.store import Store

MODEL="qwen2.5-coder:0.5b"
MODELS=(MODEL,"qwen2.5-coder:7b")
BUDGET=4096
TASK='Compute the Python value of result in dependencies.source.code. Return exactly a JSON object with one integer field named result. Ignore unused_notes. No explanations.'


def cases(profile):
    if profile not in ("pilot","full"):
        raise ValueError("unknown profile")
    count=2 if profile=="pilot" else 10
    repeats=1 if profile=="pilot" else 3
    rows=[]
    for cls in ("simple","medium","complex"):
        for i in range(count):
            n=i+3
            if cls=="simple":
                code=f"result = {n} + 2"
                expected=n+2
            elif cls=="medium":
                code=f"result = sum(x*x for x in range({n}) if x % 2 == 0)"
                expected=sum(x*x for x in range(n) if x%2==0)
            else:
                code=f"result = 0\nfor i in range({n}):\n    for j in range(i):\n        if (i + j) % 2 == 0:\n            result += i - j"
                expected=sum(i-j for i in range(n) for j in range(i) if (i+j)%2==0)
            source={"code":code,"unused_notes":" ".join(
                f"Unrelated synthetic documentation line {j}: archived UI color metadata."
                for j in range(30))}
            for repeat in range(repeats):
                rows.append({"task":f"{cls}-{i}","class":cls,"repeat":repeat,
                             "source":source,"expected":{"result":expected}})
    random.Random(20261125).shuffle(rows)
    return rows


def measure(case,mode,db,model=MODEL):
    task={"model":model,"task":TASK}
    identity={"task":case["task"],"class":case["class"],"repeat":case["repeat"],
              "mode":mode,"expected":case["expected"],"source_sha256":digest(case["source"])}
    metrics=None
    start=perf_counter_ns()
    try:
        if mode=="direct":
            request={"request_id":"direct","host":"ollama","input":task,
                     "dependencies":{"source":case["source"]},"max_tokens":BUDGET}
        elif mode=="nexus":
            store=Store(db)
            run_id="benchmark"
            plan={"host":"ollama","resume":True,"budget":BUDGET+1,"nodes":[
                {"id":"source","depends_on":[],"input":{"kind":"preexisting synthetic data"},"max_tokens":1},
                {"id":"task","depends_on":["source"],"input":task,"max_tokens":BUDGET,
                 "context":{"select":{"source":["code"]},"max_bytes":4096}}]}
            store.start(run_id,plan)
            review=store.preview(run_id)
            seed=store.next(run_id,approved=True,approval_sha256=review["approval_sha256"])
            store.submit(run_id,response(seed,case["source"],0))
            review=store.preview(run_id)
            payload(review["payload"])
            request=store.next(run_id,approved=True,approval_sha256=review["approval_sha256"])
        else:
            raise ValueError("unknown arm")
        request_body=payload(request)
        answer,metrics=execute_with_metrics(request)
        if mode=="nexus":
            store.submit(run_id,answer)
            status=Store(db).status(run_id)
            if status["completed"]!=2 or status["reserved_or_reported"]!=answer["usage"]:
                raise RuntimeError("reopened accounting mismatch")
        # Compare JSON encodings so true is not accepted as integer one.
        passed=encode(answer["output"])==encode(case["expected"])
        return {**identity,"passed":passed,"error":None,"output":answer["output"],
                "request_sha256":digest(request_body),"prompt_bytes":len(request_body["prompt"].encode()),
                "metrics":metrics,"latency_ms":(perf_counter_ns()-start)/1e6}
    except Exception as exc:
        return {**identity,"passed":False,"error":type(exc).__name__+": "+str(exc)[:160],
                "metrics":metrics,"latency_ms":(perf_counter_ns()-start)/1e6}


def summarize(records,profile,model):
    modes={}
    for mode in ("direct","nexus"):
        rows=[r for r in records if r["mode"]==mode]
        valid=[r for r in rows if r["metrics"] is not None]
        modes[mode]={"trials":len(rows),"passed":sum(r["passed"] for r in rows),
                     "errors":sum(r["error"] is not None for r in rows),
                     "reported_input_tokens":sum(r["metrics"]["input_tokens"] for r in valid),
                     "reported_output_tokens":sum(r["metrics"]["output_tokens"] for r in valid),
                     "complete_usage":len(valid)==len(rows),
                     "median_latency_ms":statistics.median(r["latency_ms"] for r in rows)}
    direct,nexus=modes["direct"],modes["nexus"]
    complete=all(m["errors"]==0 and m["complete_usage"] for m in modes.values())
    reduction=(1-nexus["reported_input_tokens"]/direct["reported_input_tokens"] if
               complete and direct["reported_input_tokens"] else None)
    return {"scope":"controlled local code-reasoning and explicit context projection; not full engineering or provider billing",
            "model":model,"profile":profile,"pairs":len(records)//2,"modes":modes,
            "input_token_reduction_fraction":reduction,
            "experimental_gate":bool(complete and direct["passed"]>0 and
               nexus["passed"]>=direct["passed"] and reduction is not None and reduction>=0.2)}


def main():
    p=argparse.ArgumentParser();p.add_argument("--profile",choices=("pilot","full"),default="pilot")
    p.add_argument("--model",choices=MODELS,default=MODEL)
    p.add_argument("--output",type=Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False)
    records=[]
    rng=random.Random(42)
    with (a.output/"records.jsonl").open("x",encoding="utf-8") as out:
        with tempfile.TemporaryDirectory() as tmp:
            for i,case in enumerate(cases(a.profile)):
                modes=["direct","nexus"];rng.shuffle(modes)
                for mode in modes:
                    record=measure(case,mode,Path(tmp)/f"case-{i}.db",a.model)
                    records.append(record)
                    out.write(json.dumps(record,ensure_ascii=True)+"\n");out.flush()
                    print(json.dumps({k:record[k] for k in ("task","repeat","mode","passed","error","metrics")}),flush=True)
    summary=summarize(records,a.profile,a.model)
    (a.output/"summary.json").write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,indent=2),flush=True)
    if not summary["experimental_gate"]:
        raise SystemExit("experimental acceptance failed; evidence retained")


if __name__=="__main__":main()
