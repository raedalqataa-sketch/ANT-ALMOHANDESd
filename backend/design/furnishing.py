"""Relational furniture layouts with explicit use zones, never arbitrary free rectangles."""
import copy
import math

EPS=1e-7


def overlap(a,b):
    return min(a['x']+a['width'],b['x']+b['width'])-max(a['x'],b['x'])>EPS and min(a['y']+a['depth'],b['y']+b['depth'])-max(a['y'],b['y'])>EPS


def inside(r,q):
    return q['x']>=r['x']-EPS and q['y']>=r['y']-EPS and q['x']+q['width']<=r['x']+r['width']+EPS and q['y']+q['depth']<=r['y']+r['depth']+EPS


def fixture(kind,x,y,w,h,**kwargs):
    return dict(kind=kind,x=x,y=y,width=w,depth=h,capacity=0,seats=0,rotation=0,physical=True,use_zones=[],**kwargs)


def front_zone(q,depth=.7):
    return dict(x=q['x'],y=q['y']+q['depth'],width=q['width'],depth=depth)


def transform(q,r,rotation):
    out=copy.deepcopy(q)
    def box(b):
        x,y,w,h=b['x'],b['y'],b['width'],b['depth']
        if rotation==0:return dict(x=r['x']+x,y=r['y']+y,width=w,depth=h)
        if rotation==90:return dict(x=r['x']+r['width']-y-h,y=r['y']+x,width=h,depth=w)
        if rotation==180:return dict(x=r['x']+r['width']-x-w,y=r['y']+r['depth']-y-h,width=w,depth=h)
        return dict(x=r['x']+y,y=r['y']+r['depth']-x-w,width=h,depth=w)
    out.update(box(q));out['rotation']=(q.get('rotation',0)+rotation)%360
    out['use_zones']=[box(z) for z in q.get('use_zones',[])]
    return out


def port_keepouts(floor,r):
    boxes=[]
    walls={w['id']:w for w in floor['walls']}
    for o in floor['openings']:
        if o['kind']=='window' or r['id'] not in o['connects']:continue
        wall=walls[o['wall_id']];x,y=o['center'];width=o['width']
        if wall['axis']=='vertical':
            left=x<r['x']+r['width']/2
            boxes.append(dict(x=r['x'] if left else r['x']+r['width']-.7,y=y-width/2-.12,width=.7,depth=width+.24))
        else:
            top=y<r['y']+r['depth']/2
            boxes.append(dict(x=x-width/2-.12,y=r['y'] if top else r['y']+r['depth']-.7,width=width+.24,depth=.7))
        if o.get('swing_rect') and o['connects'][0]==r['id']:boxes.append(o['swing_rect'])
    return boxes


def valid_group(floor,r,items,existing=None):
    existing=existing if existing is not None else [q for q in floor['furniture'] if q['room_id']==r['id']]
    physical=[q for q in items+existing if q.get('physical',True)]
    keepouts=port_keepouts(floor,r)
    for q in items:
        if not inside(r,q):return False
        if q.get('physical',True) and any(overlap(q,k) for k in keepouts):return False
        if any(not inside(r,z) for z in q.get('use_zones',[])):return False
    for i,a in enumerate(physical):
        if any(overlap(a,b) for b in physical[i+1:]):return False
    for q in items+existing:
        for z in q.get('use_zones',[]):
            if any(other is not q and overlap(z,other) for other in physical):return False
    return True


def add(floor,r,items,revision):
    for q in items:
        q=dict(q,id=f"{floor['id']}-F{len(floor['furniture'])+1:03}",floor_id=floor['id'],room_id=r['id'],revision_id=revision,status='DESIGNER_PROPOSED',source_ref='PROPOSED_FURNITURE_DIMENSIONS_AND_USE_ZONES')
        floor['furniture'].append(q)


