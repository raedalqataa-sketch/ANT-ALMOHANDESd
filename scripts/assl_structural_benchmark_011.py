"""Fresh010 baseline or explicit verified010 coordinates, followed by011."""
import sys,json,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.design.general_models import VillaBrief
from assl.structural_replanner_011 import replan,circulation_function_review
from assl.openings_preview_009 import draw
from assl.topology_options import structural_evidence,compare_structural_evidence

def run(out,baseline=None):
 out=Path(out)
 if out.exists() and any(out.iterdir()):raise ValueError('Output must be empty')
 out.mkdir(parents=True)
 if baseline is None:
  from scripts.assl_replan_benchmark import run as generate
  baseline=out/'baseline010';generate(baseline)
 baseline=Path(baseline);cases=json.loads((ROOT/'tests/fixtures/assl_architecture_cases.json').read_text())['cases'];rows=[]
 for case in cases:
  brief=VillaBrief.model_validate(case['brief']);group=[];d=out/case['id'];d.mkdir()
  for path in sorted((baseline/case['id']).glob('concept_*.json')):
   old=json.loads(path.read_text())['best'];start=time.monotonic();result=replan(brief,old,per_class=4)
   result['circulation_function_review']=circulation_function_review(brief,result['best'])
   result.update(case=case['id'],alternative=path.stem,seconds=time.monotonic()-start,source=old)
   group.append(result);print(case['id'],path.stem,result['status'],{k:v.get('accepted',0) for k,v in result['categories'].items()},flush=True)
  evidence=[structural_evidence(r['best']['rooms_by_floor'],r['best']['halls_by_floor'],r['best']['topology_style'],brief.entrance_face) for r in group]
  diverse=all(compare_structural_evidence(a,b)['different_measured_geometry'] for i,a in enumerate(evidence) for b in evidence[i+1:])
  if not diverse:
   for result in group:result['status']='REJECT_AND_REPLAN_UNRESOLVED';result['portfolio_issue']='DIVERSITY_NOT_PROVEN'
  for result in group:
   name=result['alternative'];(d/(name+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2));draw(brief,result['source'],d/(name+'-before.pdf'),status='010 baseline');draw(brief,result['best'],d/(name+'-after.pdf'),status=result['status'])
  rows.append(dict(case=case['id'],diversity=diverse,alternatives=group))
 report=dict(cases=rows,accepted=sum(a['status']=='ACCEPT' for c in rows for a in c['alternatives']),total=9,legal='UNRESOLVED')
 report['recommendation']='READY_FOR_ARCHITECTURAL_REVIEW' if report['accepted']==9 else 'PARTIALLY_IMPROVED' if any(a['original_hash']!=a['final_hash'] for c in rows for a in c['alternatives']) else 'NEEDS_MORE_DEVELOPMENT'
 (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));return report
if __name__=='__main__':run(sys.argv[1],sys.argv[2] if len(sys.argv)>2 else None)
