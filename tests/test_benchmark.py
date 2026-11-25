import unittest
from benchmarks.evaluate import evaluate


def record(mode):
    return dict(task="T1",**{"class":"simple"},repeat=1,host="codex",model="example",
                config_sha256="a"*64,initial_sha256="b"*64,prompt_sha256="c"*64,
                budget=100,mode=mode,passed=True,latency_ms=12,
                input_tokens=5,output_tokens=3,recovered=False)


class BenchmarkTests(unittest.TestCase):
    def test_pair(self):
        result=evaluate([record("direct"),record("nexus")])
        self.assertEqual(result["classes"]["simple"]["pairs"],1)
        self.assertFalse(result["all_minimum_samples_met"])

    def test_mismatch(self):
        a,b=record("direct"),record("nexus");b["initial_sha256"]="d"*64
        with self.assertRaises(ValueError):evaluate([a,b])

    def test_invalid_usage(self):
        a,b=record("direct"),record("nexus");b["output_tokens"]=101
        with self.assertRaises(ValueError):evaluate([a,b])

    def test_duplicate(self):
        with self.assertRaises(ValueError):evaluate([record("direct"),record("direct")])

    def test_minimum_sample(self):
        rows=[]
        for cls in ("simple","medium","complex"):
            for i in range(10):
                for j in range(3):
                    for mode in ("direct","nexus"):
                        r=record(mode);r.update(task=f"{cls}-{i}",repeat=j);r["class"]=cls;rows.append(r)
        self.assertTrue(evaluate(rows)["all_minimum_samples_met"])
