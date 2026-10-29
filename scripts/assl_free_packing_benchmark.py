"""Three-program before/after real architecture-only constraint solver benchmark.

Unlike historical re-ranking, this constructs NEW room coordinates with a
bounded free-placement search, and compares them with the previous cluster
family without changing or deploying production. Failure cases are explicit.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from backend.design.general_models import VillaBrief
from backend.design.general_engine import search
from assl.free_layout_solver import solve_free_concepts
from assl.architecture_preview import render_concept_svg


def baseline_report(brief):
    candidate=search(brief,'cluster',policy='relationship_aware',
                     architecture_first=True)
    return candidate['architectural_quality'] if candidate else None


def summarize(q):
    if not q:return None
    return {'hall_union_m2':q.get('hall_union_area_m2'),
            'gross_rectangles_m2':q.get('gross_rectangles_m2'),
            'architectural_score':q.get('architecture_score'),
            'longest_straight_hall_run_m':max(
                [r['max_straight_run_m'] for r in q.get('corridor_topology',[])],
                default=None),
            'functional_closeness_penalty':q.get('functional_closeness_penalty'),
            'critical_issues':q.get('hard_issues',[]),
            'direct_facade_only_potential':q.get('external_facade_only_potential')}


def run(fixtures,destination):
    cases=json.loads(Path(fixtures).read_text(encoding='utf8'))['cases']
    out=Path(destination);out.mkdir(parents=True,exist_ok=True)
    reports=[]
    for case in cases:
        name=case['id'];brief=VillaBrief.model_validate(case['brief'])
        begin=time.monotonic()
        results=solve_free_concepts(brief,seeds=range(9),max_results=3)
        elapsed=round(time.monotonic()-begin,2)
        baseline=baseline_report(brief)
        case_out=out/name;case_out.mkdir(exist_ok=True)
        for n,option in enumerate(results['proposals'],1):
            (case_out/f'free_concept_{n}.svg').write_text(
                render_concept_svg(option,title=f'{name} — free constraints #{n}'),
                encoding='utf8')
        row={
            'case':name,'engine':'independent_free_constraint_packing',
            'runtime_seconds':elapsed,
            'baseline_cluster':summarize(baseline),
            'free_candidate_count':len(results['proposals']),
            'valid_found':results['valid_found'],
            'free_candidates':[summarize(o['quality'])
                               for o in results['proposals']],
            'failure_reasons':results['rejected_seeds'],
            'same_customer_program':results['program_integrity_gate'],
            'stair_position_consistency':results['stair_consistency_gate'],
            'furniture_used':False,
            'not_construction_ready':True,
            'doors_windows_actual_access_verified':False,
        }
        if baseline and results['proposals']:
            old=baseline.get('hall_union_area_m2',0)
            new=results['proposals'][0]['quality'].get('hall_union_area_m2',0)
            row['hall_union_saved_vs_cluster_m2']=round(old-new,4)
            row['architectural_score_change']=round(
                results['proposals'][0]['quality']['architecture_score']-
                baseline['architecture_score'],4)
        (case_out/'comparison.json').write_text(
            json.dumps(row,ensure_ascii=False,indent=2),encoding='utf8')
        reports.append(row)
        print(name,'valid',len(results['proposals']),
              'hall_diff',row.get('hall_union_saved_vs_cluster_m2'),
              'rejections',[x['reason'] for x in results['rejected_seeds'][:3]],
              flush=True)
    report={'stage':'PRE_FURNITURE_CONSTRAINT_SEARCH',
            'baseline_family':'cluster',
            'production_modified':False,
            'cases':reports}
    (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    return report


if __name__=='__main__':
    fixture=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'tests/fixtures/assl_architecture_cases.json'
    folder=Path(sys.argv[2]) if len(sys.argv)>2 else ROOT/'free-packing-benchmark'
    result=run(fixture,folder)
    if not all(row['free_candidate_count']>=1 for row in result['cases']):
        raise SystemExit('FREE_PACKING_HAS_UNSOLVED_PROGRAM: inspect summary and rejection diagnostics')
