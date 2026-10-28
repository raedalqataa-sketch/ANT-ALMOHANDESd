"""Opt-in, bounded council-furniture repair: no silent plan changes."""
import copy
import unittest
from assl.guest_furniture_repair import attempt_guest_furniture_repair


def model():
    return {'floors':[{'id':'GF',
      'rooms':[{'id':'M','kind':'majlis','zone':'guest'},
               {'id':'D','kind':'corridor','zone':'guest','guest_distributor':True},
               {'id':'B','kind':'bathroom','zone':'guest'}],
      'openings':[{'guest_entry':True,'connects':['D','OUTSIDE']}],
      'furniture':[{'room_id':'M','id':'F1','kind':'sofa','state':'blocked'},
                   {'room_id':'B','id':'F2','kind':'toilet'}],
      'decorations':[],
      'furnishing_choice_counts':{'M':3}}]}


def furnish(floor,revision,choice_map):
    state='clear' if choice_map['M']==1 else 'blocked'
    floor['furniture'].append({'room_id':'M','id':'new','kind':'sofa','state':state})


def access(model,floor,**kwargs):
    blocked=any(q['room_id']=='M' and q.get('state')!='clear'
                for q in floor['furniture'])
    return {'unreachable':['M'] if blocked else []}


class RepairTests(unittest.TestCase):
    def test_success_existing_group_preserves_other_room(self):
        m=model();orig=copy.deepcopy(m['floors'][0]['furniture'][1])
        result=attempt_guest_furniture_repair(
            m,'test',floor_access=access,furnish_floor=furnish)
        self.assertEqual(result['status'],'REPAIRED')
        self.assertEqual(result['attempts'][0]['choice_index'],1)
        self.assertEqual(m['floors'][0]['furniture'][0]['room_id'],'B')
        self.assertEqual(m['floors'][0]['furniture'][0]['kind'],orig['kind'])

    def test_restores_furniture_if_no_repair(self):
        m=model();before=copy.deepcopy(m['floors'][0]['furniture'])
        result=attempt_guest_furniture_repair(
            m,'test',floor_access=lambda *a,**k:{'unreachable':['M']},
            furnish_floor=furnish)
        self.assertEqual(result['status'],'NOT_REPAIRED')
        self.assertEqual(m['floors'][0]['furniture'],before)

    def test_no_work_if_initially_accessible(self):
        m=model();before=copy.deepcopy(m)
        result=attempt_guest_furniture_repair(
            m,'test',floor_access=lambda *a,**k:{'unreachable':[]},
            furnish_floor=furnish)
        self.assertEqual(result['status'],'ALREADY_ACCESSIBLE')
        self.assertEqual(m,before)

    def test_cannot_mask_blocked_bathroom(self):
        m=model()
        result=attempt_guest_furniture_repair(
            m,'test',floor_access=lambda *a,**k:{'unreachable':['M','B']},
            furnish_floor=furnish)
        self.assertEqual(result['status'],'NOT_REPAIRED')

    def test_missing_entrance_does_not_attempt(self):
        m=model();m['floors'][0]['openings']=[]
        result=attempt_guest_furniture_repair(
            m,'test',floor_access=access,furnish_floor=furnish)
        self.assertEqual(result['status'],'UNRESOLVED')

    def test_non_council_obstruction_not_hidden(self):
        m=model()
        result=attempt_guest_furniture_repair(
            m,'test',floor_access=lambda *a,**k:{'unreachable':['B']},
            furnish_floor=furnish)
        self.assertEqual(result['status'],'NOT_REPAIRED')
        self.assertFalse(result['changed'])


if __name__=='__main__':
    unittest.main()
