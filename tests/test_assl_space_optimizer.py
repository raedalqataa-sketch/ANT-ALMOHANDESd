"""Regression gates for opt-in ASSL spatial candidate evaluation."""
import copy
import unittest
from assl.space_optimizer import room_quality, score_layout, rank_existing_candidates

def room(kind="bedroom",w=4,d=4,requested=12):
    return {"request_id":"r1","kind":kind,"width":w,"depth":d,"min_area":requested}

class TestOptimizer(unittest.TestCase):
    def test_balanced_beats_long(self):
        self.assertLess(room_quality(room(w=4,d=4))["penalty"],
                        room_quality(room(w=2,d=8))["penalty"])
    def test_client_minimum_bigger_than_guideline_not_failure(self):
        self.assertEqual(room_quality(room(kind="living",w=7,d=7,requested=49))["excess_above_request_aware_target_m2"],0)
    def test_excess_above_request_penalized(self):
        self.assertGreater(room_quality(room(kind="living",w=6.4,d=8.4,requested=44.8))["penalty"],0)
    def test_nonprogram_corridor_not_room(self):
        self.assertEqual(room_quality({"kind":"corridor","width":2,"depth":12})["penalty"],0)
    def test_nan_unresolved(self):
        self.assertEqual(room_quality(room(w=float("nan")))["measurement_status"],"UNRESOLVED")
    def test_layout_unmodified(self):
        layout={"score":200,"floors":[[room(w=2,d=8)]],
                "halls_by_floor":[[{"width":2,"depth":10}]]}
        before=copy.deepcopy(layout)
        report=score_layout(layout,wall_thickness=0)
        self.assertEqual(before,layout)
        self.assertGreater(report["assl_rank_score"],200)
        self.assertFalse(report["legal_compliance_certified"])
    def test_balanced_candidate_wins_without_geometry_edit(self):
        def c(name,w,d,circulation):
            return {"model_revision_id":name,"release":{"drawing_export_allowed":True},
                    "metrics":{"floor_built_by_id":{"GF":100},"circulation_m2":circulation},
                    "checks":[],"floors":[{"rooms":[room(w=w,d=d)]}]}
        cases=[c("long",2,8,20),c("balanced",4,4,19)]
        before=copy.deepcopy(cases)
        self.assertEqual(rank_existing_candidates(cases)["recommended_revision_id"],"balanced")
        self.assertEqual(cases,before)
    def test_failed_baseline_blocks_automatic_replacement(self):
        a={"model_revision_id":"bad","release":{"drawing_export_allowed":True},
           "metrics":{"floor_built_by_id":{"GF":50},"circulation_m2":4},
           "checks":[{"check_id":"guest-route","status":"FAIL"}],"floors":[]}
        b={"model_revision_id":"good","release":{"drawing_export_allowed":True},
           "metrics":{"floor_built_by_id":{"GF":150},"circulation_m2":22},
           "checks":[],"floors":[]}
        self.assertIsNone(rank_existing_candidates([a,b])["recommended_revision_id"])
    def test_blocked_excluded(self):
        a={"model_revision_id":"x","release":{"drawing_export_allowed":False},
           "metrics":{"floor_built_by_id":{"GF":1},"circulation_m2":1},
           "checks":[],"floors":[]}
        self.assertIsNone(rank_existing_candidates([a])["recommended_revision_id"])
    def test_more_movement_cannot_win(self):
        def c(name,area,movement):
            return {"model_revision_id":name,"release":{"drawing_export_allowed":True},
                    "metrics":{"floor_built_by_id":{"GF":area},"circulation_m2":movement},
                    "checks":[],"floors":[]}
        self.assertEqual(rank_existing_candidates([c("base",150,20),c("less-area",125,24)])["recommended_revision_id"],"base")
    def test_guest_route_status_preserved(self):
        def c(name,status,area):
            return {"model_revision_id":name,"release":{"drawing_export_allowed":True},
                    "metrics":{"floor_built_by_id":{"GF":area},"circulation_m2":20},
                    "checks":[{"check_id":"guest-route","status":status}],"floors":[]}
        self.assertEqual(rank_existing_candidates([c("base","PASS",150),c("new","PENDING",125)])["recommended_revision_id"],"base")
    def test_client_program_must_match(self):
        def c(name,program,area):
            return {"model_revision_id":name,"brief":{"rooms":program},
                    "release":{"drawing_export_allowed":True},
                    "metrics":{"floor_built_by_id":{"GF":area},"circulation_m2":20},
                    "checks":[],"floors":[]}
        self.assertEqual(rank_existing_candidates([c("base",["a","b"],150),c("missing-room",["a"],100)])["recommended_revision_id"],"base")
    def test_minimum_room_area_not_violated(self):
        def c(name,area,w,d):
            return {"model_revision_id":name,"release":{"drawing_export_allowed":True},
                    "metrics":{"floor_built_by_id":{"GF":area},"circulation_m2":10},
                    "checks":[],"floors":[{"rooms":[room(w=w,d=d,requested=12)]}]}
        self.assertEqual(rank_existing_candidates([c("base",150,4,4),c("invalid",100,2,4)])["recommended_revision_id"],"base")
    def test_missing_metrics_never_recommended(self):
        a={"model_revision_id":"unknown","release":{"drawing_export_allowed":True},
           "checks":[],"floors":[]}
        self.assertIsNone(rank_existing_candidates([a])["recommended_revision_id"])

if __name__=="__main__":
    unittest.main()
