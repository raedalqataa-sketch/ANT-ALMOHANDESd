import copy
import pytest
from backend.design.architect_planner import ClientIntent, propose
from backend.design.intelligence.topology import program_graph, proposals, signature
from backend.design.intelligence.metrics import inspect


def simple_model():
    cells=[dict(id='H',kind='corridor',x=4,y=0,width=2,depth=10),dict(id='R',kind='living',request_id='r',x=0,y=0,width=4,depth=10)]
    rooms=copy.deepcopy(cells)
    return dict(candidate_id='x',model_revision_id='x',brief={'rooms':[dict(id='r',kind='living',count=1,floor=0,min_area=20)],'proposed_room_area_factor':1.2},
      floors=[dict(id='GF',cells=cells,rooms=rooms,walls=[],openings=[],furniture=[])],stairs=[],site={'width':20,'depth':30},
      metrics={'floor_built_by_id':{'GF':60}},checks=[],functional_program_v4={'movement':{'routes':[],'unreachable':[]},'furniture_issues':[]})


def test_topologies_are_program_dependent_and_never_drop_functions():
    b,_=propose(ClientIntent(width=20,depth=30,country='SA',region='الرياض',family=6,street_edges=['top'],main_street='top'))
    graph=program_graph(b)
    assert graph['required_counts']=={r.id:r.count for r in b.rooms}
    assert any(r['type']=='FORBIDDEN_TRANSIT' for r in graph['relations'])
    plans=proposals(b)
    assert len({(p['family'],p['core_position'],p['guest_strategy']) for p in plans})>=3
    assert {p['proposed_area_factor'] for p in plans}>={1.0,1.2}
    assert all(p['reference_projects'] and not {'P02','P05'}&set(p['reference_projects']) for p in plans)
    assert all(not p['reference_projects'] for p in proposals(b,use_references=False))


def test_structure_signature_ignores_hall_partition_and_element_names():
    a=simple_model();b=copy.deepcopy(a)
    b['floors'][0]['cells'][0]['depth']=5
    b['floors'][0]['cells'].append(dict(id='split',kind='corridor',x=4,y=5,width=2,depth=5))
    b['floors'][0]['rooms'][1]['id']='renamed';b['floors'][0]['cells'][1]['id']='renamed'
    assert signature(a)['hash']==signature(b)['hash']
    b['floors'][0]['cells'][1]['kind']='majlis';b['floors'][0]['rooms'][1]['kind']='majlis'
    assert signature(a)['hash']!=signature(b)['hash']


def test_union_does_not_double_count_and_room_elongation_is_only_review():
    m=simple_model();m['floors'][0]['cells'].append(dict(id='overlap',kind='corridor',x=4,y=4,width=2,depth=3))
    result=inspect(m)
    assert result['circulation_union_m2_total']==pytest.approx(20)
    assert result['net_usable_room_area_m2']==40
    assert result['room_aspect_ratios'][0]['aspect_ratio']==2.5
    assert result['room_aspect_ratios'][0]['status']=='REVIEW'
    assert result['natural_light_ventilation_coverage']['rooms_without_modeled_window']==['R']
    assert result['natural_light_ventilation_coverage']['adequacy']=='REVIEW'
    assert result['dead_space_m2'] is None


def test_slit_has_area_and_polygon_evidence_not_hidden_in_usable_area():
    m=simple_model();f=m['floors'][0]
    f['cells']=[dict(id='a',kind='living',x=0,y=0,width=3,depth=5),dict(id='b',kind='living',x=3.4,y=0,width=3,depth=5),dict(id='c',kind='living',x=3,y=1.8,width=.4,depth=3.2)]
    r=inspect(m)
    assert r['unassigned_sliver_area_m2']==pytest.approx(.72)
    assert r['dead_space_polygon_evidence'][0]['polygon_m']


def test_functional_hub_does_not_inflate_a_living_room_to_fill_long_lane():
    from backend.design.general_engine import allocate
    r=dict(id='living',request_id='l',name='معيشة',kind='living',zone='family',min_area=24.,min_side=3.)
    lane=dict(x=0,y=0,width=3.7,depth=14.,axis='y',door_side='east')
    old=allocate([copy.deepcopy(r)],[lane],.2,coherent=True,policy='relationship_aware')
    new=allocate([copy.deepcopy(r)],[lane],.2,coherent=True,policy='functional_hub',guest_area_factor=1.0)
    old_r=next(c for c in old if c.get('request_id'));new_r=next(c for c in new if c.get('request_id'))
    assert new_r['depth'] < old_r['depth']
    assert (new_r['width']-.2)*(new_r['depth']-.2)>=24.-1e-6
    assert any(c['kind']=='reserve' for c in new)


def test_reported_gross_area_keeps_existing_wall_allowance_definition():
    m=simple_model();m['metrics']['floor_built_by_id']['GF']=65
    result=inspect(m)
    assert result['gross_floor_area_m2']==65
    assert result['floors'][0]['gross_cell_union_m2']==60


