"""Reuse furniture patterns, accepting only real polygon/use-zone/body fits."""
import copy,itertools
from shapely.geometry import box,Point
from shapely.ops import unary_union
from backend.design import furnishing as patterns
from assl.openings_009 import swing,inward,shortest_path
from .geometry import shape,net_shape,axial_edges


def adapter(p):
    walls=[];opened=[]
    for i,d in enumerate(p['opening_model_009'][0]['doors']):
        walls.append(dict(id=f'w{i}',axis='horizontal' if d['axis']=='x' else 'vertical'))
        opened.append(dict(d,wall_id=f'w{i}'))
    return dict(walls=walls,openings=opened,furniture=[])

def groups(p,r,t):
    n=net_shape(r,t);x,y,xx,yy=n.bounds
    # Old furniture patterns use clear dimensions. They never receive gross wall axes.
    q=dict(r,x=x,y=y,width=xx-x,depth=yy-y)
    if r['kind'] in ('majlis','living'):return polygon_seating(p,r,t)
    if r['kind'] in ('bedroom','master'):return bedroom_groups(q)
    if r['kind']=='dining':return patterns.dining_layouts(q)
    if r['kind']=='kitchen':return patterns.kitchen_layouts(q)
    if r['kind']=='bathroom':return patterns.bathroom_layouts(q)
    return patterns.simple_layouts(q,r['kind'])

def group_valid(p,r,items,t):
    n=net_shape(r,t);physical=[q for q in items if q.get('physical',True)]
    def rect(q):return box(q['x'],q['y'],q['x']+q['width'],q['y']+q['depth'])
    for q in items:
        if not n.buffer(1e-6).covers(rect(q)):return False
        if any(not n.buffer(1e-6).covers(rect(z)) for z in q.get('use_zones',[])):return False
    for i,q in enumerate(physical):
        if any(rect(q).intersection(rect(z)).area>1e-6 for z in physical[i+1:]):return False
    for q in items:
        for z in q.get('use_zones',[]):
            if any(other is not q and rect(z).intersection(rect(other)).area>1e-6 for other in physical):return False
    doors=[d for d in p['opening_model_009'][0]['doors'] if r['id'] in d['connects']]
    for d in doors:
        if d['receiving_room']==r['id'] and any(swing(d,r,t).intersection(rect(q)).area>1e-6 for q in physical):return False
    free=n.difference(unary_union([rect(q) for q in physical]));origins=[inward(d,r,.65) for d in doors]
    if not origins:return False
    # All doors in a through-room must connect, and every fixture's use-zone
    # centre must be reachable with a real 0.60m body after furnishing.
    targets=origins[1:]
    for q in items:
        for z in q.get('use_zones',[]):
            standing=free.buffer(-.3,join_style=2).intersection(rect(z))
            if standing.is_empty:return False
            targets.append(list(standing.representative_point().coords)[0])
    for target in targets:
        if shortest_path(free,origins[0],target) is None:return False
    return True

def furnish_clustered(brief,p):
    out=copy.deepcopy(p);furniture=[];missing=[]
    for r in out['rooms_by_floor'][0]:
        if not r.get('request_id'):continue
        found=next((items for items in groups(out,r,brief.wall_thickness) if group_valid(out,r,items,brief.wall_thickness)),None)
        if found is None:missing.append(r['id']);continue
        for i,q in enumerate(found):furniture.append(dict(q,id=r['id']+f'-F{i+1}',room_id=r['id']))
    out['furniture_by_floor']=[furniture];out['furnishing_diagnostics']=dict(missing=missing,body_width_m=.6)
    return out


