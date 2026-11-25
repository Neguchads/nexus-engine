"""CLI for deterministic execution and explicitly approved external JSON handoffs."""
import argparse
import json
import sqlite3
from pathlib import Path
from .contracts import LIMIT, Rejected, route, validate


def read(path):
    with Path(path).open("rb") as f:
        raw=f.read(LIMIT+1)
    if len(raw)>LIMIT:
        raise Rejected("input exceeds limit")
    return json.loads(raw)


def main():
    p=argparse.ArgumentParser(prog="nexus-engine")
    sub=p.add_subparsers(dest="command",required=True)
    for name in ("plan","run","start","next","submit","status"):
        q=sub.add_parser(name)
        if name in ("plan","run","start"):
            q.add_argument("plan")
        if name!="plan":
            q.add_argument("--db",required=name!="run")
            q.add_argument("--run-id",required=name!="run")
        if name=="next":
            q.add_argument("--approve",action="store_true")
        if name=="submit":
            q.add_argument("answer")
    a=p.parse_args()
    try:
        if a.command=="plan":
            plan,order=validate(read(a.plan))
            result={"mode":route(plan),"host":plan["host"],"order":[n["id"] for n in order]}
        elif a.command=="run":
            from .engine import run
            result=run(read(a.plan),db=a.db,run_id=a.run_id)
        else:
            from .store import Store
            store=Store(a.db)
            if a.command=="start":
                store.start(a.run_id,read(a.plan))
                result=store.status(a.run_id)
            elif a.command=="next":
                result=store.next(a.run_id,approved=a.approve)
            elif a.command=="submit":
                store.submit(a.run_id,read(a.answer))
                result=store.status(a.run_id)
            else:
                result=store.status(a.run_id)
        print(json.dumps(result,indent=2))
    except (ValueError,OSError,sqlite3.Error,KeyError,TypeError) as exc:
        p.exit(2,"nexus-engine: "+str(exc)+"\n")

if __name__=="__main__":
    main()
