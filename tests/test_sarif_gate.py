import json
import tempfile
import unittest
from pathlib import Path
from scripts.sarif_gate import inspect


class SarifTests(unittest.TestCase):
    def test_missing_and_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with self.assertRaises(ValueError):inspect(root)
            p=root/"python.sarif"
            p.write_text(json.dumps({"version":"2.1.0","runs":[{"results":[]}]}),encoding="utf-8")
            self.assertEqual(inspect(root)["finding_count"],0)
            p.write_text(json.dumps({"version":"2.1.0","runs":[{"results":[{"ruleId":"py/example"}]}]}),encoding="utf-8")
            self.assertEqual(inspect(root)["finding_count"],1)
