"""Program-first grouping: preserve every requested room and guest separation."""
import unittest
from assl.functional_graph import relation_graph,pair_functional_bundles

def r(id,kind,zone='family',area=16):
    return {'id':id,'kind':kind,'zone':zone,'request_id':id,
            'min_area':area,'min_side':2.8}

class FunctionalGraphTests(unittest.TestCase):
    def test_kitchen_and_dining_are_reserved_as_neighbors(self):
        groups=[[r('k','kitchen')],[r('d','dining')],[r('l','living')]]
        data=pair_functional_bundles(groups)
        self.assertEqual(len(data['bundles']),2)
        self.assertEqual({x['id'] for x in data['bundles'][0]},{'k','d'})
        self.assertEqual(groups[0][0]['id'],'k')
    def test_men_council_and_bath_remain_guest_only(self):
        guest=[r('m','majlis','guest'),r('gb','bathroom','guest'),
               {'id':'gd','kind':'corridor','zone':'guest',
                'guest_distributor':True,'min_area':0,'min_side':1.6}]
        groups=[guest,[r('k','kitchen')],[r('d','dining')],
                [r('fb','bathroom')]]
        out=pair_functional_bundles(groups)
        self.assertEqual([x['id'] for x in out['bundles'][0]],
                         ['m','gb','gd'])
        self.assertEqual(len(out['bundles'][0]),3)
    def test_master_pairs_with_family_bathroom(self):
        data=pair_functional_bundles([[r('master','master')],
                                      [r('bath','bathroom')]])
        self.assertEqual(len(data['bundles']),1)
        self.assertEqual({x['id'] for x in data['bundles'][0]},
                         {'master','bath'})
    def test_does_not_duplicate_or_drop_any_requested_room(self):
        groups=[[r('k','kitchen')],[r('d','dining')],
                [r('m','master')],[r('b','bathroom')],
                [r('bed1','bedroom')],[r('bed2','bedroom')]]
        result=pair_functional_bundles(groups)
        ids=[x['id'] for g in result['bundles'] for x in g]
        self.assertEqual(sorted(ids),['b','bed1','bed2','d','k','m'])
        self.assertEqual(len(ids),len(set(ids)))
    def test_graph_declares_preferences_not_legal_approval(self):
        g=relation_graph([[r('k','kitchen')],[r('d','dining')]])
        self.assertTrue(g['relationships'])
        self.assertFalse(g['relationships'][0]['legal_obligation'])
        self.assertFalse(g['furniture_used'])
    def test_no_mutation_of_original_bundles(self):
        groups=[[r('k','kitchen')],[r('d','dining')]]
        previous=[[dict(x) for x in g] for g in groups]
        pair_functional_bundles(groups)
        self.assertEqual(groups,previous)

if __name__=='__main__':
    unittest.main()
