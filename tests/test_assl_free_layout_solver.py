"""Independent constraint packing contracts; absolutely no furnishing involved."""
import copy
import unittest

from assl.free_layout_solver import (
    rect,area,overlap_area,clear,room_shapes,initial_core,
    guest_suite,anchors,hall_extensions,pack_floor,inside
)
from assl.concept_quality_v2 import edge_contact


def space(id,kind,area_min,side,zone='family'):
    return {'id':id,'request_id':id,'kind':kind,'min_area':area_min,
            'min_side':side,'name':id,'zone':zone}


class FreeLayoutSolverTests(unittest.TestCase):
    def test_overlap_is_actual_area_not_corner_contact(self):
        a=rect(0,0,4,4)
        self.assertAlmostEqual(overlap_area(a,rect(3,3,2,2)),1.)
        self.assertAlmostEqual(overlap_area(a,rect(4,4,2,2)),0.)

    def test_shapes_respect_real_net_area_and_minimum_side(self):
        for kind,minimum,side in [('bedroom',16,3.2),
                                  ('majlis',24,3.5),
                                  ('bathroom',4,1.6),
                                  ('master',22.4,3.5)]:
            shapes=room_shapes(space(kind,kind,minimum,side),.2)
            self.assertTrue(shapes,kind)
            for w,d,_ in shapes:
                self.assertGreaterEqual((w-.2)*(d-.2)+1e-6,minimum)
                self.assertGreaterEqual(min(w-.2,d-.2)+1e-6,side)

    def test_fixed_stair_directly_contacts_family_hub(self):
        hub_stair=initial_core(15.3,20.3,2,.2)
        self.assertIsNotNone(hub_stair)
        halls,stair=hub_stair
        self.assertGreaterEqual(edge_contact(halls[0],stair),2.4)
        self.assertEqual(stair['width'],3.)
        self.assertTrue(all(inside(h,15.3,20.3) for h in halls+[stair]))

    def test_independent_guest_suite_has_direct_vestibule_contacts(self):
        core=initial_core(15.3,20.3,1,.2)
        rooms,issue=guest_suite([
            space('c','majlis',24,3.5,'guest'),
            space('b','bathroom',4,1.6,'guest')],
            core[0][0],15.3,20.3,.2)
        self.assertIsNone(issue)
        maj,vestibule,bath=rooms
        self.assertGreaterEqual(edge_contact(maj,vestibule),.9)
        self.assertGreaterEqual(edge_contact(vestibule,bath),.9)
        self.assertTrue(vestibule['guest_distributor'])
        self.assertNotIn('guest_distributor',core[0][0])

    def test_unresolved_extra_guest_rooms_are_never_dropped(self):
        core=initial_core(20,25,1,.2)
        suite,issue=guest_suite([
            space('c','majlis',24,3.5,'guest'),
            space('b','bathroom',4,1.6,'guest'),
            space('b2','bathroom',4,1.6,'guest')],
            core[0][0],20,25,.2)
        self.assertIsNone(suite)
        self.assertEqual(issue,'UNSUPPORTED_GUEST_PROGRAM_UNRESOLVED')

    def test_anchors_require_real_wall_overlap(self):
        hall=rect(5,5,2.5,2.5)
        choices=list(anchors(hall,4,4,0))
        self.assertTrue(choices)
        self.assertTrue(all(edge_contact(hall,r)>=.9 for r in choices))

    def test_generated_halls_never_cross_stair_or_guest_suite(self):
        core=initial_core(18,24,1,.2)
        halls,stair=core
        ext=list(hall_extensions(halls,[stair]+halls,18,24,1))
        self.assertTrue(ext)
        self.assertTrue(all(clear(h,[stair]+halls,18,24) for h in ext))

    def test_solver_does_not_mutate_program(self):
        requests=[space('living','living',22,3.5),
                  space('kitchen','kitchen',12,3)]
        core=initial_core(20,25,1,.2)
        original=copy.deepcopy(requests)
        state,error=pack_floor(requests,20,25,.2,1,core,[],
                               beam_width=8,max_branches=3)
        self.assertEqual(requests,original)
        if state is not None:
            self.assertEqual(
                sorted(r['request_id'] for r in state.rooms if r.get('request_id')),
                ['kitchen','living'])
        else:
            self.assertIsInstance(error,str)

    def test_disabled_furnishing_no_cad_functions_imported(self):
        from assl import free_layout_solver
        self.assertFalse(hasattr(free_layout_solver,'furnish_floor'))
        self.assertFalse(hasattr(free_layout_solver,'export_general_model'))


if __name__ == '__main__':
    unittest.main()
