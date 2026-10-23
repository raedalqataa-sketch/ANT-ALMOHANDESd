"""V4: real geometry fault injection, rollback, semantic and source integrity."""
import copy
import json
from itertools import combinations
import pytest
from backend.design.adaptive_geometry import clustered_topology
from backend.design.auto_repair import ArchitectureAutoRepairEngine,fingerprint
from backend.design.general_quality import door_geometry,sweep_hits_box
from backend.design.functional_program import FunctionalGraph,RoomProgramValidator,furniture_issues
from backend.design.general_models import VillaBrief


def simple_model():
    room=dict(id='K',kind='kitchen',request_id='k',x=0.,y=0.,width=4.,depth=4.,capacity=0)
    dining=dict(id='D',kind='dining',request_id='d',x=0.,y=5.,width=4.,depth=4.,capacity=0)
    hall=dict(id='H',kind='corridor',x=4.,y=0.,width=2.,depth=9.)
    walls=[];openings=[]
    for rid,y in (('K',0.),('D',5.)):
        walls.append(dict(id=rid+'W',axis='vertical',start=[4.,y],end=[4.,y+4],room_ids=[rid,'H'],thickness=.2))
        openings.append(dict(id=rid+'O',kind='door',wall_id=rid+'W',connects=[rid,'H'],center=[4.,y+2],width=1.0))
    f=dict(id='GF',rooms=[room,dining,hall],cells=[room,dining,hall],walls=walls,openings=openings,furniture=[],decorations=[])
    return dict(model_revision_id='test-model',floors=[f],footprint=dict(x=0.,y=0.,width=6.,depth=9.),stairs=[],brief={})


def test_cluster_topology_is_connected_disjoint_and_has_no_full_axial_hall():
    from backend.design.massing_quality import measures
    from backend.design.general_geometry import union_polygons
    for fraction,split in ((.35,.36),(.42,.5),(.65,.64)):
        halls,lanes=clustered_topology(20,30,1.6,fraction,split)
        assert len(halls)==3 and len(lanes)==4
        assert not any(h['depth']==30 for h in halls)
        assert measures(halls+lanes)['components']==1
        for a,b in combinations(halls+lanes,2):
            assert min(a['x']+a['width'],b['x']+b['width'])<=max(a['x'],b['x'])+1e-7 or min(a['y']+a['depth'],b['y']+b['depth'])<=max(a['y'],b['y'])+1e-7
        assert union_polygons(halls+lanes,0)
    assert clustered_topology(6,8,1.6,.5,.5) is None


def test_functional_paths_record_polyline_and_detect_furniture_barrier():
    m=simple_model();r=FunctionalGraph(m).inspect()['routes'][0]
    assert r['status']=='MEASURED' and len(r['points'])>2
    assert r['route_m']==pytest.approx(sum(__import__('math').dist(a,b) for a,b in zip(r['points'],r['points'][1:])),abs=.001)
    # Barrier severs the actual 2m hall. Labels and the door graph stay identical.
    m['floors'][0]['furniture']=[dict(id='block',room_id='H',kind='storage',x=4.,y=4.3,width=2.,depth=.5)]
    r=FunctionalGraph(m).inspect()['routes'][0]
    assert r['status']=='UNREACHABLE' and not r['points']


def test_semantic_program_catches_capacity_even_if_area_passes():
    m=simple_model();b=VillaBrief(plot_width=12,plot_depth=14,floors=1,setbacks=dict(north=0,south=0,east=0,west=0),rooms=[dict(id='k',name='نوم',kind='bedroom',floor=0,min_area=12,min_side=3,capacity=2),dict(id='d',name='طعام',kind='dining',floor=0,min_area=12,min_side=3)])
    report=RoomProgramValidator(b).validate(m)
    assert report['status']=='FAIL'
    assert report['errors'][0]['problem']=='function_capacity_or_dimensions'
    assert report['spaces'][0]['preferred_dimensions'] is None
    assert 'wardrobe' in report['spaces'][0]['required_furniture']