def bed_layouts(r):
    count=1 if r['kind']=='master' else 2
    for rotation in (0,90,180,270):
        W,H=(r['depth'],r['width']) if rotation in (90,270) else (r['width'],r['depth'])
        for lateral in ((0,) if count==1 else (0,.4,-.4)):
            if count==1:
                bx=(W-1.8)/2
                beds=[fixture('double_bed',bx,.2,1.8,2.0)]
                beds[0]['capacity']=2
                beds[0]['use_zones']=[dict(x=bx,y=2.2,width=1.8,depth=.7),dict(x=bx-.6,y=.9,width=.6,depth=1.0),dict(x=bx+1.8,y=.9,width=.6,depth=1.0)]
                tables=[fixture('bedside',bx-.55,.25,.45,.45),fixture('bedside',bx+1.9,.25,.45,.45)]
            else:
                bx1=.65+lateral;bx2=W-1.65+lateral
                beds=[fixture('single_bed',bx1,.2,1,2),fixture('single_bed',bx2,.2,1,2)]
                for i,b in enumerate(beds):
                    b['capacity']=1
                    beds[i]['use_zones']=[dict(x=b['x'],y=2.2,width=1,depth=.7),dict(x=b['x']+1 if i==0 else b['x']-.6,y=.9,width=.6,depth=1.0)]
                tables=[fixture('bedside',bx1-.55,.25,.45,.45),fixture('bedside',bx2+1.1,.25,.45,.45)]
            if r.get('capacity')==1:
                # Explicit customer capacity; existing profiles without this field are unchanged.
                if r['kind']=='master':
                    bx=(W-1.)/2
                    beds=[fixture('single_bed',bx,.2,1.,2.,)]
                    beds[0]['capacity']=1
                    beds[0]['use_zones']=[dict(x=bx,y=2.2,width=1.,depth=.7),dict(x=bx+1.,y=.9,width=.6,depth=1.)]
                    tables=[]
                else:
                    beds=beds[:1];tables=tables[:1]
            for group in (beds+tables,beds):yield [transform(q,r,rotation) for q in group]


def wardrobe_layouts(r):
    for rotation in (0,90,180,270):
        W,H=(r['depth'],r['width']) if rotation in (90,270) else (r['width'],r['depth'])
        for length in (2.0,1.6):
            for x in ((W-length)/2,W-length-.1,.1):
                q=fixture('wardrobe',x,.05,length,.55);q['use_zones']=[front_zone(q,.7)]
                yield [transform(q,r,rotation)]


def seating_layouts(floor,r):
    keepouts=port_keepouts(floor,r)
    for edges in [('north','west','east'),('south','west','east'),('west','north','south'),('east','north','south'),('west','east'),('north','south')]:
        items=[]
        for edge in edges:
            horizontal=edge in ('north','south')
            fixed=r['y']+.2 if edge=='north' else r['y']+r['depth']-1.05 if edge=='south' else r['x']+.2 if edge=='west' else r['x']+r['width']-1.05
            start=(r['x'] if horizontal else r['y'])+.2
            end=(r['x']+r['width'] if horizontal else r['y']+r['depth'])-.2
            spans=[(start,end)]
            strip=dict(x=start if horizontal else fixed,y=fixed if horizontal else start,width=end-start if horizontal else .85,depth=.85 if horizontal else end-start)
            for blocked in keepouts+items:
                if not overlap(strip,blocked):continue
                lo=(blocked['x'] if horizontal else blocked['y'])-.2;hi=lo+(blocked['width'] if horizontal else blocked['depth'])+.4
                next_spans=[]
                for a,b in spans:
                    if hi<=a or lo>=b:next_spans.append((a,b))
                    else:
                        if a<lo:next_spans.append((a,lo))
                        if hi<b:next_spans.append((hi,b))
                spans=next_spans
            for a,b in sorted(spans,key=lambda s:-(s[1]-s[0])):
                length=min(4.2,b-a)
                if length<1.35:continue
                q=fixture('sofa',a if horizontal else fixed,fixed if horizontal else a,length if horizontal else .85,.85 if horizontal else length)
                q['seats']=max(2,int(length/.68));q['rotation']={'north':0,'east':90,'south':180,'west':270}[edge]
                if edge=='north':z=dict(x=a+.1,y=fixed+.85,width=length-.2,depth=.6)
                elif edge=='south':z=dict(x=a+.1,y=fixed-.6,width=length-.2,depth=.6)
                elif edge=='west':z=dict(x=fixed+.85,y=a+.1,width=.6,depth=length-.2)
                else:z=dict(x=fixed-.6,y=a+.1,width=.6,depth=length-.2)
                q['use_zones']=[z]
                if valid_group(floor,r,items+[q],existing=[]):items.append(q)
        if items:
            for w,h in [(1.2,.7),(.7,1.2),(.7,.5)]:
                q=fixture('coffee_table',r['x']+(r['width']-w)/2,r['y']+(r['depth']-h)/2,w,h)
                if valid_group(floor,r,items+[q],existing=[]):items.append(q);break
            yield items


