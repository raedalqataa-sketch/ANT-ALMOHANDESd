"""Measured draft checks and shared door/stair geometry (not code certification)."""
import math
import re
from .furnishing import overlap,inside


def normalize(text):
    text=re.sub(r'[\u064b-\u065f\u0640]','',text)
    return re.sub(r'\s+',' ',text.translate(str.maketrans('أإآىة','ااايه'))).strip()


def resolve_notes(brief):
    """Recognize only complete, narrow phrases. Unknown or negated clauses remain pending."""
    clauses=[s.strip() for s in re.split(r'[\n،,؛;.!؟]+',brief.notes) if s.strip()]
    mapped=[];unmapped=[];majlis=[r for r in brief.rooms if r.kind=='majlis' and r.floor==0]
    for text in clauses:
        n=normalize(text)
        if n in ('مجلس رجال','اريد مجلس رجال','مطلوب مجلس رجال') and len(majlis)==1:
            mapped.append({'text':text,'action':'classify_men_majlis','request_id':majlis[0].id})
        elif n in ('مدخل ضيوف مستقل','مدخل رجال مستقل','فصل مدخل الضيوف') and majlis and brief.separate_guest_entry:
            mapped.append({'text':text,'action':'separate_guest_entry'})
        else:unmapped.append(text)
    return {'mapped':mapped,'unmapped':unmapped,'method':'explicit Arabic phrases only; no language model inference'}


def door_geometry(floor,opening):
    wall=next(w for w in floor['walls'] if w['id']==opening['wall_id'])
    axis=0 if wall['axis']=='horizontal' else 1
    room=next(r for r in floor['rooms'] if r['id']==opening['connects'][0])
    side=1 if room['y' if axis==0 else 'x']+room['depth' if axis==0 else 'width']/2>opening['center'][1-axis] else -1
    hinge=list(opening['center']);hinge[axis]-=opening['width']/2
    closed=[0.,0.];closed[axis]=1.
    opened=[0.,0.];opened[1-axis]=side
    return {'hinge':hinge,'closed_direction':closed,'open_direction':opened,'radius':opening['width']}


def sweep_hits_box(geometry,q):
    """Exact quarter-disc vs axis-aligned rectangle test for orthogonal doors."""
    h=geometry['hinge'];u=geometry['closed_direction'];v=geometry['open_direction'];r=geometry['radius']
    corners=[(x,y) for x in (q['x'],q['x']+q['width']) for y in (q['y'],q['y']+q['depth'])]
    us=[(x-h[0])*u[0]+(y-h[1])*u[1] for x,y in corners]
    vs=[(x-h[0])*v[0]+(y-h[1])*v[1] for x,y in corners]
    if max(us)<=1e-6 or max(vs)<=1e-6:return False
    return max(0,min(us))**2+max(0,min(vs))**2<(r-1e-6)**2


def make_stairs(model):
    stairs=[];height=model['brief']['floor_height'];risers=math.ceil(height/.18)
    if risers%2:risers+=1
    half=risers//2;tread=.28;run=(half-1)*tread
    for f in model['floors']:
        for room in f['rooms']:
            if room['kind']!='stair':continue
            x,y,w,d=[room[k] for k in ('x','y','width','depth')]
            apron=1.0;landing=1.1;flight=1.1
            flights=[dict(x=sx,y=y+apron,width=flight,depth=run) for sx in (x,x+w-flight)]
            entry=dict(x=x,y=y,width=w,depth=apron)
            far=dict(x=x,y=y+apron+run,width=w,depth=landing)
            s=dict(id=f['id']+'-STAIR',floor_id=f['id'],room_id=room['id'],x=x,y=y,width=w,depth=d,
                   riser_count=risers,riser_height_m=height/risers,tread_depth_m=tread,flight_width_m=flight,
                   landing_depth_m=landing,flights=flights,entry_apron=entry,landing=far,
                   required_depth_m=apron+run+landing,proposed_headroom_m=model['brief']['stair_headroom'])
            stairs.append(s)
    return stairs


def sweep_polygon(g):
    h=g['hinge'];u=g['closed_direction'];v=g['open_direction'];r=g['radius']
    return [h]+[[h[0]+r*(math.cos(i*math.pi/64)*u[0]+math.sin(i*math.pi/64)*v[0]),h[1]+r*(math.cos(i*math.pi/64)*u[1]+math.sin(i*math.pi/64)*v[1])] for i in range(33)]


