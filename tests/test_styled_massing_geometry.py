"""Compare exported mesh sections to the selected plan in metres."""
import json
from pathlib import Path

import pytest
from shapely import build_area
from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union

from assl.strategies.styled_massing import build_styles
from backend.design.plan_editing import refresh_and_validate


# Vertices are serialized to 5 decimal places. Allow 0.1 mm at mesh edges.
EDGE_TOLERANCE_M = 0.0001


def mesh_section(faces, elevation, color=None):
    edges = []
    for vertices, tint in faces:
        if color is not None and tint != color:
            continue
        bottom = min(v[2] for v in vertices)
        top = max(v[2] for v in vertices)
        if bottom < elevation < top:
            ends = [v[:2] for v in vertices if v[2] == bottom]
            assert len(ends) == 2
            edges.append(LineString(ends))
    return build_area(unary_union(edges))


def opening_rectangle(opening, half_depth):
    x, y = opening["center"]
    half_width = opening.get("wall_span_m", opening["width"]) / 2 if opening.get(
        "open_passage"
    ) else opening["width"] / 2
    dx, dy = (half_width, half_depth) if opening["axis"] == "x" else (half_depth, half_width)
    return box(x - dx, y - dy, x + dx, y + dy)


def assert_matches(actual, expected, context):
    assert not actual.is_empty, context
    assert actual.buffer(EDGE_TOLERANCE_M).covers(expected), context
    assert expected.buffer(EDGE_TOLERANCE_M).covers(actual), context


def test_ground_floor_mesh_sections_preserve_edited_plan():
    sample = Path(__file__).resolve().parents[1] / "frontend/composition/clustered-sample.json"
    baseline = json.loads(sample.read_text())["proposals"][0]
    result = refresh_and_validate(
        baseline, [{"type": "wall", "room_id": "men-wc-1", "edge": 0, "offset": 0.05}]
    )
    assert result["exportable"]
    plan = result["proposal"]
    assert_ground_floor_mesh_matches(plan, build_styles(plan))


def assert_ground_floor_mesh_matches(plan, model):
    thickness = plan["brief_snapshot"]["wall_thickness"]
    height = plan["brief_snapshot"]["floor_height"]
    polygons = [Polygon(r["polygon"]) for r in plan["rooms_by_floor"][0] + plan["halls_by_floor"][0]]
    footprint = unary_union(polygons).buffer(thickness / 2, join_style=2)
    walls = unary_union([
        p.buffer(thickness / 2, join_style=2).difference(p.buffer(-thickness / 2, join_style=2))
        for p in polygons
    ])
    openings = plan["opening_model_009"][0]
    doors = unary_union([
        opening_rectangle(d, thickness / 2 + 1e-6 if d.get("open_passage") else thickness)
        for d in openings["doors"]
    ])
    windows = unary_union([opening_rectangle(w, thickness) for w in openings["windows"]])

    assert model["units"] == "m"
    assert len(model["styles"]) == 4
    for style in model["styles"]:
        base = style["faces"][:style["base_faces"]]
        wall_color = next(tint for _, tint in base if tint not in {"#a09a8e", "#618a9b", "#aaa59a"})
        expected_levels = {
            wall_color: [0, .9, 2.15, height - .18],
            "#618a9b": [.9, 2.15],
            "#aaa59a": [height - .18, height],
        }
        for color, levels in expected_levels.items():
            actual_levels = sorted({vertex[2] for face, tint in base if tint == color for vertex in face})
            assert actual_levels == pytest.approx(levels, abs=EDGE_TOLERANCE_M), style["id"]
        expected_sections = (
            (-0.09, "#a09a8e", footprint, "slab"),
            (0.45, wall_color, walls.difference(doors), "door positions and widths"),
            (1.5, wall_color, walls.difference(doors.union(windows)), "window and door cuts"),
            (1.5, "#618a9b", walls.intersection(windows), "glazing positions and widths"),
            (2.2, wall_color, walls, "walls above openings"),
            (height - 0.09, "#aaa59a", footprint, "roof slab"),
        )
        for elevation, color, expected, name in expected_sections:
            assert_matches(mesh_section(base, elevation, color), expected, (style["id"], name))


def test_wider_plot_has_two_distinct_ground_floor_alternatives():
    from backend.design.general_api import MassingRequest, clustered_concepts, concept_massing
    from backend.design.general_models import VillaBrief

    reference = Path(__file__).resolve().parents[1] / "frontend/composition/reference-brief.json"
    data = json.loads(reference.read_text())
    next(room for room in data["rooms"] if room["id"] == "living")["min_area"] = 26
    brief = VillaBrief.model_validate({**data, "plot_width": 32, "plot_depth": 37})
    result = clustered_concepts(brief, max_results=2)
    assert result["requested_results"] == 2
    assert not result["failures"]
    front, side = result["proposals"]
    assert (front["id"], side["id"]) == ("front-ground-suite", "side-ground-suite")
    assert front["functional_differences"] != side["functional_differences"]
    assert all(p["brief_snapshot"] == brief.model_dump(mode="json") for p in (front, side))
    models = [concept_massing(MassingRequest(proposal=p)) for p in (front, side)]
    assert [len(m["styles"]) for m in models] == [4, 4]
    assert models[0]["revision"] != models[1]["revision"]
    for plan, model in zip((front, side), models, strict=True):
        assert_ground_floor_mesh_matches(plan, model)


def test_failed_alternative_does_not_fill_requested_count():
    from backend.design.general_api import clustered_concepts
    from backend.design.general_models import VillaBrief

    reference = Path(__file__).resolve().parents[1] / "frontend/composition/reference-brief.json"
    data = json.loads(reference.read_text())
    next(room for room in data["rooms"] if room["id"] == "elder")["min_area"] = 18
    brief = VillaBrief.model_validate({**data, "plot_width": 32, "plot_depth": 37})
    result = clustered_concepts(brief, max_results=2)
    assert result["requested_results"] == 2
    assert [p["id"] for p in result["proposals"]] == ["side-ground-suite"]
    assert result["failures"] == [{
        "scheme": "front-ground-suite", "reason": "INCOMPLETE_FIXTURE_PROGRAM:elder-bath-1",
    }]
