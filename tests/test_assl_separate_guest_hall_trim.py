"""A separate guest suite must not inflate the unrelated family hall."""
import unittest
from backend.design.massing_quality import trim_corridor_tails
from assl.concept_quality_v2 import hall_shape,edge_contact

class IndependentGuestHallTrimTests(unittest.TestCase):
    def test_guest_cluster_not_used_to_prolong_family_hall(self):
        halls=[
            {'x':4.,'y':0.,'width':1.6,'depth':10.,'hub_leg':'long'},
            {'x':4.,'y':10.,'width':7.6,'depth':1.6,'hub_leg':'bridge'}]
        guest={'id':'men','kind':'majlis','zone':'guest',
               'x':0.,'y':0.,'width':4.,'depth':4.}
        family={'id':'living','kind':'living','zone':'family',
                'x':5.6,'y':7.,'width':4.,'depth':3.}
        old=trim_corridor_tails(halls,[guest,family])
        new=trim_corridor_tails(halls,[family])
        self.assertGreater(old[0]['depth'],new[0]['depth']+2)
        self.assertGreaterEqual(edge_contact(new[0],family),2.9)
        self.assertEqual(hall_shape(new)['components'],1)
        self.assertEqual(guest['x'],0.)

if __name__=='__main__':
    unittest.main()
