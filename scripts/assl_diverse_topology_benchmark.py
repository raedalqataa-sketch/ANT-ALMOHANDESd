"""Test structural—not cosmetic—diversity of independent room-first layouts.

Regenerates three physical geometric hall graphs, verifies via a separate
auditor and publishes original coordinates/preview for each. No furniture,
actual door/window validation, construction approval or production merge.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import time
from collections import Counter

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from backend.design.general_models import VillaBrief
from backend.design.general_engine import search
from assl.architectural_composer import spatial_signature
from assl.architecture_preview import render_concept_svg
from assl.free_layout_audit import audit_preliminary_concept
from assl.free_layout_solver import solve_free_concepts
from assl.topology_options import compare_structural_evidence
from assl.room_arrangement_diversity import compare_room_arrangements,difference_passes


STYLES=('axial','elbow','split_hub')
SEEDS=range(9)


def orientation_check(brief,option):
    # The family-entry spur must reach the buildable boundary associated
    # with the requested street face, not an invented southern frontage.
    width=brief.plot_width-brief.setbacks.east-brief.setbacks.west-brief.wall_thickness
    depth=brief.plot_depth-brief.setbacks.north-brief.setbacks.south-brief.wall_thickness
    opening=next((r for r in option['halls_by_floor'][0]
                  if r.get('id')=='family-entry-spur'),None)
    if opening is None:
        return {'pass':False,'reason':'FAMILY_ENTRY_SPUR_NOT_RESERVED'}
    tolerance=1e-5
    tests={
        'south':abs(opening['y'])<tolerance,
        'north':abs(opening['y']+opening['depth']-depth)<tolerance,
        'east':abs(opening['x']+opening['width']-width)<tolerance,
        'west':abs(opening['x'])<tolerance,
    }
    return {'pass':tests[brief.entrance_face],
            'street_face':brief.entrance_face,
            'test_type':'buildable_boundary_exposure_only',
            'actual_street_or_gate_access_verified':False}


def info(option):
    q=option['quality']
    return {'style':option['topology_style'],
            'room_signature':option['structural_signature'],
            'hall_union_m2':q['hall_union_area_m2'],
            'gross_rectangles_m2':q['gross_rectangles_m2'],
            'functional_penalty':q['functional_closeness_penalty'],
            'max_straight_run_m':max((h['max_straight_run_m']
                                      for h in q['corridor_topology']),default=0.),
            'architecture_score':q['architecture_score'],
            'topology_graph':option['topology_evidence']}


def run(fixture,destination):
    cases=json.loads(Path(fixture).read_text(encoding='utf-8'))['cases']
    out=Path(destination)
    out.mkdir(parents=True,exist_ok=True)
    results=[]
    for item in cases:
        brief=VillaBrief.model_validate(item['brief'])
        start=time.monotonic()
        data=solve_free_concepts(brief,seeds=SEEDS,max_results=3,
             topologies=STYLES,orient_to_frontage=True,
             require_room_diversity=True)
        case_dir=out/item['id']
        case_dir.mkdir(exist_ok=True)
        accepted=[];rejected=[]
        for idx,option in enumerate(data['proposals'],1):
            audit=audit_preliminary_concept(brief,option)
            entrance=orientation_check(brief,option)
            active=option['topology_evidence']['distinctive_nodes_actually_serve_rooms']
            valid=(audit['status']=='PRELIMINARY_CONSISTENT'
                   and entrance['pass'] and active)
            record={'position':idx,'summary':info(option),
                    'independent_qa':audit,'orientation':entrance,
                    'distinctive_corridor_nodes_used':active,
                    'accepted':valid}
            if valid:accepted.append(record)
            else:rejected.append(record)
            (case_dir/f'concept_{idx}.svg').write_text(render_concept_svg(
                option,title=f"{item['id']} | {option['topology_style']} | {idx}"),
                encoding='utf-8')
            (case_dir/f'concept_{idx}.json').write_text(
                json.dumps(option,ensure_ascii=False,indent=2),encoding='utf-8')
        styles=[r['summary']['style'] for r in accepted]
        room_pairwise=data.get('room_diversity_selection',{}).get('comparisons',[])
        room_diverse=(len(room_pairwise)==3 and
                      all(difference_passes(x) for x in room_pairwise))
        pairwise=[]
        for i,a in enumerate(accepted):
            for b in accepted[i+1:]:
                evidence=compare_structural_evidence(
                    a['summary']['topology_graph'],b['summary']['topology_graph'])
                pairwise.append({'between':[a['summary']['style'],
                                            b['summary']['style']],
                                 **evidence})
        meaningful=(len(accepted)==3 and len(set(styles))==3
                    and len(pairwise)==3
                    and all(r['different_measured_geometry']
                            for r in pairwise)
                    and room_diverse)
        baseline=search(brief,'cluster',policy='relationship_aware',
                        architecture_first=True)
        baseline_hall=baseline['architectural_quality']['hall_union_area_m2'] if baseline else None
        rows={'case':item['id'],'requested_three_distinct':True,
              'accepted_count':len(accepted),
              'accepted_styles':styles,
              'styles_with_candidates':data['topology_availability'],
              'measured_structural_diversity':meaningful,
              'pairwise_graph_differences':pairwise,
              'pairwise_room_rearrangement':room_pairwise,
              'strong_room_arrangement_difference':room_diverse,
              'diversity_selection_diagnostics':data.get('room_diversity_selection',{}),
              'accepted':accepted,'rejected':rejected,
              'baseline_cluster_hall_union_m2':baseline_hall,
              'candidate_failure_reasons':data['rejected_seeds'],
              'elapsed_seconds':round(time.monotonic()-start,2),
              'furniture_used':False,'real_entrances_certified':False,
              'exterior_windows_or_ventilation_certified':False,
              'legally_approved':False}
        (case_dir/'verification.json').write_text(json.dumps(
            rows,ensure_ascii=False,indent=2),encoding='utf-8')
        results.append(rows)
        print(item['id'],'accepted',len(accepted),
              'styles',styles,'distinct_geometric_graph',meaningful,
              'available',data['topology_availability'],flush=True)
    document={'stage':'PRELIMINARY_THREE_CORE_GEOMETRIC_SEARCH',
              'all_three_cases_have_three':all(x['measured_structural_diversity']
                                               for x in results),
              'production_deployed':False,'cases':results}
    (out/'summary.json').write_text(json.dumps(
        document,ensure_ascii=False,indent=2),encoding='utf-8')
    return document


if __name__=='__main__':
    source=(Path(sys.argv[1]) if len(sys.argv)>1
            else ROOT/'tests/fixtures/assl_architecture_cases.json')
    dest=(Path(sys.argv[2]) if len(sys.argv)>2
          else ROOT/'diverse-topology-evidence')
    result=run(source,dest)
    if not result['all_three_cases_have_three']:
        raise SystemExit(
            'THREE_STRUCTURALLY_DIFFERENT_ACCEPTED_CONCEPTS_NOT_ACHIEVED: see summary.json')
