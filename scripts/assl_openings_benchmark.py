"""Regenerate the unchanged 008 nine concepts, then build/validate 009 openings.
No furnishings, production integration, code certification or mocked results.
"""
import argparse,copy,json,sys,time,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.design.general_models import VillaBrief
from assl.openings_009 import revise,validate
from assl.free_layout_audit import audit_preliminary_concept
from assl.topology_options import structural_evidence,compare_structural_evidence

def run(source,destination):
 from scripts.assl_diverse_topology_benchmark import run as generate
 out=Path(destination)
 if out.exists() and any(out.iterdir()):raise ValueError('Use an empty output directory; evidence is immutable')
 out.mkdir(parents=True,exist_ok=True);generate(source,out/'before')
 return evaluate(source,out)

def evaluate(source,out):
 from assl.openings_preview_009 import draw
 cases=json.loads(Path(source).read_text())['cases'];rows=[]
 for case in cases:
  b=VillaBrief.model_validate(case['brief']);results=[]
  for path in sorted((out/'before'/case['id']).glob('concept_*.json')):
   old=json.loads(path.read_text());saved=copy.deepcopy(old);start=time.monotonic();new=revise(b,old)
   assert old==saved
   assert [[r for r in f if r['kind']=='stair'] for f in new['rooms_by_floor']]==[[r for r in f if r['kind']=='stair'] for f in old['rooms_by_floor']]
   fresh=validate(b,new);assert fresh==new['validation_009']
   directory=out/'after'/case['id'];directory.mkdir(parents=True,exist_ok=True)
   (directory/path.name).write_text(json.dumps(new,ensure_ascii=False,indent=2))
   draw(b,old,directory/(path.stem+'-before.pdf'),status='UNVERIFIED: no placed doors or windows')
   draw(b,new,directory/(path.stem+'-after.pdf'),status=fresh['status'])
   topology=structural_evidence(new['rooms_by_floor'],new['halls_by_floor'],new['topology_style'],b.entrance_face)
   record=dict(alternative=path.stem,topology=new['topology_style'],before=validate(b,old),after=fresh,
               relocations=new['relocations_009'],opening_attempts=new['repair_history_009'],
               unchanged_program=True,fixed_stair=True,preliminary_audit=audit_preliminary_concept(b,new),
               topology_evidence=topology,seconds=round(time.monotonic()-start,3),
               input_sha256=hashlib.sha256(json.dumps(case['brief'],sort_keys=True).encode()).hexdigest())
   results.append(record);print(case['id'],path.stem,fresh['status'],fresh['issues'],flush=True)
  pair=[compare_structural_evidence(a['topology_evidence'],b['topology_evidence']) for i,a in enumerate(results) for b in results[i+1:]]
  rows.append(dict(case=case['id'],alternatives=results,passed=sum(r['after']['status']=='PASS' for r in results),
                   geometric_diversity_preserved=len(pair)==3 and all(p['different_measured_geometry'] for p in pair),pairwise=pair))
 report=dict(stage='009',cases=rows,total=9,passed=sum(c['passed'] for c in rows),
             legal_compliance='UNRESOLVED',furniture_used=False,production_changed=False)
 report['recommendation']='READY_FOR_REVIEW' if report['passed']==9 and all(c['geometric_diversity_preserved'] for c in rows) else 'NEEDS_MORE_DEVELOPMENT'
 (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));return report

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('destination',type=Path);p.add_argument('--reuse-current-before',action='store_true',help='Only reuse the documented local generation from this experiment')
 a=p.parse_args();source=ROOT/'tests/fixtures/assl_architecture_cases.json'
 evaluate(source,a.destination) if a.reuse_current_before else run(source,a.destination)
