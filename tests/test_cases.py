import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from run_cases import run_all  # noqa: E402


class VerdictTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results = {r.case.name: r for r in run_all()}

    def _check(self, name):
        r = self.results[name]
        exp = r.case.expected
        self.assertEqual(r.baseline, exp["baseline"], f"{name}: baseline drifts={r.baseline_drifts}")
        self.assertEqual(r.pro, exp["pro"], f"{name}: findings={r.pro_findings}")
        self.assertEqual(r.baseline_waived, exp.get("baseline_waived"), name)

    def test_base(self):
        self._check("base")

    def test_m1_silent_shrinkage(self):
        self._check("M1-silent-shrinkage")
        self.assertTrue(any(f.startswith("shrinkage:") for f in self.results["M1-silent-shrinkage"].pro_findings))

    def test_m2a_inside_scope(self):
        self._check("M2a-divergence-inside-scope")

    def test_m2b_outside_scope(self):
        self._check("M2b-divergence-outside-scope")
        self.assertTrue(any("schema violation" in f or "differ inside the scope" in f for f in self.results["M2b-divergence-outside-scope"].pro_findings))

    def test_m3_unknown_surface(self):
        self._check("M3-unknown-surface")

    def test_b1_line_endings(self):
        self._check("B1-line-endings")

    def test_b2_formatting_only(self):
        self._check("B2-formatting-only")

    def test_b3_authorized_singleton(self):
        self._check("B3-authorized-singleton")


if __name__ == "__main__":
    unittest.main()
