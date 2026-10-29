"""Room-level architectural difference must not be spoofed by corridor labels."""
import unittest

from assl.room_arrangement_diversity import (
    compare_room_arrangements,difference_passes,select_distinct_proposals
)


def option(style,places,score=100):
    # All plans have the same requested program, unchanged walls and minimums.
    floor=[{'id':name,'kind':'bedroom','request_id':name,'zone':'family',
            'x':x,'y':y,'width':3,'depth':3} for name,x,y in places]
    return {'rooms_by_floor':[floor],
            'building_envelope_m':[20,20],
            'quality':{'architecture_score':score},
            'topology_evidence':{
                'distinctive_nodes_actually_serve_rooms':True,
                'geometric_graph_signature':f'actual-{style}'}}


class RoomDiversityTests(unittest.TestCase):
    def test_cosmetic_corridor_change_is_not_room_diversity(self):
        rooms=[('bed1',0,0),('bed2',6,0),('bed3',12,0)]
        a=option('axial',rooms)
        b=option('elbow',rooms)
        diff=compare_room_arrangements(a,b)
        self.assertTrue(diff['corridor_graph_changed'])
        self.assertEqual(diff['mean_normalized_room_displacement'],0)
        self.assertFalse(difference_passes(diff))

    def test_real_room_reconfiguration_passes(self):
        a=option('axial',[('bed1',0,0),('bed2',5,0),('bed3',10,0)])
        b=option('elbow',[('bed1',0,6),('bed2',5,8),('bed3',10,10)])
        d=compare_room_arrangements(a,b)
        self.assertGreater(d['mean_normalized_room_displacement'],.25)
        self.assertEqual(d['fraction_rooms_moved_at_least_5pct'],1)
        self.assertTrue(difference_passes(d))

    def test_missing_requested_room_never_compatible(self):
        a=option('axial',[('bed1',0,0),('bed2',5,0)])
        b=option('elbow',[('bed1',0,6)])
        d=compare_room_arrangements(a,b)
        self.assertFalse(d['program_compatible'])
        self.assertFalse(difference_passes(d))

    def test_group_selector_rejects_three_cosmetic_corridor_variants(self):
        geometry=[('bed1',0,0),('bed2',5,0),('bed3',10,0)]
        pools={style:[option(style,geometry)]
               for style in ('axial','elbow','split_hub')}
        result=select_distinct_proposals(pools,tuple(pools))
        self.assertEqual(result['selected'],[])
        self.assertEqual(result['reason'],'REAL_ROOM_CONFIGURATION_DIVERSITY_SHORTFALL')

    def test_group_selector_finds_three_materially_different_plans(self):
        p1=[('bed1',0,0),('bed2',5,0),('bed3',10,0)]
        p2=[('bed1',0,6),('bed2',5,8),('bed3',10,10)]
        p3=[('bed1',8,13),('bed2',0,15),('bed3',12,14)]
        pool={'axial':[option('axial',p1)],
              'elbow':[option('elbow',p2)],
              'split_hub':[option('split_hub',p3)]}
        output=select_distinct_proposals(pool,tuple(pool))
        self.assertEqual(len(output['selected']),3)
        self.assertEqual(output['reason'],'MEASURED_GROUP_DIVERSITY')
        self.assertEqual(len(output['comparisons']),3)
        self.assertTrue(all(difference_passes(x) for x in output['comparisons']))

    def test_unreasonably_bad_plan_not_selected_to_fake_diversity(self):
        p1=[('bed1',0,0),('bed2',5,0)]
        p2=[('bed1',0,8),('bed2',5,8)]
        p3=[('bed1',10,12),('bed2',2,13)]
        pools={'axial':[option('axial',p1)],
               'elbow':[option('elbow',p2),option('elbow',p3,score=500)],
               'split_hub':[option('split_hub',p1)]}
        output=select_distinct_proposals(pools,tuple(pools))
        self.assertFalse(output['selected'])


if __name__ == '__main__':
    unittest.main()
