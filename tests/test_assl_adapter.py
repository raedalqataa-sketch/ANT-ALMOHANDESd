"""ASSL contract and boundary tests, no full generator execution required."""
import unittest
from types import SimpleNamespace
from assl.core import resolve_rules, validate_metrics, score_room
from assl.experimental_adapter import inspect_candidate

class ASSLAdapterTests(unittest.TestCase):
    def test_adapter_read_only(self):
        brief = SimpleNamespace(country="YE")
        model = {"floors": [{"id": "GF", "rooms": [{"id": "bed1", "kind": "bedroom", "width": 3, "depth": 8}]}]}
        before = repr(model)
        report = inspect_candidate(brief, model)
        self.assertEqual(before, repr(model))
        self.assertEqual(report["design_warnings"], 1)
        self.assertFalse(report["legal_approval"])

    def test_no_rooms(self):
        report = inspect_candidate(SimpleNamespace(country="SA"), {"floors": []})
        self.assertEqual(report["design_rooms"], [])

    def test_boundary_minimum(self):
        self.assertEqual(score_room("bedroom", 3, 4)["status"], "DESIGN_ACCEPTABLE")

    def test_oversized(self):
        self.assertIn("above_advisory_max", score_room("bedroom", 5, 5)["reasons"])

    def test_zero_dimension(self):
        self.assertEqual(score_room("bedroom", 0, 4)["status"], "UNRESOLVED")

    def test_nan_dimension(self):
        self.assertEqual(score_room("bedroom", float("nan"), 4)["status"], "UNRESOLVED")

    def test_unknown_country_rejected(self):
        with self.assertRaises(ValueError):
            resolve_rules("XX")

    def test_missing_metric_is_unresolved(self):
        rule = resolve_rules("YE", context={"space_type": "habitable_room"})[0]
        self.assertEqual(validate_metrics([rule], {})[0]["status"], "UNRESOLVED")

    def test_legal_compliance_never_certified(self):
        report = inspect_candidate(SimpleNamespace(country="SA"), {"floors": []})
        self.assertTrue(all(not r["legal_compliance_certified"] for r in report["legal_checks"]))

if __name__ == "__main__":
    unittest.main()
