"""Metric wing search for rectangular villa plots (1–2 floors).

Copyright (c) 2026 ANT ALMOHANDES. New module licensed under MIT; see
web_generator/ENGINE_LICENSE. Beam search assigns the actual requested spaces to
variable wing lanes; there is no pre-filled family program or raster synthesis.
"""
import copy
import hashlib
import json
import math
from pathlib import Path
from uuid import uuid4
from .general_models import VillaBrief
from .furnishing import furnish_floor, overlap, inside
from .furniture_symbols import SYMBOL_VERSION
from . import saudi_rules
from .general_geometry import union_polygons,signed_area,annotate
from .general_quality import resolve_notes,make_stairs,movement_evidence,privacy_evidence,repair_furniture_access

EPS=1e-6
FAMILIES={'L':'جناحان مرتبطان','U':'توزيع حول فناء','stepped':'تكوين متنوع العمق','spine':'توزيع مدمج بممر محوري','cross':'عناقيد غرف حول عقدة حركة'}


def box(x,y,w,d,**kw):return dict(x=x,y=y,width=w,depth=d,**kw)
def area(r):return r['width']*r['depth']


def topology(family,W,D,c,ratio,top):
    """Disjoint cells tile a nonrectangular mass; lanes abut connected halls."""
    a=W*ratio;b=D*top
    if family=='cross':
        # Four independently allocated clusters around a connected circulation node.
        return [box(a-c/2,0,c,D),box(0,b-c/2,a-c/2,c),box(a+c/2,b-c/2,W-a-c/2,c)],[
            box(x,y,w,d,axis='y',door_side=side)
            for x,w,side in ((0,a-c/2,'east'),(a+c/2,W-a-c/2,'west'))
            for y,d in ((0,b-c/2),(b+c/2,D-b-c/2))]
    if family=='spine':
        # Additional compact rectangular search family; no mandatory L/U/recessed shape.
        return [box(a-c/2,0,c,D)],[box(0,0,a-c/2,D,axis='y',door_side='east'),box(a+c/2,0,W-a-c/2,D,axis='y',door_side='west')]
    if family in ('L','U'):
        halls=[box(a-c,0,c,D),box(a,b-c,W-a,c)]
        lanes=[box(0,0,a-c,D,axis='y',door_side='east'),box(a,0,W-a,b-c,axis='x',door_side='south')]
        if family=='U':
            if W-2*a<2.4:return None
            halls.append(box(W-a,b,c,D-b))
            lanes.append(box(W-a+c,b,a-c,D-b,axis='y',door_side='west'))
        return halls,lanes
    # Two genuine recesses; a continuous spine connects both sides of all steps.
    spine=W*.5-c/2
    halls=[box(spine,0,c,D)]
    lanes=[]
    first=D*top;second=D*min(.80,top+.30)
    for lo,hi,x0,x1 in [(0,first,0,W),(first,second,W*.12,W),(second,D,W*.12,W*.80)]:
        lanes += [box(x0,lo,spine-x0,hi-lo,axis='y',door_side='east'),
                  box(spine+c,lo,x1-spine-c,hi-lo,axis='y',door_side='west')]
    return halls,lanes


def length_for(room,lane,t):
    cross=lane['width' if lane['axis']=='y' else 'depth']-t
    if room.get('guest_distributor'):return room['min_side']+t
    if cross+EPS<room['min_side']:return math.inf
    if room['kind']=='dining' and cross<3.45-EPS:return math.inf  # proposed furniture + 0.60 m movement clearance, not a legal minimum
    length=max(room['min_side'],room['min_area']/cross,cross/2.8)
    if max(cross,length)/min(cross,length)>2.8:return math.inf
    return length+t


def allocate(requests,lanes,t,guest_clear_width=1.6,coherent=False,policy='legacy',entry_face='south'):
    """Bounded beam search, rejecting area/width violations before placement."""
    capacities=[r['depth' if r['axis']=='y' else 'width'] for r in lanes]
    states=[([0.]*len(lanes),[[] for _ in lanes])]
    bundles={}
    for r in requests:bundles.setdefault(r.get('guest_parent') or r['id'],[]).append(r)
    for key,bundle in bundles.items():
        if any(r.get('guest_parent') or (r['kind']=='majlis' and r.get('zone')=='guest' and r.get('separate_guest_entry')) for r in bundle):
            distributor=dict(id='guest-dist-'+key,kind='corridor',name='موزع ضيوف مستقل',zone='guest',guest_distributor=True,guest_parent=key,min_side=max(1.6,guest_clear_width),min_area=0)
            for r in bundle:r['guest_vestibule']=distributor['id']
            bundle.append(distributor)
    def bundle_order(rs):
        size=(-max(r['min_side'] for r in rs),-sum(r['min_area'] for r in rs),rs[0]['id'])
        if policy=='legacy':return size
        rank={'majlis':0,'living':1,'dining':2,'kitchen':3,'office':4,'master':5,'bedroom':6,'bathroom':7,'laundry':8,'storage':9}
        return (min(rank.get(r['kind'],10) for r in rs),*size)
    ordered=sorted(bundles.values(),key=bundle_order)
    for bundle in ordered:
        expanded=[]
        for used,groups in states:
            for i,lane in enumerate(lanes):
                length=sum(length_for(room,lane,t) for room in bundle)
                if used[i]+length>capacities[i]+EPS:continue
                u=used.copy();u[i]+=length;g=[row.copy() for row in groups];g[i].extend(bundle)
                # Best-fit plus load balance; not an architectural quality score.
                score=sum(((cap-v)*(lanes[j]['width'] if lanes[j]['axis']=='y' else lanes[j]['depth']))**2 for j,(cap,v) in enumerate(zip(capacities,u)))
                expanded.append((score,u,g))
        if not expanded:return None
        expanded.sort(key=lambda state:state[0]);states=[(u,g) for _,u,g in expanded[:20]]
    used,groups=min(states,key=lambda s:sum((cap-v)**2 for cap,v in zip(capacities,s[0])))
    cells=[]
    for i,lane in enumerate(lanes):
        axis=lane['axis'];start=lane['y' if axis=='y' else 'x']
        if not groups[i]:
            cells.append(box(lane['x'],lane['y'],lane['width'],lane['depth'],kind='reserve',name='مساحة احتياطية مقترحة',door_side=lane['door_side']));continue
        extra=capacities[i]-used[i];weights=sum(r['min_area'] for r in groups[i])
        # Functional sequencing along a wing: services then social spaces, bedrooms together.
        order={'bathroom':0,'storage':1,'laundry':2,'kitchen':3,'dining':4,'living':5,'majlis':6,'office':7,'master':8,'bedroom':9}
        sequence=sorted(groups[i],key=lambda q:((0,q.get('guest_parent') or q['id'],(1 if q.get('guest_distributor') else 2 if q.get('guest_parent') else 0)) if q.get('zone')=='guest' else (1,str(order[q['kind']]),q['id'])))
        if policy=='social_front':
            # Guests stay a contiguous majlis/distributor/WC bundle when reversed.
            if (axis=='y' and entry_face=='south') or (axis=='x' and entry_face=='east'):sequence=list(reversed(sequence))
        elif policy=='family_front':
            sequence=sorted(sequence,key=lambda q:q.get('zone')=='guest')
        for r in sequence:
            base=length_for(r,lane,t)
            growth=min(extra*r['min_area']/weights,base*(.75 if coherent else .15))
            if coherent:
                cross=lane['width' if axis=='y' else 'depth']-t
                growth=min(growth,max(0,2.8*cross+t-base))
            length=base+growth
            cell=box(lane['x'] if axis=='y' else start,start if axis=='y' else lane['y'],lane['width'] if axis=='y' else length,length if axis=='y' else lane['depth'],**copy.deepcopy(r),door_side=lane['door_side'])
            cells.append(cell);start+=length
        remaining=lane['y' if axis=='y' else 'x']+capacities[i]-start
        if remaining>t+.05:
            if remaining<1.6 and cells and cells[-1].get('request_id'):
                cells[-1]['depth' if axis=='y' else 'width']+=remaining
            else:
                cells.append(box(lane['x'] if axis=='y' else start,start if axis=='y' else lane['y'],lane['width'] if axis=='y' else remaining,remaining if axis=='y' else lane['depth'],kind='reserve',name='مساحة مرنة مقترحة',door_side=lane['door_side']))
    return cells


