import copy
from test_assl_replan_010 import fixture

def test_all_operation_classes_get_reserved_slots_without_duplicates():
 from assl.structural_replanner_011 import schedule,OPERATIONS
 b,p=fixture();events=list(schedule(b,p,per_class=1))
 assert {e[1]['category'] for e in events}==set(OPERATIONS)
 assert len(events)==len(OPERATIONS)

def test_fingerprint_ignores_names_and_metadata():
 from assl.structural_replanner_011 import physical_hash
 b,p=fixture();q=copy.deepcopy(p)
 q['rooms_by_floor'][0][0]['name']='renamed';q['quality']={'score':-100}
 assert physical_hash(p)==physical_hash(q)
 q['rooms_by_floor'][0][0]['x']+=.1
 assert physical_hash(p)!=physical_hash(q)

def test_stair_lock_and_cross_floor_alignment_are_distinct_constraints():
 from assl.structural_replanner_011 import stair_valid
 b,p=fixture();q=copy.deepcopy(p)
 for floor in q['rooms_by_floor']:
  for r in floor:
   if r['kind']=='stair':r['x']+=1
 assert stair_valid(p,q,False)
 assert not stair_valid(p,q,True)
 q['rooms_by_floor'][1][0]['x']+=1
 assert not stair_valid(p,q,False)

def test_required_long_corridor_removal_fails_hard_gate():
 from assl.openings_009 import construct,validate
 b,p=fixture();q=copy.deepcopy(p);q['halls_by_floor'][0]=[]
 assert validate(b,construct(b,q))['status']=='FAIL'

def test_privacy_window_and_missing_program_cannot_be_soft_penalties():
 from assl.openings_009 import validate,construct
 b,p=fixture()
 q=copy.deepcopy(p);q['opening_model_009'][0]['windows']=[]
 assert validate(b,q)['status']=='FAIL'
 q=copy.deepcopy(p);q['rooms_by_floor'][0]=[r for r in q['rooms_by_floor'][0] if r.get('kind')!='kitchen']
 assert validate(b,construct(b,q))['status']=='FAIL'
 q=copy.deepcopy(p);d=next(d for d in q['opening_model_009'][0]['doors'] if d['id']=='guest-entry');d['connects'][1]='auto-living-1'
 assert validate(b,q)['status']=='FAIL'

def test_far_kitchen_and_inefficient_bedroom_relations_are_measured():
 from assl.layout_critic_010 import critique
 b,p=fixture();r=critique(b,p,{'kitchen_dining_m':.1,'bed_bath_m':.1})
 assert any(d['type']=='FUNCTIONAL_DISTANCE' and 'kitchen' in d['room'] for d in r['defects'])
 assert any(d['type']=='FUNCTIONAL_DISTANCE' and ('children' in d['room'] or 'master' in d['room']) for d in r['defects'])

def test_unrepairable_budget_keeps_valid_original_without_approval():
 from assl.structural_replanner_011 import replan,physical_hash
 b,p=fixture();r=replan(b,p,per_class=0,limits={'long_run_m':.1})
 assert r['status']=='REJECT_AND_REPLAN_UNRESOLVED'
 assert physical_hash(r['best'])==physical_hash(p)

def test_scheduler_uses_latest_accepted_geometry_not_stale_source():
 from assl.structural_replanner_011 import schedule
 b,p=fixture();current=copy.deepcopy(p);stream=schedule(b,lambda:current,per_class=1)
 next(stream)
 current['rooms_by_floor'][1][0]['x']+=.125
 candidate,op=next(stream)
 assert candidate['rooms_by_floor'][1][0]['x']==current['rooms_by_floor'][1][0]['x']

def test_already_good_design_returns_complete_identity_metadata():
 from assl.structural_replanner_011 import replan
 b,p=fixture();r=replan(b,p,limits={'long_run_m':100,'kitchen_dining_m':100,'bed_bath_m':100,'max_aspect':100,'max_excess':100})
 assert r['status']=='ACCEPT'
 assert r['original_hash']==r['final_hash']

def test_priority_override_keeps_existing_packer_default_behavior():
 from assl.free_layout_solver import pack_floor,initial_core
 b,p=fixture();rooms=p['rooms_by_floor'][1];requests=[{k:v for k,v in r.items() if k not in ('x','y','width','depth')} for r in rooms if r.get('request_id')]
 core=initial_core(16,20,0,.2)
 a,ea=pack_floor(requests,16,20,.2,0,core,[])
 z,ez=pack_floor(requests,16,20,.2,0,core,[],priority_order=None)
 assert ea==ez
 assert (a.rooms if a else None)==(z.rooms if z else None)
