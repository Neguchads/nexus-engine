import sqlite3
from contextlib import closing
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from nexus_engine.contracts import Rejected, route, response
from nexus_engine.engine import run
from nexus_engine.store import Store


def node(key="A",deps=(),values=(2,3),cap=3):
    return {"id":key,"depends_on":list(deps),"input":{"values":list(values)},"max_tokens":cap}


def plan(nodes=None,host="fixture",resume=False,budget=20):
    return {"host":host,"budget":budget,"resume":resume,"nodes":nodes or [node()]}


class EngineTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.db=Path(tmp.name)/"state.db"

    def test_lite(self):
        self.assertEqual(route(plan()),"lite")
        self.assertEqual(run(plan(),db=self.db)["outputs"],{"A":5})
        self.assertFalse(self.db.exists())

    def test_dag_diamond(self):
        p=plan([node("D",["B","C"],[1]),node("B",["A"],[1]),node("C",["A"],[2]),node()])
        self.assertEqual(run(p,db=self.db,run_id="r")["outputs"],{"A":5,"B":6,"C":7,"D":14})

    def test_completed_resume(self):
        p=plan([node(),node("B",["A"])],resume=True)
        a=run(p,db=self.db,run_id="r")
        self.assertEqual(a,run(p,db=self.db,run_id="r"))

    def test_no_resume(self):
        p=plan(resume=False)
        run(p,db=self.db,run_id="r",force_durable=True)
        with self.assertRaises(Rejected):
            run(p,db=self.db,run_id="r",force_durable=True)

    def test_cycle(self):
        with self.assertRaises(Rejected): route(plan([node("A",["B"]),node("B",["A"])]))

    def test_unknown_dep(self):
        with self.assertRaises(Rejected): route(plan([node("A",["B"])]))

    def test_duplicate(self):
        with self.assertRaises(Rejected): route(plan([node(),node()]))

    def test_budget(self):
        for p in (plan(budget=2),plan(budget=True),plan([node(cap=True)])):
            with self.assertRaises(Rejected):route(p)

    def test_size_limit(self):
        p=plan();p["nodes"][0]["input"]={"a":"x"*140000}
        with self.assertRaises(Rejected):route(p)

    def test_unknown_host(self):
        with self.assertRaises(Rejected):route(plan(host="arbitrary"))

    def test_no_provider_fallback(self):
        for host in ("codex","claude","gemini","copilot","ollama"):
            p=plan(host=host)
            self.assertEqual(route(p),"durable")
            with self.assertRaises(Rejected):run(p)
        self.assertFalse(self.db.exists())

    def test_external_approval_and_binding(self):
        s=Store(self.db)
        for host in ("codex","claude","gemini","copilot","ollama"):
            s.start(host,plan(host=host,resume=True))
            with self.assertRaises(Rejected):s.next(host)
            req=s.next(host,approved=True,approval_sha256=s.preview(host)["approval_sha256"])
            self.assertEqual(req["host"],host)
            wrong=response(req,5,1);wrong["host"]="fixture"
            with self.assertRaises(Rejected):s.submit(host,wrong)
            s.submit(host,response(req,5,1))
            self.assertEqual(s.status(host)["outputs"],{"A":5})
            self.assertIsNone(s.next(host))

    def test_reservation_persists_across_restart(self):
        s=Store(self.db);s.start("r",plan(resume=True));req=s.next("r")
        s=Store(self.db)
        self.assertEqual(s.status("r")["reserved_or_reported"],3)
        with self.assertRaisesRegex(Rejected,"unsettled"):s.next("r")
        s.submit("r",response(req,5,1))
        self.assertEqual(s.status("r")["reserved_or_reported"],1)

    def test_concurrent_dispatch(self):
        s=Store(self.db);s.start("r",plan(resume=True))
        def reserve():
            try:return Store(self.db).next("r")
            except Rejected:return None
        with ThreadPoolExecutor(max_workers=8) as e:
            results=list(e.map(lambda _:reserve(),range(8)))
        self.assertEqual(sum(r is not None for r in results),1)

    def test_invalid_usage(self):
        s=Store(self.db);s.start("r",plan(resume=True));req=s.next("r")
        for usage in (-1,4,True,1.2):
            with self.assertRaises(Rejected):s.submit("r",response(req,5,usage))
        self.assertEqual(s.status("r")["pending"],[req["request_id"]])

    def test_idempotent_submission(self):
        s=Store(self.db);s.start("r",plan(resume=True));req=s.next("r")
        answer=response(req,5,1)
        s.submit("r",answer);s.submit("r",answer)
        with self.assertRaises(Rejected):s.submit("r",response(req,6,1))

    def test_changed_plan(self):
        s=Store(self.db);p=plan(resume=True);s.start("r",p);p["budget"]+=1
        with self.assertRaises(Rejected):s.start("r",p)

    def test_artifact_integrity(self):
        s=Store(self.db);s.start("r",plan(resume=True));req=s.next("r")
        s.submit("r",response(req,5,1))
        with closing(sqlite3.connect(self.db)) as c, c:
            c.execute("UPDATE steps SET answer=replace(answer,'5','6')")
        with self.assertRaises(Rejected):s.status("r")

    def test_oversize_output(self):
        s=Store(self.db);s.start("r",plan());req=s.next("r")
        with self.assertRaises(Rejected):s.submit("r",response(req,"x"*140000,1))

    def test_fixture_failure_is_not_replayed(self):
        p=plan(resume=True);p["nodes"][0]["input"]={"invalid":1}
        with self.assertRaises(Rejected):run(p,db=self.db,run_id="r")
        with self.assertRaisesRegex(Rejected,"unsettled"):run(p,db=self.db,run_id="r")

    def test_request_id_mismatch(self):
        s=Store(self.db);s.start("r",plan());req=s.next("r")
        a=response(req,5,1);a["request_id"]="other"
        with self.assertRaises(Rejected):s.submit("r",a)

    def test_lite_durable_equivalence(self):
        p=plan()
        self.assertEqual(run(p)["outputs"],run(p,db=self.db,run_id="r",force_durable=True)["outputs"])


    def test_abandon_fail_closed(self):
        s=Store(self.db);s.start("r",plan(resume=True));req=s.next("r")
        s.abandon("r","operator cannot verify outcome")
        self.assertTrue(s.status("r")["abandoned"])
        self.assertEqual(s.status("r")["reserved_or_reported"],3)
        with self.assertRaises(Rejected):s.next("r")
        with self.assertRaises(Rejected):s.submit("r",response(req,5,1))

    def test_audit_omits_payload(self):
        import json
        p=plan(host="codex",resume=True);p["nodes"][0]["input"]={"private":"confidential-content"}
        s=Store(self.db);s.start("r",p);req=s.next("r",approved=True,approval_sha256=s.preview("r")["approval_sha256"])
        s.submit("r",response(req,"private-output",1))
        evidence=s.audit("r")
        self.assertEqual(evidence["steps"][0]["state"],"done")
        self.assertNotIn("confidential-content",json.dumps(evidence))
        self.assertNotIn("private-output",json.dumps(evidence))

    def test_restart_from_committed_prefix(self):
        s=Store(self.db);p=plan([node(),node("B",["A"])],resume=True)
        s.start("r",p);req=s.next("r");s.submit("r",response(req,5,1))
        s=Store(self.db);s.start("r",p);next_req=s.next("r")
        self.assertEqual(next_req["node"],"B")
        self.assertEqual(next_req["dependencies"],{"A":5})
        s.submit("r",response(next_req,10,1))
        self.assertEqual(s.status("r")["outputs"],{"A":5,"B":10})


    def test_process_exit_after_reservation(self):
        import subprocess
        import sys
        s=Store(self.db);s.start("r",plan(resume=True))
        code="import os,sys; from nexus_engine.store import Store; Store(sys.argv[1]).next('r'); os._exit(19)"
        proc=subprocess.run([sys.executable,"-c",code,str(self.db)],timeout=20,check=False)
        self.assertEqual(proc.returncode,19)
        s=Store(self.db)
        self.assertEqual(s.status("r")["reserved_or_reported"],3)
        with self.assertRaisesRegex(Rejected,"unsettled"):s.next("r")


    def test_approval_requires_matching_review(self):
        s=Store(self.db);s.start("r",plan(host="codex",resume=True))
        review=s.preview("r")
        self.assertEqual(s.status("r")["pending"],[])
        for token in (None,"0"*64):
            with self.assertRaises(Rejected):s.next("r",approved=True,approval_sha256=token)
        req=s.next("r",approved=True,approval_sha256=review["approval_sha256"])
        self.assertEqual({k:v for k,v in req.items() if k!="request_id"},review["payload"])

    def test_stale_approval_cannot_dispatch_next_node(self):
        s=Store(self.db);s.start("r",plan([node(),node("B",["A"])],host="codex"))
        old=s.preview("r")["approval_sha256"]
        req=s.next("r",approved=True,approval_sha256=old)
        s.submit("r",response(req,5,1))
        with self.assertRaises(Rejected):s.next("r",approved=True,approval_sha256=old)
        self.assertEqual(s.status("r")["pending"],[])

    def test_parallel_diamond(self):
        p=plan([node("D",["B","C"],[1]),node("B",["A"],[1]),node("C",["A"],[2]),node()])
        p["workers"]=3
        self.assertEqual(run(p,db=self.db,run_id="r")["outputs"],{"A":5,"B":6,"C":7,"D":14})

    def test_parallel_frontier_and_ambiguous_resume(self):
        p=plan([node("A"),node("B"),node("C",["A","B"])],resume=True)
        p["workers"]=2
        s=Store(self.db);s.start("r",p)
        batch=s.reserve_batch("r")
        self.assertEqual([r["node"] for r in batch],["A","B"])
        self.assertEqual(s.status("r")["reserved_or_reported"],6)
        s.submit("r",response(batch[0],5,1))
        with self.assertRaisesRegex(Rejected,"unsettled"):Store(self.db).reserve_batch("r")
        s.submit("r",response(batch[1],5,1))
        self.assertEqual([r["node"] for r in s.reserve_batch("r")],["C"])

    def test_parallel_rejects_external_host(self):
        p=plan(host="ollama");p["workers"]=2
        with self.assertRaises(Rejected):route(p)

    def test_parallel_racing_reservations(self):
        p=plan([node("A"),node("B"),node("C")],resume=True);p["workers"]=2
        s=Store(self.db);s.start("r",p)
        def reserve():
            try:return Store(self.db).reserve_batch("r")
            except Rejected:return []
        with ThreadPoolExecutor(max_workers=8) as ex:
            batches=list(ex.map(lambda _:reserve(),range(8)))
        self.assertEqual(sum(map(len,batches)),2)
        self.assertEqual(s.status("r")["reserved_or_reported"],6)


if __name__=="__main__":unittest.main()
