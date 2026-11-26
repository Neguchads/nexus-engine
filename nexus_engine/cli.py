"""CLI for deterministic execution and explicitly approved external JSON handoffs."""
import argparse
import json
import sqlite3
from pathlib import Path
from .contracts import LIMIT, Rejected, decode, route, validate


def read(path):
    with Path(path).open("rb") as f:
        raw=f.read(LIMIT+1)
    if len(raw)>LIMIT:
        raise Rejected("input exceeds limit")
    return decode(raw)


def main():
    from . import __version__
    p=argparse.ArgumentParser(prog="nexus-engine")
    p.add_argument("--version",action="version",version=__version__)
    sub=p.add_subparsers(dest="command",required=True)
    for name in ("plan","run","start","preview","next","submit","status","audit","abandon","ollama-step","context","merge","attach","artifact","verify-db","backup","restore","recover-fixtures","codex-import"):
        q=sub.add_parser(name)
        if name in ("plan","run","start"):
            q.add_argument("plan")
        if name!="plan":
            q.add_argument("--db",required=name!="run")
            if name not in ("verify-db","backup","restore","recover-fixtures"):
                q.add_argument("--run-id",required=name!="run")
        if name in ("next","ollama-step"):
            q.add_argument("--approve",action="store_true")
            q.add_argument("--approval-sha256")
        if name=="submit":
            q.add_argument("answer")
        if name=="codex-import":
            q.add_argument("trace")
            q.add_argument("--confirm",action="store_true")
        if name=="merge":
            q.add_argument("nodes",nargs="+")
        if name in ("attach","artifact"):
            q.add_argument("node")
            q.add_argument("artifact_name")
            q.add_argument("file")
        if name=="artifact":
            q.add_argument("--consumer")
        if name in ("backup","restore","recover-fixtures"):
            q.add_argument("destination")
        if name=="recover-fixtures":
            q.add_argument("--confirm",action="store_true")
        if name=="abandon":
            q.add_argument("--reason",required=True)
            q.add_argument("--confirm",action="store_true")
    a=p.parse_args()
    try:
        if a.command=="plan":
            plan,order=validate(read(a.plan))
            result={"mode":route(plan),"host":plan["host"],"order":[n["id"] for n in order]}
        elif a.command=="run":
            from .engine import run
            result=run(read(a.plan),db=a.db,run_id=a.run_id)
        elif a.command in ("backup","restore","recover-fixtures"):
            from .recovery import snapshot
            if a.command=="recover-fixtures" and not a.confirm:
                raise Rejected("explicit recovery confirmation required")
            result=snapshot(a.db,a.destination,seal=a.command=="restore",promote=a.command=="recover-fixtures")
        else:
            from .store import Store
            if a.command!="start" and not Path(a.db).is_file():
                raise Rejected("database must exist")
            store=Store(a.db)
            if a.command=="start":
                store.start(a.run_id,read(a.plan))
                result=store.status(a.run_id)
            elif a.command=="preview":
                result=store.preview(a.run_id)
            elif a.command=="next":
                result=store.next(a.run_id,approved=a.approve,approval_sha256=a.approval_sha256)
            elif a.command=="submit":
                store.submit(a.run_id,read(a.answer))
                result=store.status(a.run_id)
            elif a.command=="codex-import":
                if not a.confirm:
                    raise Rejected("reviewed trace import requires --confirm")
                from .codex_trace import read_trace
                answer,evidence=read_trace(a.trace)
                store.submit(a.run_id,answer)
                result={"trace":evidence,"audit":store.audit(a.run_id)}
            elif a.command=="ollama-step":
                if not a.approve:
                    raise Rejected("explicit approval required for local HTTP dispatch")
                from .ollama import step
                result=step(store,a.run_id,a.approval_sha256)
            elif a.command=="context":
                result=store.context_report(a.run_id)
            elif a.command=="merge":
                result=store.merge(a.run_id,a.nodes)
            elif a.command=="attach":
                with Path(a.file).open("rb") as f:
                    data=f.read(1048577)
                result=store.attach(a.run_id,a.node,a.artifact_name,data)
            elif a.command=="artifact":
                data,result=store.artifact(a.run_id,a.node,a.artifact_name,consumer=a.consumer)
                import os
                fd=os.open(a.file,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
                with os.fdopen(fd,"wb") as f:
                    f.write(data)
            elif a.command=="verify-db":
                result=store.verify_all()
            elif a.command=="audit":
                result=store.audit(a.run_id)
            elif a.command=="abandon":
                if not a.confirm:
                    raise Rejected("permanent abandonment requires --confirm")
                store.abandon(a.run_id,a.reason)
                result=store.audit(a.run_id)
            else:
                result=store.status(a.run_id)
        print(json.dumps(result,indent=2))
    except (ValueError,OSError,sqlite3.Error,KeyError,TypeError) as exc:
        p.exit(2,"nexus-engine: "+str(exc)+"\n")

if __name__=="__main__":
    main()
