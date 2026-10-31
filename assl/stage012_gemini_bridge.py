"""Gemini -> bounded stage 012 topology *advice*, not AI-authored geometry.

Live inference is opt-in only. Offline JSON is not evidence of a live Gemini
call. Solver layouts, hard constraints and stages 008/009/010 stay authoritative.
No production integration, payment changes, furniture, publication or merge.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from assl import relationship_first_012 as solver
from assl.stage012_feedback_search import run_search

X_POSITIONS = {'left': 6.25, 'center': 7.25, 'right': 8.25}
Y_POSITIONS = {'front': 4.5, 'middle': 5.5, 'rear': 6.5}


class _Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class Stage012Option(_Strict):
    guest_mode: Literal['compact', 'stacked']
    corridor_branch: Literal['none', 'west', 'east', 'both', 'cross']
    hub_x: Literal['left', 'center', 'right']
    hub_y: Literal['front', 'middle', 'rear']


class Stage012SearchPlan(_Strict):
    """Three to six *structurally* different strategies, no raw coordinates."""
    options: list[Stage012Option] = Field(min_length=3, max_length=6)

    @model_validator(mode='after')
    def structural_diversity(self):
        classes = [(o.guest_mode, o.corridor_branch) for o in self.options]
        if len(set(classes)) != len(classes):
            raise ValueError('DUPLICATE_STRUCTURAL_TOPOLOGY')
        return self


def topology_for_option(option):
    """Map only enumerated relative choices to the *existing* solver tags."""
    return (option.guest_mode, X_POSITIONS[option.hub_x],
            Y_POSITIONS[option.hub_y], option.corridor_branch)


def select_existing_layouts(plan, *, available=None):
    """No fabricated or tweaked geometry, no nearest-match fallback."""
    if not isinstance(plan, Stage012SearchPlan):
        raise TypeError('VALIDATED_STAGE012_SEARCH_PLAN_REQUIRED')
    existing = {tuple(row[0]): row for row in
                (solver.layouts() if available is None else available)}
    selected, diagnostics = [], []
    for i, option in enumerate(plan.options, 1):
        tag = topology_for_option(option)
        row = existing.get(tag)
        diagnostics.append({'option': i, 'topology': list(tag),
                            'status': 'MATCHED_EXISTING_SOLVER_LAYOUT' if row
                            else 'UNSUPPORTED_OR_INFEASIBLE_SOLVER_LAYOUT'})
        if row:
            selected.append(row)
    return selected, diagnostics


def minimal_context(brief):
    """Only synthetic site geometry and room requirements; no personal data."""
    return {
        'site': {
            'country': brief.country,
            'plot_width_m': brief.plot_width,
            'plot_depth_m': brief.plot_depth,
            'entrance_face': brief.entrance_face,
            'setbacks_m': brief.setbacks.model_dump(),
            'floors': brief.floors,
        },
        'program': [
            {'kind': r.kind, 'floor': r.floor, 'count': r.count,
             'min_area_m2': r.min_area, 'min_side_m': r.min_side}
            for r in brief.rooms
        ],
        'stage': 'EXPERIMENTAL_012',
        'allowed_geometry': {
            'guest_mode': ['compact', 'stacked'],
            'corridor_branch': ['none', 'west', 'east', 'both', 'cross'],
            'hub_x': list(X_POSITIONS),
            'hub_y': list(Y_POSITIONS),
        },
        'constraints': [
            'All rooms, room minimums, setbacks, and stair are immutable.',
            'Guest exterior entrance, council and bathroom are separate from family circulation.',
            'Natural external openings required in bedrooms, kitchens and bathrooms.',
            'Only existing stage012 layout enumerator may create geometry.',
            'Only original 008/009/010 checkers can screen candidates.',
            'Never treat MILP success as architectural acceptance.',
            'Select at least three different guest/branch structural classes.',
        ],
    }


def evaluate_plan(brief, baseline, plan, *, repacks=2, seconds=1.0):
    selected, mapping = select_existing_layouts(plan)
    if not selected:
        return ({
            'status': 'BLOCKED_NO_SUPPORTED_LAYOUTS',
            'origin': 'PLAN_ONLY',
            'mapped_options': mapping,
            'stage009_executed': False,
            'accepted_candidates': 0,
            'three_structural_alternatives_verified': False,
            'architecture_approved': False,
        }, [])
    report, accepted = run_search(
        brief, baseline, max_layouts=len(selected),
        repacks=repacks, seconds=seconds, layout_sequence=selected,
    )
    report.update(
        mapped_options=mapping,
        proposed_options=len(plan.options),
        matched_options=len(selected),
        geometry_source='ORIGINAL_STAGE012_SOLVER',
        validation_authority='ORIGINAL_008_009_010',
        architecture_approved=False,
        model_coordinates_trusted=False,
    )
    return report, accepted


def main(argv=None):
    parser = argparse.ArgumentParser(description='Gemini advice -> original experimental 012')
    parser.add_argument('--mode', choices=('offline', 'live'), default='offline')
    parser.add_argument('--plan-file', type=Path,
                        help='Strict JSON advice; OFFLINE_PLAN only, never labeled live')
    parser.add_argument('--model', default='',
                        help='Explicit Gemini model; required in live mode')
    parser.add_argument('--allow-remote-program', action='store_true',
                        help='Explicit opt-in to send synthetic site/program data')
    parser.add_argument('--case', default='sa-corner')
    parser.add_argument('--fixture', type=Path,
                        default=Path('tests/fixtures/assl_architecture_cases.json'))
    parser.add_argument('--out', type=Path,
                        default=Path('stage012-experimental/gemini_bridge_result.json'))
    parser.add_argument('--repacks', type=int, default=2)
    parser.add_argument('--seconds', type=float, default=1.0)
    args = parser.parse_args(argv)
    if args.case != 'sa-corner':
        parser.error('Only sa-corner implemented in 012; no silent reuse for other sites')
    if args.repacks not in range(1, 7) or not 0.1 <= args.seconds <= 15:
        parser.error('Out-of-budget MILP search')
    if args.mode == 'live':
        if args.plan_file or not args.allow_remote_program or not args.model:
            parser.error('Live requires --model and --allow-remote-program, not --plan-file')
    elif not args.plan_file or args.allow_remote_program or args.model:
        parser.error('Offline requires --plan-file only, without model/remote flags')

    from backend.design.general_models import VillaBrief
    fixture = json.loads(args.fixture.read_text(encoding='utf-8'))
    brief = VillaBrief.model_validate(
        next(row['brief'] for row in fixture['cases'] if row['id'] == args.case))
    # No inference, geometry or expenditure occurs before the source is checked.
    if (brief.country, brief.plot_width, brief.plot_depth,
            brief.entrance_face, brief.floors) != ('SA', 20, 25, 'south', 2):
        parser.error('Unsupported site: stage012 geometry is fixed to Saudi 20x25 south')

    source = 'OFFLINE_PLAN_NOT_GEMINI_LIVE'
    report = None
    try:
        if args.mode == 'live':
            from backend.design.ai_lab.providers import Provider, ProviderConfig
            with_provider = Provider(ProviderConfig.from_env('GEMINI', args.model))
            try:
                plan = with_provider.propose(minimal_context(brief),
                                             response_schema=Stage012SearchPlan)
                source = with_provider.metrics.get('result_origin', 'LIVE_API')
                # No untrusted prompt/key/response body retained in evidence.
            finally:
                with_provider.close()
        else:
            plan = Stage012SearchPlan.model_validate_json(
                args.plan_file.read_text(encoding='utf-8'))
        baseline = json.loads(solver.SOURCE_009.read_text(encoding='utf-8'))
        report, accepted = evaluate_plan(
            brief, baseline, plan, repacks=args.repacks, seconds=args.seconds)
        report['proposal_origin'] = source
        report['source_case'] = args.case
        report['requested_model'] = args.model if args.mode == 'live' else None
    except (ValidationError, ValueError, OSError, StopIteration) as exc:
        # ProviderError is a safe code-only ValueError. Never echo raw input.
        from backend.design.ai_lab.providers import ProviderError
        code = str(exc) if isinstance(exc, ProviderError) else type(exc).__name__
        report = {'status': 'BLOCKED_ADVICE_OR_ENVIRONMENT', 'error_code': code,
                  'proposal_origin': 'NO_LIVE_API_RESULT' if args.mode == 'live'
                  else 'INVALID_OFFLINE_PLAN',
                  'stage009_executed': False, 'accepted_candidates': 0,
                  'architecture_approved': False}
        accepted = []

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False,
                                   indent=2, allow_nan=False), encoding='utf-8')
    for i, candidate in enumerate(accepted, 1):
        target = args.out.with_name(args.out.stem + '_review_' + str(i) + '.json')
        target.write_text(json.dumps(candidate, ensure_ascii=False,
                                     indent=2, allow_nan=False), encoding='utf-8')
    print('Stage012 Gemini advice:', report['status'],
          '| source:', report.get('proposal_origin'),
          '| 009/010 screening accepted:', report['accepted_candidates'])
    return 0 if report.get('three_structural_alternatives_verified') else 2


if __name__ == '__main__':
    raise SystemExit(main())