def expanded_program(brief,floor):
    resolved=resolve_notes(brief);men={m.get('request_id') for m in resolved['mapped'] if m['action']=='classify_men_majlis'}
    rows=[dict(id=f'{r.id}-{n+1}',request_id=r.id,name=('مجلس رجال' if r.id in men else r.name)+(f' {n+1}' if r.count>1 else ''),kind=r.kind,
                 min_area=max(r.min_area,saudi_rules.minimum(r.kind)[0] if brief.apply_saudi_rules else 0),min_side=max(r.min_side,saudi_rules.minimum(r.kind)[1] if brief.apply_saudi_rules else 0),capacity=r.capacity,dining_seats=brief.dining_seats if r.kind=='dining' else 0,
                 zone='guest' if floor==0 and (r.kind=='majlis' or (any(p.kind=='majlis' and p.floor==0 for p in brief.rooms) and r.kind=='bathroom' and ('ضيف' in r.name or 'ضيوف' in r.name or 'رجال' in r.name))) else 'family')
          for r in brief.rooms if r.floor==floor for n in range(r.count)]
    for row in rows:row['separate_guest_entry']=brief.separate_guest_entry
    for row in rows:row['include_shower']=row['kind']=='bathroom' and row['zone']!='guest'
    if brief.separate_guest_entry:
        parents=[r for r in rows if r['kind']=='majlis' and r['zone']=='guest']
        for i,r in enumerate(r for r in rows if r['kind']=='bathroom' and r['zone']=='guest'):
            if parents:r['guest_parent']=parents[min(i,len(parents)-1)]['id']
    return rows


def search(brief,family,policy='legacy',core_position='rear'):
    # Reserve clearance outside the mass for a balcony on a non-street facade.
    margin={face:(brief.automatic_features.balcony_depth_m+.15 if brief.automatic_features.balcony and brief.boundary_widths.get(face,0)<10 else 0) for face in ('north','south','east','west')}
    aw=brief.plot_width-brief.setbacks.west-brief.setbacks.east-brief.wall_thickness-margin['west']-margin['east']
    ad=brief.plot_depth-brief.setbacks.north-brief.setbacks.south-brief.wall_thickness-margin['north']-margin['south']
    origin_x=brief.setbacks.west+margin['west'];origin_y=brief.setbacks.north+margin['north']
    best=None;attempts=0;pool=[]
    # Each candidate searches dimensions AND allocation, never just scales a fixed plan.
    variations=[(s,d,r,b) for s in (1.,.85,.70) for d in (1.,.82,.68,.55) for r in (.33,.36,.38,.40,.44,.47) for b in (.30,.36,.40,.44,.48)]
    if family=='cross':variations=[(s,d,r,b) for s in (1.,.85,.7) for d in (1.,.85,.7) for r in (.4,.5,.6) for b in (.35,.5,.65)]
    if family=='spine':variations=[(s,d,r,.4) for s in (1.,.85,.7) for d in (1.,.9,.82,.74,.68,.60) for r in (.35,.4,.45,.5,.55,.6,.65)]
    if family=='stepped':variations=[(s,d,.4,b) for s in (1.,.85,.70) for d in (1.,.90,.82,.74,.68,.60,.55) for b in (.30,.36,.40,.44,.48)]
    if brief.adaptive_search and family=='spine':
        # Program-sized wings on large plots; never enlarge a house just to fill land.
        wing=max(r.min_side for r in brief.rooms)+brief.wall_thickness
        nominal=2*wing+brief.corridor_width+brief.wall_thickness
        scales=sorted({round(min(aw,w)/aw,6) for w in (nominal,nominal+1.5,nominal+3,aw*.7,aw*.85,aw)})
        variations=[(s,d,r,.4) for s in scales for d in (1.,.9,.82,.74,.68,.60) for r in (.35,.4,.45,.5,.55,.6,.65)]
    for ws,ds,ratio,top in variations:
        W,D=aw*ws,ad*ds
        shape=topology(family,W,D,max(brief.corridor_width+brief.wall_thickness,1.9 if brief.automatic_features.roof_annex else 0),ratio,top)
        attempts+=1
        if not shape:continue
        halls,lanes=copy.deepcopy(shape)
        if min(min(l['width'],l['depth']) for l in lanes)<1.6:continue
        stair=None
        if brief.floors==2 or brief.automatic_features.roof_annex:
            # Reserve an identical vertical core on BOTH floors, before packing rooms.
            eligible=[(i,l) for i,l in enumerate(lanes) if l['axis']=='y' and l['width']-brief.wall_thickness>=2.8 and l['depth']>=4.6]
            if not eligible:continue
            if brief.automatic_features.roof_annex:
                # Keep the roof stair inside a recessed annex, not on the front edge.
                eligible=[(i,l) for i,l in eligible if l['depth']>=9.5]
                if not eligible:continue
            i,l=min(eligible,key=lambda p:p[1]['depth'])
            core_depth=4.6 if l['depth']>=7.0 else l['depth']
            retreat=1.6 if brief.automatic_features.roof_annex else 0
            stair=box(l['x'],l['y']+l['depth']-core_depth-retreat,l['width'],core_depth,id='stair',kind='stair',name='درج مشترك',door_side=l['door_side'])
            if core_position=='front' and not brief.automatic_features.roof_annex:
                stair['y']=l['y'];l['y']+=core_depth
            l['depth']-=core_depth+retreat
            if l['depth']<EPS:lanes.pop(i)
        from .automatic_features import reserve_lightwell
        reserved=reserve_lightwell(lanes,brief)
        if reserved is None:continue
        lanes,wells=reserved
        floors=[];failed=False
        for f in range(brief.floors):
            cells=allocate(expanded_program(brief,f),lanes,brief.wall_thickness,brief.corridor_width,brief.massing_strategy=='coherent',policy,brief.entrance_face)
            if cells is None:failed=True;break
            if brief.automatic_features.roof_annex:
                # Only retain the strip supporting the annex lounge immediately
                # before the stair. Unrelated spare lanes remain removable.
                extension=max(3.6,brief.automatic_features.annex_lounge_min_m2/(stair['width']-brief.wall_thickness)+brief.wall_thickness)
                for r in cells:
                    if r['kind']!='reserve' or abs(r['x']-stair['x'])>EPS or abs(r['width']-stair['width'])>EPS or abs(r['y']+r['depth']-stair['y'])>EPS:continue
                    start=max(r['y'],stair['y']-extension);depth=stair['y']-start
                    previous=next((p for p in cells if p.get('request_id') and abs(p['x']-r['x'])<EPS and abs(p['y']+p['depth']-r['y'])<EPS),None)
                    if depth<brief.wall_thickness+.9 and previous:
                        previous['depth']=stair['y']-previous['y']
                    else:r.update(y=start,depth=depth,kind='corridor',name='بهو وصول الملحق')
            if brief.flexible_space_policy=='remove':cells=[r for r in cells if r['kind']!='reserve']
            floors.append(cells+([copy.deepcopy(stair)] if stair else []))
        if failed:continue
        if wells and any(not any(r.get('request_id') and (abs(r['y']+r['depth']-(w['y']-brief.wall_thickness/2))<EPS or abs(r['y']-(w['y']+w['depth']+brief.wall_thickness/2))<EPS) and min(r['x']+r['width'],w['x']+w['width'])-max(r['x'],w['x'])>.7 for r in cells for w in wells) for cells in floors):continue
        halls_by_floor=[halls for _ in floors]
        if brief.massing_strategy=='coherent':
            from .massing_quality import trim_corridor_tails
            halls_by_floor=[trim_corridor_tails(halls,cells) for cells in floors]
        gross=max(sum(area(r) for r in cells)+sum(area(h) for h in floor_halls) for cells,floor_halls in zip(floors,halls_by_floor))
        spare=sum(area(r) for rooms in floors for r in rooms if r['kind']=='reserve')
        score=gross*brief.floors+spare*.8
        massing=None
        if brief.massing_strategy=='coherent':
            from .massing_quality import penalty
            massing=[];massing_cost=0
            for cells,floor_halls in zip(floors,halls_by_floor):
                cost,metrics=penalty([cells],floor_halls);massing_cost+=cost/len(floors);massing.extend(metrics)
            score*=1+massing_cost
        pool.append(dict(W=W,D=D,halls=halls,halls_by_floor=halls_by_floor,floors=floors,score=score,gross=gross,top_fraction=top,wells=wells,origin_x=origin_x,origin_y=origin_y,massing_quality=massing))
        if best is None or score<best['score']:best=pool[-1]
    if best:
        pool.sort(key=lambda r:r['score']);best=pool[0];best['attempts']=attempts
        best['alternatives']=[{**r,'attempts':attempts} for r in pool[1:12]]
        if brief.massing_strategy=='coherent':
            fallback=search(brief.model_copy(update={'massing_strategy':'legacy','site_placement':'legacy'}),family,policy,core_position)
            if fallback:
                backups=[{k:v for k,v in fallback.items() if k!='alternatives'}]+fallback.get('alternatives',[])
                best['alternatives'].extend({**r,'massing_fallback':True} for r in backups)
    if best and brief.site_placement=='auto_rear_corner':
        from .site_placement import alternatives as placements
        layouts=[{k:v for k,v in best.items() if k!='alternatives'}]+best.get('alternatives',[])
        expanded=[placed for group,layout in enumerate(layouts) for placed in placements(brief,layout,group)]
        best=expanded[0];best['alternatives']=expanded[1:]
    return best


