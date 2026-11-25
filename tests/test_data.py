import hashlib
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from nexus_engine.contracts import Rejected, response, validate
from nexus_engine.engine import run
from nexus_engine.recovery import snapshot
from nexus_engine.store import Store
from nexus_engine.merge import merge_objects


def node(key,deps=(),context=None):
    n={"id":key,"depends_on":list(deps),"input":{"values":[1]},"max_tokens":100}
    if context is not None:n["context"]=context
    return n


def plan(host="fixture",context=None):
    return {"host":host,"budget":300,"resume":True,
            "nodes":[node("A"),node("B",["A"],context),node("C")]}


def complete(s,r,value):
    preview=s.preview(r)
    req=s.next(r,approved=True,approval_sha256=preview["approval_sha256"])
    s.submit(r,response(req,value,1))
    return req


class DataTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name);self.db=self.root/"state.db"
        self.s=Store(self.db)

    def test_artifact_scope_and_integrity(self):
        run(plan(),db=self.db,run_id="r")
        data=b"artifact\x00"
        meta=self.s.attach("r","A","report",data)
        self.assertEqual(meta["sha256"],hashlib.sha256(data).hexdigest())
        self.assertEqual(self.s.artifact("r","A","report",consumer="B"),(data,meta))
        self.assertEqual(self.s.attach("r","A","report",data),meta)
        for consumer in ("C","A","unknown"):
            with self.assertRaises(Rejected):self.s.artifact("r","A","report",consumer=consumer)
        with self.assertRaises(Rejected):self.s.attach("r","A","report",b"changed")
        run(plan(),db=self.db,run_id="other")
        with self.assertRaises(Rejected):self.s.artifact("other","A","report")
        self.assertEqual(self.s.verify_all()["artifacts"],1)

    def test_artifact_bounds_and_unfinished_node(self):
        self.s.start("r",plan())
        with self.assertRaises(Rejected):self.s.attach("r","A","file",b"a")
        complete(self.s,"r",1)
        for name,data in (("../file",b"a"),("file",b"a"*1048577),("file","text")):
            with self.assertRaises(Rejected):self.s.attach("r","A",name,data)
        for i in range(32):self.s.attach("r","A",f"file{i}",b"a")
        with self.assertRaises(Rejected):self.s.attach("r","A","extra",b"a")

    def test_corruption_detected(self):
        run(plan(),db=self.db,run_id="r")
        self.s.attach("r","A","report",b"original")
        with closing(sqlite3.connect(self.db)) as c,c:
            c.execute("UPDATE artifacts SET content=?",(b"tampered",))
        with self.assertRaisesRegex(Rejected,"artifact integrity"):self.s.verify_all()
        with self.assertRaises(Rejected):snapshot(self.db,self.root/"bad.db")
        self.assertFalse((self.root/"bad.db").exists())

    def test_merge_conflicts_and_provenance(self):
        self.s.start("r",plan("codex"))
        complete(self.s,"r",{"a":1,"same":True})
        complete(self.s,"r",{"c":3})
        complete(self.s,"r",{"b":2,"same":True})
        result=self.s.merge("r",["B","A"])
        self.assertEqual(result["output"],{"a":1,"b":2,"same":True})
        self.assertEqual(result["sha256"],self.s.merge("r",["A","B"])["sha256"])
        self.assertEqual(set(result["sources"]),{"A","B"})
        with self.assertRaises(Rejected):merge_objects({"A":{"x":True},"B":{"x":1}})
        with self.assertRaises(Rejected):self.s.merge("r",["A","missing"])

    def test_context_projection_bound_to_preview(self):
        ctx={"select":{"A":["summary"]},"max_bytes":100}
        self.s.start("r",plan("codex",ctx))
        complete(self.s,"r",{"summary":"ok","private":"x"*5000})
        complete(self.s,"r",{"unrelated":"value"})
        review=self.s.preview("r")
        self.assertEqual(review["payload"]["dependencies"],{"A":{"summary":"ok"}})
        req=self.s.next("r",approved=True,approval_sha256=review["approval_sha256"])
        self.s.submit("r",response(req,{"ok":True},5))
        b=next(x for x in self.s.context_report("r") if x["node"]=="B")
        self.assertGreater(b["full_bytes"],b["selected_bytes"])
        self.assertEqual(Store(self.db).verify_all()["runs"],1)

    def test_context_rejects_missing_fields_without_reserving(self):
        self.s.start("r",plan("codex",{"select":{"A":["missing"]},"max_bytes":100}))
        complete(self.s,"r",{"summary":"ok"});complete(self.s,"r",{})
        with self.assertRaisesRegex(Rejected,"fields missing"):self.s.preview("r")
        self.assertEqual(self.s.status("r")["pending"],[])

    def test_context_budget_and_policy(self):
        with self.assertRaises(Rejected):validate(plan("fixture",{"select":{},"max_bytes":100}))
        with self.assertRaises(Rejected):validate(plan("codex",{"select":{"C":["x"]},"max_bytes":100}))
        self.s.start("r",plan("codex",{"select":{"A":["summary"]},"max_bytes":2}))
        complete(self.s,"r",{"summary":"too long"});complete(self.s,"r",{})
        with self.assertRaisesRegex(Rejected,"byte budget"):self.s.preview("r")

    def test_snapshot_preserves_pending_and_seals(self):
        self.s.start("r",plan())
        req=self.s.next("r")
        backup=self.root/"backup.db"
        info=snapshot(self.db,backup)
        self.assertTrue(info["sealed"])
        restored=Store(backup)
        self.assertEqual(restored.status("r")["pending"],[req["request_id"]])
        with self.assertRaises(Rejected):restored.submit("r",response(req,1,1))
        with self.assertRaises(Rejected):restored.start("new",plan())
        with self.assertRaises(Rejected):restored.abandon("r","cannot")
        with self.assertRaises(Rejected):snapshot(self.db,backup)
        self.s.submit("r",response(req,1,1))
        self.assertEqual(restored.status("r")["completed"],0)
        self.assertEqual(self.s.status("r")["completed"],1)

    def test_snapshot_completed_artifact_and_restore(self):
        run(plan(),db=self.db,run_id="r")
        self.s.attach("r","A","blob",b"data")
        backup=self.root/"copy.db";restored=self.root/"restored.db"
        snapshot(self.db,backup)
        self.assertTrue(snapshot(backup,restored,seal=True)["sealed"])
        s=Store(restored)
        self.assertEqual(s.artifact("r","A","blob")[0],b"data")
        with self.assertRaises(Rejected):s.attach("r","A","new",b"data")

    def test_snapshot_invalid_source(self):
        invalid=self.root/"invalid.db"
        with closing(sqlite3.connect(invalid)) as c,c:c.execute("CREATE TABLE unrelated(a)")
        with self.assertRaises(Rejected):snapshot(invalid,self.root/"bad.db")
        self.assertFalse((self.root/"bad.db").exists())


if __name__=="__main__":unittest.main()
