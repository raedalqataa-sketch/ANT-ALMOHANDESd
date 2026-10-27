import copy,json
from pathlib import Path
import pytest
from backend.design.architect_planner import ClientIntent
from backend.design.ai_lab.schemas import LabRequest
from backend.design.intelligence.engine import rank_portfolio, failure_record, run
from backend.design.intelligence.topology import signature


def model(label,union=20,shape=1.2):
    # Small selection fixture; real geometry integration is separately replayed.
    return {'candidate_id':label,'release':{'drawing_export_allowed':True},'checks':[],
      'architecture_intelligence':{'circulation_union_m2_total':union,'gross_floor_area_m2':100,
        'longest_required_travel_path_m':10,'unassigned_area_m2':0,
        'room_aspect_ratios':[{'aspect_ratio':shape}], 'program_completeness':{'status':'PASS'},
        'unreachable_required_routes':[],'structural_signature':{'hash':label[0]}}}


def test_smaller_hall_is_not_distinct_if_functional_graph_is_identical():
    a=model('A-original');b=model('A-small',union=18);c=model('B');d=model('C')
    original=copy.deepcopy([a,b,c,d]);chosen=rank_portfolio([a,b,c,d])
    assert len(chosen)==3 and b in chosen and a not in chosen
    assert [a,b,c,d]==original


def test_no_invalid_geometry_or_missing_routes_can_win_on_low_area():
    a=model('A');invalid=model('B',union=1);invalid['checks']=[{'status':'FAIL','check_id':'access'}]
    missing=model('C',union=1);missing['architecture_intelligence']['unreachable_required_routes']=[{'id':'bath'}]
    gap=model('D',union=1);gap['architecture_intelligence']['unassigned_area_m2']=.72
    assert rank_portfolio([a,invalid,missing,gap])==[a]
    record=failure_record(invalid,{'family':'spine'},'baseline')
    assert record['failed_checks']==['access'] and record['never_a_permanent_ban']


def test_experiment_is_default_off_and_invalid_budgets_rejected(tmp_path):
    intent=ClientIntent(width=20,depth=30,country='SA',region='الرياض',family=6,street_edges=['top'],main_street='top')
    assert LabRequest(intent=intent).architectural_intelligence is False
    with pytest.raises(ValueError,match='budget'):run(intent,tmp_path,budget=0)


def test_failed_ai_advice_is_not_replaced_by_local_search_without_fallback(monkeypatch,tmp_path):
    import backend.design.intelligence.engine as engine
    import backend.design.ai_lab.pipeline as pipeline
    from backend.design.ai_lab.schemas import LabRequest
    intent=ClientIntent(width=20,depth=30,country='SA',region='الرياض',family=6,street_edges=['top'],main_street='top')
    request=LabRequest(intent=intent,provider='GEMINI',model='fixture',allow_remote_program=True,architectural_intelligence=True)
    failed={'status':'BLOCKED','origin':'NO_API_RESULT','candidates':[],'fallback_used':False,'history':[],'telemetry':{'request_count':1}}
    monkeypatch.setenv('INTELLIGENCE_LIVE_BUDGET_CONFIRMED','true')
    monkeypatch.setattr(pipeline,'run',lambda *a,**kw:failed)
    monkeypatch.setattr(engine,'run',lambda *a,**kw:pytest.fail('silent local replacement'))
    result=engine.run_lab(request,tmp_path,provider_factory=None)
    assert result['origin']=='NO_API_RESULT' and result['status']=='BLOCKED'


@pytest.fixture(scope='module')
def real_experiment(tmp_path_factory):
    root=tmp_path_factory.mktemp('intelligence-real')
    intent=ClientIntent.model_validate(json.loads(Path('quality_review/gemini_sa600_case.json').read_text())['intent'])
    return run(intent,root,budget=3),root


