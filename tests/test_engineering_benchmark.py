import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from benchmarks.repair_cases import cases,verify
from benchmarks.engineering import measure,MODES,summarize
from nexus_engine.contracts import response


class RepairTests(unittest.TestCase):
    def test_unique_correct_candidate(self):
        self.assertEqual(len(cases()),9)
        for case in cases():
            self.assertEqual(sum(verify(case,{"candidate":k}) for k in case["options"]),1,case["task"])
            self.assertFalse(verify(case,{"candidate":"__import__('os')"}))

    def test_three_arms_and_identical_projected_payload(self):
        case=cases()[0]
        good=next(k for k in case["options"] if verify(case,{"candidate":k}))
        def fake(req):
            return response(req,{"candidate":good},11),{"input_tokens":8,"output_tokens":3}
        with tempfile.TemporaryDirectory() as tmp,patch("benchmarks.engineering.execute_with_metrics",side_effect=fake):
            rows=[measure(case,m,Path(tmp)/"run.db") for m in MODES]
        self.assertTrue(all(r["passed"] for r in rows))
        report=summarize(rows)
        self.assertTrue(report["matched_projected_request_bodies"])
        self.assertFalse(report["experimental_gate"])