def test_reserve_partitions_do_not_invent_structural_diversity():
    a=simple_model();reserve=dict(id='reserve',kind='reserve',x=0,y=10,width=6,depth=2)
    a['floors'][0]['rooms'].append(copy.deepcopy(reserve));a['floors'][0]['cells'].append(copy.deepcopy(reserve))
    b=copy.deepcopy(a)
    for field in ['rooms','cells']:
        b['floors'][0][field][-1]['width']=3
        b['floors'][0][field].append(dict(reserve,id='reserve2',x=3,width=3))
    assert signature(a)['hash']==signature(b)['hash']


def test_guest_distributor_partition_does_not_invent_structural_diversity():
    a=simple_model()
    for field in ['cells','rooms']:
        a['floors'][0][field][0].update(zone='guest',guest_distributor=True)
    b=copy.deepcopy(a)
    for field in ['cells','rooms']:
        b['floors'][0][field][0]['depth']=5
        b['floors'][0][field].append(dict(id='guest_split',kind='corridor',zone='guest',guest_distributor=True,x=4,y=5,width=2,depth=5))
    assert signature(a)['hash']==signature(b)['hash']


def test_family_entry_routes_cannot_transit_someone_elses_bedroom():
    from backend.design.intelligence.metrics import entry_routes
    from shapely.geometry import LineString,box
    rooms=[dict(id='L',kind='living',x=0,y=0,width=3,depth=3),dict(id='B',kind='bedroom',x=3,y=0,width=3,depth=3),
           dict(id='D',kind='dining',x=6,y=0,width=3,depth=3),dict(id='H',kind='corridor',x=0,y=3,width=9,depth=2)]
    floor=dict(id='GF',rooms=rooms,cells=rooms,furniture=[],walls=[dict(id='entry',axis='horizontal',start=[0,0],end=[3,0],thickness=.2)],
        openings=[dict(id='door',kind='door',wall_id='entry',center=[1.5,0],width=1.,connects=['L','OUTSIDE'])])
    model=dict(footprint=dict(x=0,y=0,width=9,depth=5),stairs=[])
    paths=entry_routes(model,floor,'family')
    assert paths['lengths_m']['D']>8
    assert not LineString(paths['paths_m']['D']).intersects(box(3.31,.31,5.69,2.69))


def test_reference_shapes_scale_to_program_not_reference_area():
    from backend.design.intelligence.references import preferred_shape,matching_features
    room=dict(id='living',request_id='l',kind='living',zone='family',min_area=24.,min_side=3.)
    lane=dict(x=0,y=0,width=5.0,depth=15.,axis='y',door_side='east')
    shape=preferred_shape(room,lane,.2,1.1)
    assert shape and shape['net_width']*shape['net_depth']==pytest.approx(26.4)
    assert shape['aspect_ratio']==pytest.approx(matching_features('living')['preferred_aspect_ratio'])
    assert shape['source_projects']==['P04']
    assert preferred_shape(dict(room,min_side=8.),lane,.2,1.1) is None
    assert matching_features('storage') is None


def test_reference_conditioning_changes_geometry_before_materialization():
    from backend.design.general_engine import allocate
    room=dict(id='living',request_id='l',name='معيشة',kind='living',zone='family',min_area=24.,min_side=3.)
    lane=dict(x=0,y=0,width=5.0,depth=15.,axis='y',door_side='east')
    a=allocate([copy.deepcopy(room)],[lane],.2,coherent=True,policy='functional_hub',guest_area_factor=1.1)
    b=allocate([copy.deepcopy(room)],[lane],.2,coherent=True,policy='reference_hub',guest_area_factor=1.1)
    a=next(r for r in a if r.get('request_id'));b=next(r for r in b if r.get('request_id'))
    assert (a['x'],a['width'],a['depth'])!=(b['x'],b['width'],b['depth'])
    assert b['reference_shape']['source_projects']==['P04']
    assert (b['width']-.2)*(b['depth']-.2)>=24.


def test_short_tail_does_not_silently_stretch_a_reference_shaped_room():
    from backend.design.intelligence.references import preferred_shape
    from backend.design.general_engine import allocate
    room=dict(id='living',request_id='l',name='معيشة',kind='living',zone='family',min_area=24.,min_side=3.)
    lane=dict(x=0,y=0,width=5.,depth=15.,axis='y',door_side='east')
    shape=preferred_shape(room,lane,.2,1.0);lane['depth']=shape['net_depth']+.2+1.
    cells=allocate([room],[lane],.2,coherent=True,policy='reference_hub',guest_area_factor=1.0)
    actual=next(c for c in cells if c.get('request_id'))
    assert actual['depth']-.2==pytest.approx(shape['net_depth'])
    assert (actual['width']-.2)*(actual['depth']-.2)==pytest.approx(24)
    assert any(c['kind']=='reserve' for c in cells)
