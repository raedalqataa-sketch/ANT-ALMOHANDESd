"""Architecture-first design rules: geometry/program before furnishings and PDFs."""
import ast
import math
import unittest
from pathlib import Path
from assl.architectural_composer import (
    architectural_length, limit_growth, shared_edge,
    facade_exposure, assess_layout, spatial_signature,
)


def room(id,kind="bedroom",x=0,y=0,w=3,d=4,requested=10,zone="family",**other):
    return {"id":id,"request_id":id,"kind":kind,"zone":zone,
            "x":x,"y":y,"width":w,"depth":d,
            "min_area":requested,"min_side":1.5,**other}


def layout(rooms,halls):
    return {"floors":[rooms],"halls_by_floor":[halls]}


class CompositionTests(unittest.TestCase):
    def test_adjoining_wall_has_length(self):
        a=room("a",w=3,d=4)
        b={"x":3,"y":1,"width":2,"depth":3}
        self.assertAlmostEqual(shared_edge(a,b),3)

    def test_corner_touch_is_not_door_adjacent(self):
        a=room("a",w=3,d=4)
        b={"x":3,"y":4,"width":2,"depth":3}
        self.assertEqual(shared_edge(a,b),0)

    def test_external_facade_when_not_blocked(self):
        a=room("bed")
        hall={"kind":"corridor","x":3,"y":0,"width":1.5,"depth":4}
        self.assertGreaterEqual(facade_exposure(a,[a,hall]),3)

    def test_inside_room_blocked_by_surroundings(self):
        a=room("internal",x=1,y=1,w=3,d=3,requested=6)
        blocks=[{"kind":"reserve","x":0,"y":1,"width":1,"depth":3},
                {"kind":"reserve","x":1,"y":0,"width":3,"depth":1},
                {"kind":"reserve","x":1,"y":4,"width":3,"depth":1},
                {"kind":"corridor","x":4,"y":1,"width":1.5,"depth":3}]
        self.assertAlmostEqual(facade_exposure(a,[a]+blocks),0)
        report=assess_layout(layout([a]+blocks[:3],blocks[3:]),.20)
        self.assertIn("NO_DIRECT_EXTERIOR_FACADE_POTENTIAL",
                      [x["reason"] for x in report["hard_issues"]])

    def test_room_no_corridor_contact_rejected(self):
        a=room("alone")
        result=assess_layout(layout([a],[]),.20)
        self.assertIn("NO_CORRIDOR_CONNECTION_POTENTIAL",
                      [x["reason"] for x in result["hard_issues"]])

    def test_good_room_passes_preliminary_geometry(self):
        a=room("bed",x=0,y=0,w=3,d=4,requested=10)
        hall={"kind":"corridor","x":3,"y":0,"width":1.5,"depth":4}
        report=assess_layout(layout([a],[hall]),.20)
        self.assertEqual(report["status"],"PRELIMINARY_GEOMETRY_ELIGIBLE")
        self.assertFalse(report["furniture_used"])
        self.assertFalse(report["windows_verified"])
        self.assertFalse(report["legal_compliance_certified"])

    def test_elongated_bedroom_rejected_early(self):
        a=room("bed",x=0,y=0,w=2,d=6,requested=9)
        hall={"kind":"corridor","x":2,"y":0,"width":1.5,"depth":6}
        report=assess_layout(layout([a],[hall]),.20)
        self.assertIn("ROOM_TOO_ELONGATED",
                      [x["reason"] for x in report["hard_issues"]])

    def test_requested_min_area_never_lowered(self):
        a=room("bed",w=3,d=4,requested=13)
        hall={"kind":"corridor","x":3,"y":0,"width":1.5,"depth":4}
        report=assess_layout(layout([a],[hall]),.20)
        self.assertIn("BELOW_CLIENT_MIN_AREA",
                      [x["reason"] for x in report["hard_issues"]])

    def test_guest_must_reach_guest_distributor_not_family_hall(self):
        a=room("council","majlis",w=4,d=4,requested=13,
               zone="guest",guest_vestibule="guest-dist")
        hall={"kind":"corridor","x":4,"y":0,"width":1.5,"depth":4,
              "guest_distributor":False}
        report=assess_layout(layout([a],[hall]),.20)
        self.assertIn("NO_CORRIDOR_CONNECTION_POTENTIAL",
                      [x["reason"] for x in report["hard_issues"]])

    def test_plan_length_balances_normal_bedroom(self):
        lane={"axis":"y","width":3.2,"depth":12}
        bed={"kind":"bedroom","request_id":"b","min_area":12,"min_side":2.8}
        value=architectural_length(bed,lane,.20)
        self.assertTrue(math.isfinite(value))
        self.assertGreaterEqual(value,12/(3.2-.2)+.2)

    def test_wide_wing_uses_normal_bedroom_width_instead_of_inflation(self):
        from assl.architectural_composer import architectural_profile
        lane={"axis":"y","width":8.2,"depth":12}
        bed={"kind":"bedroom","request_id":"b","min_area":12,"min_side":2.8}
        result=architectural_profile(bed,lane,.20)
        self.assertIsNotNone(result)
        self.assertLess(result["gross_cross"],5.0)
        self.assertGreaterEqual(result["net_cross"]*result["net_length"],12.0)
        self.assertLessEqual(result["net_cross"]*result["net_length"],16.8)

    def test_plan_rejects_narrow_long_room(self):
        lane={"axis":"y","width":2.9,"depth":16}
        bed={"kind":"bedroom","request_id":"b","min_area":30,"min_side":2.5}
        self.assertEqual(architectural_length(bed,lane,.20),math.inf)

    def test_wing_spare_capacity_not_inflated_into_rooms(self):
        from assl.architectural_composer import architectural_profile
        lane={"axis":"y","width":4.2,"depth":20}
        bed={"kind":"bedroom","request_id":"b","min_area":16,"min_side":2.8}
        profile=architectural_profile(bed,lane,.2)
        self.assertIsNotNone(profile)
        base=profile["gross_length"]
        growth=limit_growth(bed,lane,.2,base,4)
        self.assertGreaterEqual(growth,0)
        self.assertLessEqual(growth,16*.08/profile["net_cross"]+1e-6)

    def test_signatures_change_with_room_positions(self):
        a=layout([room("a",x=0),room("b",x=6)],[])
        b=layout([room("a",x=6),room("b",x=0)],[])
        self.assertNotEqual(spatial_signature(a),spatial_signature(b))

    def test_hall_area_is_identified_as_proxy(self):
        a=room("bed",w=3,d=4)
        hall={"kind":"corridor","x":3,"y":0,"width":1.5,"depth":4}
        report=assess_layout(layout([a],[hall]),.20)
        self.assertAlmostEqual(report["hall_rectangle_area_m2"],6)
        self.assertTrue(report["external_facade_only_potential"])

    def test_missing_floors_not_certified(self):
        report=assess_layout({"floors":[],"halls_by_floor":[]},.20)
        self.assertEqual(report["status"],"ARCHITECTURAL_REVIEW")

    def test_existing_generator_is_default_unaffected(self):
        code=(Path(__file__).resolve().parents[1]/
              "backend/design/general_engine.py").read_text(encoding="utf8")
        tree=ast.parse(code)
        fns={f.name:f for f in tree.body if isinstance(f,ast.FunctionDef)}
        for func in ("search","allocate"):
            fn=fns[func]
            kwargs=[a.arg for a in fn.args.kwonlyargs]
            self.assertIn("architecture_first",kwargs)
            self.assertIs(fn.args.kw_defaults[kwargs.index("architecture_first")].value,False)


if __name__=="__main__":
    unittest.main()
