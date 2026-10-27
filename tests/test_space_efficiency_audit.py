"""Regression tests for the opt-in floor space-efficiency audit."""
import unittest
from backend.design.space_efficiency_audit import audit_floor


class TestSpaceEfficiencyAudit(unittest.TestCase):
    def test_no_double_counting_corridor(self):
        floor = {"id": "GF", "rooms": [
            {"id": "h1", "kind": "corridor", "x": 0, "y": 0, "width": 2, "depth": 2},
            {"id": "h2", "kind": "corridor", "x": 1, "y": 0, "width": 2, "depth": 2},
        ]}
        report = audit_floor(floor, {"x": 0, "y": 0, "width": 3, "depth": 2})
        self.assertEqual(report["corridor_union_m2"], 6)
        self.assertEqual(report["room_area_sum_m2"], 8)
        self.assertEqual(report["status"], "INVALID_GEOMETRY")

    def test_pocket_and_elongation_review(self):
        floor = {"id": "GF", "rooms": [
            {"id": "bed", "kind": "bedroom", "x": 0, "y": 0, "width": 2, "depth": 5},
        ]}
        report = audit_floor(floor, {"x": 0, "y": 0, "width": 4, "depth": 5})
        self.assertEqual(report["leftover_m2"], 10)
        self.assertEqual(report["status"], "REVIEW")
        self.assertEqual(report["elongated_room_reviews"][0]["room_id"], "bed")

    def test_invalid_dimensions(self):
        floor = {"id": "GF", "rooms": [
            {"id": "bad", "x": 0, "y": 0, "width": -2, "depth": 3},
        ]}
        report = audit_floor(floor, {"x": 0, "y": 0, "width": 4, "depth": 5})
        self.assertEqual(report["status"], "INVALID_GEOMETRY")

    def test_no_mutation(self):
        floor = {"id": "GF", "rooms": [{"id": "a", "kind": "living",
                 "x": 0, "y": 0, "width": 3, "depth": 3}]}
        original = repr(floor)
        audit_floor(floor, {"x": 0, "y": 0, "width": 3, "depth": 3})
        self.assertEqual(repr(floor), original)


if __name__ == "__main__":
    unittest.main()
