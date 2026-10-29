"""Independent topology geometry and street-facing rigid transform tests."""
import unittest

from assl.free_layout_solver import initial_core,rect,overlap_area
from assl.topology_options import (
    transform_rectangle,transform_candidate,local_envelope,
    structural_evidence,compare_structural_evidence,
)
from assl.concept_quality_v2 import hall_shape,union_area,edge_contact


class ArchitectureTopologies(unittest.TestCase):
    def test_three_core_graphs_are_genuinely_different(self):
        shapes={}
        for style in ('axial','elbow','split_hub'):
            core=initial_core(18.0,25.0,2,.2,style=style)
            self.assertIsNotNone(core,style)
            halls,stair=core
            self.assertEqual(hall_shape(halls)['components'],1)
            self.assertTrue(all(overlap_area(stair,h)<1e-6 for h in halls))
            shapes[style]=(len(halls),round(union_area(halls),2))
        self.assertEqual([shapes[s][0] for s in
                          ('axial','elbow','split_hub')],[3,4,5])
        self.assertEqual(len(set(shapes.values())),3)

    def test_no_family_hall_crosses_reserved_stair(self):
        for seed in range(9):
            for style in ('axial','elbow','split_hub'):
                core=initial_core(15.3,20.3,seed,.2,style=style)
                if core:
                    halls,stair=core
                    self.assertTrue(all(overlap_area(h,stair)<1e-6
                                        for h in halls))

    def test_four_frontages_preserve_area_and_envelope(self):
        physical_W,physical_D=30.,24.
        for face in ('south','north','east','west'):
            virtual_W,virtual_D=local_envelope(physical_W,physical_D,face)
            orig=rect(2,0,1.5,4.5,id='family-entry-spur')
            placed=transform_rectangle(orig,virtual_W,virtual_D,face)
            self.assertAlmostEqual(orig['width']*orig['depth'],
                                   placed['width']*placed['depth'])
            self.assertGreaterEqual(placed['x'],0)
            self.assertGreaterEqual(placed['y'],0)
            self.assertLessEqual(placed['x']+placed['width'],physical_W+1e-6)
            self.assertLessEqual(placed['y']+placed['depth'],physical_D+1e-6)
            if face=='south':self.assertAlmostEqual(placed['y'],0)
            if face=='north':self.assertAlmostEqual(placed['y']+placed['depth'],physical_D)
            if face=='east':self.assertAlmostEqual(placed['x']+placed['width'],physical_W)
            if face=='west':self.assertAlmostEqual(placed['x'],0)

    def test_transform_keeps_original_rooms_immutable(self):
        data={'floors':[[rect(1,1,3,4,id='b')]],
              'halls_by_floor':[[rect(4,1,1.5,4,id='h')]]}
        out=transform_candidate(data,12,20,'east')
        self.assertEqual(data['floors'][0][0]['x'],1)
        self.assertAlmostEqual(out['floors'][0][0]['width'],4)
        self.assertEqual(out['floors'][0][0]['id'],'b')
        self.assertAlmostEqual(edge_contact(out['floors'][0][0],
                                            out['halls_by_floor'][0][0]),4)

    def test_geometric_signature_not_based_on_style_name(self):
        rooms=[[rect(0,0,4,4,kind='living',id='r',request_id='r')]]
        halls=[[rect(4,0,1.5,4)]]
        a=structural_evidence(rooms,halls,'axial','south')
        b=structural_evidence(rooms,halls,'elbow','south')
        d=compare_structural_evidence(a,b)
        self.assertTrue(d['different_reported_styles'])
        self.assertFalse(d['different_measured_geometry'])
        self.assertTrue(d['unproven_radical_difference'])

    def test_structural_signature_changes_if_graph_changes(self):
        rooms=[[rect(0,0,4,4,id='r',request_id='r')]]
        a=structural_evidence(rooms,[[rect(4,0,1.5,4)]],'axial','south')
        b=structural_evidence(rooms,[[rect(4,0,1.5,4),
                                       rect(5.5,1,3,1.5)]],'elbow','south')
        self.assertTrue(compare_structural_evidence(a,b)['different_measured_geometry'])


if __name__=='__main__':
    unittest.main()
