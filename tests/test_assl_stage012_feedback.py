"""Regression tests for stage 012 no-good MILP feedback (not a 009 approval)."""
from assl import relationship_first_012 as m
from assl.stage012_feedback_search import reason_codes, placement_key


def test_stage009_error_always_fail_closed():
    report = {'status': 'GATE_RUNTIME_ERROR', 'error_type': 'ImportError',
              'stage009_executed': False}
    reasons = reason_codes(report)
    assert '009:NOT_EXECUTED' in reasons
    assert 'RUNTIME:ImportError' in reasons


def test_stage009_rejection_reason_preserved():
    report = {'status': 'REJECT_AND_REPLAN_UNRESOLVED',
              'stage009_executed': True,
              'stage009_actual_validation': {'issues': ['NO_BODY_ROUTE:living']},
              'stage010_critic': {'defects': [{'type': 'LONG_CORRIDOR'}]}}
    assert '009:NO_BODY_ROUTE:living' in reason_codes(report)
    assert '010:LONG_CORRIDOR' in reason_codes(report)


def test_exact_floor_solution_exclusion_changes_milp_assignment():
    # Tiny synthetic problem: excludes geometry only, never removes a room.
    room = {'id': 'living-test', 'request_id': 'living-test',
            'kind': 'living', 'zone': 'family', 'min_area': 16.0, 'min_side': 3.0}
    hall = m.rect(5., 6., 2.5, 3., kind='corridor', id='hub')
    stair = m.rect(11., 5., 3., 4.6, kind='stair', id='stair')
    first, info = m.optimize_floor([room], [hall], stair, [], time_limit=3.)
    assert first is not None, info
    second, info2 = m.optimize_floor([room], [hall], stair, [],
                                      time_limit=3., forbidden=[first])
    assert second is not None, info2
    assert info2['no_good_cuts'] >= 1
    assert placement_key(first) != placement_key(second)
    assert {r['id'] for r in first} == {r['id'] for r in second}


def test_deterministic_identity_key():
    a = [{'id': 'b', 'x': 1, 'y': 2, 'width': 3, 'depth': 4},
         {'id': 'a', 'x': 5, 'y': 6, 'width': 7, 'depth': 8}]
    assert placement_key(a) == placement_key(list(reversed(a)))
