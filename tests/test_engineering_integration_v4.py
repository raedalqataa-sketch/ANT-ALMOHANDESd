"""New engineering libraries must affect V4 validation/choice, not just imports."""
import copy

import pytest

from backend.design.independent_audit import inspect
from backend.design.engineering_selection import choose_distinct_subset
from backend.design.functional_program import checks


def candidate_floor():
    return {
        "id": "GF",
        "rooms": [
            {"id": "GF-ENTRY", "kind": "corridor", "x": 0, "y": 0,
             "width": 2, "depth": 4},
            {"id": "GF-LIVING", "kind": "living", "request_id": "living",
             "x": 2, "y": 0, "width": 4, "depth": 4},
            {"id": "GF-KITCHEN", "kind": "kitchen", "request_id": "kitchen",
             "x": 0, "y": 4, "width": 3, "depth": 3},
        ],
        "openings": [
            {"id": "entry", "kind": "door", "connects": ["GF-ENTRY", "EXTERIOR"]},
            {"id": "living", "kind": "door", "connects": ["GF-ENTRY", "GF-LIVING"]},
            {"id": "kitchen", "kind": "door", "connects": ["GF-ENTRY", "GF-KITCHEN"]},
        ],
    }


def example_model():
    return {"footprint": {"x": 0, "y": 0, "width": 10, "depth": 10},
            "floors": [candidate_floor()]}


def test_independent_geometry_and_door_graph_validate_actual_geometry():
    report = inspect(example_model())
    assert report["status"] == "PASS"
    assert not report["requires_circulation_review"]
    floor = report["floors"][0]
    assert floor["graph_nodes"] == 3
    assert floor["graph_edges"] == 2
    assert floor["graph_components"] == 1
    assert floor["requested_rooms_without_entry_graph_route"] == []


def test_independent_geometry_blocks_overlap_and_outside_mass():
    model = example_model()
    model["floors"][0]["rooms"][1]["x"] = 1.5
    model["floors"][0]["rooms"][2]["x"] = 9
    report = inspect(model)
    assert report["status"] == "FAIL"
    floor = report["floors"][0]
    assert floor["intersections"][0]["overlap_m2"] > 0
    assert floor["outside_envelope"][0]["outside_envelope_m2"] > 0


def test_networkx_graph_exposes_missing_door_without_invented_access():
    model = example_model()
    model["floors"][0]["openings"].pop()
    report = inspect(model)
    assert report["status"] == "PASS"
    assert report["requires_circulation_review"]
    assert report["floors"][0]["requested_rooms_without_entry_graph_route"] == ["GF-KITCHEN"]


def test_no_external_ground_entry_fails_graph_review_not_geometry():
    model = example_model()
    model["floors"][0]["openings"].pop(0)
    report = inspect(model)
    assert report["status"] == "PASS"
    assert report["requires_circulation_review"]


def test_cpsat_finds_three_instead_of_greedy_single_solution():
    # Best-ranked candidate 0 conflicts with all others. The next 3
    # are pairwise different. Cardinality must win over first-best greed.
    indices, details = choose_distinct_subset(4, [(0, 1), (0, 2), (0, 3)])
    assert indices == [1, 2, 3]
    assert details["optimality_proven"]
    assert details["selected_count"] == 3


def test_cpsat_never_selects_conflicting_or_invalid_index_pairs():
    indices, details = choose_distinct_subset(5, [(0, 1), (1, 2), (3, 4)])
    assert len(indices) == 3
    assert all(not (a in indices and b in indices)
               for a, b in ((0, 1), (1, 2), (3, 4)))
    with pytest.raises(ValueError):
        choose_distinct_subset(3, [(2, 1)])


def test_new_v4_checks_block_geom_but_not_unverified_graph():
    report = {
        "program": {"status": "PASS", "errors": []},
        "movement": {"unreachable": []},
        "furniture_issues": [],
        "independent_geometry": {
            "status": "FAIL", "requires_circulation_review": True, "floors": []
        },
    }
    rows = {row["check_id"]: row for row in checks(report)}
    assert rows["V4-geos-independent"]["status"] == "FAIL"
    assert rows["V4-networkx-topology"]["status"] == "PENDING"
