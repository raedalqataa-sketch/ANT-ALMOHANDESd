import json
import pytest
from backend.design.architect_planner import ClientIntent,propose,generate_automatic
from backend.design.site_placement import alternatives,recheck,OPPOSITE

@pytest.mark.parametrize('face',['north','south','east','west'])
def test_corner_pair_uses_all_floor_bounds_and_opposite_entrance(face):
 b,_=propose(ClientIntent(width=30,depth=36,city='الرياض',street_edges=['bottom'],family=4))
 b=b.model_copy(update={'entrance_face':face})
 rooms=[{'x':2,'y':3,'width':8,'depth':9}]
 layout={'floors':[rooms,[{'x':1,'y':2,'width':10,'depth':11}]],'halls':[],'halls_by_floor':[[],[]]}
 pair=alternatives(b,layout,7)
 assert len(pair)==2 and pair[0]['site_placement']['anchor_faces']!=pair[1]['site_placement']['anchor_faces']
 for variant in pair:
  meta=variant['site_placement'];assert meta['active'] and OPPOSITE[face] in meta['anchor_faces'] and face not in meta['anchor_faces']
  cells=[{**r,'x':r['x']+variant['origin_x']+b.wall_thickness/2,'y':r['y']+variant['origin_y']+b.wall_thickness/2} for f in layout['floors'] for r in f]
  model={'site_placement':meta,'floors':[{'cells':cells}]}
  assert recheck(model,b)['status']=='PASS'
  model['floors'][0]['cells'][0]['x']+=100
  assert recheck(model,b)['status']=='FAIL'

def test_no_corner_for_insufficient_surplus_and_legacy_unchanged():
 b,_=propose(ClientIntent(width=24,depth=32,city='الرياض',street_edges=['bottom'],family=6))
 layout={'floors':[[{'x':0,'y':0,'width':20,'depth':24}]],'halls':[]}
 assert not alternatives(b,layout,0)[0]['site_placement']['active']
 assert alternatives(b.model_copy(update={'site_placement':'legacy'}),layout,0)==[layout]
 with pytest.raises(ValueError):type(b)(**{**b.model_dump(),'site_placement':'waive_setbacks'})

def test_actual_three_proposals_are_sited_and_revalidated(tmp_path):
 result=generate_automatic(ClientIntent(width=24,depth=32,city='الرياض',street_edges=['bottom'],family=6),tmp_path)
 json.dumps(result,allow_nan=False)
 for m in result['candidates']:
  assert m['release']['drawing_export_allowed']
  b=__import__('backend.design.general_models',fromlist=['VillaBrief']).VillaBrief(**m['brief'])
  placement=m['site_placement'];assert placement['active'] and not placement['setbacks_waived']
  assert 'north' in placement['anchor_faces'] and 'south' not in placement['anchor_faces']
  assert recheck(m,b)['status']=='PASS'
  assert all(value+1e-5>=getattr(b.setbacks,face) for face,value in placement['actual_clearances_m'].items())
  assert placement['front_open_envelope']['depth']>b.setbacks.south+3
  assert 'SITE' in m['previews'] and sum(r['capacity']*r['count'] for r in m['brief']['rooms'])==6
  assert next(c for c in m['checks'] if c['check_id']=='SITE-rear-corner')['status']=='PASS'
