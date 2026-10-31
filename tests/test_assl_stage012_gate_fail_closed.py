"""Stage012: 008 rejection cannot be overruled by 009 or 010.

Mocks isolate the gate control-flow and never claim a real 009 PASS.
"""
import sys
import types

import pytest

from assl.stage012_validation_gate import evaluate


def _install(monkeypatch, precheck, full=None, critic=None, *,
             must_not_run_009=False):
    counts = {'precheck': 0, 'revision': 0, 'validation': 0, 'critic': 0}
    def check(brief, proposal):
        counts['precheck'] += 1
        return precheck
    def revise(brief, proposal):
        counts['revision'] += 1
        if must_not_run_009:
            pytest.fail('Stage 009 ran despite a rejected 008 precheck')
        return {'opening_model_009': [{}, {}], 'repair_history_009': []}
    def validate(brief, proposal):
        counts['validation'] += 1
        return full or {'status': 'PASS', 'issues': []}
    def critique(brief, proposal):
        counts['critic'] += 1
        return critic or {'status': 'ACCEPTABLE_DESIGN_INDICATORS', 'defects': []}
    monkeypatch.setitem(sys.modules, 'assl.free_layout_audit',
                        types.SimpleNamespace(audit_preliminary_concept=check))
    monkeypatch.setitem(sys.modules, 'assl.openings_009',
                        types.SimpleNamespace(_opening_revision=revise, validate=validate))
    monkeypatch.setitem(sys.modules, 'assl.layout_critic_010',
                        types.SimpleNamespace(critique=critique))
    return counts


def test_rejected_008_never_reaches_009_even_if_009_mock_would_pass(monkeypatch):
    counts = _install(monkeypatch,
        {'status': 'REJECTED', 'issues': [{'reason': 'DISCONNECTED_BUILDING_FOOTPRINT'}]},
        must_not_run_009=True)
    result = evaluate(None, {'claim_009_verified': True})
    assert result['status'] == 'REJECT_AND_REPLAN_UNRESOLVED'
    assert result['rejection_stage'] == '008_PRECHECK'
    assert result['stage009_executed'] is False
    assert result['all_architectural_indicators_passed'] is False
    assert counts['revision'] == counts['validation'] == counts['critic'] == 0


@pytest.mark.parametrize('precheck', [None, {}, {'status': 'PASS'}, {'status': 'UNKNOWN'}])
def test_unknown_precheck_cannot_be_treated_as_consistent(monkeypatch, precheck):
    counts = _install(monkeypatch, precheck, must_not_run_009=True)
    result = evaluate(None, {})
    assert result['status'] == 'REJECT_AND_REPLAN_UNRESOLVED'
    assert result['stage009_executed'] is False
    assert counts['revision'] == 0


def test_precheck_exception_is_a_recorded_runtime_error(monkeypatch):
    def broken(*args): raise RuntimeError('mocked')
    monkeypatch.setitem(sys.modules, 'assl.free_layout_audit',
                        types.SimpleNamespace(audit_preliminary_concept=broken))
    monkeypatch.setitem(sys.modules, 'assl.openings_009',
                        types.SimpleNamespace(_opening_revision=None, validate=None))
    monkeypatch.setitem(sys.modules, 'assl.layout_critic_010',
                        types.SimpleNamespace(critique=None))
    result = evaluate(None, {})
    assert result['status'] == 'GATE_RUNTIME_ERROR'
    assert result['stage009_executed'] is False
    assert result['error_stage'] == '008_PRECHECK'


def test_only_all_three_consistent_mock_states_can_mark_ready(monkeypatch):
    counts = _install(monkeypatch, {'status': 'PRELIMINARY_CONSISTENT', 'issues': []})
    result = evaluate(None, {})
    assert result['status'] == 'READY_FOR_ARCHITECTURAL_REVIEW'
    assert result['stage009_executed'] is True
    assert counts['revision'] == counts['validation'] == counts['critic'] == 1
    assert result['legal_compliance_certified'] is False


def test_009_fail_overrides_positive_008_and_skips_010(monkeypatch):
    counts = _install(monkeypatch, {'status': 'PRELIMINARY_CONSISTENT', 'issues': []},
                      full={'status': 'FAIL', 'issues': ['NO_BODY_ROUTE']})
    result = evaluate(None, {})
    assert result['status'] == 'REJECT_AND_REPLAN_UNRESOLVED'
    assert result['doors_and_body_routes_009_passed'] is False
    assert counts['critic'] == 0


def test_010_failure_cannot_turn_into_ready(monkeypatch):
    _install(monkeypatch, {'status': 'PRELIMINARY_CONSISTENT', 'issues': []},
             critic={'status': 'REJECT_AND_REPLAN', 'defects': [{'type': 'LONG_CORRIDOR'}]})
    result = evaluate(None, {})
    assert result['status'] == 'REJECT_AND_REPLAN_UNRESOLVED'
    assert result['all_architectural_indicators_passed'] is False
