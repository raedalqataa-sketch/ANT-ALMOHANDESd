import json,copy
from pathlib import Path
from backend.design.general_models import VillaBrief

def fixture():
 root=Path(__file__).parent/'fixtures';return VillaBrief.model_validate(json.loads((root/'assl_architecture_cases.json').read_text())['cases'][0]['brief']),json.loads((root/'assl_openings_009_valid.json').read_text())

def test_union_and_long_run_ignore_cell_splitting():
 from assl.layout_critic_010 import corridor_metrics
 a=[dict(x=0,y=0,width=1.5,depth=12)]
 b=[dict(x=0,y=0,width=1.5,depth=5),dict(x=0,y=5,width=1.5,depth=7)]
 assert corridor_metrics(a)==corridor_metrics(b)
 assert corridor_metrics(a)['longest_run_m']==12

def test_long_corridor_requires_replan_not_pass():
 from assl.layout_critic_010 import critique
 b,p=fixture();r=critique(b,p,limits={'long_run_m':1})
 assert r['status']=='REJECT_AND_REPLAN'
 assert any(x['type']=='LONG_CORRIDOR' for x in r['defects'])

def test_replan_preserves_program_stair_and_original_and_records_real_geometry():
 from assl.replan_010 import replan,fingerprint
 from assl.openings_009 import validate
 b,p=fixture();original=copy.deepcopy(p);r=replan(b,p,budget=15)
 assert p==original
 assert validate(b,r['best'])['status']=='PASS'
 assert r['status'] in ('ACCEPT','REJECT_AND_REPLAN_UNRESOLVED')
 for step in r['history']:
  if step['accepted']:assert step['before_hash']!=step['after_hash']
 assert r['history']

def test_actual_functional_route_limit_triggers_defect():
 from assl.layout_critic_010 import critique
 b,p=fixture();r=critique(b,p,{'kitchen_dining_m':.1})
 assert any(d['type']=='FUNCTIONAL_DISTANCE' for d in r['defects'])
 assert any(x['distance_m'] is not None and x['distance_m']>.1 for f in r['floors'] for x in f['relationships'] if x['target_kind']=='dining')

def test_global_packer_receives_program_without_old_coordinates(monkeypatch):
 from assl.replan_010 import global_repacking
 from assl import free_layout_solver
 b,p=fixture();seen=[]
 def pack(requests,*args,**kwargs):
  seen.append(requests)
  assert all(not set(('x','y','width','depth'))&set(r) for r in requests)
  return None,'EXPECTED_TEST_NO_SOLUTION'
 monkeypatch.setattr(free_layout_solver,'pack_floor',pack)
 list(global_repacking(b,p));assert seen
