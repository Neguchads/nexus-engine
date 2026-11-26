"""Bounded model-proposed expressions applied to historical Nexus source copies.

Only a small comparison-expression grammar is accepted; no arbitrary model code.
Historical source and verifier are trusted repository files, never modified in main.
"""
import argparse
import ast
import hashlib
import json
import random
import re
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path
from time import perf_counter_ns
from nexus_engine.contracts import digest,response
from nexus_engine.ollama import execute_with_metrics,payload
from nexus_engine.store import Store

BASE="25cb48b5ea45b8ac05fdcf0f4a018641d835f97d"
MODEL="qwen2.5-coder:7b"
MODES=("direct-full","direct-projected","nexus-projected")
# Each pair is an exact historical source comparison; the proposed expression
# replaces both operands via AST substitution, never raw model string injection.
TARGETS={
 "completion":[("old","answer")],
 "request":[('request["max_tokens"]','node["max_tokens"]'),('request["input"]','node["input"]')],
 "dependencies":[('request["dependencies"]','project(known[key],{d:steps[d][1]["output"] for d in deps})')],
}
TASK=("Fix the historical JSON comparison defect described in dependencies.source. "
      "Return exactly JSON with one string field expression. The expression must be True "
      "when left and right differ as canonical JSON, False when identical. "
      "Allowed names: left, right; functions encode (canonical JSON), type; operators "
      "!=, ==, is, is not, and, or, not. No statements or attributes. "
      "Do not return code fences or explanations.")


def proposed(expression,left,right):
    if not isinstance(expression,str) or not 1<=len(expression)<=240:
        raise ValueError("expression size")
    parsed=ast.parse(expression,mode="eval")
    nodes=list(ast.walk(parsed))
    allowed=(ast.Expression,ast.Compare,ast.Name,ast.Load,ast.Call,ast.BoolOp,
             ast.UnaryOp,ast.Eq,ast.NotEq,ast.Is,ast.IsNot,ast.And,ast.Or,ast.Not)
    if len(nodes)>40 or any(not isinstance(n,allowed) for n in nodes):
        raise ValueError("outside expression grammar")
    if {n.id for n in nodes if isinstance(n,ast.Name)}-{"left","right","encode","type"}:
        raise ValueError("unknown identifier")
    if not {"left","right"}<={n.id for n in nodes if isinstance(n,ast.Name)}:
        raise ValueError("both operands required")
    for n in nodes:
        if isinstance(n,ast.Call):
            if not isinstance(n.func,ast.Name) or n.func.id not in ("encode","type") or len(n.args)!=1 or n.keywords:
                raise ValueError("function outside grammar")
            if not isinstance(n.args[0],ast.Name) or n.args[0].id not in ("left","right"):
                raise ValueError("call operand outside grammar")
    class Replace(ast.NodeTransformer):
        def visit_Name(self,n):
            if n.id in ("left","right"):
                return ast.parse(left if n.id=="left" else right,mode="eval").body
            return n
    return "("+ast.unparse(Replace().visit(parsed).body)+")"


def patch_source(source,case,expression):
    for left,right in TARGETS[case]:
        target=left+" != "+right
        if source.count(target)!=1:
            raise ValueError("historical patch target mismatch")
        source=source.replace(target,proposed(expression,left,right),1)
    ast.parse(source)
    return source


def checkout(root):
    root.mkdir()
    names=subprocess.check_output(["git","ls-tree","-r","--name-only",BASE,"nexus_engine"],text=True).splitlines()
    if not names or len(names)>40:
        raise RuntimeError("unexpected source inventory")
    for name in names:
        if not re.fullmatch(r"nexus_engine/[A-Za-z0-9_]+\.py",name):
            raise RuntimeError("unexpected historical source path")
        data=subprocess.check_output(["git","show",BASE+":"+name])
        if len(data)>128*1024:
            raise RuntimeError("historical file too large")
        path=root/name;path.parent.mkdir(exist_ok=True);path.write_bytes(data)
    return root/"nexus_engine/store.py"


def verify(root,case):
    verifier=Path(__file__).with_name("historical_verify.py").resolve()
    code="import sys,runpy; sys.path.insert(0,sys.argv[1]); sys.argv=[sys.argv[2],sys.argv[3]]; runpy.run_path(sys.argv[0],run_name='__main__')"
    p=subprocess.run([sys.executable,"-I","-B","-c",code,str(root),str(verifier),case],
                     cwd=root,capture_output=True,text=True,timeout=30)
    return p.returncode==0 and p.stdout.strip()=="PASS",p.stderr[-800:]


def case_data(source,case):
    target_lines=[]
    for left,right in TARGETS[case]:
        token=left+" != "+right
        lines=source.splitlines()
        i=next(i for i,line in enumerate(lines) if token in line)
        target_lines.extend(lines[max(0,i-3):i+4])
    useful={"defect":"Python equality conflates JSON boolean and integer values, including nested fields. Preserve exact canonical JSON identity.",
            "target_lines":"\n".join(target_lines),
            "available":"encode(value) returns canonical JSON text; left and right denote the two operands."}
    # Real unrelated source, not generated documentation.
    start=source.index("    def attach(")
    end=source.index("    def artifact(",start)
    return {**useful,"unrelated_artifact_method":source[start:end]}