def door_fault_model():
    m=simple_model();f=m['floors'][0];o=f['openings'][0]
    # Door opens west, low hinge y=1.5; obstacle near the low hinge.
    f['furniture']=[dict(id='obstacle',room_id='K',kind='storage',x=3.4,y=1.51,width=.1,depth=.04)]
    return m


def sweep_validator(m):
    f=m['floors'][0];o=f['openings'][0]
    hit=any(sweep_hits_box(door_geometry(f,o),q) for q in f['furniture'])
    return [dict(check_id='GF-door-sweeps',status='FAIL' if hit else 'PASS',evidence={'collisions':[{'door':o['id']}] if hit else []}),dict(check_id='local-code',status='PENDING')]


def test_same_model_door_fault_is_repaired_and_inputs_not_mutated():
    m=door_fault_model();before=copy.deepcopy(m)
    assert sweep_validator(m)[0]['status']=='FAIL'
    repaired=ArchitectureAutoRepairEngine(sweep_validator).repair(m)
    assert m==before
    assert repaired['auto_repair_v4']['accepted_steps']==1
    assert repaired['floors'][0]['openings'][0]['hinge_end']=='high'
    assert sweep_validator(repaired)[0]['status']=='PASS'
    assert repaired['floors'][0]['rooms']==m['floors'][0]['rooms']
    assert repaired['auto_repair_v4']['attempts'][0]['before_geometry_sha256']!=repaired['geometry_sha256']


def test_repair_rolls_back_when_change_creates_new_failure():
    m=door_fault_model();original=fingerprint(m)
    def check(candidate):
        rows=sweep_validator(candidate)
        # A second independent safety requirement is deliberately incompatible.
        if fingerprint(candidate)!=original:rows.append(dict(check_id='new-safety-failure',status='FAIL'))
        return rows
    repaired=ArchitectureAutoRepairEngine(check,max_attempts=4).repair(m)
    assert fingerprint(repaired)==original
    assert not repaired['auto_repair_v4']['accepted_steps']
    assert all(not a['accepted'] for a in repaired['auto_repair_v4']['attempts'])
    assert repaired['checks'][0]['status']=='FAIL'


def test_traceability_has_all_199_distinct_rules_without_fake_completion():
    from backend.design.rule_traceability import matrix
    report=matrix({'checks':[]})
    assert report['rule_count']==199 and len({r['rule_id'] for r in report['rows']})==199
    assert all(r['runtime_status']=='REVIEW' for r in report['rows'])
    assert not any(r['implementation_status']=='COMPLETED' for r in report['rows'])
    assert all(r['source_provenance'].startswith('PENDING_') for r in report['rows'] if r['category']=='visual')
    assert not report['complete_code_coverage']


def test_v4_disabled_by_default_for_saved_api_clients():
    import inspect
    from backend.design.architect_planner import generate_automatic
    from backend.design.general_api import auto_design
    assert inspect.signature(generate_automatic).parameters['generation_v4'].default is False
    assert inspect.signature(auto_design).parameters['generation_v4'].default is False


def test_relationship_allocator_keeps_guest_distributor_between_majlis_and_wc():
    from backend.design.general_engine import allocate
    requests=[dict(id='M',kind='majlis',name='مجلس',zone='guest',separate_guest_entry=True,min_area=24,min_side=3.5),
              dict(id='W',kind='bathroom',name='حمام ضيوف',zone='guest',guest_parent='M',min_area=4,min_side=1.6)]
    lane=dict(x=0.,y=0.,width=5.,depth=14.,axis='y',door_side='east')
    cells=allocate(requests,[lane],.2,policy='relationship_aware')
    assert [r['kind'] for r in cells if r['kind']!='reserve']==['majlis','corridor','bathroom']
    m,d,w=cells[:3]
    assert m['y']+m['depth']==pytest.approx(d['y'])
    assert d['y']+d['depth']==pytest.approx(w['y'])


