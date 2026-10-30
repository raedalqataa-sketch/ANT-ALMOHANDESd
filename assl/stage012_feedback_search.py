"""Experimental 012 feedback search; never bypass stages 008/009/010.

Only the Saudi corner fixture is supported. A passing MILP solve is NOT an
architecturally accepted plan. Existing 009 validators are the authority.
"""
from __future__ import annotations

import argparse
import copy
import json
from collections import Counter
from pathlib import Path

from assl import relationship_first_012 as solver
from assl.stage012_validation_gate import evaluate


def placement_key(rooms):
    """Stable identity/coordinate key; prevents rechecking identical floors."""
    return tuple(sorted((r['id'], *(round(float(r[k]), 4)
                                    for k in ('x', 'y', 'width', 'depth')))
                        for r in rooms))


def reason_codes(result):
    """Never substitute a successful assertion for a missing 009 execution."""
    reasons = []
    for item in result.get('stage008_precheck', {}).get('issues', []):
        reasons.append('008:' + str(item.get('reason', item) if isinstance(item, dict) else item))
    for item in result.get('stage009_actual_validation', {}).get('issues', []):
        reasons.append('009:' + str(item))
    critic = result.get('stage010_critic') or {}
    for item in critic.get('defects', []):
        reasons.append('010:' + str(item.get('type', 'UNKNOWN')))
    if result.get('status') == 'GATE_RUNTIME_ERROR':
        reasons.append('RUNTIME:' + result.get('error_type', 'UNKNOWN'))
    if not result.get('stage009_executed'):
        reasons.append('009:NOT_EXECUTED')
    return sorted(set(reasons))


def candidate_of(topology, halls, stair, guests, floors, reports):
    per_floor_halls = [halls, [h for h in halls if h.get('id') != 'family-entry-spur']]
    audit = solver.audit(floors, per_floor_halls, guests, stair)
    return {
        'label': 'stage012_feedback_not_architecturally_approved',
        'topology': topology,
        'rooms_by_floor': [[copy.deepcopy(stair)] + copy.deepcopy(guests) + floors[0],
                           [copy.deepcopy(stair)] + floors[1]],
        'halls_by_floor': per_floor_halls,
        'independent_audit': audit,
        'solver': reports,
        'building_envelope_m': [solver.PLOT_W, solver.PLOT_D],
        'claim_009_verified': False,
    }


