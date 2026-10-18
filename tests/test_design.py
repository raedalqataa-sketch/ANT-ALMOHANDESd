import copy
import hashlib
import json
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree
import ezdxf
import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from backend.main import app, Project, Room, layout
from backend.design.models import DesignOptions
from backend.design.generator import generate_candidates
from backend.design.requirements import project_profile, import_brief, normalize_number
from backend.design.validators import validate_model, release_decision
from backend.design.export import wall_runs, export_dxf


@pytest.fixture
def candidate():
    return generate_candidates(DesignOptions(candidate_count=1))[0]


def state(model, check):
    return next(c for c in validate_model(model) if c['check_id']==check)['status']


def test_prior_counterexample_and_order_dependence_fixed():
    p=Project(plot_width=6,plot_depth=6,rooms=[Room(name='A',width=4,depth=6),Room(name='B',width=2,depth=3),Room(name='C',width=2,depth=3)])
    assert len(layout(p))==3
    for dims in [[(6,2),(6,2),(4,2),(4,2)],[(6,2),(4,2),(6,2),(4,2)]]:
        p=Project(plot_width=10,plot_depth=4,rooms=[Room(name=str(i),width=w,depth=d) for i,(w,d) in enumerate(dims)])
        assert len(layout(p))==4


def test_proposed_candidates_and_no_false_executive_approval():
    for model in generate_candidates(DesignOptions()):
        checks=validate_model(model)
        assert not [c for c in checks if c['status']=='FAIL']
        assert {'GF','FF'}=={f['id'] for f in model['floors']}
        assert model['profile']['site']['plot_depth_m']==30
        assert model['profile']['household']['members']==9
        release=release_decision(checks)
        assert release['drawing_export_allowed']
        assert not release['execution_claim_allowed']
        assert 'local_regulations' in release['pending_checks']
        assert not release_decision(checks,'EXECUTION_DOCUMENTATION')['drawing_export_allowed']
        for check in checks:
            assert check['model_revision_id']==model['model_revision_id']
            assert check['expected_criterion'] and check['criterion_source'] and check['reason']


def test_overlap_and_bounds_are_detected_independently(candidate):
    rooms=candidate['floors'][0]['rooms']
    rooms[1]['x']=rooms[0]['x'];rooms[1]['y']=rooms[0]['y']
    assert state(candidate,'overlap')=='FAIL'
    rooms[0]['x']=-3
    assert state(candidate,'bounds')=='FAIL'
    assert not release_decision(validate_model(candidate))['drawing_export_allowed']


def test_deleted_door_breaks_reachability_and_guest_service(candidate):
    f=candidate['floors'][0]
    f['openings']=[o for o in f['openings'] if not (o['kind']=='door' and 'GF-men-bath' in o['connects'])]
    assert state(candidate,'reachability')=='FAIL'
    assert state(candidate,'guest_route')=='FAIL'


def test_missing_required_storage_and_parking(candidate):
    f=candidate['floors'][0]
    f['rooms']=[r for r in f['rooms'] if r['kind']!='storage']
    candidate['parking']=[]
    assert state(candidate,'mandatory_program')=='FAIL'


def test_windows_missing_or_illegal_do_not_pass(candidate):
    candidate['floors'][0]['openings']=[o for o in candidate['floors'][0]['openings'] if not (o['kind']=='window' and o['connects'][0]=='GF-elderly')]
    assert state(candidate,'physical_windows')=='FAIL'
    checks=validate_model(candidate,opening_faces=['north'])
    assert next(c for c in checks if c['check_id']=='opening_legality')['status']=='FAIL'
    assert next(c for c in checks if c['check_id']=='ventilation_quantity')['status']=='PENDING'


def test_wall_links_and_missing_enclosure(candidate):
    floor=candidate['floors'][0]
    floor['walls'].pop(0)
    assert state(candidate,'room_wall_enclosure')=='FAIL'
    floor['openings'][0]['wall_id']='NONEXISTENT'
    assert state(candidate,'references')=='FAIL'


def test_opening_outside_wall_and_wrong_revision(candidate):
    opening=candidate['floors'][0]['openings'][0]
    opening['center']=[1000,1000]
    opening['revision_id']='stale'
    assert state(candidate,'opening_fit')=='FAIL'
    assert state(candidate,'references')=='FAIL'


def test_door_furniture_collision_and_insufficient_beds(candidate):
    f=candidate['floors'][0]
    o=next(o for o in f['openings'] if o['kind']=='door' and o['connects'][0]=='GF-elderly')
    bed=next(q for q in f['furniture'] if q['room_id']=='GF-elderly' and q['kind']=='single_bed')
    bed.update(o['swing_rect'])
    assert state(candidate,'door_envelopes')=='FAIL'
    for floor in candidate['floors']:
        floor['furniture']=[q for q in floor['furniture'] if q['capacity']==0]
    assert state(candidate,'placed_bed_capacity')=='FAIL'


