"""Architectural before/after evidence for optional pre-layout functional grouping.

No furniture, PDF/DXF, actual openings or legal certification. Runs exactly
the same synthetic three brief programs and cluster family in both modes.
"""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.design.general_models import VillaBrief
from backend.design.general_engine import search,expanded_program
from assl.architectural_composer import spatial_signature
from assl.architecture_preview import render_concept_svg


def snapshot(candidate):
    if candidate is None:return None
    q=candidate['architectural_quality']
    return {'score':q['architecture_score'],
            'gross_rectangles_m2':q['gross_rectangles_m2'],
            'hall_union_m2':q['hall_union_area_m2'],
            'functional_closeness_penalty':q['functional_closeness_penalty'],
            'max_hall_run_m':max([m['max_straight_run_m'] for m in q['corridor_topology']],default=0),
            'hard_issues':q['hard_issues']}


def integrity(brief,candidate):
    if not candidate:return False
    return all(sorted(r['id'] for r in expanded_program(brief,i))==
               sorted(r['id'] for r in floor if r.get('request_id'))
               for i,floor in enumerate(candidate['floors']))


def svg_option(family,c):
    return {'family':family,'quality':c['architectural_quality'],
            'rooms_by_floor':[[dict(r) for r in floor if r.get('request_id') or
                               r.get('guest_distributor') or r.get('kind')=='stair']
                              for floor in c['floors']],
            'halls_by_floor':c['halls_by_floor']}


def run(fixtures,out_dir):
    cases=json.loads(Path(fixtures).read_text(encoding='utf-8'))['cases']
    out=Path(out_dir);out.mkdir(parents=True,exist_ok=True)
    rows=[]
    for item in cases:
        brief=VillaBrief.model_validate(item['brief'])
        baseline=search(brief,'cluster',policy='relationship_aware',
                        architecture_first=True,relationship_pack=False)
        grouped=search(brief,'cluster',policy='relationship_aware',
                       architecture_first=True,relationship_pack=True)
        before,after=snapshot(baseline),snapshot(grouped)
        valid=integrity(brief,grouped)
        changed=bool(baseline and grouped and
                     spatial_signature(baseline)!=spatial_signature(grouped))
        row={'case':item['id'],'mode':'GEOMETRY_ONLY',
             'before':before,'after':after,
             'full_program_preserved':valid,'topology_changed':changed,
             'actual_doors_verified':False,'furniture_used':False}
        if not grouped or not valid:
            row['status']='REJECTED'
        elif not baseline:
            row['status']='NEW_FEASIBLE_CANDIDATE'
        else:
            gains=(before['score']-after['score'],
                   before['hall_union_m2']-after['hall_union_m2'],
                   before['functional_closeness_penalty']-after['functional_closeness_penalty'])
            row['deltas']={
                'score_improvement':round(gains[0],4),
                'hall_union_saved_m2':round(gains[1],4),
                'functional_relation_penalty_improvement':round(gains[2],4)}
            row['status']='IMPROVED' if gains[0]>1e-5 else (
                'EQUAL' if abs(gains[0])<=1e-5 else 'REGRESSED')
        caseout=out/item['id'];caseout.mkdir(exist_ok=True)
        for label,c in (('before',baseline),('after',grouped)):
            if c:
                (caseout/(label+'.svg')).write_text(
                    render_concept_svg(svg_option('cluster',c),
                       title=item['id']+' — '+label+' grouping concept'),
                    encoding='utf-8')
        (caseout/'comparison.json').write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding='utf-8')
        print(item['id'],row['status'],row.get('deltas',{}),flush=True)
        rows.append(row)
    result={'stage':'PRE_FURNITURE_FUNCTIONAL_GROUPING','rows':rows,
            'no_production_changes':True}
    (out/'functional_graph_summary.json').write_text(
        json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result

if __name__=='__main__':
    path=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'tests/fixtures/assl_architecture_cases.json'
    out=Path(sys.argv[2]) if len(sys.argv)>2 else ROOT/'function-graph-benchmark'
    r=run(path,out)
    if any(row['status']=='REJECTED' for row in r['rows']):
        raise SystemExit('FUNCTIONAL_GRAPH_REJECTED: some program not preserved')
    if not any(row['status']=='IMPROVED' for row in r['rows']):
        raise SystemExit('FUNCTIONAL_GRAPH_NO_MEASURED_IMPROVEMENT: report saved for review')
