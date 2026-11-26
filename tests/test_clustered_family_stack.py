import json
import os
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

from assl.openings_009 import inward
from assl.strategies.geometry import net_shape
from assl.strategies.styled_massing import geometry_fingerprint
from backend.design.general_api import MassingRequest, concept_massing
from backend.main import app


REFERENCE = Path(__file__).resolve().parents[1] / "frontend/composition/reference-brief.json"
TWO_GROUPS = [[1, 1, 0], [0, 1, 1]]
THREE_GROUPS = [[1, 1, 1], [2, 1, 0]]
CASES = (
    ("2-bedrooms", None, {"children": 2, "child_area_m2": 11.0, "child_min_side_m": 2.6}, TWO_GROUPS),
    ("3-bedrooms", None, {"children": 3, "child_area_m2": 11.5, "child_min_side_m": 2.7}, THREE_GROUPS),
    ("narrow-28x38", (28, 38, {"west": 2.5, "east": 2.75, "north": 3.5}, {"women": 19, "women-wc": 6}),
     {"children": 2, "child_area_m2": 11.0, "child_min_side_m": 2.6}, TWO_GROUPS),
    ("wide-36x40", (36, 40, {"west": 4.5, "east": 3.75, "north": 4, "south": 3.5}, {}),
     {"children": 3, "child_area_m2": 11.6, "child_min_side_m": 2.7}, THREE_GROUPS),
)


def generate(site, program):
    brief = json.loads(REFERENCE.read_text())
    if site:
        width, depth, setbacks, room_areas = site
        brief.update(plot_width=width, plot_depth=depth)
        brief["setbacks"].update(setbacks)
        for room in brief["rooms"]:
            if room["id"] in room_areas:
                room["min_area"] = room_areas[room["id"]]
    with TestClient(app) as client:
        return client.post(
            "/api/v3/concepts/clustered/stream",
            params={"first_floor": "true", "max_results": 2, **program},
            json=brief,
        )


@pytest.fixture(scope="module", params=CASES, ids=[case[0] for case in CASES])
def case(request):
    return request.param


@pytest.fixture(scope="module")
def proposals(case):
    _, site, program, groups = case
    result = generate(site, program)
    assert result.status_code == 200
    response = json.loads(result.text.splitlines()[-1])["result"]
    assert response["requested_results"] == 2
    assert not response["failures"]
    plans = response["proposals"]
    assert [p["upper_wing_group"] for p in plans] == groups
    assert all(p["upper_program"] == program for p in plans)
    return plans


