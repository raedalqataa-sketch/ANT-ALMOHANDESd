"""ASSL opt-in, independent physical guest-access audit.

Verifies real hosted door geometry and restricted guest routing, rather than
trusting precomputed check statuses or text labels. Optional raster probe is
needed before claiming furniture-clear physical walking access. No legal claim.
"""
from __future__ import annotations
from collections import deque
import math

EPS = 1e-4
OUTSIDE = frozenset(('OUTSIDE', 'EXTERIOR'))


def _number(x):
    return type(x) in (int, float) and math.isfinite(x)


def _on_edge(cell, wall, axis):
    """Sign of the actual wall edge of a gross room cell, or zero if not hosted."""
    if axis == 0:
        fixed, low, high = wall['start'][1], cell['x'], cell['x']+cell['width']
        e1, e2 = cell['y'], cell['y']+cell['depth']
    else:
        fixed, low, high = wall['start'][0], cell['y'], cell['y']+cell['depth']
        e1, e2 = cell['x'], cell['x']+cell['width']
    wlow = min(wall['start'][axis], wall['end'][axis])
    whigh = max(wall['start'][axis], wall['end'][axis])
    if low > wlow + EPS or high < whigh - EPS:
        return 0
    if abs(fixed-e1) <= EPS:
        return -1
    if abs(fixed-e2) <= EPS:
        return 1
    return 0


def _real_door(door, walls, cells, rooms):
    """Return (valid, issue). Drawn door must be a physical hosted portal."""
    wall = walls.get(door.get('wall_id'))
    if not wall:
        return False, 'MISSING_HOST_WALL'
    if wall.get('axis') not in ('horizontal', 'vertical'):
        return False, 'INVALID_HOST_AXIS'
    axis = 0 if wall['axis']=='horizontal' else 1
    c = door.get('center')
    width = door.get('width')
    if (not isinstance(c,(list,tuple)) or len(c)!=2 or
        not all(_number(q) for q in c) or not _number(width) or width < .75):
        return False, 'INVALID_OPENING_GEOMETRY'
    start, end = wall['start'], wall['end']
    if not all(_number(q) for q in (*start,*end)):
        return False, 'INVALID_WALL_GEOMETRY'
    parallel = 1-axis
    low,high = sorted((start[axis],end[axis]))
    if (abs(c[parallel]-start[parallel])>EPS or
        c[axis]-width/2<low-EPS or c[axis]+width/2>high+EPS):
        return False, 'DOOR_OUTSIDE_HOST_SEGMENT'
    host = wall.get('room_ids',[])
    if not host or len(set(host))!=len(host):
        return False, 'MALFORMED_WALL_ROOM_IDS'
    outside = set(door.get('connects',[])) & OUTSIDE
    if bool(wall.get('exterior')) != bool(outside):
        return False, 'EXTERIOR_FLAG_MISMATCH'
    expected = set(host) | (set(outside) if wall.get('exterior') else set())
    if set(door.get('connects',[])) != expected or len(door.get('connects',[])) != len(expected):
        return False, 'DOOR_CONNECTIONS_DO_NOT_MATCH_HOST'
    sides = []
    for rid in host:
        if rid not in rooms or rid not in cells:
            return False, 'MISSING_HOST_ROOM_OR_CELL'
        side = _on_edge(cells[rid],wall,axis)
        if not side:
            return False, 'WALL_NOT_ON_ROOM_BOUNDARY'
        sides.append(side)
    if wall.get('exterior'):
        if len(sides)!=1:
            return False, 'EXTERIOR_WALL_NOT_SINGLE_SIDED'
    elif len(sides)!=2 or sides[0]==sides[1]:
        return False, 'INTERIOR_WALL_NOT_SHARED_ON_OPPOSITE_SIDES'
    return True, None