def add_room_door(floor,r,wall,revision,**metadata):
    t=wall['thickness'];length=math.dist(wall['start'],wall['end']);width=min(.90,length-t-.12)
    if width<.75:return None
    center=[(a+b)/2 for a,b in zip(wall['start'],wall['end'])];axis=0 if wall['axis']=='horizontal' else 1
    center[axis]=wall['start'][axis]+t/2+.18+width/2
    if center[axis]+width/2>wall['end'][axis]-t/2:center[axis]=(wall['start'][axis]+wall['end'][axis])/2
    if r['kind']=='bathroom':center[axis]=(wall['start'][axis]+wall['end'][axis])/2
    if r['kind']=='stair' and axis==1:center[1]=r['y']+t/2+.5
    x,y=center
    if axis==0:
        top=y<r['y']+r['depth']/2;swing=box(x-width/2,y if top else y-width,width,width)
    else:
        left=x<r['x']+r['width']/2;swing=box(x if left else x-width,y-width/2,width,width)
    o=dict(id=f"{floor['id']}-O{len(floor['openings'])+1}",wall_id=wall['id'],floor_id=floor['id'],kind='door',center=center,width=width,height=2.2,sill=0,
           connects=[r['id']]+[i for i in wall['room_ids'] if i!=r['id']],swing_rect=swing,revision_id=revision,**metadata)
    floor['openings'].append(o)
    if r['kind']=='bathroom':
        from .furnishing import bathroom_layouts,valid_group
        net=next(room for room in floor['rooms'] if room['id']==r['id'])
        original=copy.deepcopy(o)
        for fraction in (.5,.60,.40,.70,.30):
            proposed=wall['start'][axis]+length*fraction
            if proposed-width/2<wall['start'][axis]+t/2+.1 or proposed+width/2>wall['end'][axis]-t/2-.1:continue
            delta=proposed-o['center'][axis];o['center'][axis]=proposed;o['swing_rect']['x' if axis==0 else 'y']+=delta
            if any(valid_group(floor,net,group,existing=[]) for group in bathroom_layouts(net)):break
        else:o.clear();o.update(original)
    return o


def make_walls(floor,t,revision):
    """Split coincident edges into atomic host walls; remove hall-to-hall seams."""
    edges={};cells=floor['cells']
    for r in cells:
        x,y,w,d=r['x'],r['y'],r['width'],r['depth']
        for axis,fixed,lo,hi in [('h',y,x,x+w),('h',y+d,x,x+w),('v',x,y,y+d),('v',x+w,y,y+d)]:
            key=(axis,round(fixed,6));edges.setdefault(key,[]).append((lo,hi,r['id']))
    by_id={r['id']:r for r in cells}
    for (axis,fixed),spans in edges.items():
        cuts=sorted({round(q,6) for lo,hi,_ in spans for q in (lo,hi)})
        for lo,hi in zip(cuts,cuts[1:]):
            ids=sorted({rid for a,b,rid in spans if a< (lo+hi)/2 <b})
            if not ids:continue
            if len(ids)==2 and all(by_id[i]['kind']=='corridor' and not by_id[i].get('guest_distributor') for i in ids):continue
            a,b=((lo,fixed),(hi,fixed)) if axis=='h' else ((fixed,lo),(fixed,hi))
            floor['walls'].append(dict(id=f"{floor['id']}-W{len(floor['walls'])+1}",floor_id=floor['id'],axis='horizontal' if axis=='h' else 'vertical',start=a,end=b,thickness=t,room_ids=ids,exterior=len(ids)==1,revision_id=revision))
    # Guest rooms open onto their allocated vestibule; ordinary rooms onto family halls.
    for r in cells:
        if r['kind']=='corridor':continue
        # Guest bathrooms must open onto a guest distributor, never through the majlis.
        # Keep the vestibule/family seam as a real wall, with no shared passage.
        hosts=[w for w in floor['walls'] if r['id'] in w['room_ids'] and any(by_id[i]['kind']=='corridor' for i in w['room_ids'])]
        if r.get('guest_vestibule'):
            vestibule=floor['id']+'-'+r['guest_vestibule']
            hosts=[w for w in hosts if vestibule in w['room_ids']]
        if hosts:add_room_door(floor,r,max(hosts,key=lambda w:math.dist(w['start'],w['end'])),revision)
        if r['kind']=='majlis' and r.get('guest_vestibule'):
            family_hosts=[w for w in floor['walls'] if r['id'] in w['room_ids'] and any(by_id[i]['kind']=='corridor' and not by_id[i].get('guest_distributor') for i in w['room_ids'])]
            if family_hosts:add_room_door(floor,r,max(family_hosts,key=lambda w:math.dist(w['start'],w['end'])),revision,access_control='family_only')