def test_two_functional_stacks_share_a_canonical_plan_and_massing_geometry(proposals, case, monkeypatch):
    assert proposals[0]["rooms_by_floor"][0] == proposals[1]["rooms_by_floor"][0]
    assert proposals[0]["rooms_by_floor"][1] != proposals[1]["rooms_by_floor"][1]
    assert len({geometry_fingerprint(p) for p in proposals}) == 2

    def reject_regeneration(*args, **kwargs):
        pytest.fail("Massing must inspect the selected model without generating a new plan")

    monkeypatch.setattr("assl.strategies.clustered_multilevel.build_family_stack", reject_regeneration)
    models = []
    verification = []
    for proposal in proposals:
        model = concept_massing(MassingRequest(proposal=proposal))
        assert model["floors"] == 2 and len(model["styles"]) == 4
        assert model["revision"] == geometry_fingerprint(proposal)
        assert model["proposal_id"] == proposal["id"]
        assert "first_floor" not in proposal
        program = proposal["upper_program"]
        brief = proposal["brief_snapshot"]
        thickness = brief["wall_thickness"]
        setbacks = brief["setbacks"]
        envelope = box(
            0, 0, brief["plot_width"] - setbacks["west"] - setbacks["east"] - thickness,
            brief["plot_depth"] - setbacks["south"] - setbacks["north"] - thickness,
        ).buffer(1e-6)
        for rooms, halls in zip(proposal["rooms_by_floor"], proposal["halls_by_floor"], strict=True):
            assert all(envelope.covers(Polygon(room["polygon"])) for room in rooms + halls)
        rooms = [r for r in proposal["rooms_by_floor"][1] if r["kind"] == "bedroom"]
        assert len(rooms) == program["children"]
        measures = []
        for room in rooms:
            clear = net_shape(room, thickness)
            west, south, east, north = clear.bounds
            shortest = min(east-west, north-south)
            assert clear.area >= program["child_area_m2"] - 1e-6
            assert shortest >= program["child_min_side_m"] - 1e-6
            measures.append({"room_id": room["id"], "area_m2": clear.area, "shortest_side_m": shortest})
        verification.append({"proposal_id": proposal["id"], "revision": model["revision"], "bedrooms": measures})
        models.append(model)
        [slab_opening] = proposal["slab_openings_by_floor"][1]
        stair = next(room for room in proposal["rooms_by_floor"][1] if room["id"] == "stair-core")
        [door] = [d for d in proposal["opening_model_009"][1]["doors"] if "stair-core" in d["connects"]]
        landing = Point(inward(door, stair, .65)).buffer(.30)
        floor_height = proposal["brief_snapshot"]["floor_height"]
        for style in model["styles"]:
            slab = unary_union([
                Polygon([v[:2] for v in face]) for face, tint in style["faces"][:style["base_faces"]]
                if tint == "#a09a8e" and all(abs(v[2] - floor_height) < 1e-6 for v in face)
            ])
            assert slab.buffer(0.0001).covers(landing)
            assert slab.intersection(Polygon(slab_opening).buffer(-0.0001)).area < 1e-6

    if evidence := os.getenv("ANT_FAMILY_EVIDENCE_DIR"):
        folder = Path(evidence) / case[0]
        folder.mkdir(parents=True, exist_ok=True)
        for filename, data in (
            ("floor-plans.json", proposals), ("massing.json", models),
            ("verification.json", {"commit": os.getenv("GITHUB_SHA"), "program": program, "alternatives": verification}),
        ):
            (folder / filename).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def test_selected_stack_checks_and_legacy_plan(proposals):
    plan = proposals[1]
    legacy = deepcopy(plan)
    upper = legacy["rooms_by_floor"].pop()
    legacy["halls_by_floor"].pop()
    openings = legacy["opening_model_009"].pop()
    legacy.pop("slab_openings_by_floor")
    legacy["first_floor"] = {"rooms": upper, **openings}
    assert concept_massing(MassingRequest(proposal=legacy))["revision"] == geometry_fingerprint(plan)
    if plan["upper_program"] == CASES[1][2]:
        legacy.pop("upper_program")
        old_plan = {key: value for key, value in plan.items() if key != "upper_program"}
        assert concept_massing(MassingRequest(proposal=legacy))["revision"] == geometry_fingerprint(old_plan)

    invalid = deepcopy(plan)
    invalid["upper_program"]["child_area_m2"] = 70
    with pytest.raises(HTTPException, match="MASSING_UPPER_BEDROOM_DIMENSIONS"):
        concept_massing(MassingRequest(proposal=invalid))

    invalid = deepcopy(plan)
    invalid["upper_program"]["children"] = 5 - plan["upper_program"]["children"]
    with pytest.raises(HTTPException, match="MASSING_UPPER_PROGRAM_MISMATCH"):
        concept_massing(MassingRequest(proposal=invalid))

    invalid = deepcopy(plan)
    invalid["rooms_by_floor"][1][0]["polygon"][0][0] += .2
    with pytest.raises(HTTPException, match="MASSING_STAIR_LEVELS_MISALIGNED"):
        concept_massing(MassingRequest(proposal=invalid))
    invalid = deepcopy(plan)
    invalid["opening_model_009"][1]["doors"][0]["center"][0] += .1
    with pytest.raises(HTTPException, match="MASSING_UPPER_OPENINGS_MISMATCH"):
        concept_massing(MassingRequest(proposal=invalid))
    invalid = deepcopy(plan)
    invalid["slab_openings_by_floor"][1] = []
    with pytest.raises(HTTPException, match="MASSING_SLAB_OPENING_MISMATCH"):
        concept_massing(MassingRequest(proposal=invalid))


def test_restricted_site_reports_envelope_shortfall():
    site = (17, 24, dict.fromkeys(("west", "east", "north", "south"), 4), {})
    result = generate(site, CASES[1][2])
    assert result.status_code == 200
    response = json.loads(result.text.splitlines()[-1])["result"]
    assert response["status"] == "REJECT_AND_REPLAN"
    assert response["proposals"] == []
    assert len(response["failures"]) == response["requested_results"] == 2
    for failure in response["failures"]:
        assert "CENTRAL_EXCEEDS_ENVELOPE" in failure["reason"]
        assert "available 8.80 x 15.80 m" in failure["reason"]
    if evidence := os.getenv("ANT_FAMILY_EVIDENCE_DIR"):
        output = Path(evidence)
        output.mkdir(parents=True, exist_ok=True)
        (output / "restricted-17x24.json").write_text(json.dumps(response, indent=2), encoding="utf-8")