def test_visual_samples_respect_actual_walls_and_restore_closed_family_door():
    from backend.design.visual_privacy import inspect
    m=simple_model();f=m['floors'][0];r=f['rooms'][0];r.update(kind='living',zone='family')
    f['openings'].append(dict(id='guest',kind='door',guest_entry=True,wall_id='front',connects=['H','OUTSIDE'],center=[6.,2.],width=1.))
    f['walls'].append(dict(id='front',axis='vertical',start=[6.,0.],end=[6.,4.],room_ids=['H'],thickness=.2,exterior=True))
    opened=inspect(m)
    assert 'K' in opened['sampled_exposed_rooms'] and not opened['certified']
    f['openings'][0]['access_control']='family_only'
    closed=inspect(m)
    assert 'K' not in closed['sampled_exposed_rooms']
    assert closed['status']=='REVIEW'  # never claims complete privacy from samples


def test_real_v4_exports_have_no_failed_gate_and_stale_geometry_cannot_export(tmp_path):
    import ezdxf
    from backend.design.architect_planner import ClientIntent,generate_automatic
    from backend.design.general_engine import export_general_model
    from backend.design.general_models import VillaBrief
    result=generate_automatic(ClientIntent(width=24,depth=32,country='YE',region='الحديدة',family=6,street_edges=['bottom']),tmp_path,generation_v4=True)
    assert len(result['candidates'])==3
    assert result['planning']['reference_design']['project_count']==6
    assert result['planning']['reference_design']['unique_images']==19
    assert result['planning']['generation_v4']['reproducibility']['stochastic'] is False
    for m in result['candidates']:
        assert not [c for c in m['checks'] if c['status']=='FAIL']
        assert m['rule_traceability_v4']['rule_count']==199
        assert all(s['width']<=2.8+1e-6 for s in m['stairs'])
        assert m['functional_program_v4']['movement']['routes']
        assert not m['functional_program_v4']['movement']['unreachable']
        assert m['functional_program_v4']['independent_geometry']['status']=='PASS'
        assert m['functional_program_v4']['execution_coordination']['site']['geometric_status']=='PASS'
        assert m['functional_program_v4']['execution_coordination']['mep']['status']=='PENDING'
        assert m['design_evaluation']['selection_solver']['selected_count']==3
        assert any(c['check_id']=='V4-site-gross-envelope' and c['status']=='PASS' for c in m['checks'])
        d=ezdxf.readfile(tmp_path/(m['model_revision_id']+'.dxf'))
        assert d.dxfversion=='AC1024' and not d.audit().errors
        assert not list(d.modelspace().query('HATCH SOLID'))
        assert (tmp_path/(m['model_revision_id']+'.pdf')).read_bytes().startswith(b'%PDF')
    m=result['candidates'][0];m['floors'][0]['rooms'][0]['width']+=1
    before=set(tmp_path.iterdir())
    with pytest.raises(ValueError,match='تغيرت هندسة'):
        export_general_model(m,VillaBrief(**m['brief']),tmp_path)
    assert set(tmp_path.iterdir())==before


def test_complete_furniture_group_is_replaced_instead_of_deleting_obstacles():
    m=simple_model();f=m['floors'][0]
    q=dict(id='a',room_id='K',kind='kitchen_counter',x=.2,y=.2,width=1.,depth=.6,use_zones=[])
    f['furniture']=[q,{**q,'id':'b'}];f['furnishing_choice_counts']={'K':4}
    def check(candidate):
        bad=furniture_issues(candidate)
        counters=[q for q in candidate['floors'][0]['furniture'] if q['room_id']=='K' and q['kind']=='kitchen_counter']
        return [dict(check_id='V4-furniture-clearance',status='FAIL' if bad or not counters else 'PASS',evidence={'invalid':bad})]
    assert check(m)[0]['status']=='FAIL'
    result=ArchitectureAutoRepairEngine(check).repair(m)
    assert result['auto_repair_v4']['accepted_steps']==1
    assert result['auto_repair_v4']['attempts'][0]['operation']=='replace_complete_furniture_group'
    assert check(result)[0]['status']=='PASS'
    assert result['floors'][0]['rooms']==m['floors'][0]['rooms']


