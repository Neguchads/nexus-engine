import tempfile
import unittest
from pathlib import Path
from nexus_engine.contracts import Rejected, decode, response
from nexus_engine.cli import read
from nexus_engine.store import Store


class JsonSecurityTests(unittest.TestCase):
    def test_ambiguous_json(self):
        for raw in ('{"a":1,"a":2}', '{"a":{"x":1,"x":2}}', '{"a":NaN}', '{"a":Infinity}', '{"a":-Infinity}', '{"a":1e400}', '{"a":-1e400}'):
            with self.assertRaises(Rejected):decode(raw)

    def test_cli_rejects_duplicate_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"plan.json";p.write_text('{"host":"fixture","host":"codex"}',encoding="utf-8")
            with self.assertRaises(Rejected):read(p)

    def test_boolean_integer_conflicting_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            s=Store(Path(tmp)/"db")
            p={"host":"fixture","budget":2,"resume":True,"nodes":[{"id":"A","depends_on":[],"input":{"values":[1]},"max_tokens":2}]}
            s.start("r",p);req=s.next("r");s.submit("r",response(req,True,1))
            with self.assertRaises(Rejected):s.submit("r",response(req,1,1))

    def test_valid_json(self):
        self.assertEqual(decode(b'{"ok":true,"count":1}'),{"ok":True,"count":1})
