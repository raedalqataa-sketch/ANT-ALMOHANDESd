"""Architectural core and circulation diagnostics, without furniture."""
import copy
import unittest
from assl.concept_quality_v2 import (
    hall_shape,union_area,edge_contact,relation_penalties,
    enrich_composition_quality
)

def rect(x,y,w,d,**kw):
    return dict(x=x,y=y,width=w,depth=d,**kw)

class ConceptQualityTests(unittest.TestCase):
    def test_union_no_double_count(self):
        self.assertAlmostEqual(union_area([rect(0,0,2,5),rect(1,2,2,3)]),13)

    def test_touch_edge_but_not_corner(self):
        a=rect(0,0,3,3)
        self.assertEqual(edge_contact(a,rect(3,0,2,2)),2)
        self.assertEqual(edge_contact(a,rect(3,3,2,2)),0)

    def test_connected_hall_graph(self):
        halls=[rect(2,0,2,6),rect(2,6,5,2),rect(5,8,2,6)]
        data=hall_shape(halls)
        self.assertEqual(data["components"],1)
        self.assertEqual(data["pattern"],"CONNECTED_BENDS_OR_JUNCTIONS")

    def test_disconnected_halls_rejected(self):
        layout={"floors":[[]],"halls_by_floor":[[rect(0,0,1.5,4),
                                                rect(8,8,1.5,4)]]}
        base={"hard_issues":[],"architecture_score":100}
        quality=enrich_composition_quality(layout,.2,base)
        self.assertIn("DISCONNECTED_HALLWAY_SEGMENTS",
                      [x["reason"] for x in quality["hard_issues"]])

    def test_long_straight_hall_has_higher_penalty(self):
        short=hall_shape([rect(0,0,1.6,8)])
        long=hall_shape([rect(0,0,1.6,18)])
        self.assertEqual(short["long_run_excess_sq_m2"],0)
        self.assertGreater(long["long_run_excess_sq_m2"],60)

    def test_kitchen_dining_neighbors_better_than_detached(self):
        kitchen=rect(0,0,4,4,kind="kitchen",request_id="k",zone="family")
        near=rect(4,0,4,4,kind="dining",request_id="d",zone="family")
        far=rect(12,0,4,4,kind="dining",request_id="d",zone="family")
        near_cost,_=relation_penalties([kitchen,near])
        far_cost,_=relation_penalties([kitchen,far])
        self.assertLess(near_cost,far_cost)

    def test_aligned_stairs_preserved_across_floors(self):
        stair=rect(0,0,3,4,kind="stair")
        hall=rect(3,0,1.6,8)
        layout={"floors":[[copy.deepcopy(stair)],[copy.deepcopy(stair)]],
                "halls_by_floor":[[hall],[copy.deepcopy(hall)]]}
        q=enrich_composition_quality(layout,.2,{"hard_issues":[],"architecture_score":200})
        self.assertEqual(q["hard_issues"],[])
        self.assertEqual(q["stair_cores_reserved_by_floor"],[1,1])

    def test_displaced_stair_rejected(self):
        layout={"floors":[[rect(0,0,3,4,kind="stair")],
                          [rect(0,2,3,4,kind="stair")]],
                "halls_by_floor":[[rect(3,0,1.6,8)],[rect(3,0,1.6,8)]]}
        q=enrich_composition_quality(layout,.2,{"hard_issues":[],"architecture_score":200})
        self.assertIn("VERTICAL_STAIR_CORE_MISALIGNED",
                      [x["reason"] for x in q["hard_issues"]])

    def test_guest_distributor_directly_adjoins_associated_rooms(self):
        vestibule=rect(0,3,4,1.8,kind="corridor",guest_distributor=True,id="G")
        majlis=rect(0,0,4,3,kind="majlis",guest_vestibule="G")
        bath=rect(0,4.8,4,3,kind="bathroom",guest_vestibule="G")
        q=enrich_composition_quality({"floors":[[vestibule,majlis,bath]],
             "halls_by_floor":[[rect(4,0,1.5,8)]]},.2,
             {"hard_issues":[],"architecture_score":150})
        self.assertNotIn("GUEST_VESTIBULE_NOT_ADJACENT_TO_ASSOCIATED_ROOMS",
                         [x["reason"] for x in q["hard_issues"]])

    def test_guest_distributor_does_not_mask_missing_portal(self):
        vestibule=rect(0,3,4,1.8,kind="corridor",guest_distributor=True,id="G")
        majlis=rect(0,0,4,3,kind="majlis",guest_vestibule="G")
        bath=rect(0,9,4,3,kind="bathroom",guest_vestibule="G")
        q=enrich_composition_quality({"floors":[[vestibule,majlis,bath]],
             "halls_by_floor":[[rect(4,0,1.5,14)]]},.2,
             {"hard_issues":[],"architecture_score":150})
        self.assertIn("GUEST_VESTIBULE_NOT_ADJACENT_TO_ASSOCIATED_ROOMS",
                      [x["reason"] for x in q["hard_issues"]])

    def test_guest_independent_entrance_needs_contiguous_outer_edge(self):
        guest=rect(1,1,3,2,kind="corridor",guest_distributor=True,id="vestibule")
        closed=[rect(0,1,1,2),rect(4,1,1,2),
                rect(1,0,3,1),rect(1,3,3,1)]
        hall=rect(6,0,1.5,8)
        report=enrich_composition_quality(
            {"floors":[[guest]+closed],"halls_by_floor":[[hall]]},.2,
            {"hard_issues":[],"architecture_score":100})
        self.assertIn("NO_INDEPENDENT_GUEST_ENTRANCE_POTENTIAL",
                      [x["reason"] for x in report["hard_issues"]])
        self.assertFalse(report["entrance_facade_potential"][0]["doors_verified"])

    def test_family_entry_potential_remains_unresolved_without_door(self):
        hall=rect(1,1,1.5,3)
        closed=[rect(0,1,1,3),rect(2.5,1,1,3),
                rect(1,0,1.5,1),rect(1,4,1.5,1)]
        report=enrich_composition_quality(
            {"floors":[closed],"halls_by_floor":[[hall]]},.2,
            {"hard_issues":[],"architecture_score":100})
        self.assertIn("NO_FAMILY_EXTERNAL_ENTRANCE_POTENTIAL",
                      [x["reason"] for x in report["hard_issues"]])
        self.assertFalse(report["entrance_facade_potential"][0]["street_access_verified"])

    def test_architectural_scope_never_proves_walkability(self):
        layout={"floors":[[]],"halls_by_floor":[[rect(0,0,1.5,3)]]}
        q=enrich_composition_quality(layout,.2,{"hard_issues":[],"architecture_score":100})
        self.assertFalse(q["circulation_walk_paths_validated"])
        self.assertFalse(q["doors_generated"])

if __name__=="__main__":
    unittest.main()