def test_v4_report_pagination_preserves_all_rows_and_readable_type():
    from unittest.mock import patch
    from backend.design.scene import Scene
    from backend.design.general_drawing import review_pages
    scene=Scene((0,0,21,55))
    for i in range(100):
        scene.text(19.5,1+i*.5,f'check-{i}',.19,align='right')
        scene.text(1.5,1+i*.5,'PASS',.18,align='left')
    with patch('backend.design.general_drawing.review_drawing',return_value=scene):
        pages=review_pages({'functional_program_v4':True})
    assert len(pages)==2
    rows=[p for page in pages for p in page.items if p['text'].startswith('check-')]
    assert len(rows)==100 and len({r['text'] for r in rows})==100
    assert all(p['size']>=.23 and 0<p['y']<29.7 for page in pages for p in page.items)


def test_v4_preflight_rejects_first_geometric_option_but_accepts_next(monkeypatch,tmp_path):
    """A baseline-V3 PASS must never short-circuit a later viable V4 candidate."""
    from backend.design import general_engine as g
    from types import SimpleNamespace
    layouts=[{'variant':'first'},{'variant':'next'}]
    monkeypatch.setattr(g,'search',lambda *a,**kw:{**layouts[0],'alternatives':[layouts[1]]})
    monkeypatch.setattr(g,'materialize',lambda brief,family,layout:{
        'model_revision_id':layout['variant'],'search':{},'checks':[],
        'floors':[],'site_placement':{}})
    monkeypatch.setattr(g,'validate_general',lambda *args:[
        {'check_id':'baseline','status':'PASS'}])
    assessed=[]
    def v4_preflight(model):
        assessed.append(model['model_revision_id'])
        model['checks'].append({'check_id':'V4-measured-clearance',
            'status':'FAIL' if model['model_revision_id']=='first' else 'PASS'})
        model['auto_repair_v4']={'accepted_steps':0}
        return model
    result=g.generate_general(SimpleNamespace(),tmp_path,candidate_families=('spine',),
        emit_drawings=False,candidate_validator=v4_preflight,validation_budget=3)
    assert assessed==['first','next']
    assert result['candidates'][0]['model_revision_id']=='next'
    assert result['candidates'][0]['release']['drawing_export_allowed']
    assert result['candidates'][0]['search']['v4_preflights']==2
    assert not result['candidates'][0]['search']['v4_search_budget_exhausted']
    assert json.loads((tmp_path/'next.json').read_text())['checks'][-1]['status']=='PASS'


def test_v4_preflight_budget_rejects_unverified_following_candidate(monkeypatch,tmp_path):
    """A search timeout/budget exhaustion cannot be disguised as a passing drawing."""
    from backend.design import general_engine as g
    from types import SimpleNamespace
    monkeypatch.setattr(g,'search',lambda *a,**kw:{
        'variant':'first','alternatives':[{'variant':'unchecked'}]})
    monkeypatch.setattr(g,'materialize',lambda brief,family,layout:{
        'model_revision_id':layout['variant'],'search':{},'checks':[],
        'floors':[],'site_placement':{}})
    monkeypatch.setattr(g,'validate_general',lambda *args:[
        {'check_id':'baseline','status':'PASS'}])
    assessed=[]
    def reject(model):
        assessed.append(model['model_revision_id'])
        model['checks'].append({'check_id':'V4-real','status':'FAIL'})
        return model
    result=g.generate_general(SimpleNamespace(),tmp_path,candidate_families=('spine',),
        emit_drawings=False,candidate_validator=reject,validation_budget=1)
    assert assessed==['first']
    assert result['candidates'][0]['release']['status']=='BLOCKED'
    assert not result['candidates'][0]['release']['drawing_export_allowed']
    assert result['candidates'][0]['search']['v4_search_budget_exhausted']
    assert not (tmp_path/'first.pdf').exists()
    with pytest.raises(ValueError,match='validation_budget'):
        g.generate_general(SimpleNamespace(),tmp_path,candidate_families=('spine',),
            emit_drawings=False,candidate_validator=reject,validation_budget=0)