def test_stair_arithmetic_and_core_stacking(candidate):
    candidate['stairs'][0]['riser_count']+=1
    assert state(candidate,'stair_geometry')=='FAIL'
    first=next(r for r in candidate['floors'][1]['rooms'] if r['kind']=='stairs')
    first['x']+=.3
    assert state(candidate,'core_stacking')=='FAIL'


def test_proposed_height_can_trigger_stair_failure():
    model=generate_candidates(DesignOptions(layout_family="legacy",footprint_width=14,footprint_depth=19.2,floor_height=4))[0]
    assert state(model,'stair_geometry')=='FAIL'


def test_arabic_numeric_mapping_and_unknown_brief_not_auto_adopted():
    assert normalize_number('٢٠')==20
    assert normalize_number('۳۰')==30
    wb=Workbook()
    for row in [('الحقل','القيمة'),('اسم المشروع','مشروع آخر'),('عرض الأرض بالمتر','٢٠'),('عمق الأرض بالمتر','٣٠'),('عدد الأدوار',2),('عدد أفراد الأسرة',9),('المتطلبات الأساسية','طلبات جديدة')]:wb.active.append(row)
    buffer=BytesIO();wb.save(buffer)
    preview=import_brief(buffer.getvalue())
    assert preview['mapped_fields']['plot_depth']==30
    assert preview['requires_mapping_confirmation']
    assert not preview['recognized_approved_source']
    assert preview['profile'] is None


def test_bundle_sources_hashes_and_ids():
    root=Path(__file__).resolve().parents[1]
    bundle=json.loads((root/'constitution/references/floor_plan_rules_v1.json').read_text())
    for source in bundle['source_documents']:
        data=json.dumps(source['content'],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
        assert hashlib.sha256(data).hexdigest()==source['content_sha256_canonical_json']
    ids=[r['rule_id'] for rules in bundle['rule_catalog'].values() for r in rules]
    assert len(ids)==len(set(ids))==139


def test_generated_revisions_are_new_and_requirements_unchanged():
    before=project_profile()
    a=generate_candidates(DesignOptions(candidate_count=1))[0]
    b=generate_candidates(DesignOptions(candidate_count=1))[0]
    assert a['model_revision_id']!=b['model_revision_id']
    assert a['requirements_sha256']==b['requirements_sha256']
    assert project_profile()==before
    assert len(a['profile']['pending_decisions'])==3


def test_openings_remove_wall_runs(candidate,tmp_path):
    floor=candidate['floors'][0]
    o=floor['openings'][0];wall=next(w for w in floor['walls'] if w['id']==o['wall_id'])
    idx=1 if wall['axis']=='vertical' else 0
    lo,hi=o['center'][idx]-o['width']/2,o['center'][idx]+o['width']/2
    assert all(min(b[idx],hi)-max(a[idx],lo)<=1e-6 for a,b in wall_runs(floor,wall))
    audit=export_dxf(candidate,tmp_path/'test.dxf')
    assert audit['audit_errors']==0 and audit['units']==6
    dxf=ezdxf.readfile(tmp_path/'test.dxf')
    assert len(dxf.modelspace().query('ARC[layer=="DOOR"]'))==sum(o['kind']=='door' for f in candidate['floors'] for o in f['openings'])


def test_api_snapshots_exports_and_blocking(tmp_path,monkeypatch):
    import backend.design.api as api
    import backend.main as main
    monkeypatch.setattr(api,'OUT',tmp_path);monkeypatch.setattr(main,'OUT',tmp_path)
    client=TestClient(app)
    r=client.post('/api/v2/design',json={'candidate_count':1})
    assert r.status_code==200
    model=r.json()['candidates'][0]
    for url in [*model['downloads'].values(),*model['previews'].values()]:
        response=client.get(url);assert response.status_code==200
        if url.endswith('.svg'):
            root=ElementTree.fromstring(response.text)
            assert root.attrib['data-revision']==model['model_revision_id']
    stored=client.get(model['downloads']['json']).json()
    assert stored['checks']==model['checks']
    assert stored['export_audit']['model_revision_id']==model['model_revision_id']
    blocked=client.post('/api/v2/design',json={'candidate_count':1,'confirmed_opening_faces':[]}).json()['candidates'][0]
    assert not blocked['release']['drawing_export_allowed']
    assert set(blocked['downloads'])=={'json'}
    assert blocked['previews']=={}
    changed=project_profile();changed['household']['members']=1
    assert client.post('/api/v2/design',json={'project_profile':changed}).status_code==422


def test_zero_or_negative_room_geometry_rejected(candidate):
    candidate['floors'][0]['rooms'][0]['width']=-1
    assert state(candidate,'finite_geometry')=='FAIL'


def test_required_fixtures_not_inferred_from_room_name(candidate):
    floor=candidate['floors'][0]
    floor['furniture']=[f for f in floor['furniture'] if f['room_id']!='GF-storage']
    assert state(candidate,'fixture_presence')=='FAIL'
