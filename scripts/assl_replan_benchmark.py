"""Fresh 009 generation followed by measured 010 corrections; never accept residual defects."""
import sys,json,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.design.general_models import VillaBrief
from assl.replan_010 import replan
from assl.openings_preview_009 import draw
from assl.topology_options import structural_evidence,compare_structural_evidence

def run(out,source009=None):
 from scripts.assl_openings_benchmark import run as generate009
 out=Path(out);out.mkdir(parents=True,exist_ok=True)
 if source009 is None:source009=out/'generated009';generate009(ROOT/'tests/fixtures/assl_architecture_cases.json',source009)
 cases=json.loads((ROOT/'tests/fixtures/assl_architecture_cases.json').read_text())['cases'];rows=[]
 for case in cases:
  b=VillaBrief.model_validate(case['brief']);group=[];d=out/case['id'];d.mkdir(exist_ok=True)
  for path in sorted((Path(source009)/'after'/case['id']).glob('concept_*.json')):
   old=json.loads(path.read_text());start=time.monotonic();result=replan(b,old,budget=30)
   (d/path.name).write_text(json.dumps(result,ensure_ascii=False,indent=2));draw(b,old,d/(path.stem+'-before.pdf'),status='009 baseline');draw(b,result['best'],d/(path.stem+'-after.pdf'),status=result['status'])
   result['case']=case['id'];result['alternative']=path.stem;result['seconds']=time.monotonic()-start
   group.append(result);print(case['id'],path.stem,result['status'],sum(h['accepted'] for h in result['history']),len(result['after']['defects']),flush=True)
  evidence=[structural_evidence(r['best']['rooms_by_floor'],r['best']['halls_by_floor'],r['best']['topology_style'],b.entrance_face) for r in group]
  diversity=all(compare_structural_evidence(a,bb)['different_measured_geometry'] for i,a in enumerate(evidence) for bb in evidence[i+1:])
  if not diversity:
   for r in group:r['status']='REJECT_AND_REPLAN_UNRESOLVED';r['portfolio_issue']='DIVERSITY_NOT_PROVEN'
  # Persist only final portfolio decisions; no ACCEPT survives diversity rejection.
  for result in group:
   name=result['alternative']
   (d/(name+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2))
   draw(b,result['best'],d/(name+'-after.pdf'),status=result['status'])
  rows.append(dict(case=case['id'],diversity=diversity,alternatives=group))
 report=dict(cases=rows,accepted=sum(a['status']=='ACCEPT' for c in rows for a in c['alternatives']),total=9,legal='UNRESOLVED')
 report['recommendation']='READY_FOR_REVIEW' if report['accepted']==9 else 'NEEDS_MORE_DEVELOPMENT'
 (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));return report
if __name__=='__main__':run(sys.argv[1],sys.argv[2] if len(sys.argv)>2 else None)