def run_search(brief, baseline, *, max_layouts=12, repacks=4, seconds=1.5):
    """Apply 009/010 fail-closed feedback to bounded MILP no-good cuts.

    No-good cuts forbid exact *floor solutions*, not whole topologies or
    functional rooms. Repack alternating floors to avoid repeats while
    preserving a feasible search space. Never weaken the checker or limits.
    """
    required = [[r for r in floor if r.get('request_id') and r.get('zone') != 'guest']
                for floor in baseline['rooms_by_floor']]
    attempts, accepted = [], []
    reason_tally = Counter()
    seen_full = set()
    for layout_idx, (tag, halls, stair, guests) in enumerate(solver.layouts()):
        if layout_idx >= max_layouts:
            break
        upper_halls = [h for h in halls if h.get('id') != 'family-entry-spur']
        by_floor_halls = [halls, upper_halls]
        exclusions = [[], []]
        seen_floor = [set(), set()]
        for iteration in range(repacks):
            floors, solver_reports = [], []
            for fi in range(2):
                placement, info = solver.optimize_floor(
                    required[fi], by_floor_halls[fi], stair,
                    guests if fi == 0 else [],
                    time_limit=seconds, forbidden=exclusions[fi])
                solver_reports.append(info)
                if placement is None:
                    break
                floors.append(placement)
            record = {'topology': tag, 'layout_index': layout_idx,
                      'iteration': iteration, 'solver': solver_reports}
            if len(floors) != 2:
                record.update(status='MILP_INFEASIBLE_OR_TIMEOUT')
                attempts.append(record)
                break
            key = (tuple(tag), placement_key(floors[0]), placement_key(floors[1]))
            if key in seen_full:
                record.update(status='DUPLICATE_REJECTED')
                attempts.append(record)
            else:
                seen_full.add(key)
                proposal = candidate_of(tag, halls, stair, guests, floors, solver_reports)
                if not proposal['independent_audit']['passed_independent_geometry']:
                    reasons = ['012:' + s for s in proposal['independent_audit']['issues']]
                    record.update(status='GEOMETRY_REJECTED', reasons=reasons)
                else:
                    verdict = evaluate(brief, proposal)
                    reasons = reason_codes(verdict)
                    record.update(status=verdict['status'], reasons=reasons,
                                  stage009_executed=verdict.get('stage009_executed', False),
                                  stage009_passed=verdict.get('doors_and_body_routes_009_passed', False),
                                  stage009_issues=(verdict.get('stage009_actual_validation') or {}).get('issues', []),
                                  stage010_defects=(verdict.get('stage010_critic') or {}).get('defects', []),
                                  stage008_issues=(verdict.get('stage008_precheck') or {}).get('issues', []),
                                  revision_trials=verdict.get('revision_trials', []),
                                  geometric_metrics=proposal['independent_audit']['floors'])
                    if verdict['status'] == 'READY_FOR_ARCHITECTURAL_REVIEW':
                        # This is only a screening verdict, not legal/design approval.
                        proposal['claim_009_verified'] = True
                        proposal['verified_009_evidence'] = verdict
                        accepted.append(proposal)
                reason_tally.update(record.get('reasons', []))
                attempts.append(record)
            # Deterministic alternating 009 feedback. Each cut forbids one
            # exact floor assignment; previous room program remains intact.
            fi = iteration % 2
            floor_key = placement_key(floors[fi])
            if floor_key in seen_floor[fi]:
                attempts[-1].setdefault('diagnostic', 'ALREADY_EXCLUDED_FLOOR')
            else:
                seen_floor[fi].add(floor_key)
                exclusions[fi].append(copy.deepcopy(floors[fi]))
            if len(accepted) >= 3:
                break
        if len(accepted) >= 3:
            break
    # Distinct floor coordinates alone do NOT count as structural diversity.
    distinct_topologies = len({tuple(p['topology']) for p in accepted})
    report = {'status': 'EXPERIMENTAL_ONLY', 'stage009_required': True,
              'attempted': len(attempts), 'accepted_candidates': len(accepted),
              'distinct_topology_count': distinct_topologies,
              'three_structural_alternatives_verified': len(accepted) >= 3 and distinct_topologies >= 3,
              'diagnostic_codes': dict(reason_tally.most_common()),
              'attempts': attempts, 'furniture_used': False,
              'production_modified': False, 'legal_approval': False}
    return report, accepted


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--fixture', type=Path, default=Path('tests/fixtures/assl_architecture_cases.json'))
    p.add_argument('--case', default='sa-corner')
    p.add_argument('--layouts', type=int, default=12)
    p.add_argument('--repacks', type=int, default=4)
    p.add_argument('--seconds', type=float, default=1.5)
    p.add_argument('--out', type=Path, default=Path('stage012-experimental/feedback_012.json'))
    args = p.parse_args()
    if args.case != 'sa-corner':
        p.error('Only sa-corner implemented in stage 012; other cases are NOT verified')
    from backend.design.general_models import VillaBrief
    fixture = json.loads(args.fixture.read_text(encoding='utf-8'))
    brief = VillaBrief.model_validate(next(x['brief'] for x in fixture['cases'] if x['id'] == args.case))
    baseline = json.loads(solver.SOURCE_009.read_text(encoding='utf-8'))
    report, accepted = run_search(brief, baseline, max_layouts=args.layouts,
                                  repacks=args.repacks, seconds=args.seconds)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    for i, proposal in enumerate(accepted, 1):
        file = args.out.with_name(args.out.stem + f'_verified_candidate_{i}.json')
        file.write_text(json.dumps(proposal, ensure_ascii=False, indent=2), encoding='utf-8')
    print('012 feedback attempts:', report['attempted'],
          '009+010 screening passes:', report['accepted_candidates'],
          'unique topologies:', report['distinct_topology_count'])
    return 0 if report['three_structural_alternatives_verified'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
