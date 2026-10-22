"""Deterministic architectural V2 policy tests (no fabricated code approval)."""
from backend.design.constitution_v2 import (
    GATE_IDS, MANUS_CROSSWALK, WEIGHTS, assess_candidate, public_manifest, policy_bundle
)


def sample_model():
    names = (
        "GF-site", "GF-program", "GF-sizes", "GF-doors", "GF-walkability",
        "GF-openings", "GF-door-sweeps", "GF-fixtures", "GF-beds", "GF-windows"
    )
    return {
        "brief": {"plot_width": 20, "plot_depth": 25, "building_type": "villa"},
        "floors": [{"id": "GF", "rooms": []}],
        "checks": [{"check_id": name, "status": "PASS"} for name in names]
                  + [{"check_id": "guest-route", "status": "NOT_APPLICABLE"}],
        "parking": [],
    }


def gate(report, gate_id):
    return next(item for item in report["gates"] if item["id"] == gate_id)


def test_manifest_is_explicitly_partial_and_scoring_uncalibrated():
    report = assess_candidate(sample_model())
    assert len(GATE_IDS) == report["gate_count"] == 16
    assert len(MANUS_CROSSWALK) == 12
    assert len(policy_bundle()['prior_visual_extraction_143_rules']) == 143
    assert len(policy_bundle()['functional_relationships']) == 28
    assert public_manifest()['visual_rules_total'] == 143
    assert sum(WEIGHTS.values()) == 100
    assert report["score_100"] is None
    assert not report["executive_approval"]
    assert public_manifest()["status"] == "EXPERIMENTAL_OPT_IN"
    assert gate(report, "CODE_COMPLIANCE")["status"] == "REVIEW"
    assert gate(report, "EXPORT_INTEGRITY")["status"] == "REVIEW"


def test_verified_geometry_can_pass_without_pretending_code_certification():
    report = assess_candidate(sample_model())
    assert gate(report, "BUILDABLE_ENVELOPE")["status"] == "PASS"
    assert gate(report, "SPACE_PROGRAM")["status"] == "PASS"
    assert gate(report, "PRIVACY")["status"] == "NOT_APPLICABLE"
    assert gate(report, "STAIRS_AND_LIFTS")["status"] == "NOT_APPLICABLE"
    assert gate(report, "VEHICLE_PEDESTRIAN")["status"] == "NOT_APPLICABLE"
    assert report["release_decision"] == "DRAFT_REVIEW"


def test_missing_evidence_never_becomes_pass():
    model = sample_model()
    model["checks"] = []
    result = assess_candidate(model)
    assert gate(result, "BUILDABLE_ENVELOPE")["status"] == "REVIEW"
    assert gate(result, "FURNITURE_FIT")["status"] == "REVIEW"


def test_geometry_failure_blocks_candidate():
    model = sample_model()
    next(c for c in model["checks"] if c["check_id"] == "GF-site")["status"] = "FAIL"
    result = assess_candidate(model)
    assert gate(result, "BUILDABLE_ENVELOPE")["status"] == "FAIL"
    assert result["release_decision"] == "BLOCKED"
    assert "BUILDABLE_ENVELOPE" in result["hard_failures"]


def test_missing_natural_window_blocks_without_certifying_ventilation():
    model = sample_model()
    next(c for c in model["checks"] if c["check_id"] == "GF-windows")["status"] = "FAIL"
    result = assess_candidate(model)
    assert gate(result, "NATURAL_LIGHT_AIR")["status"] == "FAIL"
    assert result["release_decision"] == "BLOCKED"


def test_mep_maintenance_and_legal_approval_remain_review():
    model = sample_model()
    result = assess_candidate(model)
    for code in ("MEP_MAINTENANCE", "STRUCTURAL_FEASIBILITY", "CODE_COMPLIANCE"):
        assert gate(result, code)["status"] == "REVIEW"


def test_unverified_investment_not_approved_as_villa():
    model = sample_model()
    model["brief"]["building_type"] = "investment"
    result = assess_candidate(model)
    assert gate(result, "INVESTMENT_BUILDING")["status"] == "REVIEW"
    assert not result["executive_approval"]


def test_invalid_plot_dimensions_block():
    model = sample_model()
    model["brief"]["plot_width"] = 0
    report = assess_candidate(model)
    assert gate(report, "INPUT_GEOMETRY")["status"] == "FAIL"
    assert report["release_decision"] == "BLOCKED"


def test_generator_requires_opt_in():
    import inspect
    from backend.design.architect_planner import generate_automatic
    from backend.design.general_api import auto_design
    assert inspect.signature(generate_automatic).parameters["constitution_v2"].default is False
    assert inspect.signature(auto_design).parameters["constitution_v2"].default is False
