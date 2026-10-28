"""Contract tests for physical guest entry, door hosting and design gates."""
import copy
import unittest
from assl.guest_geometry_qa import inspect_guest_access


def sample():
    def r(id,kind,zone,x,y,w,d,**kw):
        return dict(id=id,kind=kind,zone=zone,x=x,y=y,width=w,depth=d,**kw)
    rooms=[r('D','corridor','guest',0,0,2,2,guest_distributor=True),
           r('M','majlis','guest',2,0,4,2),
           r('B','bathroom','guest',0,2,2,2),
           r('H','corridor','family',2,2,4,2)]
    def wall(id,axis,start,end,rids,exterior=False):
        return dict(id=id,axis=axis,start=start,end=end,room_ids=rids,exterior=exterior)
    walls=[wall('md','vertical',[2,0],[2,2],['D','M']),
           wall('bd','horizontal',[0,2],[2,2],['D','B']),
           wall('ed','vertical',[0,0],[0,2],['D'],True),
           wall('eh','vertical',[6,2],[6,4],['H'],True),
           wall('mh','horizontal',[2,2],[6,2],['M','H'])]
    def door(id,wall_id,connects,c,**kw):
        return dict(id=id,kind='door',wall_id=wall_id,connects=connects,center=c,width=.9,**kw)
    openings=[door('MD','md',['D','M'],[2,1]),
              door('BD','bd',['D','B'],[1,2]),
              door('E','ed',['D','OUTSIDE'],[0,1],guest_entry=True),
              door('EF','eh',['H','OUTSIDE'],[6,3],main_entry=True),
              door('MH','mh',['M','H'],[3,2],access_control='family_only')]
    f=dict(id='GF',rooms=copy.deepcopy(rooms),cells=copy.deepcopy(rooms),
           walls=walls,openings=openings)
    return dict(floors=[f])


class GuestGeometryQA(unittest.TestCase):
    def audit(self,model,unreachable=None):
        return inspect_guest_access(model,walkability_probe=lambda m,f,ids: {
            'unreachable':unreachable or []})

    def test_physically_valid_separated_guest_path_passes(self):
        self.assertEqual(self.audit(sample())['status'],'PASS')

    def test_wall_connection_does_not_match_door(self):
        v=sample();v['floors'][0]['openings'][0]['connects']=['M','H']
        self.assertIn('INVALID_HOSTED_DOOR_GEOMETRY',self.audit(v)['issues'])

    def test_door_is_drawn_outside_wall_segment(self):
        v=sample();v['floors'][0]['openings'][0]['center']=[2,9]
        self.assertEqual(self.audit(v)['status'],'FAIL')

    def test_guest_family_privacy_closed_by_control(self):
        v=sample();v['floors'][0]['openings'][-1].pop('access_control')
        self.assertIn('FAMILY_OR_PRIVATE_SPACE_EXPOSED_TO_GUESTS',self.audit(v)['issues'])

    def test_guest_bathroom_must_have_real_portal(self):
        v=sample();v['floors'][0]['openings']=[o for o in v['floors'][0]['openings'] if o['id']!='BD']
        self.assertIn('GUEST_BATH_NOT_ACCESSIBLE_FROM_GUEST_ENTRY',self.audit(v)['issues'])

    def test_guest_entry_must_exit_building(self):
        v=sample();v['floors'][0]['openings']=[o for o in v['floors'][0]['openings'] if o['id']!='E']
        self.assertIn('NO_PHYSICAL_EXTERNAL_GUEST_ENTRANCE',self.audit(v)['issues'])

    def test_family_entry_independent(self):
        v=sample();v['floors'][0]['openings']=[o for o in v['floors'][0]['openings'] if o['id']!='EF']
        self.assertIn('NO_INDEPENDENT_FAMILY_MAIN_ENTRANCE',self.audit(v)['issues'])

    def test_large_aspect_triggers_design_rejection(self):
        v=sample()
        next(r for r in v['floors'][0]['rooms'] if r['id']=='M')['width']=10
        self.assertIn('MAJLIS_EXCESSIVE_ELONGATION_M',self.audit(v)['issues'])

    def test_small_body_route_blocked(self):
        self.assertIn('GUEST_ROUTE_BLOCKED_AT_BODY_CLEARANCE',
                      self.audit(sample(),unreachable=['B'])['issues'])

    def test_no_raster_does_not_claim_pass(self):
        self.assertEqual(inspect_guest_access(sample())['status'],'UNRESOLVED')

    def test_missing_walls_remains_unresolved(self):
        v=sample();v['floors'][0]['walls']=[]
        self.assertEqual(inspect_guest_access(v)['status'],'UNRESOLVED')

    def test_no_guest_room_not_applicable(self):
        v=sample()
        v['floors'][0]['rooms']=[r for r in v['floors'][0]['rooms'] if r['zone']!='guest']
        self.assertEqual(inspect_guest_access(v)['status'],'NOT_APPLICABLE')

    def test_source_data_immutable(self):
        v=sample();old=copy.deepcopy(v)
        self.audit(v)
        self.assertEqual(v,old)


if __name__=='__main__':
    unittest.main()
