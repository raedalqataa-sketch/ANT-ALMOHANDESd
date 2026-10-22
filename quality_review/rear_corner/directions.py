"""Exercise actual automatic generation for each main street edge."""
import json,tempfile
from pathlib import Path
from backend.design.architect_planner import ClientIntent,generate_automatic
from backend.design.site_placement import OPPOSITE
rows=[]
for edge,face in [('top','north'),('bottom','south'),('left','west'),('right','east')]:
 with tempfile.TemporaryDirectory() as out:
  result=generate_automatic(ClientIntent(width=32,depth=36,city='الرياض',family=6,street_edges=[edge],main_street=edge),Path(out))
  assert len(result['candidates'])==3
  for m in result['candidates']:
   p=m['site_placement']
   assert p['active'] and p['rear_face']==OPPOSITE[face] and face not in p['anchor_faces']
   assert m['release']['drawing_export_allowed'],[(c['check_id'],c['status']) for c in m['checks'] if c['status']=='FAIL']
   rows.append({'street_edge':edge,'front_face':face,'pattern':m['candidate_id'],'anchor_faces':p['anchor_faces'],'clearances_m':p['actual_clearances_m'],'failed_checks':[],'executive_approved':False})
print(json.dumps({'actual_directional_generation':rows},ensure_ascii=False,indent=2))
