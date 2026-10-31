"""Reproducible012 comparison on explicit verified011 coordinates.

Freshly computed group proposals, not a rerank of archived alternatives.
The011 source is explicit, hashed and revalidated before each experiment.
"""
import sys,json,time,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.design.general_models import VillaBrief
from assl.functional_groups_012 import replan,residual_diagnostic
from assl.openings_preview_009 import draw
from assl.topology_options import structural_evidence,compare_structural_evidence


def run(out,baseline,case_ids=('ye-medium',),max_validations=48):
    cases=json.loads((ROOT/'tests/fixtures/assl_architecture_cases.json').read_text())['cases']
    if not case_ids or len(set(case_ids))!=len(case_ids) or not set(case_ids)<=set(c['id'] for c in cases):
        raise ValueError('Unknown, duplicate or empty case selection')
    out=Path(out);baseline=Path(baseline)
    if out.exists() and any(out.iterdir()):raise ValueError('Output must be empty')
    out.mkdir(parents=True,exist_ok=True)
    rows=[]
    for case in cases:
        if case['id'] not in case_ids:continue
        brief=VillaBrief.model_validate(case['brief']);dest=out/case['id'];dest.mkdir();group=[]
        paths=sorted((baseline/case['id']).glob('concept_*.json'))
        if len(paths)!=3:raise ValueError('Expected exactly three baseline alternatives')
        for path in paths:
            saved=json.loads(path.read_text());source=saved['best'];start=time.monotonic()
            result=replan(brief,source,max_validations=max_validations,beam_width=6)
            result.update(case=case['id'],alternative=path.stem,source=source,seconds=time.monotonic()-start,
                          baseline_file_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),reference_baseline_code_commit='5242446d50fec2b72ea692af498d336780e9eb41',baseline_provenance='explicit input snapshot hash; reference commit is not independently attested by this runner')
            result['residual_before']=[residual_diagnostic(rs+hs) for rs,hs in zip(source['rooms_by_floor'],source['halls_by_floor'])]
            result['residual_after']=[residual_diagnostic(rs+hs) for rs,hs in zip(result['best']['rooms_by_floor'],result['best']['halls_by_floor'])]
            group.append(result)
            print(case['id'],path.stem,result['status'],result['statistics'],'seconds',round(result['seconds'],2),flush=True)
        evidence=[structural_evidence(a['best']['rooms_by_floor'],a['best']['halls_by_floor'],a['best']['topology_style'],brief.entrance_face) for a in group]
        diversity=all(compare_structural_evidence(a,b)['different_measured_geometry'] for i,a in enumerate(evidence) for b in evidence[i+1:])
        for a in group:
            if not diversity:a['status']='REJECT_AND_REPLAN_UNRESOLVED';a['portfolio_issue']='DIVERSITY_NOT_PROVEN'
            name=a['alternative'];(dest/(name+'.json')).write_text(json.dumps(a,ensure_ascii=False,indent=2))
            draw(brief,a['source'],dest/(name+'-before.pdf'),status='011 verified baseline')
            draw(brief,a['best'],dest/(name+'-after.pdf'),status='012 '+a['status'])
        rows.append(dict(case=case['id'],diversity=diversity,alternatives=group))
    result=dict(cases=rows,accepted=sum(a['status']=='ACCEPT' for c in rows for a in c['alternatives']),total=sum(len(c['alternatives']) for c in rows),
                improved=sum(a['original_hash']!=a['final_hash'] for c in rows for a in c['alternatives']),legal='UNRESOLVED')
    result['recommendation']='READY_FOR_ARCHITECTURAL_REVIEW' if result['accepted']==result['total'] else 'PARTIALLY_IMPROVED' if result['improved'] else 'NEEDS_MORE_DEVELOPMENT'
    (out/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));return result

if __name__=='__main__':run(sys.argv[1],sys.argv[2],tuple(sys.argv[3].split(',')) if len(sys.argv)>3 else ('ye-medium',))
