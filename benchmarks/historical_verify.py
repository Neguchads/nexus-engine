"""Independent regressions for real historical Nexus Store defects."""
import json
import sqlite3
import sys
import tempfile
from contextlib import closing
from pathlib import Path
from nexus_engine.contracts import Rejected,digest,encode,response
from nexus_engine.store import Store


def plan():
    return {"host":"fixture","budget":6,"resume":True,"nodes":[
        {"id":"A","depends_on":[],"input":{"values":[1]},"max_tokens":1},
        {"id":"B","depends_on":["A"],"input":{"values":[2]},"max_tokens":3}]}


def reject(fn):
    try:fn()
    except Rejected:return
    raise AssertionError("semantic mismatch was accepted")


def change(db,node,mutate):
    with closing(sqlite3.connect(db)) as c,c:
        request=json.loads(c.execute("SELECT request FROM steps WHERE run_id='r' AND node=?",(node,)).fetchone()[0])
        mutate(request)
        c.execute("UPDATE steps SET request=?,request_hash=? WHERE run_id='r' AND node=?",
                  (encode(request),digest(request),node))


def completion(s,db):
    s.start("r",plan());a=s.next("r")
    answer=response(a,{"nested":[True]},1)
    s.submit("r",answer);s.submit("r",answer)
    reject(lambda:s.submit("r",response(a,{"nested":[1]},1)))
    reject(lambda:s.submit("r",response(a,{"nested":[False]},1)))
    assert s.status("r")["outputs"]=={"A":{"nested":[True]}}


def request(s,db):
    s.start("r",plan());s.next("r");assert s.status("r")["pending"]
    change(db,"A",lambda r:r.update(max_tokens=True))
    reject(lambda:s.status("r"))
    change(db,"A",lambda r:r.update(max_tokens=1))
    assert s.status("r")["pending"]
    change(db,"A",lambda r:r.update(input={"values":[True]}))
    reject(lambda:s.status("r"))


def dependencies(s,db):
    s.start("r",plan());a=s.next("r")
    s.submit("r",response(a,{"nested":[True]},1))
    s.next("r");assert s.status("r")["completed"]==1
    change(db,"B",lambda r:r.update(dependencies={"A":{"nested":[1]}}))
    reject(lambda:s.status("r"))


if __name__=="__main__":
    cases={"completion":completion,"request":request,"dependencies":dependencies}
    with tempfile.TemporaryDirectory() as tmp:
        db=Path(tmp)/"state.db"
        cases[sys.argv[1]](Store(db),db)
    print("PASS")