def polygon_seating(p,r,t):
    n=net_shape(r,t);options=[]
    doors=[d for d in p['opening_model_009'][0]['doors'] if r['id'] in d['connects']]
    keepouts=patterns.port_keepouts(adapter(p),r)
    for e in axial_edges(n):
        horizontal=e['axis']=='x';a=0 if horizontal else 1
        mid=[(e['lo']+e['hi'])/2,e['fixed']] if horizontal else [e['fixed'],(e['lo']+e['hi'])/2]
        probe=list(mid);probe[1-a]+=.1
        positive=n.covers(Point(probe));normal=1 if positive else -1
        pieces=[(e['lo']+.15,e['hi']-.15)]
        for k in keepouts:
            # Ignore a port at a different wall; reserve its actual body approach.
            kpoly=box(k['x'],k['y'],k['x']+k['width'],k['y']+k['depth'])
            from shapely.geometry import LineString
            line=LineString([(e['lo'],e['fixed']+normal*.4),(e['hi'],e['fixed']+normal*.4)]) if horizontal else LineString([(e['fixed']+normal*.4,e['lo']),(e['fixed']+normal*.4,e['hi'])])
            if not line.intersects(kpoly):continue
            lo=k['x' if horizontal else 'y']-.15;hi=lo+k['width' if horizontal else 'depth']+.3
            nxt=[]
            for l,h in pieces:
                if hi<=l or lo>=h:nxt.append((l,h));continue
                if lo>l:nxt.append((l,lo))
                if hi<h:nxt.append((hi,h))
            pieces=nxt
        for lo,hi in pieces:
            length=min(4.0,hi-lo)
            if length<1.4:continue
            start=lo+(hi-lo-length)/2;fixed=e['fixed']+.05 if normal>0 else e['fixed']-.90
            sofa=patterns.fixture('sofa',start if horizontal else fixed,fixed if horizontal else start,length if horizontal else .85,.85 if horizontal else length)
            sofa['seats']=max(2,int(length/.65));sofa['rotation']=(0 if normal>0 else 180) if horizontal else (270 if normal>0 else 90)
            zx=sofa['x']+.1 if horizontal else (fixed+.85 if normal>0 else fixed-.6)
            zy=(fixed+.85 if normal>0 else fixed-.6) if horizontal else sofa['y']+.1
            sofa['use_zones']=[dict(x=zx,y=zy,width=length-.2 if horizontal else .6,depth=.6 if horizontal else length-.2)]
            if n.covers(box(sofa['x'],sofa['y'],sofa['x']+sofa['width'],sofa['y']+sofa['depth'])):options.append(sofa)
    candidates=[]
    for count in (3,2,1):
        for sofas in itertools.combinations(options,count):
            items=list(sofas)
            cx,cy=n.centroid.coords[0]
            table=patterns.fixture('coffee_table',cx-.55,cy-.325,1.1,.65)
            if group_valid(p,r,items+[table],t):items=items+[table]
            if sum(q.get('seats',0) for q in items)>=max(4,r.get('capacity',0)) and group_valid(p,r,items,t):candidates.append(items)
    candidates.sort(key=lambda items:-sum(q.get('seats',0) for q in items))
    yield from candidates


def fixture_issues(req,items,brief):
    """Semantic completeness and real fixture dimensions, beyond collision tests."""
    failures=[];kind=req['kind'];rid=req['id']
    minimum={'sofa':(.8,1.35),'toilet':(.65,.75),'basin':(.5,.65),'sink':(.5,.7),'cooker':(.5,.6),'fridge':(.75,.75),'dining_chair':(.45,.5),'dining_table':(1.0,1.05),'storage':(.5,.7),'single_bed':(1.,2.),'double_bed':(1.8,2.),'wardrobe':(.55,1.6),'desk':(.7,1.5),'washing_machine':(.65,.65),'shower':(1.,1.)}
    for q in items:
        if q['kind'] not in ('sink','cooker') and not q.get('physical',True):failures.append('NONPHYSICAL_FIXTURE:'+rid)
        if q['kind'] in minimum:
            dims=sorted((q['width'],q['depth']));mins=minimum[q['kind']]
            if any(a<b-1e-6 for a,b in zip(dims,mins)):failures.append('UNDERSIZED_FIXTURE:'+rid+':'+q['kind'])
    kinds={q['kind'] for q in items}
    required={'kitchen':{'kitchen_counter','sink','cooker','fridge'},'bathroom':{'toilet','basin'},'dining':{'dining_table','dining_chair'},'storage':{'storage'},'majlis':{'sofa'},'living':{'sofa'},'bedroom':set(),'master':set(),'office':{'desk'},'laundry':{'washing_machine'}}[kind]
    if kind=='bathroom' and req.get('include_shower'):required=required|{'shower'}
    if not required<=kinds:failures.append('INCOMPLETE_FIXTURE_PROGRAM:'+rid)
    if kind in ('bedroom','master'):
        capacity=sum(1 if q['kind']=='single_bed' else 2 for q in items if q['kind'] in ('single_bed','double_bed'))
        if capacity<(req.get('capacity') or 2) or 'wardrobe' not in kinds:failures.append('INCOMPLETE_BEDROOM_PROGRAM:'+rid)
    if kind in ('majlis','living'):
        seats=sum(min(q.get('seats',0),int((max(q['width'],q['depth'])+1e-6)/.65)) for q in items if q['kind']=='sofa')
        if seats<max(4,req.get('capacity',0)):failures.append('INSUFFICIENT_SEATING:'+rid)
    if kind=='dining' and sum(q['kind']=='dining_chair' for q in items)<(brief.dining_seats or 8):failures.append('INSUFFICIENT_DINING_SEATS:'+rid)
    for q in items:
        if q['kind'] in ('sink','cooker'):
            area=box(q['x'],q['y'],q['x']+q['width'],q['y']+q['depth'])
            if not any(box(c['x'],c['y'],c['x']+c['width'],c['y']+c['depth']).covers(area) for c in items if c['kind']=='kitchen_counter'):failures.append('UNHOSTED_COUNTER_FIXTURE:'+rid)
    return list(dict.fromkeys(failures))


def bedroom_groups(r):
    for beds in patterns.bed_layouts(r):
        for wardrobes in patterns.wardrobe_layouts(r):
            yield beds+wardrobes
