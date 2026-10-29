"""Independent tests for geometry-only hub-room reflow."""
import copy
import unittest
from assl.hub_reflow import move_fork_groups_toward_bridge

def room(id,x,y,w,d,**kw):
    return {'id':id,'x':x,'y':y,'width':w,'depth':d,**kw}

class ForkReflowTests(unittest.TestCase):
    def setUp(self):
        self.halls=[room('leg',4,0,1.6,10,hub_leg='long'),
                    room('short',10,4,1.6,6,hub_leg='short'),
                    room('bridge',4,10,7.6,1.6,hub_leg='bridge')]
    def test_moves_full_group_without_area_change(self):
        lanes=[{'x':0,'y':0,'width':4,'depth':10,'axis':'y'}]
        rooms=[room('bed',0,0,4,3,kind='bedroom'),
               room('bath',0,3,4,3,kind='bathroom')]
        original=copy.deepcopy(rooms)
        output=move_fork_groups_toward_bridge(rooms,lanes,self.halls)
        self.assertEqual(rooms,original)
        self.assertEqual([r['y'] for r in output],[4,7])
        self.assertEqual([(r['width'],r['depth']) for r in output],
                         [(r['width'],r['depth']) for r in rooms])
    def test_does_not_move_rooms_into_stair_reserved_end(self):
        lanes=[{'x':0,'y':0,'width':4,'depth':5.4,'axis':'y'}]
        rooms=[room('a',0,0,4,5.4)]
        output=move_fork_groups_toward_bridge(rooms,lanes,self.halls)
        self.assertEqual(output[0]['y'],0)
    def test_bridge_and_guest_ids_are_preserved(self):
        lanes=[{'x':0,'y':0,'width':4,'depth':10,'axis':'y'}]
        rooms=[room('m',0,0,4,5,kind='majlis',zone='guest',
                    guest_vestibule='g'),
               room('g',0,5,4,2,kind='corridor',zone='guest',
                    guest_distributor=True)]
        output=move_fork_groups_toward_bridge(rooms,lanes,self.halls)
        self.assertEqual(output[0]['guest_vestibule'],'g')
        self.assertEqual(output[1]['id'],'g')
        self.assertAlmostEqual(output[0]['y']+output[0]['depth'],output[1]['y'])
    def test_no_bridge_remains_unchanged(self):
        rooms=[room('a',0,0,4,3)]
        self.assertEqual(move_fork_groups_toward_bridge(rooms,[],[]),rooms)

if __name__=='__main__':
    unittest.main()
