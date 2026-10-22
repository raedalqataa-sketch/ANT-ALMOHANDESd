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
