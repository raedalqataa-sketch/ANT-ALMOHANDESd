from backend.design.massing import propose_massing, evaluate_functional_massing


def test_area_filter_rejects_insufficient_envelope():
    envelopes = propose_massing(30, 40, 4, 5, 16, 22)
    assessments = evaluate_functional_massing(envelopes, {"guest": 100, "family": 120, "service": 90})
    assert any(a["feasibility"] == "REJECT_CONCEPT" for a in assessments)
    assert any(a["feasibility"] == "PENDING_LAYOUT" for a in assessments)
    assert all(a["note_ar"] for a in assessments)


def test_invalid_program_does_not_silently_pass():
    import pytest
    envelopes = propose_massing(30, 40, 4, 5, 16, 22)
    with pytest.raises(ValueError):
        evaluate_functional_massing(envelopes, {"guest": -3})
    with pytest.raises(ValueError):
        evaluate_functional_massing(envelopes, {})


def test_courtyard_gap_is_reviewed():
    envelopes = propose_massing(30, 40, 4, 5, 16, 22)
    assessments = evaluate_functional_massing(envelopes, {"guest": 20, "family": 20}, minimum_court_width_m=20)
    u = next(a for a in assessments if a["family"] == "U_SHAPE")
    assert u["feasibility"] == "REJECT_CONCEPT"
