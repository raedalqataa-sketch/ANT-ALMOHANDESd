import copy
from backend.design.massing_quality import measures,trim_corridor_tails
from backend.design.architect_planner import ClientIntent,propose,generate_automatic
from backend.design.general_engine import generate_general,validate_general

def box(x,y,w,d,kind='bedroom',**extra):return dict(x=x,y=y,width=w,depth=d,kind=kind,**extra)
def test_metric_counts_shared_edges_once_and_rejects_point_only_contacts():
 m=measures([box(0,0,4,4),box(4,0,4,4)])
 assert m['area']==32 and m['perimeter']==24 and m['components']==1 and m['envelope_fill']==1
 m=measures([box(0,0,4,4),box(4,4,4,4)]);assert m['components']==2

def test_only_unused_corridor_tail_is_removed_without_moving_served_room_edges():
 h=[box(4,0,1.5,18,'corridor')];rooms=[box(0,0,4,5),box(0,5,4,7)]
 trimmed=trim_corridor_tails(h,rooms)
 assert trimmed[0]['depth']==12 and trimmed[0]['y']==0 and h[0]['depth']==18

def test_coherent_massing_improves_actual_geometry_without_changing_setbacks_or_program(tmp_path):
 intent=ClientIntent(width=24,depth=32,city='الرياض',family=6,street_edges=['bottom'])
 b,_=propose(intent);old=b.model_copy(update={'massing_strategy':'legacy'})
 baseline=generate_general(old,tmp_path/'legacy');updated=generate_automatic(intent,tmp_path/'coherent')
 assert updated['planning']['design_selection']['strategy']=='objective_ranked_geometry_v1'
 assert len(updated['candidates'])==3
 assert len({m['candidate_id'] for m in updated['candidates']})==3
 before={m['candidate_id']:m for m in baseline['candidates']}
 for model in updated['candidates']:
  assert model['brief']['setbacks']==old.setbacks.model_dump()
  assert model['brief']['boundary_widths']==old.boundary_widths
  assert model['brief']['rooms']==old.model_dump()['rooms']
  assert model['release']['executive_issue_allowed'] is False
  measured=measures(model['floors'][0]['cells'])
  assert measured['components']==1
  if model['candidate_id'] in before:
   previous=measures(before[model['candidate_id']]['floors'][0]['cells'])
   assert measured['normalized_perimeter']<previous['normalized_perimeter']
  assert not [c for c in validate_general(model,b) if c['status']=='FAIL']
 model=updated['candidates'][0];moved=copy.deepcopy(model);moved['floors'][0]['cells'][0]['x']+=100
 checks=validate_general(moved,b)
 assert next(c for c in checks if c['check_id']=='GF-massing-connected')['status']=='FAIL'


def test_trimming_keeps_perpendicular_corridor_junction():
 halls=[box(0,0,8,1.5,'corridor'),box(6.5,1.5,1.5,12,'corridor')]
 rooms=[box(8,6,4,4)]
 trimmed=trim_corridor_tails(halls,rooms)
 assert trimmed[1]['y']==1.5
 assert trimmed[1]['depth']==8.5
 assert measures(trimmed+rooms)['components']==1