def kitchen_layouts(r):
    for rotation in (0,90,180,270):
        W,H=(r['depth'],r['width']) if rotation in (90,270) else (r['width'],r['depth'])
        if W<2 or H<2:continue
        top=fixture('kitchen_counter',.05,.05,W-.1,.62)
        top['use_zones']=[dict(x=.15,y=.67,width=W-.3,depth=.85)]
        sink=fixture('sink',.35,.1,.7,.5);sink['physical']=False
        cooker=fixture('cooker',W-1.05,.1,.6,.5);cooker['physical']=False
        fridge=fixture('fridge',W-.8,H-.85,.75,.75);fridge['rotation']=180
        fridge['use_zones']=[dict(x=W-.8,y=H-1.65,width=.75,depth=.8)]
        for fx in (W-.8,.05):
            fridge['x']=fx;fridge['use_zones'][0]['x']=fx
            base=[top,sink,cooker,fridge]
            for island in (True,False):
                items=copy.deepcopy(base)
                if island and W>4.0 and H>4.5:
                    q=fixture('kitchen_island',W/2-.85,H/2-.4,1.7,.8)
                    q['use_zones']=[dict(x=q['x'],y=q['y']-.9,width=q['width'],depth=.9)]
                    items.append(q)
                yield [transform(q,r,rotation) for q in items]


def bathroom_layouts(r):
    shower=r['id'].endswith(('family-bath','master-bath','child-bath'))
    for rotation in (0,90,180,270):
        W,H=(r['depth'],r['width']) if rotation in (90,270) else (r['width'],r['depth'])
        wc=fixture('toilet',.15,.1,.65,.75)
        wc['use_zones']=[dict(x=.15,y=.85,width=.65,depth=.65)]
        basin=fixture('basin',W-.8,.05,.65,.5)
        basin['use_zones']=[front_zone(basin,.65)]
        for shower_mode in (0,1,2):
            items=[wc,basin]
            if shower:
                sx,sy=(.1,H-1.1) if shower_mode==0 else (W-1.1,H-1.1) if shower_mode==1 else (W-1.1,1.3)
                q=fixture('shower',sx,sy,1,1)
                q['use_zones']=[dict(x=sx,y=sy-.65,width=1,depth=.65)]
                items=items+[q]
            yield [transform(q,r,rotation) for q in items]


def simple_layouts(r,kind):
    for rotation in (0,90,180,270):
        W,H=(r['depth'],r['width']) if rotation in (90,270) else (r['width'],r['depth'])
        if kind=='wash':q=fixture('basin',max(.05,(W-1.1)/2),.05,1.1,.5);q['use_zones']=[front_zone(q,.7)]
        elif kind=='laundry':q=fixture('washing_machine',.1,.1,.65,.65);q['use_zones']=[front_zone(q,.75)]
        elif kind=='office':q=fixture('desk',(W-1.5)/2,.1,1.5,.7);q['use_zones']=[front_zone(q,.9)]
        else:q=fixture('storage',.05,.05,max(.7,W-.1),.5);q['use_zones']=[front_zone(q,.7)]
        yield [transform(q,r,rotation)]


