"""Reproducible V3 compatibility vs V4 geometry/export matrix, synthetic inputs.

Run: python -m quality_review.v4_benchmark /tmp/ant-v4-matrix
Counts are measured, not an assertion that every plot can fit the same program.
"""
import json,time,sys
from pathlib import Path
from itertools import combinations
import ezdxf
from backend.design.architect_planner import ClientIntent,generate_automatic
from backend.design.design_selection import difference
from backend.design.functional_program import validate
from backend.design.general_models import VillaBrief

CASES=[
 ('sa-small',dict(width=12,depth=18,country='SA',region='الرياض',family=4,street_edges=['bottom'],floors='two')),
 ('ye-one-floor',dict(width=16,depth=24,country='YE',region='تعز',family=3,street_edges=['right'],main_street='right',north_edge='right',floors='one')),
 ('sa-corner',dict(width=20,depth=25,country='SA',region='مكة المكرمة',family=6,street_edges=['bottom','left'],street_widths={'bottom':15,'left':15},accessible_bedroom=True)),
 ('ye-medium',dict(width=24,depth=32,country='YE',region='الحديدة',family=6,street_edges=['bottom'])),
 ('sa-large',dict(width=32,depth=40,country='SA',region='المنطقة الشرقية',family=10,street_edges=['top','right'],main_street='top',north_edge='left',output_level='luxury',design_priority='prestige')),
]

def main(target):
 target=Path(target);target.mkdir(parents=True,exist_ok=True);summary=[]
 for name,data in CASES:
  intent=ClientIntent(**data);row={'id':name,'synthetic':True,'input':intent.model_dump(),'modes':{}}
  for mode in ('v3_compatibility','v4'):
   path=target/name/mode;start=time.monotonic()
   result=generate_automatic(intent,path,constitution_v2=True,generation_v3=True,generation_v4=mode=='v4')
   models=result['candidates'];files=[]
   for a,b in combinations(models,2):assert difference(a,b)['distinct']
   for m in models:
    assert not [c for c in m['checks'] if c['status']=='FAIL']
    assert sum(r['count'] for r in m['brief']['rooms'])==sum(bool(r.get('request_id')) for f in m['floors'] for r in f['rooms'])
    if intent.country=='YE':assert not any(c['check_id'].startswith('SA-') for c in m['checks'])
    if mode=='v4':assert not [c for c in validate(m,VillaBrief(**m['brief'])) if c['status']=='FAIL']
    rev=m['model_revision_id'];doc=ezdxf.readfile(path/(rev+'.dxf'));assert doc.dxfversion=='AC1024' and doc.header['$INSUNITS']==6 and not doc.audit().errors
    assert not list(doc.modelspace().query('HATCH SOLID'))
    assert (path/(rev+'.pdf')).read_bytes().startswith(b'%PDF')
    saved=json.loads((path/(rev+'.json')).read_text());assert saved['geometry_sha256']==m['geometry_sha256']
    files.append({'candidate':m['candidate_id'],'revision':rev,'pdf':str(path/(rev+'.pdf')),'dxf':str(path/(rev+'.dxf')),
                  'score':m['design_evaluation']['heuristic_score'],'metrics':m['design_evaluation']['metrics']})
   row['modes'][mode]={'seconds':round(time.monotonic()-start,2),'valid_distinct':len(models),'unavailable':result['unavailable'],'samples':files}
   (path/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
   print(json.dumps({'case':name,'mode':mode,'count':len(models),'seconds':row['modes'][mode]['seconds']},ensure_ascii=False),flush=True)
  summary.append(row);(target/'matrix.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
 return summary

if __name__=='__main__':main(sys.argv[1] if len(sys.argv)>1 else '/tmp/ant-v4-matrix')