def add_windows(floor,brief,revision):
    # Explicit proposed clear glass and opening fraction; actual facade legality is a separate check.
    for r in floor['rooms']:
        if not r.get('request_id') and not r.get('generated_feature_room'):continue
        target=saudi_rules.window_targets(r['kind'],area(r))[0] if brief.apply_saudi_rules else .9
        sill=1.5 if r['kind']=='bathroom' else .9;height=.8 if r['kind']=='bathroom' else 1.5
        clear_height=height-.12;left=target-sum(o.get('clear_width',0)*o.get('clear_height',0) for o in floor['openings'] if o['kind']=='window' and r['id'] in o['connects'])
        if left<EPS:continue
        walls=[w for w in floor['walls'] if w['exterior'] and r['id'] in w['room_ids']]
        for wall in sorted(walls,key=lambda w:-math.dist(w['start'],w['end'])):
            axis=0 if wall['axis']=='horizontal' else 1
            runs=[(wall['start'][axis]+.22,wall['end'][axis]-.22)]
            for o in floor['openings']:
                if o['wall_id']!=wall['id']:continue
                lo,hi=o['center'][axis]-o['width']/2-.18,o['center'][axis]+o['width']/2+.18
                following=[]
                for a,b in runs:
                    if hi<=a or lo>=b:following.append((a,b));continue
                    if lo>a:following.append((a,lo))
                    if hi<b:following.append((hi,b))
                runs=following
            for a,b in sorted(runs,key=lambda ab:ab[0]-ab[1]):
                width=min(b-a,left/clear_height+.12)
                if width<.5:continue
                center=[(u+v)/2 for u,v in zip(wall['start'],wall['end'])];center[axis]=(a+b)/2
                glazing=(width-.12)*clear_height
                floor['openings'].append(dict(id=f"{floor['id']}-O{len(floor['openings'])+1}",wall_id=wall['id'],floor_id=floor['id'],kind='window',center=center,width=width,height=height,sill=sill,clear_width=width-.12,clear_height=clear_height,operable_fraction=.5,connects=[r['id'],'OUTSIDE'],revision_id=revision,dimensions_status='PROPOSED_NOT_AS_BUILT'))
                left-=glazing
                if left<1e-6:break
            if left<1e-6:break


def entrance(floor,face,revision):
    halls={r['id'] for r in floor['rooms'] if r['kind']=='corridor' and not r.get('guest_distributor')}
    horizontal=face in ('north','south');coordinate=1 if horizontal else 0
    walls=[w for w in floor['walls'] if w['exterior'] and set(w['room_ids'])&halls and (w['axis']=='horizontal')==horizontal and math.dist(w['start'],w['end'])>1.2]
    if not walls:return
    sign=-1 if face in ('south','east') else 1
    w=min(walls,key=lambda w:sign*w['start'][coordinate])
    floor['openings'].append(dict(id=f"{floor['id']}-ENTRY",wall_id=w['id'],floor_id=floor['id'],kind='door',center=[(a+b)/2 for a,b in zip(w['start'],w['end'])],width=1.0,height=2.3,sill=0,connects=w['room_ids']+['OUTSIDE'],revision_id=revision,main_entry=True))


def separate_guests(floor,brief,revision):
    if not brief.separate_guest_entry:return
    for r in floor['rooms']:
        if r['kind']!='majlis' or r.get('zone')!='guest':continue
        for o in floor['openings']:
            if o['kind']=='door' and r['id'] in o['connects'] and any('hall-' in rid for rid in o['connects']):o['access_control']='family_only'
        if r.get('guest_vestibule'):
            r=next(q for q in floor['rooms'] if q['id']==floor['id']+'-'+r['guest_vestibule'])
        hosts=[w for w in floor['walls'] if w['exterior'] and r['id'] in w['room_ids'] and math.dist(w['start'],w['end'])>1.3]
        def preference(w):
            axis=0 if w['axis']=='horizontal' else 1
            face=('north' if w['start'][1]<r['y']+r['depth']/2 else 'south') if axis==0 else ('west' if w['start'][0]<r['x']+r['width']/2 else 'east')
            return (face!=brief.entrance_face,-math.dist(w['start'],w['end']))
        for wall in sorted(hosts,key=preference):
            # Do not overlap an existing window or another door on the host.
            axis=0 if wall['axis']=='horizontal' else 1
            for center in (wall['start'][axis]+.75,wall['end'][axis]-.75):
                if any(o['wall_id']==wall['id'] and abs(o['center'][axis]-center)<(o['width']+.9)/2+.1 for o in floor['openings']):continue
                nominal=next(c for c in floor['cells'] if c['id']==r['id'])
                o=add_room_door(floor,nominal,wall,revision,guest_entry=True)
                if o:
                    delta=center-o['center'][axis];o['center'][axis]=center;o['swing_rect']['x' if axis==0 else 'y']+=delta
                    o['connects']=[r['id'],'OUTSIDE'];break
            else:continue
            break