def inspect_guest_access(model, *, walkability_probe=None, max_majlis_aspect=2.2):
    """Assess guest entrance->distributor->majlis and bath on ground floor.

    FAIL means an actual physical/design fault. Without a furniture-aware
    probe, an otherwise sound topological path remains UNRESOLVED, not PASS.
    """
    floors = model.get('floors',[])
    if not floors:
        return {'check_id':'ASSL-guest-physical-route','status':'UNRESOLVED',
                'issues':['MISSING_GROUND_FLOOR'],'legal_compliance_certified':False}
    floor = next((f for f in floors if f.get('id')=='GF'),floors[0])
    rooms = {r['id']:r for r in floor.get('rooms',[]) if r.get('id')}
    guests = {rid:r for rid,r in rooms.items() if r.get('zone')=='guest'}
    majlis = [rid for rid,r in guests.items() if r.get('kind')=='majlis']
    baths = [rid for rid,r in guests.items() if r.get('kind')=='bathroom']
    distributors = [rid for rid,r in guests.items() if r.get('kind')=='corridor' and r.get('guest_distributor')]
    if not majlis:
        return {'check_id':'ASSL-guest-physical-route','status':'NOT_APPLICABLE',
                'issues':[],'legal_compliance_certified':False}
    issues=[]
    if not baths:issues.append('GUEST_BATHROOM_MISSING')
    if not distributors:issues.append('GUEST_DISTRIBUTOR_MISSING')
    walls = {w['id']:w for w in floor.get('walls',[]) if w.get('id')}
    cells = {c['id']:c for c in floor.get('cells',[]) if c.get('id')}
    if not walls or not cells:
        return {'check_id':'ASSL-guest-physical-route','status':'UNRESOLVED',
                'issues':['PHYSICAL_WALLS_OR_CELLS_MISSING'],
                'legal_compliance_certified':False}
    usable=[]; invalid=[]
    for door in floor.get('openings',[]):
        if door.get('kind')!='door':continue
        valid,why = _real_door(door,walls,cells,rooms)
        if not valid:
            invalid.append({'door':door.get('id'), 'reason':why})
        else:
            usable.append(door)
    if invalid:issues.append('INVALID_HOSTED_DOOR_GEOMETRY')
    guest_entry = [o for o in usable if o.get('guest_entry') and
                   len(o['connects'])==2 and set(o['connects']) & OUTSIDE and
                   set(o['connects']) & set(distributors)]
    if not guest_entry:issues.append('NO_PHYSICAL_EXTERNAL_GUEST_ENTRANCE')
    if any(o.get('guest_entry') and o.get('main_entry') for o in usable):
        issues.append('GUEST_AND_FAMILY_ENTRANCE_COLLAPSED')
    if not any(o.get('main_entry') and set(o.get('connects',[])) & OUTSIDE
               for o in usable):
        issues.append('NO_INDEPENDENT_FAMILY_MAIN_ENTRANCE')
    graph={rid:set() for rid in rooms}
    for o in usable:
        if o.get('access_control')=='family_only':continue
        ids=[rid for rid in o['connects'] if rid in rooms]
        if len(ids)==2:
            a,b=ids;graph[a].add(b);graph[b].add(a)
    roots={rid for o in guest_entry for rid in o['connects'] if rid in distributors}
    reached=set(roots);queue=deque(roots)
    while queue:
        for rid in graph[queue.popleft()]-reached:
            reached.add(rid);queue.append(rid)
    if not all(rid in reached for rid in majlis):issues.append('MAJLIS_NOT_ACCESSIBLE_FROM_GUEST_ENTRY')
    if not all(rid in reached for rid in baths):issues.append('GUEST_BATH_NOT_ACCESSIBLE_FROM_GUEST_ENTRY')
    if reached-set(guests):issues.append('FAMILY_OR_PRIVATE_SPACE_EXPOSED_TO_GUESTS')
    for rid in majlis+baths:
        if not any(o.get('access_control')!='family_only' and
                   set(o['connects'])=={rid,did} for did in distributors for o in usable):
            issues.append('NO_DIRECT_GUEST_DISTRIBUTOR_PORTAL_'+rid)
    if any(set(o.get('connects',[]))=={m,b} for m in majlis for b in baths for o in usable):
        issues.append('GUEST_BATH_ACCESS_THROUGH_MAJLIS')
    shape=[]
    for rid in majlis:
        r=rooms[rid];w,d=r.get('width'),r.get('depth')
        if _number(w) and _number(d) and min(w,d)>0:
            ratio=max(w,d)/min(w,d)
            shape.append({'room_id':rid,'ratio':round(ratio,4),
                          'max_design_ratio':max_majlis_aspect})
            if ratio > max_majlis_aspect+EPS:
                issues.append('MAJLIS_EXCESSIVE_ELONGATION_'+rid)
        else:
            issues.append('MAJLIS_DIMENSIONS_MISSING_'+rid)
    walk='UNRESOLVED'
    if walkability_probe is not None and not any(issue.startswith(('NO_PHYSICAL','INVALID_','GUEST_DISTRIBUTOR','GUEST_BATHROOM')) for issue in issues):
        data=walkability_probe(model,floor,set(guests))
        if not isinstance(data,dict) or not isinstance(data.get('unreachable'),list):
            issues.append('PHYSICAL_WALKABILITY_PROBE_MISSING')
        else:
            walk = 'FAIL' if any(rid in data['unreachable'] for rid in majlis+baths+distributors) else 'PASS'
            if walk=='FAIL':issues.append('GUEST_ROUTE_BLOCKED_AT_BODY_CLEARANCE')
    status = 'FAIL' if issues else ('PASS' if walk=='PASS' else 'UNRESOLVED')
    return {'check_id':'ASSL-guest-physical-route','status':status,
            'issues':issues,'invalid_doors':invalid,
            'guest_entry_doors':[o.get('id') for o in guest_entry],
            'guest_room_ids':sorted(guests),'reached_room_ids':sorted(reached),
            'majlis_shapes':shape,'walkability_status':walk,
            'legal_compliance_certified':False,
            'scope':'Hosted real doors + restricted guest graph; optional 0.60m furniture-aware raster; not full visual privacy, code or construction approval'}


