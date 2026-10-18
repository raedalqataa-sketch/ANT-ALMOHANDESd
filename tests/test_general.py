"""Generalization, fail-closed export, linework and optional language model boundary."""
import copy
import json
from pathlib import Path
from xml.etree import ElementTree as ET
import ezdxf
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.design.general_models import VillaBrief,from_reference_program
from backend.design.general_engine import generate_general,search,materialize,validate_general
from backend.design.general_drawing import drawing


def brief(floors=2,width=20,depth=30):
    rows=[('مجلس','majlis',0,1,24,3.5,0),('معيشة','living',0,1,24,3.5,0),('مطبخ','kitchen',0,1,16,3,0),('طعام','dining',0,1,16,3,0),('حمام ضيف','bathroom',0,1,4,1.6,0),('رئيسية','master',floors-1,1,20,3.5,2),('نوم أبناء','bedroom',floors-1,2,16,3.2,2),('حمام أسرة','bathroom',floors-1,1,5,1.6,0)]
    return VillaBrief(plot_width=width,plot_depth=depth,floors=floors,setbacks=dict(north=2,south=3,east=2,west=2),rooms=[dict(id=f'r{i}',name=n,kind=k,floor=f,count=c,min_area=a,min_side=s,capacity=cap) for i,(n,k,f,c,a,s,cap) in enumerate(rows)])


@pytest.mark.parametrize('floors,width,depth',[(1,20,30),(2,20,30),(2,24,32),(1,24,25)])
def test_distinct_topologies_and_actual_program(floors,width,depth):
    b=brief(floors,width,depth);signatures=[]
    for family in ('L','U','stepped'):
        result=search(b,family);assert result is not None
        m=materialize(b,family,result);checks=validate_general(m,b)
        assert not [c for c in checks if c['status']=='FAIL']
        assert sum(bool(r.get('request_id')) for f in m['floors'] for r in f['rooms'])==9
        assert m['search']['optimality_proven'] is False
        polygon=m['footprint']['polygon']
        polygon_area=abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(polygon,polygon[1:]+polygon[:1])))/2
        assert polygon_area==pytest.approx(result['gross'])
        cells=m['floors'][0]['cells'];signatures.append(json.dumps([(r['x'],r['y'],r['width'],r['depth']) for r in cells]))
    assert len(set(signatures))==3


def test_changing_client_changes_actual_rooms():
    a=brief(width=24,depth=32);b=a.model_copy(deep=True);b.rooms[6].count=3
    first=materialize(a,'U',search(a,'U'));second=materialize(b,'U',search(b,'U'))
    assert len([r for f in second['floors'] for r in f['rooms'] if r.get('request_id')=='r6'])==3
    assert first['geometry_sha256']!=second['geometry_sha256']
    assert not [c for c in validate_general(second,b) if c['status']=='FAIL']


def test_infeasible_does_not_drop_rooms(tmp_path):
    b=brief(width=12,depth=14);b.rooms[6].count=10
    result=generate_general(b,tmp_path)
    assert result['candidates']==[] and len(result['unavailable'])==3
    assert not list(tmp_path.iterdir())


def test_independent_recheck_rejects_tampered_geometry():
    b=brief();m=materialize(b,'L',search(b,'L'));m['floors'][0]['rooms'][0]['width']=.4
    assert next(c for c in validate_general(m,b) if c['check_id']=='GF-sizes')['status']=='FAIL'
    m=materialize(b,'L',search(b,'L'));m['floors'][0]['openings']=[o for o in m['floors'][0]['openings'] if o.get('main_entry')]
    assert next(c for c in validate_general(m,b) if c['check_id']=='GF-doors')['status']=='FAIL'


def test_shared_exports_have_no_fills_or_hatches(tmp_path):
    b=brief();result=generate_general(b,tmp_path);assert len(result['candidates'])==3
    for m in result['candidates']:
        assert m['release']['drawing_export_allowed'] and not m['release']['executive_issue_allowed']
        dxf=ezdxf.readfile(tmp_path/Path(m['downloads']['dxf']).name)
        assert dxf.dxfversion=='AC1024' and not dxf.audit().errors
        assert not list(dxf.modelspace().query('HATCH SOLID TRACE 3DFACE'))
        assert not any(e.dxf.const_width for e in dxf.modelspace().query('LWPOLYLINE'))
        assert dxf.header['$INSUNITS']==6
        for floor in m['floors']:
            scene=drawing(m,floor)
            assert all(p.get('fill','none')=='none' for p in scene.items)
            assert any(p['layer']=='WALL_OUTLINE' for p in scene.items)
            assert all(p['type']=='line' for p in scene.items if p['layer']=='WALL_OUTLINE')
            svg=ET.parse(tmp_path/Path(m['previews'][floor['id']]).name)
            assert all(n.attrib.get('fill','none')=='none' for n in svg.iter() if n.tag.rsplit('}',1)[-1]!='text')
        assert (tmp_path/Path(m['downloads']['pdf']).name).read_bytes().startswith(b'%PDF')


