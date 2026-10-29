"""Fail-closed stage-009 verification for stage-012 MILP candidates.

Never promote geometric packing into architectural acceptance. The established
009 auditor reconstructs actual doors, windows, walking routes and access.
"""
from __future__ import annotations
import copy
from shapely.geometry import box
from shapely.ops import unary_union

def _hall_m2(proposal):
    values = []
    for halls in proposal['halls_by_floor']:
        values.append(round(unary_union([
            box(h['x'], h['y'], h['x'] + h['width'], h['y'] + h['depth'])
            for h in halls
        ]).area, 4) if halls else 0.)
    return values

def verify_stage012(brief, candidate, baseline_009=None):
    """Return evidence and the inspected proposal; never mutate candidate."""
    from .free_layout_audit import audit_preliminary_concept
    from .openings_009 import revise, validate
    source = copy.deepcopy(candidate)
    preliminary = audit_preliminary_concept(brief, source)
    evidence = {
        'stage': '012',
        'status': 'REJECT_AND_REPLAN_UNRESOLVED',
        'preliminary_status': preliminary['status'],
        'preliminary_issues': preliminary['issues'],
        '009_status': 'NOT_RUN',
        '009_issues': [],
        'actual_doors_and_routes_verified': False,
        'room_program_preserved': False,
        'stair_identical_between_floors': False,
        'family_hall_area_by_floor_m2': _hall_m2(source),
        'comparison_baseline': '009 fixture, not the stage-011 best',
        'daylight_airflow_adequacy': 'UNRESOLVED',
        'visual_privacy': 'UNRESOLVED',
        'legal_and_structural': 'UNRESOLVED',
        'furniture_used': False,
        'architecturally_approved': False,
    }
    if baseline_009 is not None:
        before = _hall_m2(baseline_009)
        evidence['baseline_family_hall_area_by_floor_m2'] = before
        evidence['family_hall_delta_m2'] = round(sum(evidence['family_hall_area_by_floor_m2']) - sum(before), 4)
    if preliminary['status'] != 'PRELIMINARY_CONSISTENT':
        return evidence, source

    inspected = revise(brief, source)
    official = validate(brief, inspected)
    evidence['009_status'] = official['status']
    evidence['009_issues'] = official['issues']
    from backend.design.general_engine import expanded_program
    expected = [sorted(r['id'] for r in expanded_program(brief, i))
                for i in range(brief.floors)]
    actual = [sorted(r['id'] for r in floor if r.get('request_id'))
              for floor in inspected['rooms_by_floor']]
    program_ok = expected == actual
    stairs = [[r for r in floor if r.get('kind') == 'stair']
              for floor in inspected['rooms_by_floor']]
    stair_ok = (brief.floors != 2 or
                (all(len(s) == 1 for s in stairs) and
                 all(stairs[0][0][k] == stairs[1][0][k]
                     for k in ('x','y','width','depth'))))
    evidence['room_program_preserved'] = program_ok
    evidence['stair_identical_between_floors'] = stair_ok
    evidence['actual_doors_and_routes_verified'] = official['status'] == 'PASS'
    evidence['family_hall_area_by_floor_m2'] = _hall_m2(inspected)
    if baseline_009 is not None:
        before = evidence['baseline_family_hall_area_by_floor_m2']
        evidence['family_hall_delta_m2'] = round(sum(evidence['family_hall_area_by_floor_m2']) - sum(before), 4)
    if not program_ok: evidence['009_issues'].append('PROGRAM_INTEGRITY')
    if not stair_ok: evidence['009_issues'].append('STAIR_INCONSISTENT')
    improved = (baseline_009 is not None and evidence['family_hall_delta_m2'] < -0.01)
    evidence['measured_family_hall_improved_vs_009'] = improved
    if official['status'] == 'PASS' and program_ok and stair_ok and improved:
        evidence['status'] = 'READY_FOR_ARCHITECTURAL_REVIEW'
    return evidence, inspected
