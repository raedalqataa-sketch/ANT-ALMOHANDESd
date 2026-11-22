import unittest
from backend.design.space_efficiency_ranking import assess_candidate, compare_candidates


def candidate(cid, width):
    return {"candidate_id": cid, "baseline_score": 1.0,
            "model": {"space_audit_envelopes": {"GF": {"x": 0, "y": 0,
                      "width": 6, "depth": 5}},
                      "floors": [{"id": "GF", "rooms": [
                          {"id": "a", "kind": "living", "x": 0, "y": 0,
                           "width": width, "depth": 5}]}]}}


class TestSpaceEfficiencyRanking(unittest.TestCase):
    def test_missing_envelope_pending(self):
        result = assess_candidate({"floors": [{"id": "GF", "rooms": []}]})
        self.assertEqual(result["status"], "PENDING")

    def test_ranking_does_not_modify_models(self):
        a, b = candidate("a", 5), candidate("b", 3)
        before = repr((a, b))
        result = compare_candidates([b, a])
        self.assertEqual(result["ranked"][0]["candidate_id"], "a")
        self.assertEqual(repr((a, b)), before)
        self.assertFalse(result["approved_for_export"])

    def test_invalid_geometry_excluded(self):
        item = candidate("invalid", 7)
        result = compare_candidates([item])
        self.assertFalse(result["ranked"][0]["space_audit"]["eligible_for_ranking"])


if __name__ == "__main__":
    unittest.main()
