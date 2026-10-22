"""V3 diagnostics regressions: derive repairs from measured geometry."""
from backend.design.functional_intelligence import repair_reasons


def test_automatic_repair_never_removes_a_required_room():
    model={"floors":[],"checks":[{"check_id":"GF-beds","status":"FAIL"}]}
    assert "furnishing" in repair_reasons(model)
    assert "family_movement" not in repair_reasons(model)


def test_guest_access_failure_requests_privacy_repair():
    model={"floors":[],"checks":[{"check_id":"guest-route","status":"FAIL"}]}
    assert "guest_circulation" in repair_reasons(model)


def test_unknown_check_remains_visible():
    model={"floors":[],"checks":[{"check_id":"custom-constraint","status":"FAIL"}]}
    assert "other_existing_validation" in repair_reasons(model)



def test_executive_readiness_remains_blocked_with_clean_geometry():
    from backend.design.executive_readiness import assess
    result=assess({"floors":[{"id":"GF"}],"checks":[{"check_id":"GF-program","status":"PASS"}]})
    assert result["geometry_review_passed"] is True
    assert result["authorization_granted"] is False
    assert result["status"]=="NOT_APPROVED"
    assert result["required_signoffs"]
    assert all(s["status"]=="NOT_VERIFIED" for s in result["required_signoffs"])


def test_executive_readiness_discloses_validation_failures():
    from backend.design.executive_readiness import assess
    model={"floors":[],"checks":[
        {"check_id":"GF-overlap","status":"FAIL"},
        {"check_id":"YE-LOCAL","status":"PENDING"}],
        "constitution_v2":{"gates":[{"id":"CODE_COMPLIANCE","status":"REVIEW"}]}}
    report=assess(model)
    assert report["geometry_review_passed"] is False
    assert report["failed_checks"]==["GF-overlap"]
    assert report["pending_checks"]==["YE-LOCAL"]
    assert "CODE_COMPLIANCE" in report["unresolved_constitution_gates"]


def test_supported_v2_relationships_are_traceable_without_fake_private_suites():
    from backend.design.functional_intelligence import RELATIONSHIPS, inspect
    mapping={item[3]:item[4] for item in RELATIONSHIPS}
    assert mapping["FOOD_SERVICE"]=="E007"
    assert mapping["FAMILY_COMMON"]=="E013"
    assert mapping["LAUNDRY_SERVICE"]=="E019"
    assert mapping["STAIR_FAMILY_ACCESS"]=="E014"
    assert mapping["MASTER_BATH_ACCESS"] is None
    evidence=inspect({"floors":[]})
    assert evidence["v2_relationships_not_fully_implemented"] is True
