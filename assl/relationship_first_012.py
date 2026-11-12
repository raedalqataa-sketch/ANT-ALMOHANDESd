"""Independent relationship-first, simultaneous room-packing prototype (stage 012).

Uses SciPy/HiGHS MILP (no external paid API). This is an experimental
constraint solver, NOT an integration with ANT's production 009 checker.
Inputs are immutable program identities from an actual 009 test result.

The hallway is a searched family of connected service-node graphs; rooms are
chosen simultaneously, with hard non-overlap, real shared-wall door clearance,
and a linearized room-to-room relationship cost. Exterior frontage is audited
after assembly, and door cut geometry is checked independently.
"""
from __future__ import annotations

import copy
import itertools
import json
import math
import time
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.optimize import milp, Bounds, LinearConstraint
from scipy.sparse import coo_matrix
from shapely.geometry import box, LineString, Point
from shapely.ops import unary_union

from backend.design.relationship_catalog import RELATIONSHIPS

T = 0.20
PLOT_W, PLOT_D = 15.30, 20.30
EPS = 1e-6
DATA = Path(__file__).parent
SOURCE_009 = (DATA/'baseline_009_corner.json' if (DATA/'baseline_009_corner.json').exists() else DATA.parent/'tests'/'fixtures'/'assl_openings_009_valid.json')


def rect(x, y, w, h, **kw):
    return dict(x=round(x, 4), y=round(y, 4), width=round(w, 4), depth=round(h, 4), **kw)


def geo(r):
    return box(r['x'], r['y'], r['x'] + r['width'], r['y'] + r['depth'])


def contact(a, b):
    ax, ay, aw, ah = (a[k] for k in ('x', 'y', 'width', 'depth'))
    bx, by, bw, bh = (b[k] for k in ('x', 'y', 'width', 'depth'))
    if abs(ax + aw - bx) < EPS or abs(bx + bw - ax) < EPS:
        return max(0, min(ay + ah, by + bh) - max(ay, by))
    if abs(ay + ah - by) < EPS or abs(by + bh - ay) < EPS:
        return max(0, min(ax + aw, bx + bw) - max(ax, bx))
    return 0.0


def overlap(a, b):
    return max(0, min(a['x']+a['width'], b['x']+b['width'])-max(a['x'], b['x'])) * max(0, min(a['y']+a['depth'], b['y']+b['depth'])-max(a['y'], b['y']))


def inside(r):
    return r['x'] >= -EPS and r['y'] >= -EPS and r['x']+r['width'] <= PLOT_W+EPS and r['y']+r['depth'] <= PLOT_D+EPS


def exposed(r, shapes):
    """Maximum uninterrupted external wall interval, not daylight compliance."""
    a = geo(r)
    others = [geo(q) for q in shapes if q is not r and q.get('id') != r.get('id')]
    external = a.boundary.difference(unary_union(others))
    lines = [external] if external.geom_type == 'LineString' else list(getattr(external, 'geoms', []))
    return max((v.length for v in lines if v.geom_type == 'LineString'), default=0)


def window_strip_potential(room, solids, clear_m=.61, min_wall_m=1.10):
    """Conservative exterior clearance screen, never a certified window.

    Reject fake 'exposed' walls facing a 5 cm inaccessible inter-room slit.
    Requires one continuous >=1.10 m interval with a 0.61 m outward free
    strip against *all* placed solids. 009 remains authoritative for real
    openings, operability, light and air movement.
    """
    if room.get('kind') not in ('bathroom', 'bedroom', 'master', 'kitchen'):
        return True
    x0, y0 = room['x'], room['y']
    x1, y1 = x0 + room['width'], y0 + room['depth']
    for face, normal, lo, hi in (
            ('east', x1, y0, y1), ('west', x0, y0, y1),
            ('north', y1, x0, x1), ('south', y0, x0, x1)):
        blocked = []
        for b in solids:
            if b is room or b.get('id') == room.get('id'):
                continue
            bx0, by0 = b['x'], b['y']
            bx1, by1 = bx0 + b['width'], by0 + b['depth']
            if face == 'east':
                near = normal - EPS <= bx0 < normal + clear_m and bx1 >= normal
            elif face == 'west':
                near = normal - clear_m < bx1 <= normal + EPS and bx0 <= normal
            elif face == 'north':
                near = normal - EPS <= by0 < normal + clear_m and by1 >= normal
            else:
                near = normal - clear_m < by1 <= normal + EPS and by0 <= normal
            if near:
                a, z = ((by0, by1) if face in ('east', 'west') else (bx0, bx1))
                if min(hi, z) > max(lo, a):
                    blocked.append((max(lo, a), min(hi, z)))
        cursor, free = lo, 0.
        for a, z in sorted(blocked):
            free = max(free, a - cursor)
            cursor = max(cursor, z)
        if max(free, hi - cursor) >= min_wall_m - EPS:
            return True
    return False