def test_v3_selection_remains_compatible_without_v4_callback(monkeypatch,tmp_path):
    from backend.design import general_engine as g
    from types import SimpleNamespace
    monkeypatch.setattr(g,'search',lambda *a,**kw:{
        'variant':'first','alternatives':[{'variant':'second'}]})
    monkeypatch.setattr(g,'materialize',lambda brief,family,layout:{
        'model_revision_id':layout['variant'],'search':{},'checks':[],
        'floors':[],'site_placement':{}})
    monkeypatch.setattr(g,'validate_general',lambda *args:[
        {'check_id':'baseline','status':'PASS'}])
    result=g.generate_general(SimpleNamespace(),tmp_path,candidate_families=('spine',),
        emit_drawings=False)
    assert result['candidates'][0]['model_revision_id']=='first'
    assert result['candidates'][0]['release']['drawing_export_allowed']
    assert result['candidates'][0]['search']['preflight']['enabled'] is False


def test_search_diagnostics_prove_area_shortfall_only_when_math_requires_it():
    from backend.design.general_engine import search_feasibility_evidence
    small=VillaBrief(plot_width=8,plot_depth=10,floors=1,
        country='YE',apply_saudi_rules=False,
        setbacks=dict(north=1,south=1,east=1,west=1),
        rooms=[dict(id='m',name='غرفة ضرورية',kind='living',floor=0,min_area=100,min_side=3)])
    report=search_feasibility_evidence(small)
    assert report['available_envelope_m2_per_floor_upper_bound']==48
    assert report['required_net_room_m2_by_floor']=={'0':100.}
    assert report['classification']=='PROVEN_ENVELOPE_SHORTFALL'
    assert not report['legal_buildability_certified']

    feasible_bounds=small.model_copy(update={
        'plot_width':24,'plot_depth':32,
        'rooms':[small.rooms[0].model_copy(update={'min_area':20})]})
    report=search_feasibility_evidence(feasible_bounds)
    assert report['classification']=='SEARCH_EXHAUSTED_NOT_PROVEN_IMPOSSIBLE'
    assert report['required_net_room_m2_by_floor']=={'0':20.}
    assert report['available_envelope_m2_per_floor_upper_bound']==660
    assert not report['legal_buildability_certified']


def test_rotating_real_orthogonal_lanes_preserves_area_and_connectivity():
    from backend.design.adaptive_geometry import clustered_topology,rotate_orthogonal_topology
    from backend.design.massing_quality import measures
    halls,lanes=clustered_topology(10,20,1.5,.5,.5)
    rotated_halls,rotated_lanes=rotate_orthogonal_topology(halls,lanes,10)
    original=halls+lanes
    new=rotated_halls+rotated_lanes
    assert len(original)==len(new)
    assert sum(r['width']*r['depth'] for r in original)==pytest.approx(
        sum(r['width']*r['depth'] for r in new))
    assert measures(new)['components']==1
    assert min(r['x'] for r in new)>=0
    assert min(r['y'] for r in new)>=0
    assert max(r['x']+r['width'] for r in new)==pytest.approx(20)
    assert max(r['y']+r['depth'] for r in new)==pytest.approx(10)
    assert all(r['axis']=='x' for r in rotated_lanes)
    assert set(r['door_side'] for r in rotated_lanes)=={'north','south'}
    assert all(not (a['x']<b['x']+b['width']-1e-6 and b['x']<a['x']+a['width']-1e-6
                    and a['y']<b['y']+b['depth']-1e-6 and b['y']<a['y']+a['depth']-1e-6)
               for a,b in combinations(new,2))
