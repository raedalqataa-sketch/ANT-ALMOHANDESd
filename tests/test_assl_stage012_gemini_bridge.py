"""Strict Gemini-to-012 search-advice tests; NO paid or live inference."""
import json
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from assl import stage012_gemini_bridge as bridge
from assl.stage012_feedback_search import reason_codes
from backend.design.ai_lab.providers import Provider, ProviderConfig
from backend.design.general_models import VillaBrief

ROOT = Path(__file__).parent


def options():
    return {'options': [
        dict(guest_mode='compact', corridor_branch='none', hub_x='center', hub_y='middle'),
        dict(guest_mode='compact', corridor_branch='west', hub_x='center', hub_y='middle'),
        dict(guest_mode='compact', corridor_branch='east', hub_x='center', hub_y='middle'),
    ]}


def test_rejects_raw_coordinates_and_relaxed_critical_parameters():
    row = options()
    for bad in ('x', 'setbacks', 'doors', 'min_area', 'room_changes', 'skip_009'):
        altered = json.loads(json.dumps(row))
        altered['options'][0][bad] = 0
        with pytest.raises(ValidationError):
            bridge.Stage012SearchPlan.model_validate(altered)
    assert len(bridge.Stage012SearchPlan.model_validate(row).options) == 3


def test_rejects_fake_diversity_by_moving_same_structural_class():
    row = options()
    for opt in row['options']:
        opt['corridor_branch'] = 'none'
    row['options'][1]['hub_x'] = 'left'
    row['options'][2]['hub_y'] = 'rear'
    with pytest.raises(ValidationError, match='DUPLICATE_STRUCTURAL_TOPOLOGY'):
        bridge.Stage012SearchPlan.model_validate(row)


def test_rejects_plan_with_too_few_or_too_many_options():
    for n in (1, 2, 7):
        row = options()['options'][0]
        with pytest.raises(ValidationError):
            bridge.Stage012SearchPlan.model_validate({'options': [row] * n})


def test_only_real_solver_layouts_are_forwarded_no_geometry_nearest_match():
    plan = bridge.Stage012SearchPlan.model_validate(options())
    fake = [
        (('compact', 7.25, 5.5, 'none'), ['NONE_HALL'], 'STAIR', 'GUEST'),
        (('compact', 7.25, 5.5, 'east'), ['EAST_HALL'], 'STAIR', 'GUEST')
    ]
    selected, diagnostics = bridge.select_existing_layouts(plan, available=fake)
    assert selected == fake
    assert [d['status'] for d in diagnostics] == [
        'MATCHED_EXISTING_SOLVER_LAYOUT',
        'UNSUPPORTED_OR_INFEASIBLE_SOLVER_LAYOUT',
        'MATCHED_EXISTING_SOLVER_LAYOUT'
    ]
    assert not any(d['status'] == 'MATCHED_EXISTING_SOLVER_LAYOUT'
                   for d in diagnostics[1:2])


def test_no_alternatives_are_invented_when_enumerator_does_not_match(monkeypatch):
    plan = bridge.Stage012SearchPlan.model_validate(options())
    monkeypatch.setattr(bridge, 'select_existing_layouts',
                        lambda plan: ([], [{'status': 'UNSUPPORTED_OR_INFEASIBLE_SOLVER_LAYOUT'}]))
    monkeypatch.setattr(bridge, 'run_search',
                        lambda *a, **kw: pytest.fail('MILP must not run without topology'))
    report, accepted = bridge.evaluate_plan(object(), object(), plan)
    assert report['status'] == 'BLOCKED_NO_SUPPORTED_LAYOUTS'
    assert not accepted


def test_the_preexisting_solver_and_009_authority_remain_the_only_producers(monkeypatch):
    plan = bridge.Stage012SearchPlan.model_validate(options())
    dummy = (('compact', 7.25, 5.5, 'none'), [], {}, [])
    monkeypatch.setattr(bridge, 'select_existing_layouts',
                        lambda plan: ([dummy], [{'status':'MATCHED_EXISTING_SOLVER_LAYOUT'}]))
    def only_original(brief, baseline, **kwargs):
        assert kwargs['layout_sequence'] == [dummy]
        assert kwargs['max_layouts'] == 1
        return ({'status':'EXPERIMENTAL_ONLY', 'accepted_candidates':0,
                 'three_structural_alternatives_verified':False}, [])
    monkeypatch.setattr(bridge, 'run_search', only_original)
    report, accepted = bridge.evaluate_plan(object(), object(), plan)
    assert report['geometry_source'] == 'ORIGINAL_STAGE012_SOLVER'
    assert report['validation_authority'] == 'ORIGINAL_008_009_010'
    assert report['architecture_approved'] is False
    assert not accepted


def test_private_notes_never_enter_model_context():
    data = json.loads((ROOT / 'fixtures' / 'assl_architecture_cases.json').read_text(encoding='utf-8'))
    brief = VillaBrief.model_validate(data['cases'][0]['brief']).model_copy(update={
        'project_name':'PRIVATE_OWNER', 'notes':'CONFIDENTIAL_NOTES',
        'parcel_reference':'PRIVATE_PARCEL', 'city':'PRIVATE_CITY'})
    raw = json.dumps(bridge.minimal_context(brief), ensure_ascii=False)
    for secret in ('PRIVATE_OWNER','CONFIDENTIAL_NOTES','PRIVATE_PARCEL','PRIVATE_CITY'):
        assert secret not in raw
    assert '"min_area_m2"' in raw
    assert '"entrance_face"' in raw