def make_guest_distributor(floor,brief,revision):
    """Create a physically bounded guest vestibule when the geometry permits it.

    Never fabricate a pass: return False when an exterior entrance, both
    interior doors, and a separated family route cannot be constructed.
    """
    if not brief.separate_guest_entry:return True
    majlis=[r for r in floor['rooms'] if r['kind']=='majlis' and r.get('zone')=='guest']
    baths=[r for r in floor['rooms'] if r.get('guest_parent') and r['kind']=='bathroom']
    if not majlis:return True
    distributors=[r for r in floor['rooms'] if r.get('guest_distributor')]
    if not distributors:return False
    doors=[o for o in floor['openings'] if o['kind']=='door']
    physical='cells' in floor or 'walls' in floor
    by_id={r['id']:r for r in floor['rooms']}
    cells={r['id']:r for r in floor.get('cells',[])}
    walls={w['id']:w for w in floor.get('walls',[])}
    def valid_door(o):
        if not physical:return True  # adjacency-only contract fixtures
        wall=walls.get(o.get('wall_id'))
        if not wall:return False
        expected=set(wall['room_ids'])|({'OUTSIDE'} if wall['exterior'] else set())
        if set(o['connects'])!=expected:return False
        axis=0 if wall['axis']=='horizontal' else 1
        c=o['center'];lo,hi=sorted((wall['start'][axis],wall['end'][axis]))
        sides=[]
        for rid in wall['room_ids']:
            cell=cells.get(rid);net=by_id.get(rid)
            if not cell or not net:return False
            t=wall['thickness']
            if any(abs(net[k]-(cell[k]+(t/2 if k in ('x','y') else -t)))>EPS for k in ('x','y','width','depth')):return False
            start=cell['x' if axis==0 else 'y'];extent=cell['width' if axis==0 else 'depth']
            fixed=cell['y' if axis==0 else 'x'];cross=cell['depth' if axis==0 else 'width']
            edge=wall['start'][1-axis]
            if lo<start-EPS or hi>start+extent+EPS:return False
            if abs(edge-fixed)<EPS:sides.append(1)
            elif abs(edge-fixed-cross)<EPS:sides.append(-1)
            else:return False
        if len(sides)==2 and sides[0]==sides[1]:return False
        return (abs(c[1-axis]-wall['start'][1-axis])<EPS and
                c[axis]-o['width']/2>=lo-EPS and c[axis]+o['width']/2<=hi+EPS)
    for dist in distributors:
        did=dist['id']
        if physical:
            cell=cells.get(did)
            if not cell or dist.get('zone')!='guest' or dist['kind']!='corridor':return False
            if min(dist['width'],dist['depth'])+EPS<getattr(brief,'corridor_width',1.2):return False
            t=next((w['thickness'] for w in walls.values() if did in w['room_ids']),None)
            if t is None:return False
            if any(abs(dist[k]-(cell[k]+(t/2 if k in ('x','y') else -t)))>EPS for k in ('x','y','width','depth')):return False
            for axis,fixed,lo,hi in [('horizontal',cell['y'],cell['x'],cell['x']+cell['width']),
                                     ('horizontal',cell['y']+cell['depth'],cell['x'],cell['x']+cell['width']),
                                     ('vertical',cell['x'],cell['y'],cell['y']+cell['depth']),
                                     ('vertical',cell['x']+cell['width'],cell['y'],cell['y']+cell['depth'])]:
                ax=0 if axis=='horizontal' else 1
                spans=sorted((w['start'][ax],w['end'][ax]) for w in walls.values()
                             if did in w['room_ids'] and w['axis']==axis and abs(w['start'][1-ax]-fixed)<EPS)
                cursor=lo
                for start,end in spans:
                    if abs(start-cursor)>EPS or end<=start:return False
                    cursor=end
                if abs(cursor-hi)>EPS:return False
            if any(did in o['connects'] and any(rid in by_id and by_id[rid].get('zone')!='guest' for rid in o['connects'] if rid!=did) for o in doors):return False
        associated=[r for r in majlis+baths if not physical or r.get('guest_vestibule')==did.removeprefix(floor['id']+'-')]
        if not associated:return False
        for room in associated:
            if not any(set(o['connects'])=={room['id'],did} and valid_door(o) for o in doors):return False
        if not any(o.get('guest_entry') and set(o['connects'])=={did,'OUTSIDE'} and valid_door(o) for o in doors):return False
    if any(not any(set(o['connects'])=={bath['id'],h['id']} and valid_door(o) for h in distributors for o in doors) for bath in majlis+baths):return False
    if any(o.get('guest_entry') and not any(set(o['connects'])=={h['id'],'OUTSIDE'} and valid_door(o) for h in distributors) for o in doors):return False
    if physical and privacy_evidence({'floors':[floor]})['family_rooms_exposed']:return False
    if any(any(m['id'] in o['connects'] and bath['id'] in o['connects'] for m in majlis for bath in baths) for o in doors):return False
    return True


def materialize(brief,family,result):
    revision=uuid4().hex;t=brief.wall_thickness
    origin_x=result.get('origin_x',brief.setbacks.west);origin_y=result.get('origin_y',brief.setbacks.north)
    model=dict(schema_version='0.6.2-general',model_revision_id=revision,candidate_id=family,status='DRAFT_REVIEW',
               brief=brief.model_dump(),profile={'project_name':brief.project_name,'massing_strategy':brief.massing_strategy,'massing_revision':'coherent-1' if brief.massing_strategy=='coherent' else 'legacy','massing_fallback':bool(result.get('massing_fallback'))},site={'width':brief.plot_width,'depth':brief.plot_depth},
               footprint=box(origin_x,origin_y,result['W'],result['D']),
               search={'family':family,'family_label_ar':FAMILIES[family],'dimensions_tested':result['attempts'],'method':'bounded wing allocation beam search','optimality_proven':False},
               requirements_resolution=resolve_notes(brief),regulatory_geometry=brief.regulatory_geometry.model_dump() if brief.regulatory_geometry else None,presentation={'style':'linework','furniture_symbols':SYMBOL_VERSION},floors=[],stairs=[])
    W,D=result['W'],result['D'];a=result['halls'][0]['x']+result['halls'][0]['width']
    if family=='L':
        b=result['halls'][1]['y']+result['halls'][1]['depth'];outline=[(0,0),(W,0),(W,b),(a,b),(a,D),(0,D)]
    elif family=='U':
        b=result['halls'][1]['y']+result['halls'][1]['depth'];outline=[(0,0),(W,0),(W,D),(W-a,D),(W-a,b),(a,b),(a,D),(0,D)]
    elif family in ('spine','cross'):
        outline=[(0,0),(W,0),(W,D),(0,D)]
    else:
        first=D*result.get('top_fraction',.33);second=D*min(.8,result.get('top_fraction',.37)+.30)
        outline=[(0,0),(W,0),(W,second),(W*.80,second),(W*.80,D),(W*.12,D),(W*.12,first),(0,first)]
    model['footprint']['polygon']=[(x+origin_x,y+origin_y) for x,y in outline]
    for fi,cells in enumerate(result['floors']):
        fid=['GF','FF'][fi];f=dict(id=fid,name=['الدور الأرضي','الدور الأول'][fi],level_m=fi*brief.floor_height,rooms=[],walls=[],openings=[],furniture=[],decorations=[],cells=[])
        for n,cell in enumerate(cells+[dict(r,id=f'hall-{i}',kind='corridor',name='موزع الحركة') for i,r in enumerate(result.get('halls_by_floor',[result['halls']]*brief.floors)[fi])]):
            q=copy.deepcopy(cell);q['id']=fid+'-'+q.get('id',f'reserve-{n}');q['floor_id']=fid
            q['x']+=origin_x+t/2;q['y']+=origin_y+t/2
            f['cells'].append(q)
            net=copy.deepcopy(q);net.update(x=q['x']+t/2,y=q['y']+t/2,width=q['width']-t,depth=q['depth']-t,revision_id=revision)
            net['area_m2']=round(area(net),4);f['rooms'].append(net)
        make_walls(f,t,revision)
        if fi==0:
            entrance(f,brief.entrance_face,revision)
            separate_guests(f,brief,revision)
            f['guest_distributor_constructed']=make_guest_distributor(f,brief,revision)
        add_windows(f,brief,revision)
        # Detailed, original furniture symbols and use-zone placement are shared with V0.4.1.
        furnish_floor(f,revision,{})
        model['floors'].append(f)
    model['footprint']['polygons_by_floor']={f['id']:union_polygons(f['cells'],t/2) for f in model['floors']}
    physical_areas={fid:round(sum(signed_area(p) for p in polys),2) for fid,polys in model['footprint']['polygons_by_floor'].items()}
    model['footprint']['nominal_envelope_polygon']=model['footprint']['polygon']
    model['footprint']['polygon']=max(model['footprint']['polygons_by_floor']['GF'],key=lambda p:abs(signed_area(p)))
    from .automatic_features import build_features
    build_features(model,brief,result)
    model['stairs']=make_stairs(model)
    repair_furniture_access(model,revision)
    for f in model['floors']:f['annotations']=annotate(f,model['stairs'])
    model['parking']=saudi_rules.parking(model,brief,requested_count=brief.design_parking_count if brief.country=='YE' else None)
    model['parking_basis']={'jurisdiction':brief.country,'status':'documented Saudi count; stall and access provisional' if brief.apply_saudi_rules else 'design assumption only; Yemeni legal count unknown'}
    from .automatic_features import place_services
    place_services(model,brief)
    model['regulatory_profile']=({'jurisdiction':'SA','ruleset_id':saudi_rules.registry()['id'],'city':brief.city,'region':brief.region,'municipality':brief.municipality,'local_rules_verified':False,'full_sbc_compliance_verified':False,'sources':saudi_rules.registry()['sources']} if brief.country=='SA' else {'jurisdiction':'YE','ruleset_id':None,'city':brief.city,'region':brief.region,'local_rules_verified':False,'national_building_code_verified':False,'sources':[],'required_action':'تقديم اشتراطات الجهة المحلية للموقع قبل أي اعتماد'})
    model['metrics']={'floor_built_m2':max(physical_areas.values()),'floor_built_by_id':physical_areas,'requested_spaces':sum(r.count for r in brief.rooms),
                      'circulation_m2':round(sum(area(r) for f in model['floors'] for r in f['rooms'] if r['kind']=='corridor'),2),
                      'bed_capacity':sum(q.get('capacity',0) for f in model['floors'] for q in f['furniture']),
                      'proposed_flexible_m2':round(sum(area(r) for f in model['floors'] for r in f['rooms'] if r['kind']=='reserve'),2)}
    from .automatic_features import finalize_features
    finalize_features(model,brief)
    model['footprint']['occupied_cells_by_floor']={f['id']:[{k:r[k] for k in ('x','y','width','depth')} for r in f['cells']] for f in model['floors']}
    canonical={'floors':[{k:v for k,v in f.items() if k not in ('decorations',)} for f in model['floors']],**{k:model.get(k) for k in ('stairs','stair_arrivals','parking','service_yard','regulatory_geometry')}}
    def clean(obj):
        if isinstance(obj,dict):return {k:clean(v) for k,v in obj.items() if k!='revision_id'}
        if isinstance(obj,list):return [clean(v) for v in obj]
        return obj
    if brief.massing_strategy=='coherent':
        from .massing_quality import measures
        model['massing_quality']={'revision':'coherent-1','floors':{f['id']:measures(f['cells']) for f in model['floors']}}
    if result.get('site_placement'):
        from .site_placement import evidence
        model['site_placement']=evidence(model,brief,result['site_placement'])
    model['geometry_sha256']=hashlib.sha256(json.dumps(clean(canonical),sort_keys=True).encode()).hexdigest()
    return model


