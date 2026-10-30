"""Necessary early window clearance screens; not real 009 window approval."""
import json
from pathlib import Path
from assl.relationship_first_012 import rect, exposed, window_strip_potential

FIXTURE = Path(__file__).parent / 'fixtures' / 'assl_milp_012_candidate.json'


def test_illusory_exterior_wall_in_tiny_gap_is_rejected():
    bath = rect(4, 4, 2.45, 2.45, id='bath', kind='bathroom')
    blockers = [
        rect(6.50, 4, 2.45, 2.45, id='east'),
        rect(1.50, 4, 2.45, 2.45, id='west'),
        rect(4, 6.50, 2.45, 2.45, id='north'),
        rect(4, 1.50, 2.45, 2.45, id='south'),
    ]
    assert exposed(bath, [bath] + blockers) >= 1.1  # naive exposure is misleading
    assert not window_strip_potential(bath, [bath] + blockers)


def test_free_wall_has_preliminary_window_potential():
    bath = rect(4, 4, 2.45, 2.45, id='bath', kind='bathroom')
    assert window_strip_potential(bath, [bath])


def test_a_non_window_room_does_not_get_an_invented_window_requirement():
    living = rect(4, 4, 5, 5, id='living', kind='living')
    assert window_strip_potential(living, [living])


def test_stored_012_candidate_still_has_early_window_potential():
    p = json.loads(FIXTURE.read_text(encoding='utf-8'))
    for fi, floor in enumerate(p['rooms_by_floor']):
        solids = floor + p['halls_by_floor'][fi]
        for room in floor:
            if room['kind'] in ('bathroom', 'bedroom', 'master', 'kitchen'):
                assert window_strip_potential(room, solids), (fi, room['id'])