def test_gemini_mock_transport_uses_strict_stage012_schema_without_real_network():
    plan = options()
    def fake_response(req):
        assert req.url.host == 'generativelanguage.googleapis.com'
        body = json.loads(req.content)
        schema = body['generationConfig']['responseJsonSchema']
        assert 'Stage012Option' in json.dumps(schema)
        assert 'x-goog-api-key' in req.headers
        return httpx.Response(200, json={
            'candidates':[{'content':{'parts':[{'text':json.dumps(plan)}]}}],
            'usageMetadata':{'promptTokenCount':8,'candidatesTokenCount':12}})
    provider = Provider(
        ProviderConfig(provider='GEMINI',model='mock-flash',api_key='not-a-real-key',
                       gemini_free_tier_confirmed=True),
        client=httpx.Client(transport=httpx.MockTransport(fake_response)))
    try:
        advice = provider.propose({'site':{'width_m':20}},
                                  response_schema=bridge.Stage012SearchPlan)
        assert isinstance(advice, bridge.Stage012SearchPlan)
        assert provider.metrics['request_count'] == 1
        assert provider.metrics['input_tokens'] == 8
    finally:
        provider.close()


def test_null_precheck_is_fail_closed_and_preserves_diagnostic():
    r = reason_codes({'status':'GATE_RUNTIME_ERROR','error_type':'RuntimeError',
                      'stage008_precheck':None,'stage009_actual_validation':None,
                      'stage009_executed':False})
    assert '009:NOT_EXECUTED' in r
    assert 'RUNTIME:RuntimeError' in r


def test_exact_site_and_program_preflight_uses_stored_009_not_llm_claims():
    from assl.relationship_first_012 import SOURCE_009
    fixture = json.loads((ROOT / 'fixtures' / 'assl_architecture_cases.json').read_text(encoding='utf-8'))
    brief = VillaBrief.model_validate(fixture['cases'][0]['brief'])
    baseline = json.loads(SOURCE_009.read_text(encoding='utf-8'))
    bridge.verify_immutable_case(brief, baseline)
    altered = brief.model_copy(update={'setbacks':
        brief.setbacks.model_copy(update={'east': brief.setbacks.east + 0.5})})
    with pytest.raises(ValueError, match='STAGE012_BUILDABLE_ENVELOPE_MISMATCH'):
        bridge.verify_immutable_case(altered, baseline)
    fewer = json.loads(json.dumps(baseline))
    fewer['rooms_by_floor'][0] = [
        r for r in fewer['rooms_by_floor'][0] if r.get('id') != 'auto-ground-bath-1'
    ]
    with pytest.raises(ValueError, match='STAGE012_BASELINE_PROGRAM_MISMATCH'):
        bridge.verify_immutable_case(brief, fewer)


def test_explicit_layout_sequence_is_not_overridden_by_default_enumerator(monkeypatch):
    from assl import stage012_feedback_search as feedback
    baseline = {'rooms_by_floor': [[{'id': 'room0', 'request_id': 'room0',
                                    'zone': 'family'}],
                                   [{'id': 'room1', 'request_id': 'room1',
                                     'zone': 'family'}]]}
    row = (('compact', 7.25, 5.5, 'none'), [], {'id': 'stair'}, [])
    monkeypatch.setattr(feedback.solver, 'layouts',
                        lambda: pytest.fail('unadvised default layout enumerator called'))
    monkeypatch.setattr(feedback.solver, 'optimize_floor',
                        lambda *args, **kwargs: (None, {'reason': 'NO_SOLUTION'}))
    report, accepted = feedback.run_search(
        object(), baseline, layout_sequence=[row], max_layouts=1,
        repacks=1, seconds=0.1)
    assert report['layout_source'] == 'EXPLICIT_SOLVER_LAYOUTS'
    assert report['accepted_candidates'] == 0
    assert report['attempts'][0]['status'] == 'MILP_INFEASIBLE_OR_TIMEOUT'
    assert not accepted


def test_no_false_three_alternatives_from_unserviced_branches():
    from assl.stage012_feedback_search import counted_distinct_topologies
    def candidate(branch, extra_served=False):
        return {'topology':('compact',7.25,5.5,branch),
                'verified_009_evidence':{'opening_model_009':[
                    {'halls':[{'id':'hall-0-0'}, {'id':'hall-0-1'}],
                     'doors':[{'connects':['hall-0-0','room-a']},
                              {'connects':['hall-0-1','room-b']}] if extra_served
                             else [{'connects':['hall-0-0','room-a']}]},
                    {'halls':[{'id':'hall-1-0'}],
                     'doors':[{'connects':['hall-1-0','bed-1']}]}
                ]}}
    plain = candidate('none')
    unused = candidate('west')
    more_served = candidate('east', extra_served=True)
    assert counted_distinct_topologies([plain, unused, more_served]) == 2
    assert counted_distinct_topologies([plain, unused, {}]) == 1