def test_real_geometry_is_valid_program_complete_and_exported(real_experiment):
    import ezdxf
    from pypdf import PdfReader
    result,root=real_experiment
    assert result['candidates'] and result['experimental']
    signatures=[]
    for m in result['candidates']:
        d=m['architecture_intelligence'];signatures.append(d['structural_signature']['hash'])
        assert not d['critical_failures'] and d['program_completeness']['status']=='PASS'
        assert d['unassigned_area_m2']<=1e-6 and not d['unreachable_required_routes']
        rev=m['model_revision_id'];assert len(PdfReader(root/(rev+'.pdf')).pages)==5
        doc=ezdxf.readfile(root/(rev+'.dxf'));assert not doc.audit().errors
        saved=json.loads((root/(rev+'.json')).read_text());assert saved['geometry_sha256']==m['geometry_sha256']
    assert len(signatures)==len(set(signatures))
    assert all('architecture_intelligence' not in m for m in result['baseline_candidates'])


def test_missing_required_room_is_rejected_by_program_validator(real_experiment):
    from backend.design.functional_program import validate
    from backend.design.general_models import VillaBrief
    result,_=real_experiment;m=copy.deepcopy(result['candidates'][0]);b=VillaBrief.model_validate(m['brief'])
    assert not [c for c in validate(m,b) if c['status']=='FAIL']
    first=m['floors'][0]['rooms'];required=next(r for r in first if r.get('request_id'))
    first.remove(required)
    from backend.design.functional_program import RoomProgramValidator
    assert RoomProgramValidator(b).validate(m)['status']=='FAIL'


def test_missing_bath_door_and_window_are_detected(real_experiment):
    from backend.design.functional_program import validate
    from backend.design.general_models import VillaBrief
    from backend.design.intelligence.metrics import inspect
    result,_=real_experiment;m=copy.deepcopy(result['candidates'][0]);b=VillaBrief.model_validate(m['brief'])
    f=m['floors'][-1];bath=next(r for r in f['rooms'] if r['kind']=='bathroom')
    f['openings']=[o for o in f['openings'] if bath['id'] not in o.get('connects',[])]
    checks=validate(m,b);assert any(c['check_id']=='V4-functional-paths' and c['status']=='FAIL' for c in checks)
    m=copy.deepcopy(result['candidates'][0]);f=m['floors'][0]
    f['openings']=[o for o in f['openings'] if o['kind']!='window']
    assert inspect(m)['natural_light_ventilation_coverage']['rooms_without_modeled_window']
    assert any(c['status']=='FAIL' for c in validate(m,b))


def test_overlap_and_door_furniture_collision_are_detected(real_experiment):
    from backend.design.independent_audit import inspect as audit
    from backend.design.functional_program import furniture_issues
    result,_=real_experiment;m=copy.deepcopy(result['candidates'][0]);f=m['floors'][0]
    rooms=[r for r in f['rooms'] if r.get('request_id')]
    rooms[1].update({k:rooms[0][k] for k in ('x','y','width','depth')})
    assert audit(m)['status']=='FAIL'
    m=copy.deepcopy(result['candidates'][0]);f=m['floors'][0]
    opening=next(o for o in f['openings'] if o['kind']=='door' and o.get('swing_rect') and 'OUTSIDE' not in o['connects'])
    room=next(r for r in f['rooms'] if r['id']==opening['connects'][0]);item=next(q for q in f['furniture'] if q['room_id']==room['id'])
    item.update({k:opening['swing_rect'][k] for k in ('x','y','width','depth')})
    assert furniture_issues(m)


def test_legacy_sleeping_proportion_selection_filter_is_not_relaxed():
    a=model('A');b=model('B',union=1)
    b['design_evaluation']={'metrics':{'max_sleeping_aspect_ratio':2.45143}}
    assert rank_portfolio([a,b])==[a]


def test_total_measured_movement_prevents_fake_corridor_only_saving():
    a=model('A-original',union=20);b=model('A-small-corridor',union=15)
    a['architecture_intelligence']['movement_with_measured_internal_paths_m2_total']=25
    b['architecture_intelligence']['movement_with_measured_internal_paths_m2_total']=40
    assert rank_portfolio([a,b])==[a]


def test_known_failures_are_traceable_and_unknown_root_causes_not_invented():
    invalid=model('B');invalid['checks']=[{'status':'FAIL','check_id':'V4-program'}]
    row=failure_record(invalid,{'family':'spine'},'topology_search')
    assert 'FAIL-005' in row['known_failure_ids']
    assert row['root_cause']=='UNCONFIRMED; inspect geometric check evidence'
    assert row['resolution_status']=='OPEN' and row['verification_result']=='FAILED'
