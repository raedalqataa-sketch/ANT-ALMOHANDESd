"""Conservative 2D raster access around actual walls/openings/furniture.
Assumes doors are open; excludes windows as access. Not accessibility/code certification.
"""
import math
from collections import deque


def stair_flights(stair):
    y=stair['y']+stair['landing_depth_m'];depth=stair['depth']-stair['landing_depth_m']
    return [dict(x=stair['x'],y=y,width=stair['flight_width_m'],depth=depth),
            dict(x=stair['x']+stair['width']-stair['flight_width_m'],y=y,width=stair['flight_width_m'],depth=depth)]


def floor_access(model,floor,step=.20,body_width=.60):
    from .export import wall_runs
    radius=body_width/2;fp=model['footprint'];ox=fp['x']-.5;oy=fp['y']-.5
    nx=math.ceil((fp['width']+1)/step);ny=math.ceil((fp['depth']+1)/step)
    free=[[False]*nx for _ in range(ny)]
    def raster(q,value,expand=0):
        x0=max(0,math.ceil((q['x']-expand-ox)/step-.5));x1=min(nx,math.floor((q['x']+q['width']+expand-ox)/step-.5)+1)
        y0=max(0,math.ceil((q['y']-expand-oy)/step-.5));y1=min(ny,math.floor((q['y']+q['depth']+expand-oy)/step-.5)+1)
        for j in range(y0,y1):
            for i in range(x0,x1):free[j][i]=value
    for r in floor['rooms']:raster(r,True)
    walls={w['id']:w for w in floor['walls']}
    for o in floor['openings']:
        if o['kind'] not in ('door','passage'):continue
        w=walls.get(o['wall_id'])
        if not w:continue
        x,y=o['center']
        portal=dict(x=x-.2,y=y-o['width']/2,width=.4,depth=o['width']) if w['axis']=='vertical' else dict(x=x-o['width']/2,y=y-.2,width=o['width'],depth=.4)
        raster(portal,True)
    for w in floor['walls']:
        for a,b in wall_runs(floor,w):
            q=dict(x=min(a[0],b[0])-(w['thickness']/2 if w['axis']=='vertical' else 0),y=min(a[1],b[1])-(w['thickness']/2 if w['axis']=='horizontal' else 0),width=abs(a[0]-b[0])+(w['thickness'] if w['axis']=='vertical' else 0),depth=abs(a[1]-b[1])+(w['thickness'] if w['axis']=='horizontal' else 0))
            raster(q,False,radius)
    for q in floor['furniture']:
        if q.get('physical',True):raster(q,False,radius)
    for s in model['stairs']:
        for q in stair_flights(s):raster(q,False,radius)
    def point(i,j):return [round(ox+(i+.5)*step,3),round(oy+(j+.5)*step,3)]
    def nearest(x,y,room):
        choices=[]
        for j in range(ny):
            for i in range(nx):
                if not free[j][i]:continue
                px,py=point(i,j)
                if room['x']<=px<=room['x']+room['width'] and room['y']<=py<=room['y']+room['depth']:
                    choices.append(((px-x)**2+(py-y)**2,i,j))
        return min(choices)[1:] if choices else None
    rooms={r['id']:r for r in floor['rooms']}
    seeds=[]
    if floor['id']=='GF':
        for o in floor['openings']:
            if o['kind']=='door' and 'EXTERIOR' in o['connects']:
                r=rooms.get(o['connects'][0])
                if r is None:continue
                x,y=o['center'];cx=r['x']+r['width']/2;cy=r['y']+r['depth']/2
                w=walls[o['wall_id']]
                if w['axis']=='vertical':x+=.6 if cx>x else -.6
                else:y+=.6 if cy>y else -.6
                node=nearest(x,y,r)
                if node:seeds.append(node)
    else:
        for r in floor['rooms']:
            if r['kind']=='stairs':
                node=nearest(r['x']+r['width']-.45,r['y']+r['depth']-.5,r)
                if node:seeds.append(node)
    parent={s:None for s in seeds};queue=deque(seeds)
    while queue:
        i,j=queue.popleft()
        for di,dj in ((1,0),(-1,0),(0,1),(0,-1)):
            n=(i+di,j+dj)
            if 0<=n[0]<nx and 0<=n[1]<ny and free[n[1]][n[0]] and n not in parent:parent[n]=(i,j);queue.append(n)
    unreachable=[];routes={}
    for r in floor['rooms']:
        target=nearest(r['x']+r['width']/2,r['y']+r['depth']/2,r)
        if target is None or target not in parent:
            unreachable.append(r['id']);continue
        chain=[];p=target
        while p is not None:chain.append(point(*p));p=parent[p]
        chain.reverse()
        # Preserve turns, avoiding thousands of collinear points in evidence reports.
        simplified=[]
        for p in chain:
            if len(simplified)>1 and (simplified[-1][0]-simplified[-2][0])*(p[1]-simplified[-1][1])==(simplified[-1][1]-simplified[-2][1])*(p[0]-simplified[-1][0]):simplified[-1]=p
            else:simplified.append(p)
        routes[r['id']]=simplified
    return dict(unreachable=unreachable,routes=routes,grid_step_m=step,proposed_body_width_m=body_width,
                evidence_scope='Conservative axis-aligned clearance, doors open, rectangular furniture; no wheelchair or legal certification')


def entry_sightlines(model,floor):
    """Sampled centre-to-centre rays through open doors. Does not certify full privacy."""
    from .export import wall_runs
    rooms={r['id']:r for r in floor['rooms']};exposed=[];rays=[]
    openings=[o for o in floor['openings'] if o['kind']=='door' and 'EXTERIOR' in o['connects'] and o['connects'][0].endswith('-hall')]
    for o in openings:
        a=o['center']
        for r in floor['rooms']:
            if r['kind'] not in ('elderly','bedroom','master','living'):continue
            b=(r['x']+r['width']/2,r['y']+r['depth']/2);blocked=False
            for w in floor['walls']:
                for s,e in wall_runs(floor,w):
                    idx=0 if w['axis']=='vertical' else 1;other=1-idx;den=b[idx]-a[idx]
                    if abs(den)<1e-8:continue
                    t=(s[idx]-a[idx])/den
                    p=a[other]+t*(b[other]-a[other])
                    if 1e-5<t<1-1e-5 and min(s[other],e[other])-1e-6<=p<=max(s[other],e[other])+1e-6:blocked=True;break
                if blocked:break
            rays.append(dict(entrance=o['id'],target=r['id'],visible=not blocked,start=a,end=b))
            if not blocked:exposed.append(r['id'])
    return dict(exposed=exposed,rays=rays,scope='Sampled entrance-centre to room-centre rays only; no full visibility polygon or window privacy certification')
