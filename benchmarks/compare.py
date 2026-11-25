"""Paired synthetic benchmark. No real model quality or billing claims."""
import json
import statistics
import tempfile
from pathlib import Path
from time import perf_counter_ns
from nexus_engine.engine import run


def main():
    p={"host":"fixture","budget":3,"resume":False,"nodes":[{"id":"sum","depends_on":[],"input":{"values":[1,2,3]},"max_tokens":3}]}
    times={"direct":[],"lite":[],"durable":[]}
    with tempfile.TemporaryDirectory() as tmp:
        db=Path(tmp)/"bench.db"
        for i in range(30):
            modes=list(times)
            if i%2:modes.reverse()
            for m in modes:
                start=perf_counter_ns()
                if m=="direct":value=sum(p["nodes"][0]["input"]["values"])
                else:value=run(p,db=db,run_id=f"pair-{i}",force_durable=m=="durable")["outputs"]["sum"]
                times[m].append((perf_counter_ns()-start)/1e6)
                if value!=6:raise RuntimeError("incorrect benchmark result")
    print(json.dumps({"scope":"deterministic arithmetic only","pairs":30,"correct":90,
                      "median_ms":{k:statistics.median(v) for k,v in times.items()}},indent=2))


if __name__=="__main__":main()
