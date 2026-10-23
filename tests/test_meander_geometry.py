"""Geometry-level regression for the three-cluster meander corridor."""
from itertools import combinations

import pytest
from shapely.geometry import box
from shapely.ops import unary_union

from backend.design.meander_geometry import meander_topology
from backend.design.general_engine import topology


@pytest.mark.parametrize("ratio,split",[(.38,.30),(.44,.36),(.61,.42)])
def test_meander_has_three_independently_shifted_clusters_and_two_connectors(ratio,split):
    result=meander_topology(20,32,1.7,ratio,split)
    assert result is not None
    halls,lanes=result
    assert len(halls)==5 and len(lanes)==6
    assert len({round(h['x'],3) for h in halls[:3]})>=2
    assert all(r['width']>0 and r['depth']>0 for r in halls+lanes)
    assert all(l['axis']=='y' and l['door_side'] in ('west','east') for l in lanes)
    shapes=[box(q['x'],q['y'],q['x']+q['width'],q['y']+q['depth']) for q in halls+lanes]
    assert all(a.intersection(b).area<1e-8 for a,b in combinations(shapes,2))
    assert unary_union(shapes).geom_type=='Polygon'
    assert all(h['depth']<32 for h in halls)
    assert topology('meander',20,32,1.7,ratio,split) is not None


def test_meander_refuses_insufficient_space_without_inventing_rooms():
    assert meander_topology(9,10,1.7,.4,.4) is None
