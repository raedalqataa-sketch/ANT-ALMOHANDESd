"""Municipal 2024 geometry checks: source-bound and never executive certification."""
from types import SimpleNamespace
from backend.design.saudi_2024_geometry import checks, well_minimum
from backend.design.general_models import RegulatoryGeometry


def evaluate(features=None, boundaries=None):
    geo = RegulatoryGeometry(**features).model_dump() if features is not None else None
    model = {
        "regulatory_geometry": geo,
        "metrics": {"floor_built_by_id": {"GF": 160.0, "FF": 150.0}},
    }
    brief = SimpleNamespace(
        apply_saudi_rules=True,
        boundary_widths=boundaries if boundaries is not None else
        {"south": 15.0, "west": 0.0, "east": 0.0, "north": 0.0},
    )
    return checks(model, brief)


def item(results, key):
    return next(x for x in results if x["check_id"] == "SA-2024-" + key)


def test_lightwell_minima_all_table_classes():
    assert well_minimum(1, False) == (.9, 1.8)
    assert well_minimum(1, True) == (1.5, 1.8)
    assert well_minimum(2, False) == (1.5, 1.8)
    assert well_minimum(2, True) == (1.8, 1.8)
    assert well_minimum(3, False) == (1.8, 2.4)
    assert well_minimum(3, True) == (2.1, 2.4)
    assert well_minimum(4, False) == (2.1, 3.0)
    assert well_minimum(4, True) == (2.4, 3.0)
    assert well_minimum(5, False) == (2.4, 3.6)
    assert well_minimum(14, True) == (5.4, 9.0)


def test_lightwell_geometry_fails_narrow_and_missing_service_remains_pending():
    well = {
        "id": "W1", "storeys_served": 2, "opposing_windows": True,
        "width_m": 1.7, "length_m": 1.8,
    }
    result = evaluate({"light_wells": [well]})
    assert item(result, "lightwell-dimensions")["status"] == "FAIL"
    assert item(result, "lightwell-service")["status"] == "PENDING"
    assert item(result, "lightwell-opening-overlay")["status"] == "PENDING"
    good = evaluate({"light_wells": [{**well, "width_m": 1.8,
                                     "open_to_sky": True, "cleaning_door": True,
                                     "drains_provided": True, "light_wall_finish": True}]})
    assert item(good, "lightwell-dimensions")["status"] == "PASS"
    assert item(good, "lightwell-service")["status"] == "PASS"
    assert item(good, "lightwell-opening-overlay")["status"] == "PENDING"


def test_roof_annex_area_limit_and_above_floor_footprint_pending():
    ann = {
        "area_m2": 106.0, "street_setbacks_m": {"south": 1.6},
        "parapet_height_m": .6, "neighbor_direct_windows": False,
        "staircase_continues_to_annex_roof": False,
    }
    bad = evaluate({"roof_annex": ann})
    assert item(bad, "annex-area")["status"] == "FAIL"  # 106/150 > .70
    good = evaluate({"roof_annex": {**ann, "area_m2": 105.0}})
    assert item(good, "annex-area")["status"] == "PASS"
    assert item(good, "annex-street-setback")["status"] == "PASS"
    assert item(good, "annex-other-conditions")["status"] == "PASS"
    assert item(good, "annex-footprint-overlay")["status"] == "PENDING"
    no_parking = evaluate({"roof_annex": {**ann, "area_m2": 90,
                              "independent_unit": True, "additional_parking_space": False}})
    assert item(no_parking, "annex-other-conditions")["status"] == "FAIL"


def test_facade_and_projections_fail_without_street_permission():
    features = {
        "projections": [
            {"id": "P1", "face": "south", "kind": "facade",
             "depth_m": 1.3, "within_setback": True, "crosses_property_line": False},
            {"id": "P2", "face": "west", "kind": "balcony",
             "depth_m": .3, "within_setback": True, "crosses_property_line": False},
        ],
        "facades": [{"face": "south", "faces_main_street": True,
                     "visible_ac_or_services": True}],
    }
    result = evaluate(features)
    assert item(result, "projection-P1")["status"] == "FAIL"
    assert item(result, "projection-P2")["status"] == "FAIL"
    assert item(result, "facade-main-street-south")["status"] == "FAIL"
    assert item(result, "facade-local-identity")["status"] == "PENDING"


def test_unreported_features_never_pass():
    result = evaluate()
    for key in ("lightwell-dimensions", "annex-area", "projection-regulation",
                "facade-main-street-services", "facade-local-identity"):
        assert item(result, key)["status"] == "PENDING"
    assert item(evaluate({"light_wells": [], "roof_annex_absent": True, "projections": []}),
                "annex-area")["status"] == "NOT_APPLICABLE"


def test_regulatory_models_reject_duplicate_faces_and_conflicting_annex():
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        RegulatoryGeometry(roof_annex_absent=True, roof_annex={"area_m2": 100})
    with pytest.raises(ValidationError):
        RegulatoryGeometry(facades=[{"face": "south"}, {"face": "south"}])


def test_road_projection_across_property_is_pending_not_automatic_rejection():
    approved_street_envelope = evaluate({
        "projections": [{"id": "P3", "face": "south", "kind": "balcony",
                         "depth_m": 1.1, "within_setback": True,
                         "crosses_property_line": True}],
    })
    assert item(approved_street_envelope, "projection-P3")["status"] == "PENDING"


def test_main_street_facade_rejects_services_even_when_concealed():
    forbidden = evaluate({"facades": [{"face": "south", "faces_main_street": True,
                                       "visible_ac_or_services": False,
                                       "ac_or_services_on_facade": True}]})
    assert item(forbidden, "facade-main-street-south")["status"] == "FAIL"
    clear = evaluate({"facades": [{"face": "south", "faces_main_street": True,
                                   "ac_or_services_on_facade": False}]})
    assert item(clear, "facade-main-street-south")["status"] == "PASS"
    unknown = evaluate({"facades": [{"face": "south", "faces_main_street": True,
                                     "visible_ac_or_services": False}]})
    assert item(unknown, "facade-main-street-south")["status"] == "PENDING"