def validate_general(model,brief):
    """Recalculate constraints from emitted geometry, independent of allocator state."""
    checks=[]
    def add(id,ok,label,evidence=None):checks.append(dict(check_id=id,status='PASS' if ok else 'FAIL',label=label,evidence=evidence or {}))
    missing_hosts=[]
    for f in model['floors']:
        walls={w['id'] for w in f['walls']}
        missing_hosts.extend(o.get('id','UNIDENTIFIED') for o in f['openings'] if o.get('wall_id') not in walls)
    if missing_hosts:
        add('opening-host-integrity',False,'فتحات بلا جدران مضيفة؛ توقفت الفحوص التابعة',{'invalid':missing_hosts})
        add('guest-distributor-geometry',make_guest_distributor(model['floors'][0],brief,model['model_revision_id']),'هندسة موزع الضيوف وأبوابه')
        return checks
    for fi,f in enumerate(model['floors']):
        if brief.massing_strategy=='coherent':
            from .massing_quality import measures
            quality=measures(f['cells'])
            add(f['id']+'-massing-connected',quality['components']==1,'اتصال كتلة المبنى هندسيًا',quality)
        expected={r['id']:r for r in expanded_program(brief,fi)}
        actual={r['id'].removeprefix(f['id']+'-'):r for r in f['rooms'] if r.get('request_id')}
        add(f'{f["id"]}-program',set(expected)==set(actual) and sum(bool(r.get('request_id')) for r in f['rooms'])==len(expected),'تغطية جميع الفراغات المطلوبة في دورها',{'expected':len(expected),'actual':len(actual)})
        bad=[r['id'] for key,r in actual.items() if area(r)+EPS<expected[key]['min_area'] or min(r['width'],r['depth'])+EPS<expected[key]['min_side']]
        add(f'{f["id"]}-sizes',not bad,'الحد الأدنى للمساحات والأبعاد الصافية',{'invalid':bad})
        rooms=f['rooms'];collisions=[(a['id'],b['id']) for i,a in enumerate(rooms) for b in rooms[i+1:] if overlap(a,b)]
        add(f'{f["id"]}-overlap',not collisions,'عدم تداخل الغرف والممرات',{'collisions':collisions})
        bounds=box(brief.setbacks.west,brief.setbacks.north,brief.plot_width-brief.setbacks.west-brief.setbacks.east,brief.plot_depth-brief.setbacks.north-brief.setbacks.south)
        add(f'{f["id"]}-site',all(inside(bounds,r) for r in rooms),'الالتزام بحدود الأرض والارتدادات المدخلة')
        corridors={r['id'] for r in rooms if r['kind']=='corridor'}
        # Connectivity uses touching gross hall cells, not near-by room centers.
        halls=[r for r in f['cells'] if r['kind']=='corridor' and not r.get('guest_distributor')];seen={halls[0]['id']};changed=True
        def touches(a,b):
            dx=min(a['x']+a['width'],b['x']+b['width'])-max(a['x'],b['x'])
            dy=min(a['y']+a['depth'],b['y']+b['depth'])-max(a['y'],b['y'])
            return (abs(dx)<EPS and dy>EPS) or (abs(dy)<EPS and dx>EPS)
        while changed:
            changed=False
            for a in halls:
                if a['id'] not in seen and any(b['id'] in seen and touches(a,b) for b in halls):seen.add(a['id']);changed=True
        missing=[r['id'] for r in rooms if r['kind']!='corridor' and not any(o['kind']=='door' and r['id'] in o['connects'] and (set(o['connects'])&corridors or (r.get('guest_parent') and f['id']+'-'+r['guest_parent'] in o['connects'])) for o in f['openings'])]
        add(f'{f["id"]}-doors',not missing and len(seen)==len(halls),'كل فراغ يتصل بباب بممر مترابط',{'missing_doors':missing,'connected_halls':len(seen)})
        missing_windows=[r['id'] for r in rooms if r.get('request_id') and not any(o['kind']=='window' and r['id'] in o['connects'] for o in f['openings'])]
        add(f'{f["id"]}-windows',not missing_windows,'نافذة خارجية فعلية لكل فراغ مطلوب',{'missing':missing_windows})
        entry=any(o.get('main_entry') for o in f['openings'])
        if fi==0:add('entrance',entry,'باب دخول خارجي متصل بالموزع')
        short=[]
        walls={w['id']:w for w in f['walls']}
        for o in f['openings']:
            w=walls.get(o['wall_id']);axis=0 if w and w['axis']=='horizontal' else 1
            if not w or abs(o['center'][1-axis]-w['start'][1-axis])>EPS or o['center'][axis]-o['width']/2<w['start'][axis]-EPS or o['center'][axis]+o['width']/2>w['end'][axis]+EPS or not any(i in w['room_ids'] for i in o['connects']):short.append(o['id'])
        for wall in f['walls']:
            ports=sorted([o for o in f['openings'] if o['wall_id']==wall['id']],key=lambda o:o['center'][0 if wall['axis']=='horizontal' else 1])
            ax=0 if wall['axis']=='horizontal' else 1
            for a,b in zip(ports,ports[1:]):
                if a['center'][ax]+a['width']/2>b['center'][ax]-b['width']/2+EPS:short.extend([a['id'],b['id']])
        add(f'{f["id"]}-openings',not short,'تطابق عرض وموقع الفتحات مع الجدار المضيف',{'invalid':short})
        capacities={r['id']:sum(q.get('capacity',0) for q in f['furniture'] if q['room_id']==r['id']) for r in rooms if r.get('capacity',0)}
        add(f'{f["id"]}-beds',all(capacities[r['id']]>=r['capacity'] for r in rooms if r.get('capacity',0)),'سعة الأسرة المرسومة المطلوبة',{'actual':capacities})
    for f in model['floors']:
        fixture_missing=[]
        necessary={'master':{'single_bed','double_bed'},'bedroom':{'single_bed','double_bed'},'living':{'sofa'},'majlis':{'sofa'},'kitchen':{'kitchen_counter'},'bathroom':{'toilet'},'office':{'desk'},'laundry':{'washing_machine'},'storage':{'storage'}}
        for r in f['rooms']:
            items=[q for q in f['furniture'] if q['room_id']==r['id']]
            if (r.get('request_id') or r.get('generated_feature_room')) and r['kind'] in necessary and not {q['kind'] for q in items}&necessary[r['kind']]:fixture_missing.append(r['id'])
            if r['kind']=='bathroom' and not {'toilet','basin'}<={q['kind'] for q in items}:fixture_missing.append(r['id'])
            if r.get('include_shower') and not any(q['kind']=='shower' for q in items):fixture_missing.append(r['id'])
            if r['kind']=='dining' and sum(q.get('seats',0) for q in items if q['kind']=='dining_chair')<brief.dining_seats:fixture_missing.append(r['id'])
            if any(not inside(r,q) for q in items):fixture_missing.append(r['id'])
        add(f['id']+'-fixtures',not fixture_missing,'وجود الأثاث الأساسي ومقاعد الطعام المطلوبة داخل الغرف',{'invalid':fixture_missing,'dining_seats_required':brief.dining_seats})
        evidence=movement_evidence(model,f)
        add(f['id']+'-walkability',not evidence['access']['unreachable'],'مسارات حركة جسم بعرض 0.60 م — فحص شبكي جزئي',evidence['access'])
        add(f['id']+'-door-sweeps',not evidence['door_sweep_collisions'],'عدم تعارض أقواس الأبواب مع بعضها والأثاث ومسيري الدرج',{'collisions':evidence['door_sweep_collisions'],'scope':evidence['scope']})
    # Architectural intelligence V1: verify guest bathroom access from a corridor,
    # not via the majlis. The distributor must also serve the majlis.
    if brief.separate_guest_entry:
        gf=model['floors'][0]
        add('guest-distributor-geometry',make_guest_distributor(gf,brief,model['model_revision_id']),'موزع ضيوف هندسي مستقل متصل بمدخل خارجي والمجلس والحمام',{'constructed':bool(gf.get('guest_distributor_constructed')),'scope':'recomputed net/gross bounds, closed walls, hosted doors and separated guest route'})
        guest_baths=[r for r in gf['rooms'] if r.get('guest_parent') and r['kind']=='bathroom']
        guest_majlis=[r for r in gf['rooms'] if r.get('zone')=='guest' and r['kind']=='majlis']
        invalid=[]
        for bath in guest_baths:
            doors=[o for o in gf['openings'] if o['kind']=='door' and bath['id'] in o['connects']]
            halls={rid for o in doors for rid in o['connects'] if any(q['id']==rid and q['kind']=='corridor' for q in gf['rooms'])}
            if not halls or any(any(m['id'] in o['connects'] for m in guest_majlis) for o in doors):
                invalid.append(bath['id']);continue
            if not any(o['kind']=='door' and any(m['id'] in o['connects'] for m in guest_majlis) and halls.intersection(o['connects']) for o in gf['openings']):
                invalid.append(bath['id'])
        add('guest-distributor-access',not invalid,'حمام الضيوف والمجلس من موزع مشترك مستقل، وليس الحمام من المجلس',{'invalid_guest_bathrooms':invalid,'scope':'door adjacency; visual privacy remains PENDING'})
    if brief.separate_guest_entry and any(r.kind=='majlis' and r.floor==0 for r in brief.rooms):
        ev=privacy_evidence(model)
        add('guest-route',bool(ev['guest_entries']) and not ev['missing_guest_access'] and not ev['family_rooms_exposed'],'مسار ضيوف مستقل للمجلس ومرافقه عند إغلاق باب فصل الأسرة',ev)
    else:checks.append(dict(check_id='guest-route',status='NOT_APPLICABLE',label='فصل مدخل المجلس — لم يطلب أو لا يوجد مجلس أرضي',evidence={}))
    if brief.floors==2 or brief.automatic_features.roof_annex:
        invalid=[]
        for s in model['stairs']:
            room=next(r for f in model['floors'] for r in f['rooms'] if r['id']==s['room_id'])
            if s['required_depth_m']>s['depth']+EPS or s['width']<2*s['flight_width_m']+.1 or not all(inside(room,q) for q in s['flights']+[s['landing'],s['entry_apron']]):invalid.append(s['id'])
        add('stair-geometry',len(model['stairs'])==brief.floors and not invalid,'هندسة مسيري الدرج والبسطات وعدد القوائم داخل البئر',{'stairs':model['stairs'],'invalid':invalid,'scope':'proposed dimensions only; headroom not verified against beams or floor slabs'})
        cores=[r for f in model['floors'] for r in f['rooms'] if r['kind']=='stair']
        add('vertical-core',len(cores)==brief.floors+int(brief.automatic_features.roof_annex) and all(abs(cores[0][k]-c[k])<EPS for c in cores[1:] for k in ('x','y','width','depth')),'تطابق حدود بئر الدرج بين الدورين')
    for id,label,reason in [
        ('visual-privacy','الخصوصية البصرية والصوتية وإطلالات النوافذ','فصل مسار الضيوف مقاس في فحص مستقل؛ الرؤية الكاملة والصوت تحتاج مراجعة تصميم.'),
        ('local-code','اعتماد الارتدادات والاشتراطات المحلية ومعدلات التهوية','يلزم تحديد الدولة والمدينة ومرجع الاشتراطات الرسمي؛ الأرقام المدخلة ليست اعتمادًا قانونيًا.'),
        ('structure','التصميم الإنشائي والخدمات والتمديدات','يلزم نموذج إنشائي ومواقع أعمدة وكمرات وتمديدات؛ توافق بئر الدرج وحده لا يثبت المطابقة.'),
        ('stairs-code','اعتماد السلم والارتفاع الصافي فوق كامل المسار','هندسة السلم محسوبة جزئيًا؛ يلزم المرجع المحلي ومناسيب البلاطات والكمرات للتحقق من الارتفاع الصافي.')]:
        checks.append(dict(check_id=id,status='PENDING',label=label,evidence={'required_action':reason}))
    reserves=[r['id'] for f in model['floors'] for r in f['rooms'] if r['kind']=='reserve']
    checks.append(dict(check_id='flexible-spaces',status='PENDING' if reserves else 'PASS',label='استبعاد الفراغات الاحتياطية غير المطلوبة' if not reserves else 'اعتماد استعمال المساحات المرنة المقترحة',evidence={'reserve_ids':reserves,'policy':brief.flexible_space_policy}))
    notes=model['requirements_resolution']
    if brief.notes.strip():checks.append(dict(check_id='free-text',status='PENDING' if notes['unmapped'] else 'PASS',label='ربط الطلبات النصية المحددة بالبرنامج — العبارات الأخرى تحتاج مراجعة',evidence=notes))
    parking=model.get('parking',[])
    parked=[dict(x=p['x'],y=p['y'],width=p['width'],depth=p['depth']) for p in parking]
    invalid_parking=[]
    for i,p in enumerate(parked):
        if not inside(box(0,0,brief.plot_width,brief.plot_depth),p) or any(overlap(p,q) for q in parked[i+1:]):invalid_parking.append(i)
        if any(overlap(p,box(c['x']-brief.wall_thickness/2,c['y']-brief.wall_thickness/2,c['width']+brief.wall_thickness,c['depth']+brief.wall_thickness)) for c in model['floors'][0]['cells']):invalid_parking.append(i)
    add('parking-geometry',not invalid_parking,'احتواء المواقف وعدم تداخلها مع المبنى أو بعضها',{'invalid':invalid_parking,'scope':'stall geometry only; turning and gates remain PENDING'})
    from .automatic_features import feature_checks
    checks.extend(feature_checks(model,brief))
    checks.extend(saudi_rules.checks(model,brief))
    from .jurisdiction import checks as local_checks
    checks.extend(local_checks(model,brief))
    from .site_placement import recheck as placement_check
    placement=placement_check(model,brief)
    if placement:checks.append(placement)
    return checks


