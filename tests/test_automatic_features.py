"""Generated features must be architectural geometry, not a successful declaration."""
import copy
import json
from pathlib import Path
import pytest
import ezdxf
from backend.design.general_models import VillaBrief
from backend.design.general_engine import generate_general,validate_general
from backend.design.automatic_features import intersects,from_polygon
from backend.design.saudi_2024_overlay import covered_by
from backend.design.general_drawing import drawing

ROOT=Path(__file__).resolve().parents[1]

def brief(**overrides):
    b=json.loads((ROOT/'requirements/regressions/submitted-b4a690-brief.json').read_text())
    b.update(plot_width=24,plot_depth=32,boundary_widths={'north':0,'south':15,'east':0,'west':0},automatic_features={'lightwell':True,'roof_annex':True,'balcony':True,'service_yard':True,'main_street_faces':['south']})
    b.update(overrides)
    return VillaBrief(**b)

@pytest.fixture(scope='module')
def generated(tmp_path_factory):
    b=brief();out=tmp_path_factory.mktemp('features');r=generate_general(b,out)
    return b,r,out


def test_actual_features_and_original_program(generated):
    b,result,out=generated
    viable=[m for m in result['candidates'] if m['release']['drawing_export_allowed']]
    assert len(viable)>=2
    for m in viable:
        assert all(r['status']=='GENERATED' for r in m['feature_generation'])
        assert [f['id'] for f in m['floors']]==['GF','FF','RF']
        assert sum(bool(r.get('request_id')) for f in m['floors'] for r in f['rooms'])==9
        assert len(m['stairs'])==2  # GF->FF and FF->RF; no stair continues above annex roof.
        assert m['metrics']['annex_built_m2']>0 and m['metrics']['balcony_m2']>0
        well=m['regulatory_geometry']['light_wells'][0];void=from_polygon(well['polygon'])
        for f in m['floors'][:2]:
            assert not any(intersects(void,c) for c in f['cells'])
            assert any(o['id'] in well['window_ids'] for o in f['openings'])
        assert any(o['id']=='GF-COURT-MAINTENANCE' for o in m['floors'][0]['openings'])
        roof=m['regulatory_geometry']['roof_annex']
        assert covered_by(roof['polygon'],m['footprint']['polygons_by_floor']['FF'])
        assert m['metrics']['annex_built_m2']<=m['metrics']['floor_built_by_id']['FF']*.7
        rf=m['floors'][-1]
        assert {'sofa','toilet','basin'}<={q['kind'] for q in rf['furniture']}
        assert any(o.get('balcony_access') and o['door_style']=='sliding' for o in m['floors'][1]['openings'])
        yard=m['service_yard']
        assert not any(intersects(yard,c) for f in m['floors'] for c in f['cells'])
        assert not any(intersects(yard,c) for c in m['parking'])
        for key in ('AUTO-annex-core','AUTO-well-windows','AUTO-balcony-access','SA-2024-lightwell-opening-overlay','SA-2024-annex-footprint-overlay','SA-2024-projection-geometry-overlay','SA-2024-facade-equipment-overlay'):
            assert next(c for c in m['checks'] if c['check_id']==key)['status']=='PASS'
        assert not m['release']['executive_issue_allowed']


def test_real_exports_have_feature_layers_and_no_fills(generated):
    b,result,out=generated
    m=next(m for m in result['candidates'] if m['release']['drawing_export_allowed'])
    doc=ezdxf.readfile(out/(m['model_revision_id']+'.dxf'))
    assert doc.dxfversion=='AC1024' and not doc.audit().errors
    assert not list(doc.modelspace().query('HATCH SOLID'))
    layers={e.dxf.layer for e in doc.modelspace()}
    assert {'LIGHTWELL','BALCONY_SLAB','BALCONY_GUARD','SLIDING_DOOR','SERVICE_YARD','HVAC_EQUIPMENT','STAIR_VOID'}<=layers
    assert 'RF' in m['previews'] and 'SITE' in m['previews']
    for f in m['floors']:
        assert all(p.get('fill','none')=='none' for p in drawing(m,f).items if p['type']!='text')


def test_removed_annex_or_equipment_blocks_release_checks(generated):
    b,result,_=generated
    m=copy.deepcopy(next(m for m in result['candidates'] if m['release']['drawing_export_allowed']))
    m['floors']=[f for f in m['floors'] if f['id']!='RF']
    checks=validate_general(m,b)
    assert next(c for c in checks if c['check_id']=='AUTO-annex-core')['status']=='FAIL'
    del m['service_yard']
    checks=validate_general(m,b)
    assert next(c for c in checks if c['check_id']=='AUTO-service_yard')['status']=='FAIL'


def test_manual_geometry_and_automatic_intent_do_not_overwrite_each_other():
    with pytest.raises(ValueError,match='التلقائي'):
        brief(regulatory_geometry={'light_wells':[]})
    b=brief(automatic_features={},regulatory_geometry={'light_wells':[],'roof_annex_absent':True})
    assert b.model_dump()['regulatory_geometry']['roof_annex_absent'] is True
    with pytest.raises(ValueError,match='الشرفة'):
        brief(floors=1)


def test_impossible_feature_request_does_not_silently_omit_it(tmp_path):
    b=brief(plot_width=20,plot_depth=30)
    r=generate_general(b,tmp_path)
    assert not any(m['release']['drawing_export_allowed'] for m in r['candidates'])
    assert r['unavailable'] or r['candidates']
    assert not list(tmp_path.glob('*.dxf'))

@pytest.mark.parametrize('option',['lightwell','roof_annex','balcony','service_yard'])
def test_features_can_be_requested_independently(option,tmp_path):
    b=brief(automatic_features={option:True})
    result=generate_general(b,tmp_path)
    viable=[m for m in result['candidates'] if m['release']['drawing_export_allowed']]
    assert viable,[(m['candidate_id'],[c['check_id'] for c in m['checks'] if c['status']=='FAIL']) for m in result['candidates']]
    for m in viable:
        assert [r['feature'] for r in m['feature_generation']]==[option]
        if option!='roof_annex':assert not any(f['id']=='RF' for f in m['floors'])


def test_single_storey_annex_search_returns_diagnostics_without_crashing(tmp_path):
    data=brief(automatic_features={'roof_annex':True}).model_dump()
    data['floors']=1
    for row in data['rooms']:row['floor']=0
    r=generate_general(VillaBrief(**data),tmp_path)
    assert r['candidates'] or r['unavailable']
    for m in r['candidates']:
        if m['release']['drawing_export_allowed']:
            assert [f['id'] for f in m['floors']]==['GF','RF'] and len(m['stairs'])==1
        else:
            assert any(c['status']=='FAIL' for c in m['checks']) and not m['previews']
