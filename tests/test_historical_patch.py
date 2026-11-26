import unittest
from benchmarks.historical_patch import proposed,patch_source,TARGETS


class HistoricalPatchTests(unittest.TestCase):
    def test_exact_target(self):
        source="if old != answer:\n    pass\n"
        result=patch_source(source,"completion","encode(left) != encode(right)")
        self.assertIn("encode(old) != encode(answer)",result)
        with self.assertRaises(ValueError):patch_source("pass","completion","left != right")

    def test_forbidden_code(self):
        for expr in ("__import__('os').system('echo no')","left.__class__ != right",
                     "encode(left, right)", "left[0] != right", "left != right or open(left)"):
            with self.assertRaises(ValueError):proposed(expr,"old","answer")