def generate_general(brief:VillaBrief,output_dir=None,candidate_families=None,*,search_options=None,emit_drawings=True):
    from .general_drawing import drawing,review_drawing
    from .presentation import scene_svg,scene_pdf,scene_dxf
    out=Path(output_dir) if output_dir else Path(__file__).resolve().parents[2]/'outputs'
    out.mkdir(parents=True,exist_ok=True);candidates=[];unavailable=[]
    families=tuple(candidate_families) if candidate_families is not None else ('L','U','stepped')
    if not families or any(f not in FAMILIES for f in families) or len(set(families))!=len(families):
        raise ValueError('عائلات البحث الهندسي غير معروفة أو مكررة')
    options=search_options or [{'family':family,'policy':'legacy','core_position':'rear'} for family in families]
    for option in options:
        family=option['family'];policy=option.get('policy','legacy');core_position=option.get('core_position','rear')
        if family not in FAMILIES or policy not in ('legacy','social_front','family_front') or core_position not in ('rear','front'):
            raise ValueError('سياسة البحث غير مدعومة')
        label=FAMILIES[family]
        result=search(brief,family,policy,core_position)
        if not result:
            unavailable.append({'family':family,'label':label,'reason':('تعذر إنشاء الإضافات المطلوبة مع كامل برنامج الغرف. ' if any((brief.automatic_features.lightwell,brief.automatic_features.roof_annex,brief.automatic_features.balcony,brief.automatic_features.service_yard)) else '')+'لم يجد البحث المحدود توزيعًا يحقق عدد ومساحات وأبعاد الفراغات مع الممر والدرج في حدود الارتدادات المدخلة. جرّب تخفيف البرنامج أو زيادة المسطح المتاح.'});continue
        alternatives=[result]+result.get('alternatives',[]);model=None;failures=[]
        for attempt,layout in enumerate(alternatives):
            trial=materialize(brief,family,layout);trial['checks']=validate_general(trial,brief)
            errors=[c for c in trial['checks'] if c['status']=='FAIL']
            trial['search']['validated_layouts_tested']=attempt+1
            # Feedback-driven candidate selection: favor fewer critical architectural
            # violations rather than treating every failed check as equally severe.
            # Only valid candidates may be exported; PENDING remains unresolved.
            def violation_cost(items):
                critical={'guest-distributor-access':100,'guest-route':100,'entrance':100,
                          'GF-doors':80,'GF-program':80,'GF-overlap':80,'GF-site':80}
                return sum(critical.get(c['check_id'],20) for c in items)
            trial['search']['architectural_feedback']={
                'failed_checks':[c['check_id'] for c in errors],
                'violation_cost':violation_cost(errors),
                'pending_checks':[c['check_id'] for c in trial['checks'] if c['status']=='PENDING'],
                'candidate_selection':'minimum_weighted_violation_cost',
            }
            if model is None or (violation_cost(errors),len(errors)) < (violation_cost(failures),len(failures)):
                model=trial;failures=errors
            if not errors:
                def placement_cost(m):
                    value=m.get('site_placement',{}).get('entrance_to_street_midpoint_m')
                    return value if value is not None else float('inf')
                if failures or model is trial or placement_cost(trial)<placement_cost(model):model=trial
                failures=[]
            same_group=(attempt+1<len(alternatives) and layout.get('site_placement',{}).get('active') and alternatives[attempt+1].get('placement_group')==layout.get('placement_group'))
            if not failures and not same_group:break
            if any(c['check_id'] in ('SA-setbacks-baseline','SA-dwelling-program') for c in errors):model=trial;failures=errors;break
        model['search'].update(allocation_policy=policy,core_position=core_position,validated_layouts_tested=attempt+1)
        model['release']={'status':'BLOCKED' if failures else 'DRAFT_REVIEW','drawing_export_allowed':not failures,'executive_issue_allowed':False}
        rev=model['model_revision_id'];model['downloads']={'json':f'/api/files/{rev}.json'};model['previews']={}
        if not failures and emit_drawings:
            export_general_model(model,brief,out)
        (out/f'{rev}.json').write_text(json.dumps(model,ensure_ascii=False,indent=2),encoding='utf-8');candidates.append(model)
    return {'status':'DRAFT_REVIEW','candidates':candidates,'unavailable':unavailable,
            'scope':('أرض مستطيلة، دور أو دوران؛ بحث هندسي ضمن مكتبة حلول متاحة، دون ضمان الحل الأمثل أو الاعتماد التنفيذي.' if candidate_families is not None else 'أرض مستطيلة، دور أو دوران وملحق اختياري؛ بحث محدود L/U/متدرج؛ لا ضمان لإيجاد كل حل ممكن.'),
            'ai':{'mode':'geometric_search','language_model_connected':False}}


