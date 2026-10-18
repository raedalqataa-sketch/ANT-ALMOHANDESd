import copy
import json
from pathlib import Path
import pytest
from backend.design.general_models import VillaBrief
from backend.design.general_engine import generate_general,validate_general,expanded_program
from backend.design.general_quality import door_geometry,sweep_hits_box,privacy_evidence
from backend.design.furnishing import overlap,inside
from backend.design import saudi_rules


@pytest.fixture(scope='module')
def submitted(tmp_path_factory):
    data=json.loads((Path(__file__).resolve().parents[1]/'requirements/regressions/submitted-b4a690-brief.json').read_text())
    brief=VillaBrief(**data)
    result=generate_general(brief,tmp_path_factory.mktemp('submitted-fixed'))
    assert len(result['candidates'])==3
    assert all(c['release']['drawing_export_allowed'] for c in result['candidates'])
    return brief,result


def check(model,key):return next(c for c in model['checks'] if c['check_id']==key)


def test_submitted_case_real_fixes_without_false_certification(submitted):
    b,result=submitted
    for m in result['candidates']:
        assert m['metrics']['proposed_flexible_m2']==0
        assert m['metrics']['requested_spaces']==9 and m['metrics']['bed_capacity']==6
        assert len(m['stairs'])==2
        assert check(m,'guest-route')['status']=='PASS'
        assert check(m,'free-text')['status']=='PASS'
        assert check(m,'stair-geometry')['status']=='PASS'
        assert not m['release']['executive_issue_allowed']
        assert not m['regulatory_profile']['full_sbc_compliance_verified']
        assert check(m,'SA-parcel')['status']=='PENDING'
        for f in m['floors']:
            assert check(m,f['id']+'-walkability')['status']=='PASS'
            assert check(m,f['id']+'-door-sweeps')['status']=='PASS'
            assert check(m,'SA-'+f['id']+'-daylight')['status']=='PASS'
            assert sum(q.get('seats',0) for q in f['furniture'] if q['kind']=='dining_chair')==(6 if f['id']=='GF' else 0)
            for r in f['rooms']:
                if r.get('include_shower'):assert any(q['room_id']==r['id'] and q['kind']=='shower' for q in f['furniture'])


def test_guest_door_graph_detects_lost_separation(submitted):
    b,res=submitted;m=copy.deepcopy(res['candidates'][0])
    for o in m['floors'][0]['openings']:o.pop('access_control',None)
    ev=privacy_evidence(m)
    assert ev['family_rooms_exposed']
    assert next(c for c in validate_general(m,b) if c['check_id']=='guest-route')['status']=='FAIL'


def test_bad_opening_cannot_pass_on_host_length_only(submitted):
    b,res=submitted;m=copy.deepcopy(res['candidates'][0]);floor=m['floors'][0]
    o=next(o for o in floor['openings'] if o['kind']=='window')
    w=next(w for w in floor['walls'] if w['id']==o['wall_id']);o['center'][1 if w['axis']=='horizontal' else 0]+=.4
    assert next(c for c in validate_general(m,b) if c['check_id']=='GF-openings')['status']=='FAIL'


def test_window_and_parking_numeric_failures(submitted):
    b,res=submitted;m=copy.deepcopy(res['candidates'][0])
    for o in m['floors'][0]['openings']:
        if o['kind']=='window':o['clear_width']=.001
    assert next(c for c in saudi_rules.checks(m,b) if c['check_id']=='SA-GF-daylight')['status']=='FAIL'
    m['parking']=m['parking'][:1]
    assert next(c for c in saudi_rules.checks(m,b) if c['check_id']=='SA-parking-count')['status']=='FAIL'


def test_source_bound_setbacks_and_missing_inputs(submitted):
    b,res=submitted
    b=b.model_copy(deep=True);b.boundary_widths={'north':0,'south':20,'east':0,'west':0}
    assert saudi_rules.required_setbacks(b)=={'north':1.5,'south':4.,'east':1.5,'west':1.5}
    assert next(c for c in saudi_rules.checks(res['candidates'][0],b) if c['check_id']=='SA-setbacks-baseline')['status']=='FAIL'
    b.boundary_widths['south']=40
    assert saudi_rules.required_setbacks(b)['south']==6. # Wide-street provision is 6m, not a fabricated 8m.
    b.boundary_widths={}
    assert next(c for c in saudi_rules.checks(res['candidates'][0],b) if c['check_id']=='SA-setbacks-baseline')['status']=='PENDING'


def test_city_name_never_unlocks_local_or_full_code_approval(submitted):
    b,res=submitted
    for city in ('الرياض','جدة','نجران','مدينة أخرى'):
        v=b.model_copy(deep=True);v.city=city
        checks=saudi_rules.checks(res['candidates'][0],v)
        assert next(c for c in checks if c['check_id']=='SA-parcel')['status']=='PENDING'
        assert next(c for c in checks if c['check_id']=='SA-full-sbc')['status']=='PENDING'


def test_national_minima_and_parking_area_boundary():
    data=json.loads((Path(__file__).resolve().parents[1]/'requirements/regressions/submitted-b4a690-brief.json').read_text());b=VillaBrief(**data)
    b.rooms[0].min_area=3;b.rooms[0].min_side=1.4
    r=next(r for r in expanded_program(b,0) if r['request_id']==b.rooms[0].id)
    assert r['min_area']==11.2 and r['min_side']==2.8
    b.plot_width=20;b.plot_depth=20;assert saudi_rules.parking_count(b)==1
    b.plot_depth=20.01;assert saudi_rules.parking_count(b)==2


def test_annotation_boxes_avoid_actual_furniture_and_door_sweeps(submitted):
    _,res=submitted
    for m in res['candidates']:
        for f in m['floors']:
            for label in f['annotations']:
                if label.get('legend'):continue
                room=next(r for r in f['rooms'] if r['id']==label['room_id'])
                assert inside(room,label)
                assert not any(overlap(label,q) for q in f['furniture'] if q.get('physical',True))
                assert not any(overlap(label,o['swing_rect']) for o in f['openings'] if o.get('swing_rect'))


def test_exact_quarter_sweep_excludes_square_corner():
    g={'hinge':[0,0],'closed_direction':[1,0],'open_direction':[0,1],'radius':1}
    assert not sweep_hits_box(g,dict(x=.8,y=.8,width=.1,depth=.1))
    assert sweep_hits_box(g,dict(x=.2,y=.2,width=.1,depth=.1))
    assert not sweep_hits_box(g,dict(x=-.2,y=.2,width=.1,depth=.1))


def test_saudi_directory_is_real_directory_not_invented_local_rules():
    path=Path(__file__).resolve().parents[1]/'constitution/saudi'
    data=json.loads((path/'municipalities.json').read_text());coverage=json.loads((path/'local-coverage.json').read_text())
    assert len(data['amanats'])==17 and sum(len(a['municipalities']) for a in data['amanats'])==378
    assert all(a['downloaded'] for a in data['amanats'])
    assert 'apps.balady.gov.sa' in data['source']
    assert not data['all_local_rules_downloaded'] and not coverage['all_municipal_rules_verified']
    assert not coverage['verified_city_rule_overrides']