def guest_suite(side='compact',entry_x=7.75):
    base = json.loads((SOURCE_009).read_text(encoding='utf-8'))
    orig = base['rooms_by_floor'][0]
    m = next(x for x in orig if x['kind']=='majlis')
    b = next(x for x in orig if x.get('zone')=='guest' and x['kind']=='bathroom')
    if side == 'compact':
        # Men enter an independent vestibule from its exterior north/south or
        # east wall, with direct majlis and dedicated bathroom door potential.
        # Keep the two entrance channels structurally adjacent but with NO
        # door portal between family and guest. This is a physical shared
        # party wall, not an access path.
        gx=round(entry_x-7.50,4)
        maj = dict(m, **dict(x=gx, y=0., width=5.25, depth=5.25))
        v=rect(gx+5.25,0.,2.25,2.00,kind='corridor',zone='guest',id='men-vestibule',
               name='موزع ضيوف مستقل',guest_distributor=True)
        bath=dict(b, **dict(x=gx+5.25,y=2.00,width=2.25,depth=2.25))
    elif side == 'stacked':
        maj=dict(m,**dict(x=0.,y=0.,width=5.25,depth=5.25))
        v=rect(0.,5.25,2.25,2.,kind='corridor',zone='guest',id='men-vestibule',
               name='موزع ضيوف مستقل',guest_distributor=True)
        bath=dict(b,**dict(x=0.,y=7.25,width=2.25,depth=2.25))
    else:
        raise ValueError(side)
    maj['guest_vestibule']='men-vestibule';bath['guest_vestibule']='men-vestibule'
    assert contact(maj,v)>=1.2 and contact(v,bath)>=1.2
    return [maj,v,bath]


def layouts():
    """Generate bent relational circulation graphs with a capped straight run.

    A south entry spur turns laterally before reaching the family hub. The
    rear service stem is offset so the longest continuous hall axis is bounded
    by the 3m hub plus 3m stem. Optional east branches create real alternatives
    only when a room is actually door-served there and survives 009/010.
    """
    for entry_depth in (1.5, 2.0, 2.5):
        for branch in ('none', 'east', 'east_cross'):
            entry_x = 7.75
            hub_y = entry_depth + 1.5
            entry = rect(entry_x, 0.0, 1.5, entry_depth,
                         kind='corridor', id='family-entry-spur')
            turn = rect(entry_x, entry_depth, 3.0, 1.5,
                        kind='corridor', id='family-entry-turn')
            hub = rect(10.75, hub_y, 3.0, 3.0,
                       kind='corridor', id='family-hub')
            growth = rect(12.25, hub_y + 3.0, 1.5, 3.0,
                          kind='corridor', id='family-growth-node')
            stair = rect(7.75, hub_y, 3.0, 4.6,
                         id='shared-stair', kind='stair',
                         name='درج ثابت بين الدورين')
            walk = [entry, turn, hub, growth]
            if branch in ('east', 'east_cross'):
                walk.append(rect(13.75, hub_y + 1.5, 1.5, 1.5,
                                 kind='corridor', id='east-service-node'))
            if branch == 'east_cross':
                walk.append(rect(13.75, hub_y + 3.0, 1.5, 1.5,
                                 kind='corridor', id='east-cross-node'))

            guests = guest_suite('compact', entry_x)
            all_fixed = walk + [stair] + guests
            if not all(inside(item) for item in all_fixed):
                continue
            if any(overlap(a, b) > EPS
                   for a, b in itertools.combinations(walk + [stair], 2)):
                continue
            if any(overlap(a, b) > EPS for a in walk for b in guests + [stair]):
                continue
            if any(overlap(a, b) > EPS
                   for a, b in itertools.combinations(guests, 2)):
                continue
            if not any(contact(g, h) >= .9 for g in guests for h in walk):
                continue
            hallpoly = unary_union([geo(h) for h in walk])
            if hallpoly.geom_type != 'Polygon':
                continue
            if not any(contact(stair, h) >= 1.2 for h in walk):
                continue
            yield ('bent-entry', entry_depth, branch), walk, stair, guests


