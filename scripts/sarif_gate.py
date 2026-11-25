"""Require actual SARIF results and report all runtime findings, without suppression."""
import argparse
import json
from pathlib import Path


def inspect(directory):
    paths=sorted(Path(directory).glob("*.sarif"))
    if not paths:raise ValueError("no SARIF evidence")
    findings=[];runs=0
    for p in paths:
        if p.stat().st_size>32*1024*1024:raise ValueError("SARIF size limit")
        data=json.loads(p.read_text(encoding="utf-8"))
        if data.get("version")!="2.1.0" or not isinstance(data.get("runs"),list):
            raise ValueError("invalid SARIF format")
        for run in data["runs"]:
            runs+=1
            if not isinstance(run.get("results"),list):raise ValueError("missing analysis results")
            if any(i.get("executionSuccessful") is False for i in run.get("invocations",[])):
                raise ValueError("analysis invocation failed")
            for item in run["results"]:
                findings.append({"rule":item.get("ruleId","unknown"),"level":item.get("level","unspecified")})
    if not runs:raise ValueError("no analysis runs")
    return {"runs":runs,"finding_count":len(findings),"findings":findings,
            "scope":"CodeQL default Python security queries on runtime; not a penetration test or human audit"}


def main():
    p=argparse.ArgumentParser();p.add_argument("directory",type=Path);a=p.parse_args()
    result=inspect(a.directory);print(json.dumps(result,indent=2))
    (a.directory/"gate-summary.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    if result["finding_count"]:raise SystemExit("review reported findings before qualification")


if __name__=="__main__":main()
