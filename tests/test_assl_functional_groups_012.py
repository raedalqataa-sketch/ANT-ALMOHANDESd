import copy
import json
from pathlib import Path
import pytest
from backend.design.general_models import VillaBrief

ROOT=Path(__file__).resolve().parents[1]

def source():
 from test_assl_replan_010 import fixture
 return fixture()

def test_joint_candidates_change_group_and_reserve_stair_and_other_floor():
 from assl.functional_groups_012 import proposals
 b,p=source();saved=copy.deepcopy(p)
 candidates=list(proposals(b,p,beam_width=4,node_limit=2))
 assert p==saved
 assert candidates
 for q,details in candidates:
  assert q['rooms_by_floor'][1]==p['rooms_by_floor'][1]
  assert next(r for r in q['rooms_by_floor'][0] if r['kind']=='stair')==next(r for r in p['rooms_by_floor'][0] if r['kind']=='stair')
  assert sorted(r['id'] for r in q['rooms_by_floor'][0])==sorted(r['id'] for r in p['rooms_by_floor'][0])
  group=lambda z:{r['id']:(r['x'],r['y'],r['width'],r['depth']) for r in z['rooms_by_floor'][0] if r['kind'] in ('living','dining','kitchen')}
  assert group(q)!=group(p)

def test_joint_candidates_have_actual_door_hosts_and_no_overlaps():
 from assl.functional_groups_012 import proposals
 from assl.openings_009 import shared_edge
 from assl.free_layout_solver import overlap_area
 b,p=source()
 for q,_ in proposals(b,p,beam_width=4,node_limit=2):
  rooms=q['rooms_by_floor'][0];halls=q['halls_by_floor'][0]
  for r in rooms:
   if r['kind'] in ('living','dining','kitchen'):
    assert any((edge:=shared_edge(r,h)) and edge['length']>=1.2-1e-6 for h in halls)
   assert all(overlap_area(r,v)<1e-6 for v in rooms+halls if v is not r)

def test_failed_search_retains_original_and_reports_unresolved():
 from assl.functional_groups_012 import replan
 from assl.structural_replanner_011 import physical_hash
 b,p=source();saved=copy.deepcopy(p)
 result=replan(b,p,max_validations=0)
 assert p==saved
 assert physical_hash(result['best'])==physical_hash(p)
 assert result['status']=='REJECT_AND_REPLAN_UNRESOLVED'
 assert result['accepted_changes']==0

def test_invalid_initial_geometry_is_not_used_as_safe_fallback():
 from assl.functional_groups_012 import replan
 b,p=source();p['rooms_by_floor'][0]=[]
 with pytest.raises(ValueError,match='BASELINE'):
  replan(b,p,max_validations=0)

def test_enclosed_void_measure_is_geometry_based():
 from assl.functional_groups_012 import enclosed_voids
 rs=[dict(x=0,y=0,width=4,depth=1),dict(x=0,y=3,width=4,depth=1),dict(x=0,y=1,width=1,depth=2),dict(x=3,y=1,width=1,depth=2)]
 assert enclosed_voids(rs)['area_m2']==pytest.approx(4)
 assert enclosed_voids(rs[:-1])['area_m2']==0

def test_obstacle_aligned_door_host_is_considered_during_group_placement():
 from assl.functional_groups_012 import group_anchors
 from assl.free_layout_solver import clear
 from assl.openings_009 import shared_edge
 hall=dict(x=9,y=6.25,width=2.5,depth=3.5)
 stair=dict(x=11.5,y=2.75,width=3,depth=4.6)
 candidates=[r for r in group_anchors(hall,4.2,4.2,[stair]) if clear(r,[stair,hall],19.8,25.8)]
 assert any(abs(r['x']-11.5)<1e-6 and abs(r['y']-7.35)<1e-6 for r in candidates)
 assert all(shared_edge(hall,r)['length']>=1.2-1e-6 for r in candidates)

def test_slit_diagnostic_includes_previous_point_four_metre_regression():
 from assl.functional_groups_012 import residual_diagnostic
 objects=[dict(id='a',x=0,y=0,width=2,depth=3),dict(id='b',x=2.4,y=0,width=2,depth=3),dict(id='c',x=2,y=0,width=.4,depth=1.2)]
 result=residual_diagnostic(objects)
 assert result['unallocated_gross_area_m2']==pytest.approx(.72)

def test_node_extent_search_includes_program_obstacle_clearance_events():
 from assl.functional_groups_012 import node_candidates
 hub=dict(x=9,y=3.75,width=2.5,depth=2.5)
 bath=dict(x=3.75,y=7.25,width=2.25,depth=2.25)
 nodes=list(node_candidates(hub,[bath]))
 assert any(abs(n['y']+n['depth']-10.7)<1e-6 for n,_ in nodes)

def test_group_opening_variants_move_real_doors_without_changing_rooms():
 from assl.functional_groups_012 import opening_variants
 from assl.structural_replanner_011 import physical_hash
 b,p=source();saved=copy.deepcopy(p)
 variants=list(opening_variants(p))
 assert len(variants)==16
 assert all(physical_hash(q)==physical_hash(p) for q in variants)
 assert any(q['opening_model_009'][0]['doors']!=p['opening_model_009'][0]['doors'] for q in variants)
 assert p==saved

