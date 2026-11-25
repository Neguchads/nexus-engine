import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from benchmarks.live_ollama import cases, measure, summarize
from nexus_engine.contracts import Rejected, response
from nexus_engine.store import Store


class LiveBenchmarkTests(unittest.TestCase):
    def test_dataset_and_profiles(self):
        self.assertEqual(len(cases("pilot")),6)
        self.assertEqual(len(cases("full")),90)
        self.assertEqual(len({x["task"] for x in cases("full")}),30)

    def test_both_arms_and_projection(self):
        case=cases("pilot")[0]
        seen=[]
        def mock(req):
            seen.append(req["dependencies"])
            return response(req,case["expected"],20),{"input_tokens":15,"output_tokens":5}
        with tempfile.TemporaryDirectory() as tmp, patch("benchmarks.live_ollama.execute_with_metrics",side_effect=mock):
            direct=measure(case,"direct",Path(tmp)/"a.db")
            nexus=measure(case,"nexus",Path(tmp)/"b.db")
            self.assertTrue(direct["passed"])
            self.assertTrue(nexus["passed"])
            self.assertIn("unused_notes",seen[0]["source"])
            self.assertNotIn("unused_notes",seen[1]["source"])
            self.assertFalse(summarize([direct,nexus],"pilot","mock")["experimental_gate"])

    def test_failure_not_fabricated(self):
        case=cases("pilot")[0]
        with tempfile.TemporaryDirectory() as tmp, patch("benchmarks.live_ollama.execute_with_metrics",side_effect=Rejected("transport failed")):
            r=measure(case,"nexus",Path(tmp)/"a.db")
            self.assertFalse(r["passed"]);self.assertIsNone(r["metrics"])
            self.assertTrue(Store(Path(tmp)/"a.db").status("benchmark")["pending"])

    def test_schema_version_rejects_future_and_unrelated(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/"db.sqlite"
            Store(db)
            with closing(sqlite3.connect(db)) as c,c:
                self.assertEqual(c.execute("PRAGMA user_version").fetchone()[0],1)
                c.execute("PRAGMA user_version=2")
            with self.assertRaises(Rejected):Store(db)
            other=Path(tmp)/"other.sqlite"
            with closing(sqlite3.connect(other)) as c,c:c.execute("CREATE TABLE unrelated(a)")
            with self.assertRaises(Rejected):Store(other)

    def test_legacy_schema_migration(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/"db.sqlite"
            Store(db)
            with closing(sqlite3.connect(db)) as c,c:
                c.execute("PRAGMA user_version=0");c.execute("PRAGMA application_id=0")
            self.assertEqual(Store(db).verify_all()["runs"],0)


if __name__=="__main__":unittest.main()