def export_general_model(model,brief,out):
    from .general_drawing import drawing,review_drawing
    from .presentation import scene_svg,scene_pdf,scene_dxf
    rev=model['model_revision_id']
    if not model['release']['drawing_export_allowed']:
        raise ValueError('لا يجوز تصدير رسم أخفق في فحص هندسي')
    scenes=[drawing(model,f) for f in model['floors']]
    for f,s in zip(model['floors'],scenes):
        name=f'{rev}-{f["id"]}.svg';(out/name).write_text(scene_svg(model,f,drawing=s),encoding='utf-8');model['previews'][f['id']]=f'/api/files/{name}'
    (out/f'{rev}-SITE.svg').write_text(scene_svg(model,model['floors'][0],drawing=drawing(model,model['floors'][0],site_view=True)),encoding='utf-8')
    model['previews']['SITE']=f'/api/files/{rev}-SITE.svg'
    export_model=model;export_scenes=scenes
    if model.get('design_option') or model.get('feature_generation') or brief.regulatory_geometry or model.get('site_placement',{}).get('active'):
        export_model={**model,'floors':model['floors']+[{'id':'SITE','name':'الموقع والخدمات','rooms':[]}]}
        export_scenes=scenes+[drawing(model,model['floors'][0],site_view=True)]
    report_model={**export_model,'floors':export_model['floors']+[{'id':'REVIEW','name':'تقرير الفحوص'}]}
    scene_pdf(report_model,out/f'{rev}.pdf',drawings=export_scenes+[review_drawing(model)],include_report=False)
    model['export_audit']=scene_dxf(export_model,out/f'{rev}.dxf',drawings=export_scenes)
    model['downloads'].update({ext:f'/api/files/{rev}.{ext}' for ext in ('pdf','dxf')})
