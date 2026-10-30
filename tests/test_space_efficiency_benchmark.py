import unittest
from backend.design.space_efficiency_benchmark import build_report


def item(cid):
    return {"candidate_id": cid, "baseline_score": 1,
            "model": {"space_audit_envelopes": {"GF": {"x": 0, "y": 0,
                      "width": 4, "depth": 4}},
                      "floors": [{"id": "GF", "rooms": [
                          {"id": "living", "kind": "living", "x": 0, "y": 0,
                           "width": 4, "depth": 4}]}]}}


class TestBenchmark(unittest.TestCase):
    def test_report_never_approves(self):
        r = build_report({"candidates": [item("A"), item("B")]})
        self.assertEqual(r["decision"], "REVIEW_REQUIRED")
        self.assertFalse(r["ranking"]["approved_for_export"])
        self.assertEqual(set(r["critiques"]), {"A", "B"})

    def test_duplicate_ids_rejected(self):
        with self.assertRaises(ValueError):
            build_report({"candidates": [item("A"), item("A")]})


if __name__ == "__main__":
    unittest.main()
