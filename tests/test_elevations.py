from shapely.geometry import Polygon
from shapely.ops import unary_union

from assl.strategies.elevations import elevation_surfaces, opening_references


def test_orthographic_projection_dissolves_triangles_and_hides_rear_faces():
    faces = [
        ([(0, 0, 0), (3, 0, 0), (3, 0, 2)], "#ffffff"),
        ([(0, 0, 0), (3, 0, 2), (0, 0, 2)], "#ffffff"),
        ([(1, 2, 0), (2, 2, 0), (2, 2, 2), (1, 2, 2)], "#555555"),
    ]
    front = elevation_surfaces(faces, "south")
    assert len(front) == 1 and front[0]["color"] == "#ffffff"
    assert Polygon(front[0]["rings"][0]).equals(Polygon([(0, 0), (3, 0), (3, 2), (0, 2)]))
    rear = elevation_surfaces(faces, "north")
    assert len(rear) == 3
    combined = unary_union([Polygon(s["rings"][0]) for s in rear])
    assert combined.bounds == (-3, 0, 0, 2)
    assert combined.area == 6
    assert sum(Polygon(s["rings"][0]).area for s in rear if s["color"] == "#555555") == 2


def test_opening_references_preserve_width_center_orientation_and_floor_datum():
    room = {"id": "room", "kind": "bedroom", "polygon": [(0, 0), (4, 0), (4, 4), (0, 4)]}
    door = {"axis": "x", "center": [2, 0], "width": 1.2}
    window = {"axis": "y", "center": [4, 3], "width": 1.4}
    plan = {
        "brief_snapshot": {"floor_height": 3.2},
        "rooms_by_floor": [[room], [room]], "halls_by_floor": [[], []],
        "opening_model_009": [{"doors": [door], "windows": []}, {"doors": [], "windows": [window]}],
    }
    refs = opening_references(plan)
    assert refs["south"] == [
        {"kind":"doors", "floor":0, "center_m":2, "width_m":1.2, "bottom_m":0, "top_m":2.15},
    ]
    opening, = refs["east"]
    assert opening["floor"] == 1 and opening["center_m"] == 3
    assert opening["width_m"] == 1.4
    assert abs(opening["bottom_m"] - 4.10) < 1e-9 and abs(opening["top_m"] - 5.35) < 1e-9
    assert refs["west"] == refs["north"] == []


def test_sloping_face_hides_only_the_part_in_front():
    back = ([(0, 0, 0), (4, 0, 0), (4, 0, 2), (0, 0, 2)], "#dddddd")
    crossing = ([(0, 2, 0), (4, -2, 0), (4, -2, 2), (0, 2, 2)], "#555555")
    surfaces = elevation_surfaces([back, crossing], "south")
    assert len(surfaces) == 2
    for surface in surfaces:
        left, _, right, _ = Polygon(surface["rings"][0]).bounds
        if surface["color"] == "#dddddd":
            assert left == 0 and abs(right-2) < .00002
        else:
            assert abs(left-2) < .00002 and right == 4


def test_massing_checks_both_facade_fingerprints(monkeypatch):
    import pytest
    from fastapi import HTTPException

    from assl.strategies.styled_massing import geometry_fingerprint, mesh_fingerprint
    from backend.design import general_api

    plan = {
        "id":"plan", "rooms_by_floor":[], "halls_by_floor":[],
        "opening_model_009":[], "brief_snapshot":{},
    }
    style = {"id":"modern", "faces":[[[(0,0,0),(1,0,0),(0,0,1)],"#111111"]]}
    choice = {
        "style":"modern", "proposal_id":"plan", "revision":geometry_fingerprint(plan),
        "mesh_revision":mesh_fingerprint(style),
    }

    def build(p, progress, *, style_ids):
        assert style_ids == ("modern",)
        return {"styles":[dict(style)]}

    monkeypatch.setattr(general_api, "_plan_for_request", lambda request, progress: (plan, {}))
    monkeypatch.setattr(general_api, "_build_massing", build)
    request = general_api.MassingRequest(proposal=plan, facade_choice=choice)
    assert general_api.concept_massing(request)["styles"][0]["mesh_revision"] == choice["mesh_revision"]

    for field, error in (("revision","FACADE_PLAN_MISMATCH"), ("mesh_revision","FACADE_MESH_MISMATCH")):
        request = general_api.MassingRequest(proposal=plan, facade_choice={**choice, field:"0"*64})
        with pytest.raises(HTTPException, match=error) as exc:
            general_api.concept_massing(request)
        assert exc.value.status_code == 409