def test_single_capacity_preserves_original_fixture_geometry():
    b=brief();b.rooms[6].capacity=1
    for family in ('L','U','stepped'):
        m=materialize(b,family,search(b,family))
        for f in m['floors']:
            for r in f['rooms']:
                if r.get('request_id')=='r6':
                    beds=[q for q in f['furniture'] if q['room_id']==r['id'] and q.get('capacity',0)]
                    assert len(beds)==1 and beds[0]['kind']=='single_bed'
                    assert sorted((beds[0]['width'],beds[0]['depth']))==[1.,2.]


def test_input_validation_and_reference_migration():
    with pytest.raises(ValueError):VillaBrief(**{**brief().model_dump(),'plot_width':float('nan')})
    bad=brief().model_dump();bad['rooms'][1]['id']=bad['rooms'][0]['id']
    with pytest.raises(ValueError):VillaBrief(**bad)
    row=dict(id='bed',name='غرفة',use='bed',zone='family',floor=0,area=16,minWidth=3.2,capacity=2)
    assert from_reference_program([row])[0].min_area==16
    with pytest.raises(ValueError):from_reference_program([{**row,'accessVia':'master'}])


def test_ollama_not_falsely_reported_connected(monkeypatch):
    monkeypatch.delenv('OLLAMA_BASE_URL',raising=False);client=TestClient(app)
    assert client.get('/api/v3/ai-status').json()['configured'] is False
    response=client.post('/api/v3/interpret',json={'brief':brief().model_dump(),'text':'أريد ثلاث غرف'})
    assert response.status_code==503


def test_ollama_invalid_output_never_applied(monkeypatch):
    import backend.design.general_api as api
    monkeypatch.setenv('OLLAMA_BASE_URL','http://operator-configured-ollama:11434')
    class Response:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,n):return json.dumps({'message':{'content':json.dumps({'rooms':[], 'unresolved':[]})}}).encode()
    monkeypatch.setattr(api,'urlopen',lambda *a,**kw:Response())
    assert TestClient(app).post('/api/v3/interpret',json={'brief':brief().model_dump(),'text':'أريد ثلاث غرف'}).status_code==502


def test_wall_join_union_keeps_boundary_and_door_reveals():
    from backend.design.scene import Scene
    from backend.design.general_drawing import wall_outlines
    scene=Scene((0,0,4,4))
    wall_outlines(scene,[(0,0,3,.2,.02),(0,0,.2,3,.02)])
    assert len(scene.items)==6  # L boundary, without internal overlap caps
    length=sum(((p['b'][0]-p['a'][0])**2+(p['b'][1]-p['a'][1])**2)**.5 for p in scene.items)
    assert length==pytest.approx(12.)
    scene=Scene((0,0,4,1))
    wall_outlines(scene,[(0,0,1,.2,.02),(2,0,1,.2,.02)])
    assert len(scene.items)==8  # Two wall piers; the 1 m door remains open.


def test_ollama_proposal_requires_review_and_preserves_unknowns(monkeypatch):
    import backend.design.general_api as api
    b=brief();monkeypatch.setenv('OLLAMA_BASE_URL','http://operator-configured-ollama:11434')
    captured={}
    class Response:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,n):return json.dumps({'message':{'content':json.dumps({'rooms':[r.model_dump() for r in b.rooms], 'unresolved':['مدخل ضيوف مستقل']})}}).encode()
    def remote(request,**kw):captured.update(json.loads(request.data));return Response()
    monkeypatch.setattr(api,'urlopen',remote)
    response=TestClient(app).post('/api/v3/interpret',json={'brief':b.model_dump(),'text':'أريد مدخل ضيوف مستقل'})
    assert response.status_code==200
    d=response.json();assert d['status']=='REVIEW_REQUIRED' and d['unresolved']==['مدخل ضيوف مستقل']
    assert d['source_text']=='أريد مدخل ضيوف مستقل'
    assert captured['format']['required']==['rooms','unresolved']
