"""Locally executable regression checks for the independent 012 prototype."""
import copy
import itertools
import json
import unittest
from pathlib import Path
from shapely.ops import unary_union
from assl import relationship_first_012 as m

ROOT=Path(__file__).parent

class RelationshipFirstTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.before=json.loads((ROOT/'fixtures'/'assl_openings_009_valid.json').read_text())
        cls.after=json.loads((ROOT/'fixtures'/'assl_milp_012_candidate.json').read_text())

    def test_guest_suite_direct_access_and_separation(self):
        v=m.guest_suite('compact')
        self.assertGreaterEqual(m.contact(v[0],v[1]),1.2)
        self.assertGreaterEqual(m.contact(v[1],v[2]),1.2)
        self.assertAlmostEqual(v[1]['y'],0.)
        self.assertTrue(all(m.inside(r) for r in v))

    def test_candidate_is_milp_generated_for_both_floors(self):
        p=self.after
        self.assertEqual(len(p['solver']),2)
        self.assertTrue(all(q['binary_variables']>0 for q in p['solver']))
        self.assertTrue(all(q['solver_status'] in (0,1) for q in p['solver']))

    def test_exact_room_program_and_floor_identity(self):
        for fi in (0,1):
            before=sorted(r['id'] for r in self.before['rooms_by_floor'][fi] if r.get('request_id'))
            after=sorted(r['id'] for r in self.after['rooms_by_floor'][fi] if r.get('request_id'))
            self.assertEqual(before,after)
        s=[[r for r in f if r['kind']=='stair'][0] for f in self.after['rooms_by_floor']]
        self.assertEqual(s[0],s[1])

    def test_no_overlap_and_dimensions_for_all_requested_rooms(self):
        for fi,floor in enumerate(self.after['rooms_by_floor']):
            for a,b in itertools.combinations(floor,2):
                self.assertLessEqual(m.overlap(a,b),1e-6,(fi,a['id'],b['id']))
            for r in floor:
                self.assertTrue(m.inside(r),(fi,r['id']))
                if not r.get('request_id'):continue
                self.assertGreaterEqual((r['width']-.2)*(r['depth']-.2)+1e-6,r['min_area'])
                self.assertGreaterEqual(min(r['width']-.2,r['depth']-.2)+1e-6,r['min_side'])

    def test_room_host_and_exposure(self):
        for i,rooms in enumerate(self.after['rooms_by_floor']):
            halls=self.after['halls_by_floor'][i]
            for r in rooms:
                if not r.get('request_id') or r.get('zone')=='guest':continue
                self.assertTrue(any(m.contact(r,h)>=1.2 for h in halls),r['id'])
                if r['kind'] in ('master','bedroom','bathroom','kitchen'):
                    self.assertGreaterEqual(m.exposed(r,rooms+halls),1.1)

    def test_upper_floor_does_not_waste_external_family_entry_spur(self):
        self.assertIn('family-entry-spur',[h['id'] for h in self.after['halls_by_floor'][0]])
        self.assertNotIn('family-entry-spur',[h['id'] for h in self.after['halls_by_floor'][1]])

    def test_all_corridor_metrics_recomputed_and_no_fabricated_009_pass(self):
        p=self.after
        self.assertTrue(p['independent_audit']['passed_independent_geometry'])
        self.assertFalse(p['claim_009_verified'])
        self.assertFalse(p['independent_audit']['stage009_actual_door_swing_verified'])
        before_hall=sum(unary_union([m.geo(h) for h in halls+[r for r in rooms if r.get('guest_distributor')]]).area for halls,rooms in zip(self.before['halls_by_floor'],self.before['rooms_by_floor']))
        after_hall=sum(unary_union([m.geo(h) for h in halls+[r for r in rooms if r.get('guest_distributor')]]).area for halls,rooms in zip(p['halls_by_floor'],p['rooms_by_floor']))
        self.assertGreater(before_hall,after_hall)

    def test_physically_connected_massing_for_both_floors(self):
        for fi in (0, 1):
            shapes = self.after['rooms_by_floor'][fi] + self.after['halls_by_floor'][fi]
            mass = unary_union([m.geo(r) for r in shapes])
            self.assertEqual(mass.geom_type, 'Polygon', f'Floor {fi} split into annexes')

    def test_guest_to_family_touch_is_wall_only_not_portal(self):
        guests = [r for r in self.after['rooms_by_floor'][0] if r.get('zone') == 'guest']
        family_halls = self.after['halls_by_floor'][0]
        self.assertTrue(any(m.contact(g,h) >= .9 for g in guests for h in family_halls))
        self.assertFalse(self.after.get('claim_009_verified'))

    def test_disconnected_guest_annex_is_rejected(self):
        p=copy.deepcopy(self.after)
        for r in p['rooms_by_floor'][0]:
            if r.get('zone')=='guest':r['x']-=.25
        guests=[r for r in p['rooms_by_floor'][0] if r.get('zone')=='guest']
        stair=next(r for r in p['rooms_by_floor'][0] if r['kind']=='stair')
        floors=[[r for r in floor if r.get('request_id') and r.get('zone')!='guest'] for floor in p['rooms_by_floor']]
        evidence=m.audit(floors,p['halls_by_floor'],guests,stair)
        self.assertFalse(evidence['passed_independent_geometry'])
        self.assertIn('FLOOR_0_DISCONNECTED_BUILDING_MASS',evidence['issues'])

    def test_impossible_room_is_rejected(self):
        r={'id':'oversize','request_id':'oversize','kind':'living','zone':'family','min_area':400.,'min_side':20.}
        hall=m.rect(7,7,2,2,kind='corridor')
        stair=m.rect(9,7,3,4.6,kind='stair')
        solution,diagnostics=m.optimize_floor([r],[hall],stair,[],time_limit=.1)
        self.assertIsNone(solution)
        self.assertEqual(diagnostics['reason'],'NO_DOOR_HOSTED_CANDIDATE')

if __name__=='__main__':unittest.main()