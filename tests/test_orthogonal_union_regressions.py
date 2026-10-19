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


def test_rounding_mismatch_does_not_drop_edges():
    # Raw endpoints differ from the canonical edge by more than the former
    # sampling epsilon. This used to leave an open boundary during materialize.
    cells = [dict(x=.12345649, y=.23456749, width=4.33333333, depth=3.11111111),
             dict(x=4.45678982, y=.23456749, width=1.23456789, depth=3.11111111)]
    result = union_polygons(cells, .1)
    assert len(result) == 1
    assert len(result[0]) == 4
    assert signed_area(result[0]) > 0
    assert union_polygons(list(reversed(cells)), .1) == result


def test_hole_keeps_negative_orientation_and_net_area():
    cells = [dict(x=0,y=0,width=5,depth=1), dict(x=0,y=4,width=5,depth=1),
             dict(x=0,y=1,width=1,depth=3), dict(x=4,y=1,width=1,depth=3)]
    loops = union_polygons(cells)
    assert sorted(signed_area(p) for p in loops) == [-9, 25]
    assert sum(signed_area(p) for p in loops) == 16


def test_point_touch_and_disconnected_components_remain_simple():
    cells = [dict(x=0,y=0,width=1,depth=1), dict(x=1,y=1,width=1,depth=1),
             dict(x=4,y=0,width=1,depth=1)]
    loops = union_polygons(cells)
    assert len(loops) == 3
    assert all(len(p)==len(set(p))==4 for p in loops)
    assert sum(signed_area(p) for p in loops) == 3


def test_invalid_rectangles_are_rejected():
    import pytest
    for changes in ({'width':0}, {'x':float('nan')}, {'depth':1e-8}):
        with pytest.raises(ValueError):
            union_polygons([dict(dict(x=0,y=0,width=1,depth=1), **changes)])
