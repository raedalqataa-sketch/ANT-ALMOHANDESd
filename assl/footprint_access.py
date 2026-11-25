"""Composition selection gates; reuse 009's real entry decisions/body geometry.

No connectors, openings or rooms are inserted into the proposed building.
"""
from shapely.geometry import box
from shapely.ops import unary_union
from .openings_009 import construct,shape,inward,shortest_path
from .guest_groups import entry_door_id


def entry_approaches(brief,rooms,halls):
    opened=construct(brief,dict(rooms_by_floor=[rooms],halls_by_floor=[halls]))['opening_model_009'][0]
    objects=opened['rooms']+opened['halls'];ids={r['id']:r for r in objects}
    expected=['family-entry']+[entry_door_id(r) for r in rooms if r.get('guest_distributor')]
    W,D,t=brief.plot_width,brief.plot_depth,brief.wall_thickness
    ox=brief.setbacks.west+t/2;oy=brief.setbacks.south+t/2
    # Same physical plot and wall offset as unchanged 009.validate.
    outdoor=box(-ox,-oy,W-ox,D-oy).difference(unary_union([shape(r) for r in objects]).buffer(t/2,join_style=2))
    issues=[];routes=[]
    for entry_id in expected:
        entry=next((d for d in opened['doors'] if d['id']==entry_id and d['connects'][0]=='OUTSIDE'),None)
        if entry is None:issues.append('MISSING_EXTERIOR_ENTRY:'+entry_id);continue
        receiving=ids[entry['connects'][1]];inside=inward(entry,receiving,.65)
        out=[2*entry['center'][i]-inside[i] for i in (0,1)]
        face=brief.entrance_face
        street=([out[0],-oy+.4] if face=='south' else [out[0],D-oy-.4] if face=='north' else [W-ox-.4,out[1]] if face=='east' else [-ox+.4,out[1]])
        route=shortest_path(outdoor,street,out)
        if route is None:issues.append('NO_OUTDOOR_APPROACH:'+entry_id)
        else:routes.append(dict(entry_id=entry_id,**route))
    return dict(status='FAIL' if issues else 'PASS',issues=issues,routes=routes)


def check_partial_composition(brief,rooms,halls):
    """Check present geometry without requiring unplaced family-room links."""
    from .free_layout_solver import inside,overlap_area
    from .free_layout_audit import _connected
    from .concept_quality_v2 import edge_contact
    from .guest_groups import prepare_program,room_vestibules
    from backend.design.general_engine import expanded_program
    issues=[]
    W=brief.plot_width-brief.setbacks.west-brief.setbacks.east-brief.wall_thickness
    D=brief.plot_depth-brief.setbacks.south-brief.setbacks.north-brief.wall_thickness
    if any(not inside(r,W,D) for r in rooms+halls):issues.append('OUTSIDE_BUILDABLE_AREA')
    if any(overlap_area(r,q)>1e-6 for i,r in enumerate(rooms) for q in rooms[i+1:]+halls):
        issues.append('ROOM_OR_CORE_OVERLAP')
    if not _connected(halls):issues.append('DISCONNECTED_FAMILY_CORE')
    if any(not any(edge_contact(r,h)>=.9 for h in halls) for r in rooms if r['kind']=='stair'):
        issues.append('STAIR_WITHOUT_FAMILY_CORE')
    expected=[r for r in prepare_program(brief,expanded_program(brief,0)) if r.get('zone')=='guest']
    actual=[r for r in rooms if r.get('request_id') and r.get('zone')=='guest']
    if sorted(r['id'] for r in expected)!=sorted(r['id'] for r in actual):
        issues.append('GUEST_PROGRAM_MISMATCH')
    vestibules=[r for r in rooms if r.get('guest_distributor')]
    for r in actual:
        hosts=room_vestibules(r,vestibules)
        count=len(r.get('guest_entries',[])) or 1
        if len(hosts)!=count or any(edge_contact(r,v)<1.2-1e-6 for v in hosts):
            issues.append('GUEST_ROOM_WITHOUT_OWN_HOST:'+r['id'])
    if issues:return dict(status='FAIL',phase='PARTIAL',issues=issues,routes=[])
    report=entry_approaches(brief,rooms,halls)
    return dict(report,phase='PARTIAL')


def check_composition(brief,rooms,halls,*,complete=True):
    if not complete:return check_partial_composition(brief,rooms,halls)
    from .free_layout_audit import _connected
    if not _connected(rooms+halls):
        return dict(status='FAIL',issues=['DISCONNECTED_BUILDING_FOOTPRINT'],routes=[])
    return entry_approaches(brief,rooms,halls)
