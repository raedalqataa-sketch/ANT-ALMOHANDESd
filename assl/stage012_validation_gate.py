"""Fail-closed integration gate between experimental stage 012 and real stage 009.

Run ONLY from the full ANT-ALMOHANDESd repository, where the 009 validator,
VillaBrief, and original 011 files exist. Do not substitute the concept-only
audit for actual body-door routes or opening clearances.
"""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path


def evaluate(brief, proposal):
    """Return evidence even for rejected candidates; never mutate source."""
    from assl.free_layout_audit import audit_preliminary_concept
    from assl.openings_009 import _opening_revision, validate
    from assl.layout_critic_010 import critique
    try:
        preliminary = audit_preliminary_concept(brief, proposal)
    except Exception as exc:
        # A broken preliminary validator is not a failed geometry test and
        # must not crash before the JSON rejection evidence is written.
        return {'status': 'GATE_RUNTIME_ERROR', 'stage009_executed': False,
                'doors_and_body_routes_009_passed': False,
                'stage008_precheck': None, 'error_stage': '008_PRECHECK',
                'error_type': type(exc).__name__, 'error_message': str(exc),
                'legal_compliance_certified': False}
    # A failed/unknown 008 hard precheck must NEVER be rehabilitated by a
    # later 009 or 010 indicator. Fail closed *before* attempting 009.
    if not isinstance(preliminary, dict) or preliminary.get('status') != 'PRELIMINARY_CONSISTENT':
        return {
            'status': 'REJECT_AND_REPLAN_UNRESOLVED',
            'stage008_precheck': preliminary,
            'stage009_executed': False,
            'doors_and_body_routes_009_passed': False,
            'all_architectural_indicators_passed': False,
            'rejection_stage': '008_PRECHECK',
            'stage009_actual_validation': None,
            'stage010_critic': None,
            'legal_compliance_certified': False,
            'visual_privacy_certified': False,
            'natural_light_and_airflow_certified': False,
            'furniture_used': False,
        }
    # Stage 009 may reject swing conflicts, exterior path, privacy movement,
    # absent windows, or missing real 0.6m body clearance.
    try:
        revision = _opening_revision(brief, copy.deepcopy(proposal))
        full = validate(brief, revision)  # recompute; never trust cached PASS
        checked = full['status'] == 'PASS'
        critic = critique(brief, revision) if checked else None
        outcome = ('READY_FOR_ARCHITECTURAL_REVIEW'
                   if checked and critic['status'] == 'ACCEPTABLE_DESIGN_INDICATORS'
                   else 'REJECT_AND_REPLAN_UNRESOLVED')
        return {
            'status': outcome,
            'stage008_precheck': preliminary,
            'stage009_actual_validation': full,
            'stage010_critic': critic,
            'stage009_executed': True,
            'doors_and_body_routes_009_passed': checked,
            'all_architectural_indicators_passed': outcome == 'READY_FOR_ARCHITECTURAL_REVIEW',
            'legal_compliance_certified': False,
            'visual_privacy_certified': False,
            'natural_light_and_airflow_certified': False,
            'furniture_used': False,
            'revision_trials': revision.get('repair_history_009', []),
            'opening_model_009': revision.get('opening_model_009'),
        }
    except Exception as exc:
        # A validator runtime exception must NEVER become a success.
        return {'status': 'GATE_RUNTIME_ERROR', 'stage009_executed': False,
                'doors_and_body_routes_009_passed': False,
                'stage008_precheck': preliminary,
                'error_type': type(exc).__name__, 'error_message': str(exc),
                'legal_compliance_certified': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--case', default='sa-corner')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    from backend.design.general_models import VillaBrief
    data = json.loads(args.fixture.read_text(encoding='utf-8'))
    case = next(x for x in data['cases'] if x['id'] == args.case)
    brief = VillaBrief.model_validate(case['brief'])
    proposal = json.loads(args.candidate.read_text(encoding='utf-8'))
    evidence = evaluate(brief, proposal)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
    print('STAGE_012_TO_009_GATE:', evidence['status'])
    print('DOORS_ROUTES_PASS:', evidence.get('doors_and_body_routes_009_passed'))
    return 0 if evidence['status'] == 'READY_FOR_ARCHITECTURAL_REVIEW' else 2


if __name__ == '__main__':
    raise SystemExit(main())