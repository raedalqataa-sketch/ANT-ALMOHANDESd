"""Independent audit must reject false PASS claims and broken rectangles."""
import json
from pathlib import Path
import unittest

from backend.design.general_models import VillaBrief
from assl.free_layout_audit import _connected,audit_preliminary_concept


def r(x,y,w,d,**kw):
    return dict(x=x,y=y,width=w,depth=d,**kw)


class FreeLayoutAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path=(Path(__file__).resolve().parents[1]/
              'tests/fixtures/assl_architecture_cases.json')
        rows=json.loads(path.read_text(encoding='utf8'))['cases']
        cls.brief=VillaBrief.model_validate(rows[0]['brief'])

    def test_corner_contact_is_not_a_contiguous_building(self):
        self.assertFalse(_connected([r(0,0,2,2),r(2,2,2,2)]))

    def test_shared_wall_is_contiguous_structure(self):
        self.assertTrue(_connected([r(0,0,2,2),r(2,0,2,2)]))

    def test_disconnected_room_is_rejected(self):
        self.assertFalse(_connected([r(0,0,4,4),r(8,8,4,4)]))

    def test_missing_floor_is_rejected_without_fake_pass(self):
        result=audit_preliminary_concept(self.brief,
                                         {'rooms_by_floor':[],
                                          'halls_by_floor':[]})
        self.assertEqual(result['status'],'REJECTED')
        self.assertFalse(result['legal_code_certification'])

    def test_empty_program_is_rejected_even_with_hall(self):
        result=audit_preliminary_concept(self.brief,{
            'rooms_by_floor':[[],[]],
            'halls_by_floor':[[r(0,0,1.5,3)],[r(0,0,1.5,3)]]})
        self.assertEqual(result['status'],'REJECTED')
        self.assertTrue(any(x.get('reason')=='REQUESTED_ROOMS_LOST_OR_DUPLICATED'
                            for x in result['issues']))
        self.assertFalse(result['actual_independent_doors_verified'])

    def test_stairs_cannot_disappear_between_floors(self):
        result=audit_preliminary_concept(self.brief,{
            'rooms_by_floor':[[r(0,0,3,4.6,kind='stair')],[]],
            'halls_by_floor':[[r(3,0,1.5,4.6)],[r(3,0,1.5,4.6)]]})
        self.assertEqual(result['status'],'REJECTED')
        self.assertIn('STAIR_CORE_MISSING',
                      [x.get('reason') for x in result['issues']])


if __name__ == '__main__':
    unittest.main()