def measure(case,mode,root,source):
    state=root/"state.db"
    data=case_data(source,case)
    task={"model":MODEL,"task":TASK}
    meta={"case":case,"mode":mode,"base":BASE}
    metrics=None;start=perf_counter_ns()
    try:
        if mode=="nexus-projected":
            store=Store(state)
            plan={"host":"ollama","resume":True,"budget":4097,"nodes":[
                {"id":"source","depends_on":[],"input":{"kind":"historical source"},"max_tokens":1},
                {"id":"patch","depends_on":["source"],"input":task,"max_tokens":4096,
                 "context":{"select":{"source":["defect","target_lines","available"]},"max_bytes":8192}}]}
            store.start("r",plan)
            review=store.preview("r");req=store.next("r",approved=True,approval_sha256=review["approval_sha256"])
            store.submit("r",response(req,data,0))
            review=store.preview("r");req=store.next("r",approved=True,approval_sha256=review["approval_sha256"])
        else:
            selected=data if mode=="direct-full" else {k:v for k,v in data.items() if k!="unrelated_artifact_method"}
            req={"host":"ollama","request_id":"direct","input":task,"dependencies":{"source":selected},"max_tokens":4096}
        body_hash=digest(payload(req))
        answer,metrics=execute_with_metrics(req)
        if mode=="nexus-projected":
            store.submit("r",answer)
            status=Store(state).status("r")
            if status["completed"]!=2 or status["reserved_or_reported"]!=answer["usage"]:
                raise RuntimeError("durable accounting mismatch")
        value=answer["output"]
        if not isinstance(value,dict) or set(value)!={"expression"}:
            raise ValueError("invalid patch response")
        workspace=root/"checkout";path=checkout(workspace)
        changed=patch_source(path.read_text(encoding="utf-8"),case,value["expression"])
        path.write_text(changed,encoding="utf-8")
        passed,diagnostic=verify(workspace,case)
        return {**meta,"passed":passed,"error":None,"metrics":metrics,"body_sha256":body_hash,
                "expression":value["expression"],"patched_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
                "diagnostic":diagnostic,"latency_ms":(perf_counter_ns()-start)/1e6}
    except Exception as exc:
        return {**meta,"passed":False,"error":type(exc).__name__+": "+str(exc)[:160],
                "metrics":metrics,"latency_ms":(perf_counter_ns()-start)/1e6}


def main():
    p=argparse.ArgumentParser();p.add_argument("--output",type=Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False)
    rows=[];controls={};rng=random.Random(926)
    with tempfile.TemporaryDirectory() as tmp,(a.output/"records.jsonl").open("x",encoding="utf-8") as out:
        root=Path(tmp)
        for case in TARGETS:
            control=root/(case+"-control");path=checkout(control)
            source=path.read_text(encoding="utf-8")
            baseline,_=verify(control,case)
            path.write_text(patch_source(source,case,"encode(left) != encode(right)"),encoding="utf-8")
            positive,_=verify(control,case)
            controls[case]={"unpatched_passed":baseline,"known_fix_passed":positive}
            if baseline or not positive:
                raise RuntimeError("invalid independent regression control: "+case)
            modes=list(MODES);rng.shuffle(modes)
            for mode in modes:
                work=root/(case+"-"+mode);work.mkdir()
                row=measure(case,mode,work,source);rows.append(row)
                out.write(json.dumps(row)+"\n");out.flush();print(json.dumps(row),flush=True)
    result={}
    for mode in MODES:
        rs=[r for r in rows if r["mode"]==mode]
        result[mode]={"trials":len(rs),"passed":sum(r["passed"] for r in rs),"errors":sum(r["error"] is not None for r in rs),
                      "input_tokens":sum(r["metrics"]["input_tokens"] for r in rs if r["metrics"] is not None),
                      "output_tokens":sum(r["metrics"]["output_tokens"] for r in rs if r["metrics"] is not None),
                      "complete_usage":all(r["metrics"] is not None for r in rs),
                      "median_ms":statistics.median(r["latency_ms"] for r in rs)}
    grouped={(r["case"],r["mode"]):r for r in rows}
    matched=all(grouped[c,"direct-projected"].get("body_sha256") is not None and
                grouped[c,"direct-projected"].get("body_sha256")==grouped[c,"nexus-projected"].get("body_sha256") for c in TARGETS)
    gate=matched and all(x["complete_usage"] and x["errors"]==0 for x in result.values()) and result["nexus-projected"]["passed"]==len(TARGETS)
    report={"scope":"three related historical JSON-identity repairs with restricted expressions; not autonomous repository engineering",
            "base":BASE,"model":MODEL,"controls":controls,"matched_projected_bodies":matched,"modes":result,"experimental_gate":gate}
    (a.output/"summary.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2),flush=True)
    if not gate:raise SystemExit("historical repair gate failed; evidence preserved")


if __name__=="__main__":main()