@pytest.mark.parametrize('kwargs',[{'max_validations':-1},{'max_validations':1.5},{'beam_width':0},{'node_limit':-1}])
def test_invalid_search_budgets_are_rejected(kwargs):
 from assl.functional_groups_012 import replan
 b,p=source()
 with pytest.raises(ValueError,match='budget'):
  replan(b,p,**kwargs)

def test_yemen_joint_repartition_proves_real_nonregressing_group_gain():
 from assl.functional_groups_012 import replan,residual_diagnostic
 from assl.openings_009 import validate
 from assl.structural_replanner_011 import stair_valid
 from assl.replan_010 import acceptable_change
 cases=json.loads((ROOT/'tests/fixtures/assl_architecture_cases.json').read_text())['cases']
 brief=VillaBrief.model_validate(next(c for c in cases if c['id']=='ye-medium')['brief'])
 p=json.loads((ROOT/'tests/fixtures/assl_011_yemen_baseline.json').read_text());saved=copy.deepcopy(p)
 result=replan(brief,p,max_validations=36,beam_width=6)
 assert result['accepted_changes']>=1
 assert result['original_hash']!=result['final_hash']
 assert p==saved and result['original_preserved']
 assert validate(brief,result['best'])['status']=='PASS'
 assert stair_valid(p,result['best'],True)
 assert result['best']['rooms_by_floor'][1]==p['rooms_by_floor'][1]
 assert result['best']['halls_by_floor'][1]==p['halls_by_floor'][1]
 assert acceptable_change(result['before'],result['after'])
 assert result['after']['floors'][0]['union_m2']<result['before']['floors'][0]['union_m2']
 before={r['id']:r for r in p['rooms_by_floor'][0]}
 changes=[r for r in result['best']['rooms_by_floor'][0] if r['kind'] in ('living','dining','kitchen') and any(r[k]!=before[r['id']][k] for k in ('x','y','width','depth'))]
 assert len(changes)==3
 for rs,hs,old_rs,old_hs in zip(result['best']['rooms_by_floor'],result['best']['halls_by_floor'],p['rooms_by_floor'],p['halls_by_floor']):
  assert residual_diagnostic(rs+hs)['unallocated_gross_area_m2']<=residual_diagnostic(old_rs+old_hs)['unallocated_gross_area_m2']+1e-5
 assert result['status']=='REJECT_AND_REPLAN_UNRESOLVED'

def test_new_group_geometry_does_not_retain_source_quality_or_trace():
 from assl.functional_groups_012 import proposals
 b,p=source()
 p['quality']={'score':'STALE'};p['placement_trace']=['STALE']
 q,_=next(proposals(b,p,beam_width=2,node_limit=2))
 for field in ('quality','placement_trace','topology_evidence','structural_signature'):
  assert field not in q
 assert q['building_envelope_m']==p['building_envelope_m']

def test_benchmark_rejects_unknown_or_empty_case_selection(tmp_path):
 from scripts.assl_functional_benchmark_012 import run
 for cases in ((),('unknown',)):
  with pytest.raises(ValueError,match='case'):
   run(tmp_path/'out',tmp_path/'missing',case_ids=cases)
 assert not (tmp_path/'out').exists()

def test_removing_old_slit_does_not_offset_creating_new_slit_elsewhere():
 from assl.functional_groups_012 import new_residual_area
 def slit(x):
  return [dict(id='a',x=x,y=0,width=2,depth=3),dict(id='b',x=x+2.4,y=0,width=2,depth=3),dict(id='c',x=x+2,y=0,width=.4,depth=1.2)]
 assert new_residual_area(slit(0),slit(10))==pytest.approx(.72)
 assert new_residual_area(slit(0),slit(0))==0

def test_retained_room_halls_keep_their_transit_connectors():
 from assl.functional_groups_012 import retained_hall_network
 from assl.free_layout_audit import _connected
 b,p=source();rooms=[r for r in p['rooms_by_floor'][0] if r['kind'] not in ('living','dining','kitchen')]
 halls=retained_hall_network(p,rooms)
 assert _connected(halls)
 # The distant ground-bedroom host needs its intermediate transit segment.
 assert any(h['y']==9.75 for h in halls)

def test_zero_opening_budget_keeps_group_search_but_disables_refinement():
 from assl.functional_groups_012 import replan
 cases=json.loads((ROOT/'tests/fixtures/assl_architecture_cases.json').read_text())['cases']
 b=VillaBrief.model_validate(next(c for c in cases if c['id']=='ye-medium')['brief'])
 p=json.loads((ROOT/'tests/fixtures/assl_011_yemen_baseline.json').read_text())
 r=replan(b,p,max_validations=36,beam_width=6,max_opening_trials=0)
 assert r['statistics']['geometric_proposals']>0
 assert r['statistics'].get('opening_variants_tested',0)==0
 assert r['accepted_changes']==0