def generator_check(model):
    """Native generator check; critical guest path is fail-closed when opt-in.

    This is invoked after any V4 repairs and again immediately before export.
    Existing default/off-path behavior is entirely unaffected.
    """
    from backend.design.walkability import floor_access
    def probe(model_, floor, ids):
        # Seed from the *guest distributor*, not every exterior door. An
        # unrelated exterior door must never mask a blocked council route.
        roots=[r['id'] for r in floor['rooms'] if r.get('guest_distributor')
               and r['id'] in ids and
               any(o.get('guest_entry') and r['id'] in o.get('connects',[])
                   for o in floor['openings'])]
        if not roots:
            return {'unreachable':sorted(ids)}
        return floor_access(model_,floor,step=.20,body_width=.60,
                            start_room_id=roots[0],allowed_room_ids=ids)
    try:
        evidence=inspect_guest_access(model,walkability_probe=probe)
    except (ValueError, KeyError, TypeError, IndexError) as exc:
        evidence={'check_id':'ASSL-guest-physical-route','status':'UNRESOLVED',
                  'issues':['GEOMETRY_AUDIT_UNAVAILABLE'],
                  'error_type':type(exc).__name__,
                  'legal_compliance_certified':False}
    status=evidence['status']
    return {'check_id':'ASSL-guest-physical-route',
            'status':status if status in ('PASS','NOT_APPLICABLE') else 'FAIL',
            'label':'فحص مستقل للأبواب الحقيقية ومسار الضيوف وخلوص الحركة ونسب المجلس (اشتراط تصميمي تجريبي)',
            'evidence':evidence}
