"""Offline paired replay; no credentials, inference, production writes or mock proof.

python -m quality_review.intelligence_004.benchmark --output /tmp/ant-004 --budget 12
"""
import argparse
import copy
import hashlib
import json
import statistics
from pathlib import Path
import ezdxf
from pypdf import PdfReader
from shapely.geometry import mapping
from backend.design.architect_planner import ClientIntent
from backend.design.intelligence.engine import run
from backend.design.intelligence.metrics import inspect
from backend.design.intelligence.topology import rect
from quality_review.v4_benchmark import CASES


def summary(model):
    d=model.get('architecture_intelligence') or inspect(model)
    return dict(candidate=model['candidate_id'],revision=model['model_revision_id'],geometry_sha256=model['geometry_sha256'],metrics=d,
                checks={s:sum(c['status']==s for c in model['checks']) for s in ('PASS','FAIL','PENDING','REVIEW')})


def distributions(models):
    rows=[summary(m)['metrics'] for m in models]
    fields=['circulation_union_m2_total','gross_floor_area_m2','longest_required_travel_path_m','net_usable_room_area_m2']
    return {k:dict(values=[r[k] for r in rows],median=statistics.median(r[k] for r in rows),minimum=min(r[k] for r in rows),maximum=max(r[k] for r in rows)) for k in fields} if rows else {}


def changed_polygons(before,after):
    features=[]
    for f in before['floors']:
        other=next((g for g in after['floors'] if g['id']==f['id']),None)
        if not other:continue
        a={r['request_id']+':'+r['id'].rsplit('-',1)[-1]:r for r in f['rooms'] if r.get('request_id')}
        b={r['request_id']+':'+r['id'].rsplit('-',1)[-1]:r for r in other['rooms'] if r.get('request_id')}
        for key in a.keys()&b.keys():
            for change,geometry in [('released',rect(a[key]).difference(rect(b[key]))),('assigned',rect(b[key]).difference(rect(a[key])))]:
                if geometry.is_empty:continue
                features.append(dict(type='Feature',properties=dict(floor=f['id'],room=key,change=change,area_m2=round(geometry.area,5),scope='rank-paired alternative, not claim of single local edit'),geometry=mapping(geometry)))
    return dict(type='FeatureCollection',features=features)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--budget',type=int,default=12);parser.add_argument('--case',default='all');parser.add_argument('--ablation',action='store_true');args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    cases={'sa600':json.loads(Path('quality_review/gemini_sa600_case.json').read_text())['intent']}
    cases.update({n:d for n,d in CASES if n in ('ye-medium','sa-corner')})
    if args.case!='all':cases={args.case:cases[args.case]}
    rows=[]
    for name,data in cases.items():
        print('START',name,flush=True);intent=ClientIntent.model_validate(data);target=args.output/name
        result=run(intent,target,budget=args.budget)
        before=result['baseline_candidates'];after=result['candidates'];exports=[]
        for model in after:
            rev=model['model_revision_id'];doc=ezdxf.readfile(target/(rev+'.dxf'));pdf=PdfReader(target/(rev+'.pdf'))
            assert not doc.audit().errors and doc.header['$INSUNITS']==6 and len(pdf.pages)==5
            saved=json.loads((target/(rev+'.json')).read_text());assert saved['geometry_sha256']==model['geometry_sha256']
            exports.append(dict(revision=rev,pdf_pages=len(pdf.pages),dxf_errors=0,units='metres',geometry_sha256=model['geometry_sha256'],export_audit=model.get('export_audit')))
        row=dict(case=name,input=intent.model_dump(),seed=0,baseline_sha='32be0b0',before=[summary(m) for m in before],after=[summary(m) for m in after],
            before_distribution=distributions(before),after_distribution=distributions(after),export_checks=exports,
            baseline_options_tested=6,new_options_tested=args.budget,baseline_fallback_retained=True,
            comparison_limit='identical intent/program; expanded search budget disclosed; ranked portfolios, not matched single-room edits',
            failures=result['failure_memory'],origin='LOCAL_DETERMINISTIC_ENGINE',new_api_requests=0)
        for index,(a,b) in enumerate(zip(before,after)):
            (target/f'changed-areas-rank-{index+1}.geojson').write_text(json.dumps(changed_polygons(a,b),ensure_ascii=False))
        if args.ablation:
            original=copy.deepcopy(dict(candidates=before,origin='EXISTING_ENGINE',telemetry=result['baseline_telemetry']))
            ablated=run(intent,target/'without-references',budget=args.budget,use_references=False,baseline_result=original)
            row['reference_ablation']=dict(same_program_and_budget=True,with_references=[summary(m) for m in after],without_references=[summary(m) for m in ablated['candidates']],
                distribution_without=distributions(ablated['candidates']),interpretation='catalogue-derived search/score conditioning, not trained model; original safety gates still active')
        rows.append(row);(args.output/'results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2,allow_nan=False))
        print('DONE',name,'counts',len(before),len(after),'movement',row['before_distribution'].get('circulation_union_m2_total'),row['after_distribution'].get('circulation_union_m2_total'),flush=True)
    return rows


if __name__=='__main__':main()
