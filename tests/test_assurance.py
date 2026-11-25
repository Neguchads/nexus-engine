import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from nexus_engine.contracts import Rejected,response
from nexus_engine.recovery import snapshot
from nexus_engine.store import Store
from nexus_engine.engine import run


def plan(host="fixture"):
    return {"host":host,"budget":10,"resume":True,"nodes":[
        {"id":"A","depends_on":[],"input":{"values":[2,3]},"max_tokens":5},
        {"id":"B","depends_on":["A"],"input":{"values":[4]},"max_tokens":5}]}


class Assurance(unittest.TestCase):
    def test_recover_completed_prefix_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/"state.db";copy=Path(tmp)/"backup.db";out=Path(tmp)/"out.db"
            s=Store(db);s.start("r",plan())
            a=s.next("r");s.submit("r",response(a,{"value":5},1))
            snapshot(db,copy)
            self.assertTrue(Store(copy).verify_all()["sealed"])
            result=snapshot(copy,out,promote=True)
            self.assertFalse(result["sealed"])
            restored=Store(out)
            self.assertEqual(restored.next("r")["node"],"B")
            self.assertEqual(Store(db).status("r")["completed"],1)

    def test_recovery_refuses_external_and_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for host in ("fixture","codex"):
                db=root/(host+".db");copy=root/(host+"-copy.db");out=root/(host+"-out.db")
                s=Store(db);s.start("r",plan(host))
                if host=="fixture":s.next("r")
                snapshot(db,copy)
                with self.assertRaises(Rejected):snapshot(copy,out,promote=True)
                self.assertFalse(out.exists())

    def test_recovery_requires_sealed_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);db=root/"db";Store(db)
            with self.assertRaises(Rejected):snapshot(db,root/"out",promote=True)

    def test_database_creation_private(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/"db";Store(db)
            if os.name=="posix":self.assertEqual(db.stat().st_mode&0o777,0o600)

    def test_multiprocess_reservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/"db";s=Store(db);s.start("r",plan())
            code="import sys; from nexus_engine.store import Store; from nexus_engine.contracts import Rejected; s=Store(sys.argv[1]); exec('try:\\n s.next(\\\"r\\\"); print(\\\"reserved\\\")\\nexcept Rejected:\\n print(\\\"blocked\\\")')"
            processes=[subprocess.Popen([sys.executable,"-c",code,str(db)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for _ in range(6)]
            try:
                results=[p.communicate(timeout=30) for p in processes]
                self.assertTrue(all(p.returncode==0 for p in processes),results)
                self.assertEqual(sum(out.strip()=="reserved" for out,_ in results),1)
                self.assertEqual(len(s.status("r")["pending"]),1)
            finally:
                for p in processes:
                    if p.poll() is None:p.kill();p.communicate()


if __name__=="__main__":unittest.main()
