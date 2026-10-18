import copy
import hashlib
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.design.models import DesignOptions
from backend.design.generator import generate_candidates
from backend.design.validators import validate_model,release_decision
from backend.design.export import svg
from backend.design.walkability import floor_access


def status(model,check):return next(c for c in validate_model(model) if c['check_id']==check)['status']


def signature(model):
    return frozenset((f['id'],tuple(sorted(o['connects']))) for f in model['floors'] for o in f['openings'] if o['kind'] in ('door','passage'))


def test_reference_families_change_adjacency_and_massing():
    models=generate_candidates(DesignOptions())
    assert {m['search']['family'] for m in models}=={'garden_gallery','social_hub','open_court'}
    assert len({signature(m) for m in models})==3
    assert all(not [c for c in validate_model(m) if c['status']=='FAIL'] for m in models)
    a,b,c=models
    assert a['floors'][1]['voids']
    assert not b['floors'][1]['voids']
    assert c['floors'][0]['gross_area_proposed_m2']<c['footprint']['width']*c['footprint']['depth']
    assert all(m['floors'][1]['gross_area_proposed_m2']<m['floors'][0]['gross_area_proposed_m2'] for m in models)


def test_images_do_not_override_adopted_project():
    for m in generate_candidates(DesignOptions()):
        assert m['site']['width']==20 and m['site']['depth']==30
        assert len(m['floors'])==2
        assert not any(q['kind'] in ('pool','elevator') for f in m['floors'] for q in f['furniture'])
        assert len(m['profile']['pending_decisions'])==3
        assert not m['approval']['execution_claim_allowed']


def test_requested_empty_bedroom_cannot_pass_on_total_capacity():
    m=generate_candidates(DesignOptions(layout_family='social_hub',bedroom_count=4))[0]
    assert status(m,'room_furnishing_completeness')=='PASS'
    floor=m['floors'][1]
    floor['furniture']=[q for q in floor['furniture'] if q['room_id']!='FF-child4']
    # Total capacity remains enough for nine, but the requested fourth bedroom is now empty.
    assert status(m,'placed_bed_capacity')=='PASS'
    assert status(m,'room_furnishing_completeness')=='FAIL'
    assert not release_decision(validate_model(m))['drawing_export_allowed']


def test_bedroom_count_is_not_silently_increased_to_fill_capacity():
    m=generate_candidates(DesignOptions(layout_family='social_hub',bedroom_count=2))[0]
    assert len([r for f in m['floors'] for r in f['rooms'] if r['kind']=='bedroom'])==2
    assert status(m,'placed_bed_capacity')=='FAIL'


def test_grid_detects_obstacle_even_when_door_graph_stays_connected():
    m=generate_candidates(DesignOptions(layout_family='social_hub'))[0]
    f=m['floors'][0];r=next(r for r in f['rooms'] if r['id']=='GF-elderly')
    # A new cabinet blocks the entire room interior. Door references still exist.
    f['furniture'].append(dict(id='OBSTRUCTION',room_id=r['id'],floor_id='GF',kind='storage',x=r['x'],y=r['y'],width=r['width'],depth=r['depth'],capacity=0,physical=True,use_zones=[],revision_id=m['model_revision_id']))
    assert status(m,'reachability')=='PASS'
    assert status(m,'walkable_routes')=='FAIL'


def test_use_zone_obstruction_is_not_a_fixture_overlap():
    m=generate_candidates(DesignOptions(layout_family='social_hub'))[0];f=m['floors'][1]
    bed=next(q for q in f['furniture'] if q['kind']=='single_bed')
    z=bed['use_zones'][0]
    f['furniture'].append(dict(id='ZONE-BLOCK',room_id=bed['room_id'],floor_id='FF',kind='storage',x=z['x'],y=z['y']+.15,width=.2,depth=.2,capacity=0,physical=True,use_zones=[],revision_id=m['model_revision_id']))
    assert status(m,'proposed_use_zones')=='FAIL'


def test_upstairs_terrace_is_not_a_ground_floor_entrance():
    m=generate_candidates(DesignOptions(layout_family='social_hub'))[0]
    assert any(o.get('to_outdoor_id') for o in m['floors'][1]['openings'])
    m['stairs']=[]
    assert status(m,'reachability')=='FAIL'
    assert status(m,'stair_geometry')=='FAIL'


def test_terrace_needs_real_access_and_void_cannot_be_room():
    m=generate_candidates(DesignOptions(layout_family='garden_gallery'))[0]
    m['floors'][1]['openings']=[o for o in m['floors'][1]['openings'] if not o.get('to_outdoor_id')]
    assert status(m,'outdoor_access')=='FAIL'
    v=m['floors'][1]['voids'][0];v['x']=m['floors'][1]['rooms'][0]['x'];v['y']=m['floors'][1]['rooms'][0]['y']
    assert status(m,'void_and_terrace_bounds')=='FAIL'


def test_embedded_font_and_real_furniture_scene():
    m=generate_candidates(DesignOptions(layout_family='social_hub'))[0]
    data=svg(m,m['floors'][0])
    assert 'data:font/ttf;base64,' in data
    assert 'data-layer="FURNITURE"' in data and 'data-layer="LANDSCAPE"' in data
    assert 'data-role="room-dimensions"' in data
    assert '<ellipse' in data and '<path' in data
    assert not '<image' in data  # It is actual vector geometry, not a raster illustration of a guessed plan.


def test_api_style_changes_keep_geometry_traceable(tmp_path,monkeypatch):
    import backend.design.api as api
    monkeypatch.setattr(api,'OUT',tmp_path)
    client=TestClient(app)
    a=client.post('/api/v2/design',json={'layout_family':'social_hub','output_style':'presentation'}).json()['candidates'][0]
    b=client.post('/api/v2/design',json={'layout_family':'social_hub','output_style':'monochrome'}).json()['candidates'][0]
    assert a['geometry_sha256']==b['geometry_sha256']
    assert a['model_revision_id']!=b['model_revision_id']
    assert a['metrics']['floor_built_m2']['FF']<a['metrics']['floor_built_m2']['GF']
    assert a['metrics']['dining_seats']>=8
    assert a['release']['drawing_export_allowed'] and not a['release']['execution_claim_allowed']


def test_reference_manifest_has_five_scoped_precedents():
    p=Path(__file__).resolve().parents[1]/'references/quality_precedents_v04.json'
    data=json.loads(p.read_text())
    assert len(data['references'])==5
    assert len({r['sha256'] for r in data['references']})==5
    assert not data['policy']['official_regulations_inferred']


def test_outdoor_elements_keep_revision_and_parent_references():
    m=generate_candidates(DesignOptions(layout_family='garden_gallery'))[0]
    f=m['floors'][1]
    assert status(m,'references')=='PASS'
    f['outdoor_furniture'][0]['outdoor_id']='NONEXISTENT'
    assert status(m,'references')=='FAIL'
    f['outdoor_furniture'][0]['outdoor_id']=f['terraces'][0]['id']
    f['guardrails'][0]['revision_id']='WRONG_REVISION'
    assert status(m,'references')=='FAIL'
