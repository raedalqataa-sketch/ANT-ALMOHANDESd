import unittest
from backend.design.space_efficiency_audit import audit_floor


class TestRealCellGeometry(unittest.TestCase):
    def test_corridor_cell_not_present_in_rooms(self):
        floor = {"id": "GF",
                 "rooms": [{"id": "bed", "kind": "bedroom",
                            "x": 0, "y": 0, "width": 3, "depth": 4}],
                 "cells": [{"id": "hall", "kind": "corridor",
                            "x": 3, "y": 0, "width": 1, "depth": 4}]}
        result = audit_floor(floor, {"x": 0, "y": 0, "width": 4, "depth": 4})
        self.assertEqual(result["corridor_union_m2"], 4)
        self.assertEqual(result["leftover_m2"], 0)
        self.assertEqual(result["corridor_geometry_source"], "rooms_and_cells")

    def test_overlap_cell_and_room_not_double_counted(self):
        floor = {"id": "GF",
                 "rooms": [{"id": "r", "kind": "living",
                            "x": 0, "y": 0, "width": 4, "depth": 4}],
                 "cells": [{"id": "c", "kind": "living",
                            "x": 0, "y": 0, "width": 4, "depth": 4}]}
        result = audit_floor(floor, {"x": 0, "y": 0, "width": 4, "depth": 4})
        self.assertEqual(result["room_union_m2"], 16)
        self.assertEqual(result["status"], "MEASURED")


if __name__ == "__main__":
    unittest.main()
