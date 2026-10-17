from backend.design.functional_zoning import propose_functional_zones, check_zoning_hypothesis


def test_functional_wings_differ_between_concepts():
    variants = [propose_functional_zones({"family": name}) for name in ("L_SHAPE", "U_SHAPE", "STEPPED")]
    placements = [tuple((a["zone"], a["conceptual_wing"]) for a in v["assignments"]) for v in variants]
    assert len(set(placements)) == 3
    assert all(check_zoning_hypothesis(v)["status"] == "PENDING_GEOMETRY" for v in variants)
    assert all(v["status"] == "ZONING_HYPOTHESIS_NOT_ROOM_LAYOUT" for v in variants)


def test_separate_guest_and_family_entrance_constraints():
    proposal = propose_functional_zones({"family": "L_SHAPE"})
    proposal["assignments"][0]["entrance_group"] = "family"
    assert check_zoning_hypothesis(proposal)["status"] == "FAIL"


def test_unknown_zones_are_rejected():
    import pytest
    with pytest.raises(ValueError):
        propose_functional_zones({"family": "U_SHAPE"}, ["guest", "unknown"])