def dining_layouts(r):
    for rotation in (0,90,180,270):
        W,H=(r['depth'],r['width']) if rotation in (90,270) else (r['width'],r['depth'])
        for seats in (10,8):
            tw=2.5 if seats==10 else 2.1;th=1.05
            for yshift in (0,.4,-.4):
                x=(W-tw)/2;y=(H-th)/2+yshift
                items=[fixture('dining_table',x,y,tw,th)]
                for side in (0,1):
                    count=4 if seats==10 else 3
                    for i in range(count):
                        chair=fixture('dining_chair',x+.05+i*(tw-.55)/(count-1),y-.6 if side==0 else y+th+.15,.5,.45)
                        chair['rotation']=0 if side==0 else 180;chair['seats']=1
                        # Chair withdrawal: the additional strip behind each chair, not the table itself.
                        chair['use_zones']=[dict(x=chair['x'],y=chair['y']-.45 if side==0 else chair['y']+.45,width=.5,depth=.45)]
                        items.append(chair)
                for side in (0,1):
                    chair=fixture('dining_chair',x-.6 if side==0 else x+tw+.15,y+.25,.45,.5);chair['rotation']=270 if side==0 else 90;chair['seats']=1
                    chair['use_zones']=[dict(x=chair['x']-.45 if side==0 else chair['x']+.45,y=chair['y'],width=.45,depth=.5)];items.append(chair)
                yield [transform(q,r,rotation) for q in items]


def furnish_floor(floor,revision):
    for r in floor['rooms']:
        kind=r['kind'];groups=[]
        if kind in ('bedroom','elderly'):
            def complete_bedrooms():
                fallbacks=[]
                for beds in bed_layouts(r):
                    if not valid_group(floor,r,beds):continue
                    for storage in wardrobe_layouts(r):
                        if valid_group(floor,r,beds+storage):yield beds+storage
                    fallbacks.append(beds)
                yield from fallbacks
            groups=complete_bedrooms()
        elif kind=='master':groups=bed_layouts(r)
        elif kind in ('living','majlis'):groups=seating_layouts(floor,r)
        elif kind=='kitchen':groups=kitchen_layouts(r)
        elif kind=='bathroom':groups=bathroom_layouts(r)
        elif kind=='dining':groups=dining_layouts(r)
        elif kind in ('office','laundry','wash','storage'):groups=simple_layouts(r,kind)
        elif kind=='dressing':groups=wardrobe_layouts(r)
        else:continue
        accepted=[g for g in groups if valid_group(floor,r,g)]
        if accepted:
            if kind in ('living','majlis'):accepted.sort(key=lambda g:(any(q['kind']=='coffee_table' for q in g),-abs(sum(q['seats'] for q in g)-9)),reverse=True)
            add(floor,r,accepted[0],revision)
        else:floor.setdefault('furnishing_notes',[]).append(dict(room_id=r['id'],reason='لم توجد تشكيلة فرش تحقق الحدود والفتحات وخلوص الاستعمال المقترح'))
        if kind in ('bedroom','elderly') and not any(q['room_id']==r['id'] and q['kind']=='wardrobe' for q in floor['furniture']):
            for group in wardrobe_layouts(r):
                if valid_group(floor,r,group):add(floor,r,group,revision);break
            else:floor.setdefault('furnishing_notes',[]).append(dict(room_id=r['id'],reason='لم تتسع خزانة بفراغ استعمالها'))
        if kind=='office' and accepted:
            desk=accepted[0][0]
            # Desk chair is drawn as a symbol inside its use zone, not as a second obstacle.
        if kind in ('living','majlis','master','bedroom','elderly'):
            floor['decorations'].append(dict(kind='rug',x=r['x']+r['width']*.19,y=r['y']+r['depth']*.29,width=r['width']*.62,depth=r['depth']*.48,room_id=r['id']))
