"""Independent experimental hub-fork vs existing cluster architecture benchmark.

Generates only conceptual room/hall rectangles. No furniture, door geometry,
PDF/DXF, legal certification or automatic deployment.
"""
from __future__ import annotations
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.design.general_models import VillaBrief
from backend.design.general_engine import search,expanded_program
from assl.architecture_preview import render_concept_svg


def _measure(result):
    if result is None:return None
    q=result['architectural_quality']
    return dict(architecture_score=q['architecture_score'],
                gross_rectangles_m2=q['gross_rectangles_m2'],
                hall_rectangle_area_m2=q['hall_rectangle_area_m2'],
                hall_union_area_m2=q['hall_union_area_m2'],
                max_straight_run_m=max((v['max_straight_run_m']
                                       for v in q['corridor_topology']),default=0),
                hall_components=[v['components'] for v in q['corridor_topology']],
                functional_closeness_penalty=q['functional_closeness_penalty'],
                hard_issues=q['hard_issues'])


def _option(result):
    return {'family':'hub_fork',
            'quality':result['architectural_quality'],
            'rooms_by_floor':[[dict(r) for r in floor
                               if r.get('request_id') or r.get('guest_distributor')
                               or r.get('kind')=='stair'] for floor in result['floors']],
            'halls_by_floor':result['halls_by_floor']}


def _program_integrity(brief,result):
    expected=[sorted(r['id'] for r in expanded_program(brief,i))
              for i in range(brief.floors)]
    actual=[sorted(r['id'] for r in floor if r.get('request_id'))
            for floor in result['floors']]
    if actual!=expected:
        return {'pass':False,'error':'ROOM_PROGRAM_CHANGED','expected':expected,'actual':actual}
    stairs=[[r for r in floor if r.get('kind')=='stair']
             for floor in result['floors']]
    if brief.floors==2 and (
        any(len(stairs_on_floor)!=1 for stairs_on_floor in stairs) or
        any(any(abs(stairs[0][0][key]-others[0][key])>1e-5
                for key in ('x','y','width','depth')) for others in stairs[1:])
    ):
        return {'pass':False,'error':'STAIR_CORES_MISALIGNED'}
    return {'pass':True,'program_room_count':sum(map(len,expected))}


def run(fixtures,out_dir):
    briefs=json.loads(Path(fixtures).read_text(encoding='utf-8'))['cases']
    output=Path(out_dir);output.mkdir(parents=True,exist_ok=True)
    rows=[]
    for item in briefs:
        brief=VillaBrief.model_validate(item['brief'])
        start=time.monotonic()
        target=search(brief,'hub_fork',policy='relationship_aware',
                      architecture_first=True)
        elapsed=round(time.monotonic()-start,2)
        baseline=search(brief,'cluster',policy='relationship_aware',
                        architecture_first=True)
        case_folder=output/item['id'];case_folder.mkdir(exist_ok=True)
        row=dict(case=item['id'],target_family='hub_fork',
                 baseline_family='cluster',
                 generation_seconds=elapsed,
                 furniture_used=False,doors_verified=False,
                 verified_compliant_with_code=False,
                 hub_fork=_measure(target),
                 cluster_baseline=_measure(baseline))
        if target:
            row['program_integrity']=_program_integrity(brief,target)
            render=render_concept_svg(_option(target),
               title=f"{item['id']} | offset hubs | preliminary only")
            (case_folder/'hub_fork_concept.svg').write_text(render,encoding='utf-8')
            row['status']='PRELIMINARY_CANDIDATE' if row['program_integrity']['pass'] else 'INVALID_PROGRAM'
        else:
            row['status']='NO_FEASIBLE_HUB_TOPOLOGY'
        rows.append(row)
        (case_folder/'result.json').write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding='utf-8')
        print(item['id'],row['status'],
              'hub_hall_union',row['hub_fork']['hall_union_area_m2'] if target else '?',
              'cluster_hall_union',row['cluster_baseline']['hall_union_area_m2'] if baseline else '?',
              flush=True)
    report=dict(stage='CONCEPT_TOPOLOGY_ONLY',production_unchanged=True,
                candidates=sum(r['hub_fork'] is not None for r in rows),
                tested=len(rows),cases=rows)
    (output/'hub_fork_summary.json').write_text(
        json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report

if __name__=='__main__':
    path=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'tests/fixtures/assl_architecture_cases.json'
    output=Path(sys.argv[2]) if len(sys.argv)>2 else ROOT/'architecture-hub-experiment'
    report=run(path,output)
    if any(row['status']!='PRELIMINARY_CANDIDATE' for row in report['cases']):
        raise SystemExit('HUB_FORK_NOT_FEASIBLE_FOR_ALL_TEST_CASES: see hub_fork_summary.json')
