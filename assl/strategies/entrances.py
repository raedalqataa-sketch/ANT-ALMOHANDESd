"""Raised entry platforms from authoritative doors, including real step levels.

Uncovered conceptual landings; not a local-code/setback or step-free certificate.
"""
import math
from shapely.geometry import Polygon,box
from shapely.affinity import affine_transform
from shapely.ops import unary_union
from assl.openings_009 import inward
from backend.design.general_models import VillaBrief
from .geometry import shape


def build_platforms(brief,p):
    if brief.entry_plinth_height_m<=0:return []
    objects=p['rooms_by_floor'][0]+p['halls_by_floor'][0];ids={r['id']:r for r in objects}
    result=[];height=brief.entry_plinth_height_m
    risers=max(1,math.ceil(height/.15-1e-8));riser=height/risers;going=.32
    offset=brief.wall_thickness/2
    mass=unary_union([shape(r) for r in objects]).buffer(offset,join_style=2)
    site=parcel(brief)
    occupied=[]
    for door in p.get('opening_model_009',[{}])[0].get('doors',[]):
        if door['connects'][0]!='OUTSIDE':continue
        target=ids[door['receiving_room']];axis=0 if door['axis']=='x' else 1
        normal=1-axis;center=door['center'];inside=inward(door,target,1)
        sign=-1 if inside[normal]>center[normal] else 1
        main=target['id']=='main-foyer';family=target['id']=='family-foyer' and not target.get('guest_entry')
        width=max(door['width']+(1.2 if main else .6),1.8);depth=1.5 if main else 1.2
        origin=list(center);origin[normal]+=sign*offset
        if axis==0:
            frame=[1,0,0,sign,*origin]
            inverse=[1,0,0,sign,-origin[0],-sign*origin[1]]
        else:
            frame=[0,sign,1,0,*origin]
            inverse=[0,1,sign,0,-origin[1],-sign*origin[0]]
        local_mass=affine_transform(mass,inverse)
        local_site=affine_transform(site,inverse) if site is not None else None
        local_occupied=[affine_transform(item,inverse) for item in occupied]
        reach=depth+risers*going
        left,right=-width/2,width/2

        def fits(region,runout):
            return ((local_site is None or local_site.buffer(1e-6).covers(runout))
                    and runout.intersection(local_mass).area<=1e-6
                    and all(region.intersection(other).area<=1e-6 for other in local_occupied))

        if family:
            # Bring the landing and steps to adjacent return walls where they fit.
            adjacent=local_mass.intersection(box(left-.45,.0001,right+.45,reach))
            for part in getattr(adjacent,'geoms',[adjacent]):
                if part.is_empty:continue
                lo,v0,hi,_=part.bounds
                if v0>.001:continue
                if left-.45<=hi<=left and fits(box(hi,0,right,reach-going),box(hi,0,right,reach)):
                    left=hi
                if right<=lo<=right+.45 and fits(box(left,0,lo,reach-going),box(left,0,lo,reach)):
                    right=lo

        sides=[False,False]
        for index in range(2):
            trial=sides.copy();trial[index]=True
            runout=box(left-risers*going*trial[0],0,right+risers*going*trial[1],reach)
            occupied_run=box(left-(risers-1)*going*trial[0],0,right+(risers-1)*going*trial[1],reach-going)
            if fits(occupied_run,runout):sides=trial

        def level(index):
            return box(left-index*going*sides[0],0,right+index*going*sides[1],depth+index*going)

        def polygon(region):
            return [list(q) for q in list(affine_transform(region,frame).exterior.coords)[:-1]]

        def line(a,b):
            return [[frame[0]*u+frame[1]*v+origin[0],frame[2]*u+frame[3]*v+origin[1]] for u,v in (a,b)]

        steps=[dict(polygon=polygon(level(i+1).difference(level(i))),level_m=height-(i+1)*riser)
               for i in range(risers-1)]
        lines=[]
        for i in range(risers):
            l,_,r,f=level(i).bounds
            segments=[((l,f),(r,f))]
            if sides[0]:segments.append(((l,0),(l,f)))
            if sides[1]:segments.append(((r,0),(r,f)))
            lines.extend(dict(points=line(a,b),top_level_m=height-i*riser,bottom_level_m=height-(i+1)*riser)
                         for a,b in segments)
        occupied.append(affine_transform(level(risers-1),frame))
        result.append(dict(door_id=door['id'],role='principal' if main else 'secondary',
                           level_m=height,risers=risers,riser_height_m=riser,going_m=going,
                           landing_depth_m=depth,width_m=right-left,landing_polygon=polygon(level(0)),
                           approaches=['front']+[side for side,enabled in zip(('left','right'),sides) if enabled],
                           treads=steps,riser_lines=lines))
    return result


def parcel(brief):
    if not isinstance(brief,VillaBrief):
        return None
    offset=brief.wall_thickness/2
    ox=brief.setbacks.west+offset;oy=brief.setbacks.south+offset
    return box(-ox,-oy,brief.plot_width-ox,brief.plot_depth-oy)


def entrance_issues(brief,p):
    expected=build_platforms(brief,p);actual=p.get('entrance_platforms',[]);issues=[]
    indexed={q.get('door_id'):q for q in actual}
    if len(indexed)!=len(actual):issues.append('DUPLICATE_ENTRY_PLATFORM')
    objects=p['rooms_by_floor'][0]+p['halls_by_floor'][0]
    mass=unary_union([shape(r) for r in objects]).buffer(brief.wall_thickness/2,join_style=2)
    site=parcel(brief);footprints=[]
    for spec in expected:
        key=spec['door_id'];given=indexed.get(key)
        if given is None:issues.append('MISSING_ENTRY_PLATFORM:'+key);continue
        if given!=spec:issues.append('ENTRY_PLATFORM_GEOMETRY:'+key)
        landing=Polygon(spec['landing_polygon']);parts=[landing]+[Polygon(q['polygon']) for q in spec['treads']]
        g=unary_union(parts)
        if g.geom_type!='Polygon' or not g.is_valid or g.interiors:issues.append('INVALID_ENTRY_PLATFORM:'+key)
        if site is not None and not site.buffer(1e-6).covers(g):issues.append('ENTRY_PLATFORM_OUTSIDE_PLOT:'+key)
        if g.intersection(mass).area>1e-6:issues.append('ENTRY_PLATFORM_BUILDING_COLLISION:'+key)
        if any(g.intersection(other).area>1e-6 for other in footprints):issues.append('ENTRY_PLATFORM_COLLISION:'+key)
        footprints.append(g)
    if set(indexed)-{e['door_id'] for e in expected}:issues.append('UNAUTHORIZED_ENTRY_PLATFORM')
    return issues
