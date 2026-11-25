import sqlite3
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
            req=s.next(host,approved=True)
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
        with sqlite3.connect(self.db) as c:
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


if __name__=="__main__":unittest.main()
