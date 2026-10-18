"""Municipal 2024 supplement must not claim approvals it cannot measure."""
from types import SimpleNamespace
from backend.design.saudi_2024_extension import registry, checks


def sample(entry_width=1.0, corridor_width=1.2):
    return {
        "floors": [{"id": "GF",
                    "openings": [{"kind": "door", "main_entry": True, "width": entry_width}],
                    "rooms": [{"id": "GF-HALL", "kind": "corridor",
                               "width": corridor_width, "depth": 4.0}]}],
        "parking": [{"id": "P1"}],
        "stairs": [{"id": "S1"}],
    }


def item(items, suffix):
    return next(x for x in items if x["check_id"] == "SA-2024-" + suffix)


def test_source_distinguishes_2024_municipal_from_2018_referenced_code():
    data = registry()
    assert data["source"]["document_year"] == 2024
    assert data["source"]["referenced_sbc_edition"] == 2018
    assert data["source"]["document_pages"] == 48


def test_measured_dimensions_enforced():
    brief = SimpleNamespace(floors=2, apply_saudi_rules=True)
    result = checks(sample(), brief)
    for suffix in ("villa-storeys", "main-entrance", "corridors"):
        assert item(result, suffix)["status"] == "PASS"
        assert item(result, suffix)["source"]["pdf_page"] > 0
    bad = checks(sample(entry_width=.7, corridor_width=.75), brief)
    assert item(bad, "main-entrance")["status"] == "FAIL"
    assert item(bad, "corridors")["status"] == "FAIL"
    assert item(checks(sample(), SimpleNamespace(floors=3, apply_saudi_rules=True)),
                "villa-storeys")["status"] == "FAIL"


def test_unmodeled_regulations_never_claim_pass():
    result = checks(sample(), SimpleNamespace(floors=2, apply_saudi_rules=True))
    for suffix in ("total-height", "ground-floor-level", "roof-parapet",
                   "surface-drainage", "water-storage", "guards", "vehicle-entry-width"):
        assert item(result, suffix)["status"] == "PENDING"


def test_missing_entry_is_failure_and_missing_floor_is_pending():
    brief = SimpleNamespace(floors=1, apply_saudi_rules=True)
    model = sample()
    model["floors"][0]["openings"] = []
    assert item(checks(model, brief), "main-entrance")["status"] == "FAIL"
    assert item(checks({"floors": []}, brief), "main-entrance")["status"] == "PENDING"
    assert checks(sample(), SimpleNamespace(floors=2, apply_saudi_rules=False)) == []
