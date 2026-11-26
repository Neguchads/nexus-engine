"""Exercise exact prior public wheels; no credentials, provider calls or user data."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import venv

BASELINES={
    "0.1.0a6":"93eb15d992634c284c6bf3564c74638901a2d97d03f3b1edcd46e8d33852f43f",
    "0.1.0a8":"484a8bf4f3bbeb7acf1684a91ece61f8f3d1729c324794184fe69b6ed04b825f",
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fetch(version, directory):
    name=f"nexus_engine-{version}-py3-none-any.whl"
    path=directory/name
    url=f"https://github.com/Neguchads/nexus-engine/releases/download/v{version}/{name}"
    with urllib.request.urlopen(url,timeout=60) as stream:
        data=stream.read(1024*1024+1)
    if len(data)>1024*1024 or hashlib.sha256(data).hexdigest()!=BASELINES[version]:
        raise RuntimeError("released wheel identity mismatch")
    path.write_bytes(data)
    return path


def python(env):
    return env/("Scripts/python.exe" if os.name=="nt" else "bin/python")


def call(py,*args,ok=True):
    proc=subprocess.run([str(py),"-I",*map(str,args)],capture_output=True,text=True,timeout=90)
    if (proc.returncode==0)!=ok:
        raise RuntimeError(f"unexpected command status {proc.returncode}: {proc.stderr[:500]}")
    return proc.stdout.strip()


def cli(py,*args,ok=True):
    out=call(py,"-m","nexus_engine.cli",*args,ok=ok)
    return json.loads(out) if ok else None


def install(py,wheel):
    call(py,"-m","pip","install","--no-index","--no-deps","--force-reinstall",wheel)


def version(py):
    return call(py,"-c","import importlib.metadata as m; print(m.version('nexus-engine'))")


def write(path,value):
    path.write_text(json.dumps(value),encoding="utf-8")


def test_baseline(root,baseline,candidate,expected):
    old=fetch(baseline,root)
    env=root/"environment"
    venv.EnvBuilder(with_pip=True).create(env)
    py=python(env)
    install(py,old)
    assert version(py)==baseline
    plan=root/"plan.json"
    write(plan,{"host":"fixture","budget":6,"resume":True,"nodes":[
        {"id":"A","depends_on":[],"input":{"values":[2,3]},"max_tokens":3},
        {"id":"B","depends_on":["A"],"input":{"values":[7]},"max_tokens":3}]})
    db=root/"primary.db"; backup=root/"before.db"; answer=root/"answer.json"
    args=["--db",db,"--run-id","demo"]
    cli(py,"start",plan,*args)
    req=cli(py,"next",*args)
    write(answer,{"request_id":req["request_id"],"host":"fixture","output":5,"usage":1})
    cli(py,"submit",answer,*args)
    data=root/"input.bin";data.write_bytes(b"nexus migration evidence")
    artifact=cli(py,"attach","A","evidence",data,*args)
    before=cli(py,"audit",*args)
    cli(py,"backup",backup,"--db",db)
    backup_sha=sha(backup)
    # Independent external pending request: no provider dispatch occurs.
    external=root/"external.db";external_plan=root/"external.json"
    write(external_plan,{"host":"codex","budget":10,"resume":True,"nodes":[
        {"id":"review","depends_on":[],"input":{"task":"synthetic"},"max_tokens":10}]})
    ext=["--db",external,"--run-id","external"]
    cli(py,"start",external_plan,*ext)
    preview=cli(py,"preview",*ext)
    pending=cli(py,"next",*ext,"--approve","--approval-sha256",preview["approval_sha256"])
    ext_before=cli(py,"audit",*ext)
    # Upgrade exact prior installation with the current CI wheel.
    install(py,candidate)
    assert version(py)==expected
    assert cli(py,"audit",*args)==before
    result=cli(py,"run",plan,*args)
    assert result["outputs"]=={"A":5,"B":12}
    out=root/"extracted.bin"
    assert cli(py,"artifact","A","evidence",out,*args)==artifact
    assert out.read_bytes()==data.read_bytes()
    assert cli(py,"audit",*ext)==ext_before
    cli(py,"next",*ext,"--approve","--approval-sha256",preview["approval_sha256"],ok=False)
    assert cli(py,"status",*ext)["pending"]==[pending["request_id"]]
    ext_backup=root/"external-backup.db"
    cli(py,"backup",ext_backup,"--db",external)
    cli(py,"recover-fixtures",root/"forbidden.db","--db",ext_backup,"--confirm",ok=False)
    assert not (root/"forbidden.db").exists()
    # Rollback is isolated: never downgrade the authoritative upgraded DB.
    primary_sha=sha(db); external_sha=sha(external)
    install(py,old)
    assert version(py)==baseline
    restored=root/"rollback.db"
    cli(py,"recover-fixtures",restored,"--db",backup,"--confirm")
    rolled=cli(py,"run",plan,"--db",restored,"--run-id","demo")
    assert rolled["outputs"]==result["outputs"]
    assert sha(db)==primary_sha and sha(external)==external_sha and sha(backup)==backup_sha
    call(py,"-m","pip","uninstall","-y","nexus-engine")
    call(py,"-c","import nexus_engine",ok=False)
    assert sha(db)==primary_sha and sha(backup)==backup_sha
    return {"baseline":baseline,"baseline_sha256":BASELINES[baseline],
            "candidate":expected,"upgrade":True,"checkpoint_preserved":True,
            "artifact_preserved":True,"external_replay_blocked":True,
            "isolated_fixture_rollback":True,"uninstall_preserved_data":True}


def main():
    p=argparse.ArgumentParser();p.add_argument("wheel",type=Path)
    p.add_argument("--output",type=Path,required=True);a=p.parse_args()
    candidate=a.wheel.resolve()
    expected=candidate.name.split("-")[1]
    rows=[]
    with tempfile.TemporaryDirectory() as tmp:
        for baseline in BASELINES:
            root=Path(tmp)/baseline;root.mkdir()
            rows.append(test_baseline(root,baseline,candidate,expected))
    report={"scope":"exact public alpha wheels; deterministic data rollback only; no external replay",
            "candidate_sha256":sha(candidate),"platform":sys.platform,"python":sys.version,
            "results":rows}
    a.output.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2))


if __name__=="__main__":main()
