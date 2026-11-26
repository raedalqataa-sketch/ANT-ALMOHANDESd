import json
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi import HTTPException
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

from assl.openings_009 import inward
from assl.strategies.styled_massing import geometry_fingerprint
from backend.design.general_api import MassingRequest, clustered_concepts, concept_massing
from backend.design.general_models import VillaBrief


@pytest.fixture(scope="module")
def proposals():
    reference = Path(__file__).resolve().parents[1] / "frontend/composition/reference-brief.json"
    brief = VillaBrief.model_validate_json(reference.read_bytes())
    response = clustered_concepts(brief, first_floor=True, max_results=2)
    assert response["requested_results"] == 2
    assert not response["failures"]
    return json.loads(json.dumps(response["proposals"]))


def test_two_functional_stacks_share_a_canonical_plan_and_massing_geometry(proposals, monkeypatch):
    assert [p["upper_wing_group"] for p in proposals] == [[1, 1, 1], [2, 1, 0]]
    assert proposals[0]["rooms_by_floor"][0] == proposals[1]["rooms_by_floor"][0]
    assert proposals[0]["rooms_by_floor"][1] != proposals[1]["rooms_by_floor"][1]
    assert len({geometry_fingerprint(p) for p in proposals}) == 2

    def reject_regeneration(*args, **kwargs):
        pytest.fail("Massing must inspect the selected model without generating a new plan")

    monkeypatch.setattr("assl.strategies.clustered_multilevel.build_family_stack", reject_regeneration)
    for proposal in proposals:
        model = concept_massing(MassingRequest(proposal=proposal))
        assert model["floors"] == 2 and len(model["styles"]) == 4
        assert model["revision"] == geometry_fingerprint(proposal)
        assert model["proposal_id"] == proposal["id"]
        assert "first_floor" not in proposal
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


def test_selected_stack_checks_and_legacy_plan(proposals):
    plan = proposals[1]
    legacy = deepcopy(plan)
    upper = legacy["rooms_by_floor"].pop()
    legacy["halls_by_floor"].pop()
    openings = legacy["opening_model_009"].pop()
    legacy.pop("slab_openings_by_floor")
    legacy["first_floor"] = {"rooms": upper, **openings}
    assert concept_massing(MassingRequest(proposal=legacy))["revision"] == geometry_fingerprint(plan)

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
