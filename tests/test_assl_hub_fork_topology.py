"""Bounded independent hub-fork topology contract tests (no furniture)."""
import unittest
from backend.design.hub_geometry import compact_fork_topology
from assl.concept_quality_v2 import hall_shape, edge_contact, union_area

class HubForkGeometryTests(unittest.TestCase):
    def test_three_connected_short_hall_segments(self):
        halls,lanes=compact_fork_topology(16,22,1.7,.45,.4)
        self.assertEqual(len(halls),3)
        self.assertEqual(hall_shape(halls)['components'],1)
        self.assertEqual(hall_shape(halls)['pattern'],'CONNECTED_BENDS_OR_JUNCTIONS')
        self.assertEqual(len(lanes),4)
    def test_hall_segments_never_overlap_areas(self):
        halls,lanes=compact_fork_topology(16,22,1.7,.45,.4)
        area=sum(q['width']*q['depth'] for q in halls)
        self.assertAlmostEqual(union_area(halls),area,places=5)
    def test_lanes_and_halls_do_not_overlap(self):
        halls,lanes=compact_fork_topology(16,22,1.7,.45,.4)
        all_shapes=halls+lanes
        self.assertAlmostEqual(union_area(all_shapes),
           sum(q['width']*q['depth'] for q in all_shapes),places=5)
    def test_each_lane_contacts_some_hall(self):
        halls,lanes=compact_fork_topology(16,22,1.7,.45,.4)
        for lane in lanes:
            self.assertGreaterEqual(max(edge_contact(lane,h) for h in halls),1.5)
    def test_every_rectangle_respects_buildable_envelope(self):
        for W,D in ((16,22),(30,24),(15,19)):
            result=compact_fork_topology(W,D,1.7,.45,.4)
            self.assertIsNotNone(result)
            for r in result[0]+result[1]:
                self.assertGreater(r['width'],0)
                self.assertGreater(r['depth'],0)
                self.assertGreaterEqual(r['x'],-1e-5)
                self.assertGreaterEqual(r['y'],-1e-5)
                self.assertLessEqual(r['x']+r['width'],W+1e-5)
                self.assertLessEqual(r['y']+r['depth'],D+1e-5)
    def test_impossible_site_rejected(self):
        self.assertIsNone(compact_fork_topology(7,7,1.7,.45,.4))

if __name__ == '__main__':
    unittest.main()
