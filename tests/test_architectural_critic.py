import unittest
from backend.design.architectural_critic import critique, compare_revisions


def model(width):
    return {"space_audit_envelopes": {"GF": {"x": 0, "y": 0, "width": 5, "depth": 5}},
            "floors": [{"id": "GF", "rooms": [
                {"id": "bed", "kind": "bedroom", "x": 0, "y": 0, "width": width, "depth": 5}]}]}


class TestArchitecturalCritic(unittest.TestCase):
    def test_reports_review_without_mutation(self):
        m = model(2)
        before = repr(m)
        r = critique(m)
        self.assertEqual(r["repairs_applied"], 0)
        self.assertEqual(r["status"], "REVIEW")
        self.assertEqual(repr(m), before)

    def test_revision_deltas_are_not_approval(self):
        r = compare_revisions(model(2), model(5))
        self.assertEqual(r["status"], "MEASURED_NOT_APPROVED")
        self.assertLess(r["delta_leftover_review_m2"], 0)

    def test_missing_envelope_blocks(self):
        r = critique({"floors": [{"id": "GF", "rooms": []}]})
        self.assertTrue(r["blocked"])


if __name__ == "__main__":
    unittest.main()
