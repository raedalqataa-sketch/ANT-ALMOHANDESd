"""Regression checks for the orthogonal floor footprint boundary."""
from backend.design.general_geometry import union_polygons, signed_area


def test_adjacent_rectangles_have_single_closed_outline():
    cells = [
        dict(x=0, y=0, width=4, depth=3),
        dict(x=4, y=0, width=2, depth=3),
    ]
    polygons = union_polygons(cells)
    assert len(polygons) == 1
    assert abs(signed_area(polygons[0])) == 18


def test_l_shaped_mass_has_one_closed_outline():
    cells = [
        dict(x=0, y=0, width=6, depth=2),
        dict(x=0, y=2, width=2, depth=4),
    ]
    polygons = union_polygons(cells)
    assert len(polygons) == 1
    assert abs(signed_area(polygons[0])) == 20


def test_narrow_attached_strip_keeps_boundary_closed():
    cells = [
        dict(x=0, y=0, width=6, depth=4),
        dict(x=6, y=1, width=0.00001, depth=2),
    ]
    polygons = union_polygons(cells)
    assert len(polygons) == 1
    assert abs(abs(signed_area(polygons[0])) - 24.00002) < 1e-5
