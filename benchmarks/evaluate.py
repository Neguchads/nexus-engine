"""Validate paired measurement records; does not execute an AI or verify its claims."""
import argparse
import json
import math
import statistics
from pathlib import Path

CLASSES=("simple","medium","complex")
IDENTITY=("task","class","repeat","host","model","config_sha256","initial_sha256","prompt_sha256","budget")
MEASURE=("mode","passed","latency_ms","input_tokens","output_tokens","recovered")


def evaluate(records):
    if not isinstance(records,list) or not records or len(records)>10000:
        raise ValueError("bounded record list required")
    pairs={}
    for r in records:
        if not isinstance(r,dict) or set(r)!=set(IDENTITY+MEASURE):
            raise ValueError("record fields")
        if r["class"] not in CLASSES or r["mode"] not in ("direct","nexus"):
            raise ValueError("class or mode")
        if any(not isinstance(r[k],str) or not r[k] or len(r[k])>200 for k in ("task","host","model")):
            raise ValueError("identity fields")
        for k in ("config_sha256","initial_sha256","prompt_sha256"):
            if not isinstance(r[k],str) or len(r[k])!=64 or any(x not in "0123456789abcdef" for x in r[k]):
                raise ValueError("identity digest")
        for k in ("repeat","budget","input_tokens","output_tokens"):
            if type(r[k]) is not int or r[k]<0:
                raise ValueError("counter")
        if not r["budget"] or r["input_tokens"]+r["output_tokens"]>r["budget"]:
            raise ValueError("invalid reported budget")
        if type(r["passed"]) is not bool or type(r["recovered"]) is not bool:
            raise ValueError("verification flags")
        t=r["latency_ms"]
        if type(t) not in (int,float) or not math.isfinite(t) or t<0:
            raise ValueError("latency")
        key=tuple(r[k] for k in IDENTITY)
        pair=pairs.setdefault(key,{})
        if r["mode"] in pair:raise ValueError("duplicate arm")
        pair[r["mode"]]=r
    if any(set(p)!={"direct","nexus"} for p in pairs.values()):
        raise ValueError("missing arm or mismatched identity")
    # One coherent host/model/configuration per report.
    if len({(k[3],k[4],k[5]) for k in pairs})!=1:
        raise ValueError("mixed host/model/configuration")
    report={}
    for cls in CLASSES:
        subset=[p for k,p in pairs.items() if k[1]==cls]
        tasks={}
        for k in pairs:
            if k[1]==cls:tasks.setdefault(k[0],set()).add(k[2])
        sufficient=len(tasks)>=10 and all(len(v)>=3 for v in tasks.values())
        if not subset:
            report[cls]={"pairs":0,"minimum_sample_met":False}
            continue
        metrics={}
        for mode in ("direct","nexus"):
            rows=[p[mode] for p in subset]
            metrics[mode]={"passed":sum(r["passed"] for r in rows),
                           "recovered":sum(r["recovered"] for r in rows),
                           "median_ms":statistics.median(r["latency_ms"] for r in rows),
                           "total_reported_tokens":sum(r["input_tokens"]+r["output_tokens"] for r in rows)}
        report[cls]={"pairs":len(subset),"tasks":len(tasks),"minimum_sample_met":sufficient,
                     "metrics":metrics}
    return {"scope":"operator-supplied evidence; no execution or independent attestation",
            "classes":report,"all_minimum_samples_met":all(r["minimum_sample_met"] for r in report.values())}


def main():
    p=argparse.ArgumentParser();p.add_argument("records",type=Path);a=p.parse_args()
    with a.records.open("rb") as f:
        data=f.read(8*1024*1024+1)
    if len(data)>8*1024*1024:raise SystemExit("record file too large")
    print(json.dumps(evaluate(json.loads(data)),indent=2))


if __name__=="__main__":main()
