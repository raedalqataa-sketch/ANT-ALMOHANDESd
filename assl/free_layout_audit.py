"""Independent audit of preliminary free-layout geometry.

This auditor never trusts a model-provided PASS flag. It checks requested
room identity/count, non-overlap, potential wall contacts, fixed stair,
continuous possible exterior frontage, and connected family circulation.

Real door clearances, visual privacy, daylight area, code and furnishing
are explicitly OUT OF SCOPE, with no implied approval.
"""
from __future__ import annotations
from collections import deque

from .architectural_composer import facade_exposure, assess_layout
from .concept_quality_v2 import edge_contact,union_area,hall_shape
from .free_layout_solver import overlap_area,inside

EPS=1e-5


def _connected(rectangles):
    if not rectangles:return False
    seen={0};q=deque([0])
    while q:
        i=q.popleft()
        for j,r in enumerate(rectangles):
            if j not in seen and (
                edge_contact(rectangles[i],r)>=.01 or
                overlap_area(rectangles[i],r)>EPS):
                seen.add(j);q.append(j)
    return len(seen)==len(rectangles)


def audit_preliminary_concept(brief,proposal):
    from backend.design.general_engine import expanded_program
    from .guest_groups import prepare_program,memberships,room_vestibules
    t=brief.wall_thickness
    W=brief.plot_width-brief.setbacks.east-brief.setbacks.west-t
    D=brief.plot_depth-brief.setbacks.north-brief.setbacks.south-t
    floors=proposal.get('rooms_by_floor',[])
    halls=proposal.get('halls_by_floor',[])
    issues=[];by_floor=[]
    if len(floors)!=brief.floors or len(halls)!=brief.floors:
        return {'status':'REJECTED','issues':['FLOOR_COUNT_MISMATCH'],
                'legal_code_certification':False}
    all_stairs=[]
    for idx,(rooms,walk) in enumerate(zip(floors,halls)):
        program=prepare_program(brief,expanded_program(brief,idx))
        expected=sorted(r['id'] for r in program)
        actual=sorted(r['id'] for r in rooms if r.get('request_id'))
        if expected!=actual:
            issues.append({'floor':idx,'reason':'REQUESTED_ROOMS_LOST_OR_DUPLICATED',
                           'expected':expected,'actual':actual})
        shapes=rooms+walk
        if any(not inside(r,W,D) for r in shapes):
            issues.append({'floor':idx,'reason':'RECTANGLE_OUTSIDE_BUILDABLE_AREA'})
        for i,a in enumerate(rooms):
            for b in rooms[i+1:]+walk:
                if overlap_area(a,b)>EPS:
                    issues.append({'floor':idx,'reason':'ROOM_OR_STAIR_OVERLAP',
                                   'room_id':a.get('id'),'other':b.get('id')})
        if not _connected(shapes):
            issues.append({'floor':idx,'reason':'DISCONNECTED_BUILDING_FOOTPRINT'})
        if hall_shape(walk)['components']!=1:
            issues.append({'floor':idx,'reason':'DISCONNECTED_FAMILY_HALL'})
        stairs=[r for r in rooms if r.get('kind')=='stair']
        all_stairs.append(stairs)
        if brief.floors==2 and len(stairs)!=1:
            issues.append({'floor':idx,'reason':'STAIR_CORE_MISSING'})
        if any(not any(edge_contact(r,h)>=.9 for h in walk)
               for r in stairs):
            issues.append({'floor':idx,'reason':'STAIR_NOT_ADJACENT_TO_FAMILY_HALL'})
        for r in rooms:
            if not r.get('request_id'):continue
            if r.get('zone')!='guest' and not any(
                edge_contact(r,h)>=.9 for h in walk):
                issues.append({'floor':idx,'reason':'FAMILY_ROOM_WITHOUT_HALL_CONTACT',
                               'id':r['id']})
            net=(r['width']-t)*(r['depth']-t)
            if net+EPS<r['min_area'] or min(r['width']-t,r['depth']-t)+EPS<r['min_side']:
                issues.append({'floor':idx,'reason':'CUSTOMER_MINIMUM_NOT_MET',
                               'id':r['id']})
            if r['kind'] in ('bedroom','master','kitchen','bathroom') and (
                facade_exposure(r,shapes)<.9-EPS):
                issues.append({'floor':idx,'reason':'NO_DIRECT_EXTERIOR_FACADE_POTENTIAL',
                               'id':r['id']})
        guest=[r for r in rooms if r.get('guest_distributor')]
        requested_guests=[r for r in program if r.get('zone')=='guest']
        legacy=(len(requested_guests)==2 and
                sorted(r['kind'] for r in requested_guests)==['bathroom','majlis'] and
                not brief.guest_groups)
        expected_memberships={} if legacy else memberships(program)
        expected_entries={e for es in expected_memberships.values() for e in es}
        if legacy:
            if len(guest)!=1:
                issues.append({'floor':idx,'reason':'GUEST_VESTIBULE_MISSING_OR_DUPLICATED'})
        elif sorted(v.get('guest_entry','') for v in guest)!=sorted(expected_entries):
            issues.append({'floor':idx,'reason':'GUEST_ENTRY_MEMBERSHIP_MISMATCH'})
        for requested in requested_guests:
            r=next((q for q in rooms if q.get('id')==requested['id']),None)
            if r is None:continue
            if r.get('zone')!='guest' or (not legacy and
                    sorted(r.get('guest_entries',[]))!=sorted(expected_memberships[r['id']])):
                issues.append({'floor':idx,'reason':'GUEST_ROOM_MEMBERSHIP_MISMATCH','id':r['id']})
            hosts=room_vestibules(r,guest)
            required_count=1 if legacy else len(expected_memberships[r['id']])
            if len(hosts)!=required_count or any(edge_contact(r,v)<.9-EPS for v in hosts):
                issues.append({'floor':idx,'reason':'GUEST_SUITE_NOT_ADJACENT_TO_OWN_VESTIBULE','id':r['id']})
        for v in guest:
            if facade_exposure(v,shapes)<.9-EPS:
                issues.append({'floor':idx,'reason':'INDEPENDENT_GUEST_ENTRY_FACADE_MISSING','id':v['id']})
        by_floor.append({'floor':idx,'room_count':len([r for r in rooms if r.get('request_id')]),
                         'family_hall_union_m2':round(union_area(walk),3),
                         'footprint_union_m2':round(union_area(shapes),3),
                         'main_hall_max_straight_run_m':hall_shape(walk)['max_straight_run_m'],
                         'guest_distributor_count':len(guest),
                         'massing_connected':_connected(shapes)})
    if brief.floors==2 and all(len(a)==1 for a in all_stairs):
        first,second=all_stairs[0][0],all_stairs[1][0]
        if any(abs(first[k]-second[k])>EPS
               for k in ('x','y','width','depth')):
            issues.append({'reason':'VERTICAL_STAIR_INCONSISTENT'})
    geometry=assess_layout(
        {'floors':floors,'halls_by_floor':halls},t)
    if geometry['hard_issues']:
        issues.append({'reason':'ARCHITECTURAL_PRECHECK_FAILURE',
                       'details':geometry['hard_issues']})
    return {'status':'PRELIMINARY_CONSISTENT' if not issues else 'REJECTED',
            'issues':issues,'floor_evidence':by_floor,
            'actual_independent_doors_verified':False,
            'real_walk_paths_verified':False,
            'natural_ventilation_certified':False,
            'legal_code_certification':False,
            'furniture_used':False}