def _sizes(room):
    amin, side = room['min_area'],room['min_side']
    vals=[]
    for f in (.9,1.0,1.10,1.2):
        w=math.ceil(max(side,math.sqrt(amin)*f)*4-1e-8)/4+T
        d=math.ceil(max(side,amin/(w-T))*4-1e-8)/4+T
        for a,b in ((w,d),(d,w)):
            if (a-T)*(b-T)+1e-7>=amin and min(a-T,b-T)>=side-1e-7 and (a-T)*(b-T)<=amin*1.26:
                vals.append((round(a,4),round(b,4)))
    return sorted(set(vals),key=lambda x:abs(x[0]/x[1]-1))


def anchors(room,halls,other_fixed,limit_per_room=105):
    options={}
    for w,d in _sizes(room):
        for hall in halls:
            # Correct contact >= 1.20m as required by installed door and jambs.
            xs=[hall['x']-.0, hall['x']+hall['width']-w]
            ys=[hall['y']-d, hall['y']+hall['depth']]
            for step in range(-3,12):
                xs.extend([hall['x']+step*.5, hall['x']+hall['width']-w+step*.5])
                ys.extend([hall['y']+step*.5, hall['y']+hall['depth']-d+step*.5])
            # Horizontal/vertical exterior faces around corridor walls.
            potential=[]
            for x in xs:
                potential.append((x,hall['y']-d))
                potential.append((x,hall['y']+hall['depth']))
            for y in ys:
                potential.append((hall['x']-w,y))
                potential.append((hall['x']+hall['width'],y))
            for x,y in potential:
                c={**copy.deepcopy(room), **rect(x,y,w,d)}
                if not inside(c) or any(overlap(c,p)>EPS for p in other_fixed+halls):continue
                hosted=[h for h in halls if contact(c,h)>=1.2]
                if not hosted:continue
                # Require ample actual external wall exposure, not merely
                # touching the plot boundary, subject to final check.
                if room['kind'] in ('bathroom','bedroom','master','kitchen'):
                    if exposed(c,other_fixed+halls+[c])<1.1:continue
                    # Necessary check before MILP: no false facade facing a
                    # narrow gap beside a fixed stair / guest suite.
                    if not window_strip_potential(c, other_fixed+halls+[c]):continue
                key=(c['x'],c['y'],c['width'],c['depth'])
                if key in options:continue
                cost=.015*(c['x']+c['y'])+.04*abs(w-d)
                cost+=.004*len(hosted)
                options[key]=(c,cost)
    result=sorted(options.values(),key=lambda x:x[1])
    # retain spatial spread rather than only top-left positions
    if len(result)>limit_per_room:
        buckets={}
        for c,cost in result:
            zone=(int(c['x']//3),int(c['y']//3))
            buckets.setdefault(zone,[]).append((c,cost))
        selected=[]
        for index in range(max(len(v) for v in buckets.values())):
            for group in buckets.values():
                if len(group)>index:selected.append(group[index])
                if len(selected)>=limit_per_room:break
            if len(selected)>=limit_per_room:break
        result=selected
    return result


RELATIONSHIP_OBJECTIVE_SCALE = 12.0


def relationship_weights():
    """Return shared functional preferences as MILP soft-objective weights.

    The MILP uses centre-distance as a linearizable spatial proxy. This is
    NOT a measured door route; FunctionalGraph/009 remain the route authority.
    """
    weights = {}
    for source, target, weight, _code, _rule in RELATIONSHIPS:
        key = tuple(sorted((source, target)))
        weights[key] = max(weights.get(key, 0.0), float(weight) * RELATIONSHIP_OBJECTIVE_SCALE)
    return weights


def optimize_floor(rooms,halls,stair,guests,time_limit=7,forbidden=None):
    # Every family room is assigned simultaneously. No sequential blocker room.
    req=sorted(rooms,key=lambda r:(r['kind'],r['id']))
    fixed=[stair]+guests
    groups=[anchors(r,halls,fixed) for r in req]
    if any(not a for a in groups):return None,dict(reason='NO_DOOR_HOSTED_CANDIDATE',options=[len(x) for x in groups])
    choices=[(ri,c,cost) for ri,group in enumerate(groups) for c,cost in group]
    n=len(choices)
    origins=[];k=0
    for group in groups:origins.append(list(range(k,k+len(group))));k+=len(group)
    # One canonical relationship catalogue feeds both the production graph QA
    # and this optimizer's soft preference objective. Route QA remains separate.
    relation_weight_map = relationship_weights()
    pair_weights=[]
    for i,ra in enumerate(req):
        for j,rb in enumerate(req[i+1:],i+1):
            pair=tuple(sorted([ra['kind'],rb['kind']]))
            w=relation_weight_map.get(pair,0.)
            if w:pair_weights.append((i,j,w))
    pairstart=n
    vnum=n+2*len(pair_weights)
    obj=np.zeros(vnum)
    for i,(ri,c,cost) in enumerate(choices):obj[i]=cost
    for i,(_,_,w) in enumerate(pair_weights):obj[pairstart+2*i:pairstart+2*i+2]=w*.13
    rows=[];cols=[];data=[];low=[];up=[]
    def add(weights,lb,ub):
        row=len(low)
        for j,v in weights.items():
            if v:rows.append(row);cols.append(j);data.append(v)
        low.append(lb);up.append(ub)
    for indices in origins:add({j:1 for j in indices},1,1)
    # 009 feedback as genuine MILP no-good constraints, not post-hoc ranking.
    # A forbidden entry contains the whole rejected assignment of this floor.
    # Keep every program item and all hard geometric restrictions unchanged.
    no_good_cuts = 0
    for rejected in (forbidden or []):
        by_id = {r['id']: r for r in rejected}
        selected = []
        for ri, requested in enumerate(req):
            target = by_id.get(requested['id'])
            if target is None:
                break
            match = next((j for j in origins[ri]
                          if all(abs(choices[j][1][key]-target[key]) < EPS
                                 for key in ('x','y','width','depth'))), None)
            if match is None:
                break
            selected.append(match)
        if len(selected) == len(req) and selected:
            add({j:1 for j in selected}, -np.inf, len(selected)-1)
            no_good_cuts += 1
    # Use pairwise clash cuts (sparse) rather than coarse tile exclusions;
    # this is an exact continuous rectangle non-overlap condition for candidates.
    conflicts=0
    for i in range(len(req)):
        for j in range(i+1,len(req)):
            for a in origins[i]:
                for b in origins[j]:
                    if overlap(choices[a][1],choices[b][1])>EPS:
                        add({a:1,b:1},-np.inf,1);conflicts+=1
    for pi,(i,j,w) in enumerate(pair_weights):
        # |dx|, |dy| from selected room centers. Soft cost, hard geometry.
        for axis in ('x','y'):
            rowid=pairstart+2*pi+(0 if axis=='x' else 1)
            centers={}
            for a in origins[i]:
                q=choices[a][1];centers[a]=q[axis]+q['width' if axis=='x' else 'depth']/2
            for b in origins[j]:
                q=choices[b][1];centers[b]=-(q[axis]+q['width' if axis=='x' else 'depth']/2)
            add({**centers,rowid:-1},-np.inf,0)
            add({**{q:-v for q,v in centers.items()},rowid:-1},-np.inf,0)
    mat=coo_matrix((np.array(data), (np.array(rows),np.array(cols))),shape=(len(low),vnum)).tocsr()
    ub=np.full(vnum,np.inf);ub[:n]=1
    integrality=np.array([1]*n+[0]*(vnum-n))
    start=time.monotonic()
    result=milp(c=obj,integrality=integrality,bounds=Bounds(np.zeros(vnum),ub),
                constraints=LinearConstraint(mat,np.array(low),np.array(up)),
                options={'time_limit':time_limit,'mip_rel_gap':.08})
    evidence=dict(options=[len(group) for group in groups],no_good_cuts=no_good_cuts,binary_variables=n,
                  clashes=conflicts,linear_rows=len(low),time_sec=round(time.monotonic()-start,2),
                  solver_status=int(result.status),message=result.message,
                  objective=float(result.fun) if result.fun is not None else None)
    if result.x is None:return None,evidence
    placed=[]
    for indices in origins:
        ix=max(indices,key=lambda idx:result.x[idx]);placed.append(choices[ix][1])
    if any(overlap(a,b)>EPS for a,b in itertools.combinations(placed,2)):
        evidence['reason']='SOLVER_SELECTED_OVERLAP';return None,evidence
    return placed,evidence


def audit(floors,halls_by_floor,guests,stair):
    problems=[];data=[];doors=[]
    for fi,(rooms,halls) in enumerate(zip(floors,halls_by_floor)):
        all_fixed=(guests if fi==0 else [])+[stair]
        shapes=rooms+halls+all_fixed
        if any(not inside(r) for r in shapes):problems.append(f'FLOOR_{fi}_OUTSIDE_PLOT')
        footprint=unary_union([geo(r) for r in shapes])
        if footprint.geom_type != 'Polygon':
            problems.append(f'FLOOR_{fi}_DISCONNECTED_BUILDING_MASS')
        for a,b in itertools.combinations(rooms+all_fixed,2):
            if overlap(a,b)>EPS:problems.append(f'FLOOR_{fi}_ROOM_COLLISION:{a["id"]},{b["id"]}')
        # Guest WC also needs direct exterior window potential; family-only
        # room loop below does not inspect the fixed guest suite.
        if fi == 0:
            for guest in guests:
                if guest.get('kind') in ('bathroom', 'bedroom', 'master', 'kitchen'):
                    if not window_strip_potential(guest, shapes):
                        problems.append(f'FLOOR_0_WINDOW_CLEARANCE_BLOCKED:{guest["id"]}')
        for room in rooms:
            available=[h for h in halls if contact(room,h)>=1.2]
            if not available:problems.append(f'FLOOR_{fi}_NO_REAL_DOOR_HOST:{room["id"]}')
            if room['kind'] in ('bathroom','master','bedroom','kitchen') and exposed(room,shapes)<1.10:
                problems.append(f'FLOOR_{fi}_NO_WINDOW_FACADE:{room["id"]}')
            if not window_strip_potential(room, shapes):
                problems.append(f'FLOOR_{fi}_WINDOW_CLEARANCE_BLOCKED:{room["id"]}')
            if (room['width']-T)*(room['depth']-T)+1e-6<room['min_area']:
                problems.append(f'FLOOR_{fi}_BELOW_MIN_AREA:{room["id"]}')
            if min(room['width']-T,room['depth']-T)+1e-6<room['min_side']:
                problems.append(f'FLOOR_{fi}_BELOW_MIN_SIDE:{room["id"]}')
            if available:doors.append({'floor':fi,'room_id':room['id'],'host':available[0]['id'],
                                        'shared_wall_m':round(contact(room,available[0]),3),
                                        'door_width_m':.9,'actual_door_009_verified':False})
        hallpoly=unary_union([geo(h) for h in halls])
        if hallpoly.geom_type!='Polygon':problems.append(f'FLOOR_{fi}_DISCONNECTED_HALL')
        if not any(contact(stair,h)>=1.2 for h in halls):problems.append(f'FLOOR_{fi}_STAIR_HAS_NO_HALL_WALL')
        if fi==0:
            # outside has both a guest path and family entry; no internal
            # family guest contact represented as a portal.
            if not any(contact(guests[1],r)>=1.2 for r in [guests[0],guests[2]]):
                problems.append('GUEST_VESTIBULE_CONTACT')
            if not any(h.get('id')=='family-entry-spur' and abs(h['y'])<EPS for h in halls):
                problems.append('FAMILY_ENTRANCE_MISSING')
        lengths=[]
        for x in halls:
            lengths.append(max(x['width'],x['depth']))
        # union continuous run cannot be defeated by splitting hallway cells
        hp=unary_union([geo(x) for x in halls]);xs=sorted({round(x,4) for p in ([hp] if hp.geom_type=='Polygon' else hp.geoms) for x,y in p.exterior.coords});ys=sorted({round(y,4) for p in ([hp] if hp.geom_type=='Polygon' else hp.geoms) for x,y in p.exterior.coords})
        maxrun=0
        for direction,limits in [('vertical',xs),('horizontal',ys)]:
            for lo,hi in zip(limits,limits[1:]):
                v=(lo+hi)/2
                line=LineString([(v,-1),(v,PLOT_D+1)]) if direction=='vertical' else LineString([(-1,v),(PLOT_W+1,v)])
                inter=hp.intersection(line)
                pieces=[inter] if inter.geom_type=='LineString' else list(getattr(inter,'geoms',[]))
                maxrun=max(maxrun,max((v.length for v in pieces if v.geom_type=='LineString'),default=0))
        data.append({'floor':fi,'corridor_union_m2':round(hp.area,2),
                     'max_straight_run_m':round(maxrun,2),
                     'hall_nodes':len(halls),'requested_room_count':len(rooms)})
    return {'passed_independent_geometry':not problems,'issues':problems,
            'floors':data,'door_host_evidence':doors,
            'stage009_actual_door_swing_verified':False,
            'privacy_visual_verified':False,'light_airflow_adequacy_verified':False,
            'legal_approval':False}


def search(time_limit=5,limit=60):
    baseline=json.loads((SOURCE_009).read_text(encoding='utf-8'))
    reqs=[[r for r in floor if r.get('request_id') and r.get('zone')!='guest']
          for floor in baseline['rooms_by_floor']]
    attempts=[];found=[]
    for idx,(tag,halls,stair,guests) in enumerate(layouts()):
        if idx>=limit:break
        group=[];reports=[]
        upper_only={'family-entry-spur','family-entry-turn'}
        halls_upper=[h for h in halls if h['id'] not in upper_only]
        per_floor_halls=[halls,halls_upper]
        for fi,requests in enumerate(reqs):
            family,rep=optimize_floor(requests,per_floor_halls[fi],stair,guests if fi==0 else [],time_limit=time_limit)
            reports.append(rep)
            if family is None:break
            group.append(family)
        if len(group)!=2:
            attempts.append({'tag':tag,'status':'NO_FEASIBLE_PACK','solver':reports});continue
        out=audit(group,per_floor_halls,guests,stair)
        attempts.append({'tag':tag,'status':'GEOMETRY_PASS' if out['passed_independent_geometry'] else 'AUDIT_FAIL','audit':out,'solver':reports})
        if out['passed_independent_geometry']:
            candidate={'label':'relationship_first_scipy_milp_012',
                       'topology':tag,'rooms_by_floor':[[stair]+guests+group[0],[stair]+group[1]],
                       'halls_by_floor':per_floor_halls,
                       'doors_potential':out['door_host_evidence'],
                       'independent_audit':out,'solver':reports,
                       'building_envelope_m':[PLOT_W,PLOT_D],
                       'claim_009_verified':False}
            found.append(candidate)
            print('GEOMETRY_PASS',tag,out['floors'],flush=True)
            if len(found)>=max(5,limit):break
        elif idx%10==0:print('AUDIT_FAIL',tag,out['issues'][:5],flush=True)
        elif idx%10==0:print('NO_FEASIBLE',tag,flush=True)
    found.sort(key=lambda c: sum(v['corridor_union_m2'] for v in c['independent_audit']['floors']) + 1.5*c['independent_audit']['floors'][0]['max_straight_run_m'] + .65*c['independent_audit']['floors'][1]['max_straight_run_m'])
    report={'status':'EXPERIMENTAL_GEOMETRY_ONLY','attempts':len(attempts),'passing':len(found),
            'per_attempt':attempts,'ranking_criterion':'family hall union two floors + 1.5 ground max run + 0.65 upper max run',
            'best_tag':found[0]['topology'] if found else None,
            'stage_009_full_validation_passed':False,
            'no_furniture':True,'no_deployment':True}
    (DATA/'stage012_search_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    if found:
        (DATA/'stage012_candidate.json').write_text(json.dumps(found[0],ensure_ascii=False,indent=2))
    return report,found


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--seconds',type=float,default=5)
    parser.add_argument('--layouts',type=int,default=60)
    opts=parser.parse_args()
    report,candidates=search(time_limit=opts.seconds,limit=opts.layouts)
    print('RESULT',report['status'],'attempted',report['attempts'],'passed',report['passing'])