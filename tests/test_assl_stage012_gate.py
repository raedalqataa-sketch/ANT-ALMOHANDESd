"""Regression for connected guest geometry and fail-closed 009 validation in stage 012."""
import copy
import json
from pathlib import Path

from shapely.geometry import box
from shapely.ops import unary_union
from assl import relationship_first_012 as m
from assl.stage012_009_gate import verify_stage012, _hall_m2

FIX = Path(__file__).parent / "fixtures"

def _fixture():
    before = json.loads((FIX / "assl_openings_009_valid.json").read_text())
    candidate = json.loads((FIX / "assl_milp_012_candidate.json").read_text())
    return before, candidate

def _recheck(candidate):
    rooms = candidate["rooms_by_floor"]
    stair = next(r for r in rooms[0] if r["kind"] == "stair")
    guests = [r for r in rooms[0] if r.get("zone") == "guest"]
    family = [[r for r in f if r.get("zone") != "guest" and r["kind"] != "stair"]
              for f in rooms]
    return m.audit(family, candidate["halls_by_floor"], guests, stair)

def test_saved_candidate_has_one_connected_building_footprint():
    _, candidate = _fixture()
    audit = _recheck(candidate)
    assert audit["passed_independent_geometry"], audit["issues"]
    assert "FLOOR_0_DISCONNECTED_BUILDING_MASS" not in audit["issues"]

def test_connected_entry_preserves_separate_guest_entrance_and_saves_area():
    baseline, candidate = _fixture()
    revised = copy.deepcopy(candidate)
    family_entry = next(r for r in revised["halls_by_floor"][0]
                        if r["id"] == "family-entry-spur")
    family_entry.update(x=7.5, width=1.75)
    audit = _recheck(revised)
    assert audit["passed_independent_geometry"], audit["issues"]
    assert len([r for r in revised["rooms_by_floor"][0]
                if r.get("guest_distributor")]) == 1
    assert revised["rooms_by_floor"][0][0] == revised["rooms_by_floor"][1][0]
    before_area, after_area = sum(_hall_m2(baseline)), sum(_hall_m2(revised))
    assert before_area == 41.75
    assert after_area == 33.625
    assert before_area - after_area > 8
    # This is geometric evidence only, NOT proof of 009 or legal acceptance.
    assert revised["claim_009_verified"] is False

def test_009_gate_is_fail_closed_on_unrepaired_recorded_candidate():
    from backend.design.general_models import VillaBrief
    cases = json.loads((FIX / "assl_architecture_cases.json").read_text())["cases"]
    brief = VillaBrief.model_validate(next(c["brief"] for c in cases if c["id"] == "sa-corner"))
    baseline, candidate = _fixture()
    # Corrupt the guest wing deliberately: it must be rejected before 009.
    for room in candidate["rooms_by_floor"][0]:
        if room.get("zone") == "guest":
            room["x"] -= .25
    evidence, inspected = verify_stage012(brief, candidate, baseline)
    assert evidence["status"] == "REJECT_AND_REPLAN_UNRESOLVED"
    assert evidence["009_status"] == "NOT_RUN"
    assert evidence["preliminary_status"] == "REJECTED"
    assert evidence["architecturally_approved"] is False
    assert inspected == candidate