def sectors_overlap(a,b):
    aa,bb=sweep_polygon(a),sweep_polygon(b)
    for poly in (aa,bb):
        for p,q in zip(poly,poly[1:]+poly[:1]):
            nx,ny=-(q[1]-p[1]),q[0]-p[0]
            av=[x*nx+y*ny for x,y in aa];bv=[x*nx+y*ny for x,y in bb]
            if min(max(av),max(bv))-max(min(av),min(bv))<=1e-6:return False
    return True


def movement_evidence(model,floor):
    from .walkability import floor_access
    # The generic adapter recognizes OUTSIDE/stair and uses modeled flights per floor.
    access=floor_access(model,floor,step=.15,body_width=.60)
    collisions=[]
    for o in floor['openings']:
        if o['kind']!='door':continue
        g=door_geometry(floor,o)
        for q in floor['furniture']:
            if q.get('physical',True) and sweep_hits_box(g,q):collisions.append({'door':o['id'],'fixture':q['id']})
        for s in model['stairs']:
            if s['floor_id']==floor['id']:
                for i,q in enumerate(s['flights']):
                    if sweep_hits_box(g,q):collisions.append({'door':o['id'],'stair_flight':i})
    doors=[o for o in floor['openings'] if o['kind']=='door']
    for i,a in enumerate(doors):
        for b in doors[i+1:]:
            # Broad phase avoids polygon tests for distant doors. Main entries have no precomputed swing box.
            ga,gb=door_geometry(floor,a),door_geometry(floor,b)
            if math.dist(ga['hinge'],gb['hinge'])>ga['radius']+gb['radius']:continue
            if sectors_overlap(ga,gb):collisions.append({'door':a['id'],'other_door':b['id']})
    return {'access':access,'door_sweep_collisions':collisions,
            'scope':'0.60 m axis-aligned body, 0.15 m grid, doors open; exact door sweep vs furniture/flight rectangles; door-to-door sectors use 32 arc segments (under 1 mm chord error); not accessibility or code approval'}


def privacy_evidence(model):
    f=model['floors'][0];guests=[r for r in f['rooms'] if r.get('zone')=='guest']
    adjacency={r['id']:set() for r in f['rooms']};starts=[]
    for o in f['openings']:
        if o['kind']!='door' or o.get('access_control')=='family_only':continue
        ids=[i for i in o['connects'] if i in adjacency]
        if o.get('guest_entry'):starts.extend(ids)
        for a in ids:adjacency[a].update(i for i in ids if i!=a)
    reached=set(starts);queue=list(starts)
    while queue:
        for v in adjacency[queue.pop()]-reached:reached.add(v);queue.append(v)
    protected={r['id'] for r in f['rooms'] if r.get('zone')!='guest' and r['kind'] not in ('reserve',)}
    return {'guest_rooms':[r['id'] for r in guests], 'reachable_by_guest':sorted(reached),
            'missing_guest_access':[r['id'] for r in guests if r['id'] not in reached],
            'family_rooms_exposed':sorted(reached&protected),
            'guest_entries':[o['id'] for o in f['openings'] if o.get('guest_entry')],
            'scope':'Door graph with controlled family doors closed; not full visual/acoustic privacy or window sightline approval'}


def repair_furniture_access(model,revision):
    """Try alternate complete furniture groups; never delete a required bed to pass access."""
    from .walkability import floor_access
    from .furnishing import furnish_floor
    import copy
    for f in model['floors']:
        initial=floor_access(model,f,step=.15,body_width=.60)
        for rid in initial['unreachable']:
            room=next(r for r in f['rooms'] if r['id']==rid)
            count=f.get('furnishing_choice_counts',{}).get(rid,0)
            original=copy.deepcopy([q for q in f['furniture'] if q['room_id']==rid])
            all_rooms=f['rooms']
            for choice in range(1,min(count,16)):
                f['furniture']=[q for q in f['furniture'] if q['room_id']!=rid]
                try:
                    f['rooms']=[room];furnish_floor(f,revision,{rid:choice})
                finally:f['rooms']=all_rooms
                if rid not in floor_access(model,f,step=.15,body_width=.60)['unreachable']:break
            else:
                f['furniture']=[q for q in f['furniture'] if q['room_id']!=rid]+original
        for i,q in enumerate(f['furniture']):q['id']=f['id']+f'-F{i+1:03}'
