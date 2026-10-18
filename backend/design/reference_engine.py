"""Reference-informed orthogonal zoning search. Images are precedents, not measured CAD.
Candidate families differ in adjacency, entry orientation, massing and floor stacking.
All dimensions remain project-specific designer proposals.
"""
import copy
import hashlib
import json
from uuid import uuid4
from .models import RoomEntity, FloorModel
from .requirements import project_profile, rules_summary

WALL=.20
HALF=WALL/2
EPS=1e-6
FAMILIES={
 'garden_gallery':('حديقة جانبية وبهو مرتفع','REF-04','REF-05'),
 'social_hub':('بهو توزيع ومعيشة مترابطة','REF-01','REF-04'),
 'open_court':('حوش جانبي وكتلة متدرجة','REF-03','REF-05'),
}


def room_cells(family,fid,W,D,bedrooms,double_height):
    """Partition raw structural cells; room interiors are inset by half a wall."""
    cells=[];links=[];outside=[];voids=[];terraces=[]
    def r(key,name,kind,zone,x,y,w,h):
        cells.append(dict(key=key,name=name,kind=kind,zone=zone,x=x,y=y,width=w,depth=h))
        return key
    def link(a,b,kind='door',ratio=.5,width=None):
        links.append((a,b,kind,ratio,width))
    if family=='garden_gallery':
        L=.55*W;T=.275*D;E=.21*D;S=.36*D;M=.59*D;C=.83*D;G=.755*D
        corew=3.6;foyerw=L-corew;service_split=L+.52*(W-L)
        if fid=='GF':
            r('kitchen','مطبخ رئيسي','kitchen','service',0,0,.71*L,T)
            r('storage','مستودع ومؤن','storage','service',.71*L,0,.29*L,T/2)
            r('laundry','غسيل','laundry','service',.71*L,T/2,.29*L,T/2)
            r('elderly','غرفة ضيف أو كبير سن','elderly','private',L,0,W-L,E)
            r('service-lobby','ردهة العائلة','corridor','family',L,E,service_split-L,S-E)
            r('family-bath','حمام عائلي','bathroom','family',service_split,E,W-service_split,S-E)
            r('living','معيشة العائلة','living','family',0,T,L,M-T)
            r('dining','طعام عائلي','dining','family',L,S,W-L,M-S)
            r('hall','بهو مدخل العائلة','corridor','family',0,M,foyerw,C-M)
            r('stair','السلم','stairs','family',foyerw,M,corew,C-M)
            r('women','مجلس النساء','majlis','family',0,C,L,D-C)
            r('men-lobby','ردهة ضيوف','corridor','guest',L,M,1.8,G-M)
            r('men-wash','مغاسل الرجال','wash','guest',L+1.8,M,1.9,G-M)
            r('men-bath','حمام الرجال','bathroom','guest',L+3.7,M,W-L-3.7,G-M)
            r('men','مجلس الرجال','majlis','guest',L,G,W-L,D-G)
            for a,b in [('storage','kitchen'),('laundry','kitchen'),('elderly','service-lobby'),('family-bath','service-lobby'),('service-lobby','living'),('stair','hall'),('women','hall'),('men-lobby','men'),('men-wash','men-lobby'),('men-bath','men-wash')]:link(a,b)
            link('kitchen','living','passage',.55,1.8)
            link('dining','living','passage',.55,2.2)
            link('living','hall','door',.83,1.05)
            outside=[('hall','west',.5,1.05),('men','south',.5,1.1)]
        else:
            b=.60*L;B=2.5;K=4.0
            r('master','غرفة النوم الرئيسية','master','private',0,0,b,T)
            r('master-bath','حمام رئيسي','bathroom','private',b,0,L-b,B)
            r('dressing','ملابس رئيسية','dressing','private',b,B,L-b,K-B)
            r('suite-entry','مدخل الجناح','corridor','private',b,K,L-b,T-K)
            r('child1','نوم أبناء 1 — مقترح','bedroom','private',L,0,W-L,E)
            r('service-lobby','ردهة النوم','corridor','family',L,E,service_split-L,S-E)
            r('family-bath','حمام عائلي','bathroom','private',service_split,E,W-service_split,S-E)
            landing=M-1.6
            r('hall','بهو الدور الأول','corridor','family',0,landing,W,1.6)
            if double_height:
                balcony=1.7
                r('gallery','رواق البهو','corridor','family',L-balcony,T,balcony,landing-T)
                voids=[dict(id='VOID-01',x=0,y=T,width=L-balcony,depth=landing-T,below_room='GF-living',name='فراغ مفتوح على المعيشة')]
            else:
                r('gallery','معيشة يومية','living','family',0,T,L,landing-T)
            r('child2','نوم أبناء 2 — مقترح','bedroom','private',L,S,W-L,landing-S)
            r('stair','السلم','stairs','family',foyerw,M,corew,C-M)
            r('child4' if bedrooms==4 else 'office','نوم أبناء 4 — مقترح' if bedrooms==4 else 'مكتب منزلي','bedroom' if bedrooms==4 else 'office','private' if bedrooms==4 else 'family',0,M,foyerw,C-M)
            terraces=[dict(id='TERRACE-01',x=0,y=C,width=L,depth=D-C,name='جلسة سطح مقترحة')]
            r('men-lobby','ردهة جناح النوم','corridor','family',L,M,1.8,G-M)
            r('dressing-child','ملابس الأبناء','dressing','private',L+1.8,M,1.9,G-M)
            r('child-bath','حمام غرف خاص','bathroom','private',L+3.7,M,W-L-3.7,G-M)
            r('child3' if bedrooms>=3 else 'extra-living','نوم أبناء 3 — مقترح' if bedrooms>=3 else 'معيشة يومية','bedroom' if bedrooms>=3 else 'living','private' if bedrooms>=3 else 'family',L,G,W-L,D-G)
            c3='child3' if bedrooms>=3 else 'extra-living'
            for a,b in [('master','suite-entry'),('dressing','master'),('master-bath','master'),('suite-entry','gallery'),('child1','service-lobby'),('family-bath','service-lobby'),('service-lobby','gallery'),('child2','hall'),('stair','hall'),('child4' if bedrooms==4 else 'office','hall'),(c3,'men-lobby'),('men-lobby','hall'),('dressing-child',c3),('child-bath',c3)]:link(a,b)
            link('gallery','hall','passage',.5,1.3)
            outside.append(('stair','south',.75,.95,'TERRACE-01'))
    else:
        # A short entrance hall, central social hub and separate front guest zone.
        q=D/18.5;K=.30*W;L=.60*W;F=.40*W;corew=3.6;svc=W-2.5
        yy=lambda n:n*q
        if fid=='GF':
            r('kitchen','مطبخ رئيسي','kitchen','service',0,0,K,yy(5))
            if family=='open_court':
                terraces=[dict(id='COURT-01',x=0,y=yy(5),width=K,depth=yy(3),name='حوش مفتوح على الحديقة')]
            else:
                r('prep-kitchen','مطبخ تحضيري','kitchen','service',0,yy(5),K,yy(3));link('prep-kitchen','kitchen','passage',.5,1.4)
            r('living','معيشة العائلة','living','family',K,0,L-K,yy(8))
            r('storage','مستودع ومؤن','storage','service',L,0,svc-L,yy(2.6))
            r('laundry','غسيل','laundry','service',svc,0,W-svc,yy(2.6))
            r('service-lobby','ردهة الخدمات','corridor','family',L,yy(2.6),svc-L,yy(2.4))
            r('family-bath','حمام عائلي','bathroom','family',svc,yy(2.6),W-svc,yy(2.4))
            r('elderly','غرفة ضيف أو كبير سن','elderly','private',L,yy(5),W-L,yy(5))
            r('stair','السلم','stairs','family',0,yy(8),corew,yy(5))
            r('dining','طعام عائلي','dining','family',corew,yy(8),L-corew,yy(5))
            r('hall','بهو مدخل العائلة','corridor','family',F,yy(13),L-F,D-yy(13))
            r('women','مجلس النساء','majlis','family',0,yy(13),F,D-yy(13))
            r('men-lobby','ردهة ضيوف','corridor','guest',L,yy(10),1.8,yy(3))
            r('men-wash','مغاسل الرجال','wash','guest',L+1.8,yy(10),1.9,yy(3))
            r('men-bath','حمام الرجال','bathroom','guest',L+3.7,yy(10),W-L-3.7,yy(3))
            r('men','مجلس الرجال','majlis','guest',L,yy(13),W-L,D-yy(13))
            for a,b in [('storage','service-lobby'),('laundry','storage'),('family-bath','service-lobby'),('elderly','service-lobby'),('elderly','dining'),('women','hall'),('men-lobby','men'),('men-wash','men-lobby'),('men-bath','men-wash')]:link(a,b)
            link('stair','dining','door',.88)
            link('service-lobby','living','door',.8)
            link('kitchen','living','passage',.55,2.4)
            link('living','dining','passage',.75,2.2)
            link('dining','hall','door',.12,.95)
            outside=[('hall','south',.5,1.05),('men','south',.5,1.1)]
            if family=='open_court':outside.append(('living','west',.80,1.0))
        else:
            if family=='open_court':
                r('master','غرفة النوم الرئيسية','master','private',2.5,0,L-2.5,yy(5))
                r('master-bath','حمام رئيسي','bathroom','private',0,0,2.5,yy(2.5))
                r('dressing','ملابس رئيسية','dressing','private',0,yy(2.5),2.5,yy(2.5))
                r('living','معيشة يومية','living','family',K,yy(5),L-K,yy(3))
                terraces=[dict(id='COURT-01',x=0,y=yy(5),width=K,depth=yy(3),name='حوش مكشوف إلى الأرضي',walkable=False)]
            else:
                r('master','غرفة النوم الرئيسية','master','private',0,0,K,yy(5))
                r('master-bath','حمام رئيسي','bathroom','private',0,yy(5),2.5,yy(3))
                r('dressing','ملابس رئيسية','dressing','private',2.5,yy(5),K-2.5,yy(3))
                r('living','معيشة يومية','living','family',K,0,L-K,yy(8))
            r('child1','نوم أبناء 1 — مقترح','bedroom','private',L,0,W-L,yy(5))
            r('service-lobby','ردهة النوم','corridor','family',L,yy(5),svc-L,yy(3))
            r('family-bath','حمام عائلي','bathroom','private',svc,yy(5),W-svc,yy(3))
            r('stair','السلم','stairs','family',0,yy(8),corew,yy(5))
            r('hall','بهو الدور الأول','corridor','family',corew,yy(8),L-corew,yy(5))
            r('child2','نوم أبناء 2 — مقترح','bedroom','private',L,yy(8),W-L,yy(5))
            r('child3' if bedrooms>=3 else 'extra-living','نوم أبناء 3 — مقترح' if bedrooms>=3 else 'معيشة يومية','bedroom' if bedrooms>=3 else 'living','private' if bedrooms>=3 else 'family',0,yy(13),F,D-yy(13))
            c3='child3' if bedrooms>=3 else 'extra-living'
            if bedrooms==4:
                r('front-lobby','ردهة النوم الأمامية','corridor','family',F,yy(13),L-F,D-yy(13))
                r('child4','نوم أبناء 4 — مقترح','bedroom','private',L,yy(13),W-L,D-yy(13));link('child4','front-lobby');link('front-lobby','hall')
            else:
                r('front-lobby','ردهة المكتب','corridor','family',F,yy(13),L-F,yy(2.5))
                r('office','مكتب منزلي','office','family',L,yy(13),W-L,yy(2.5))
                terraces.append(dict(id='TERRACE-01',x=F,y=yy(15.5),width=W-F,depth=D-yy(15.5),name='جلسة سطح مقترحة'))
                link('office','front-lobby');link('front-lobby','hall')
                outside.append(('front-lobby','south',.5,.95,'TERRACE-01'))
            for a,b in [('master-bath','master'),('dressing','master'),('master','living'),('child1','service-lobby'),('family-bath','service-lobby'),('child2','hall'),(c3,'hall')]:link(a,b)
            link('stair','hall','door',.88)
            link('service-lobby','living','door',.6)
            link('living','hall','passage',.55,1.8)
    return cells,links,outside,voids,terraces


def walls_for_floor(floor,revision):
    groups={}
    for r in floor['rooms']:
        for axis,c,a,b,sign in [('vertical',r['x'],r['y'],r['y']+r['depth'],-1),('vertical',r['x']+r['width'],r['y'],r['y']+r['depth'],1),('horizontal',r['y'],r['x'],r['x']+r['width'],-1),('horizontal',r['y']+r['depth'],r['x'],r['x']+r['width'],1)]:
            groups.setdefault((axis,round(c+sign*HALF,6)),[]).append((round(a,6),round(b,6),r['id']))
    for (axis,coord),spans in sorted(groups.items()):
        ends=sorted({v for a,b,_ in spans for v in (a,b)})
        for a,b in zip(ends,ends[1:]):
            adjacent=sorted({rid for lo,hi,rid in spans if lo<=a+EPS and hi>=b-EPS})
            if not adjacent or b-a<EPS:continue
            start=(coord,a) if axis=='vertical' else (a,coord);end=(coord,b) if axis=='vertical' else (b,coord)
            void_edge=False
            midpoint=((start[0]+end[0])/2,(start[1]+end[1])/2)
            for v in floor.get('voids',[]):
                if axis=='vertical':void_edge |= (abs(coord-v['x'])<EPS or abs(coord-v['x']-v['width'])<EPS) and v['y']-EPS<=midpoint[1]<=v['y']+v['depth']+EPS
                else:void_edge |= (abs(coord-v['y'])<EPS or abs(coord-v['y']-v['depth'])<EPS) and v['x']-EPS<=midpoint[0]<=v['x']+v['width']+EPS
            floor['walls'].append(dict(id=f"{floor['id']}-W{len(floor['walls'])+1:03}",floor_id=floor['id'],axis=axis,start=start,end=end,
                                       thickness=WALL,room_ids=adjacent,exterior=len(adjacent)==1 and not void_edge,boundary_type='guardrail' if void_edge else 'wall',
                                       revision_id=revision,source_ref='PROPOSED_MASONRY_200MM'))


def openings_for_floor(floor,links,outside,revision):
    rooms={r['id']:r for r in floor['rooms']}
    def add(source,target,kind='door',ratio=.5,width=None,face=None):
        source=floor['id']+'-'+source;target=target if target=='EXTERIOR' else floor['id']+'-'+target
        room=rooms[source]
        possible=[w for w in floor['walls'] if source in w['room_ids'] and ((target=='EXTERIOR' and w['exterior']) or target in w['room_ids'])]
        if face:
            fixed=0 if face in ('east','west') else 1
            edge=room['x']-HALF if face=='west' else room['x']+room['width']+HALF if face=='east' else room['y']-HALF if face=='north' else room['y']+room['depth']+HALF
            possible=[w for w in possible if w['axis']==('vertical' if fixed==0 else 'horizontal') and abs(w['start'][fixed]-edge)<EPS]
        options=[]
        for wall in possible:
            idx=1 if wall['axis']=='vertical' else 0
            lo,hi=wall['start'][idx],wall['end'][idx];length=hi-lo
            if room['kind']=='bathroom' and kind=='door':
                ratio=.03
            intended=width or (.85 if room['kind']=='bathroom' and kind=='door' else 1.8 if kind=='window' and room['kind'] in ('living','bedroom','master','elderly','majlis') else .85 if kind=='window' and room['kind']=='bathroom' else 1.25 if kind=='window' else .95)
            ow=min(intended,length-.25)
            if ow<(.65 if kind=='window' else .85):continue
            low,high=lo+ow/2+.10,hi-ow/2-.10
            preferred=hi-.60 if room['kind']=='stairs' and kind=='door' and idx==1 else lo+length*ratio
            for priority,pos in enumerate([preferred,low,high,(lo+hi)/2]):
                pos=max(low,min(high,pos))
                if any(o['wall_id']==wall['id'] and abs(o['center'][idx]-pos)<(o['width']+ow)/2+.15 for o in floor['openings']):continue
                center=(wall['start'][0],pos) if idx==1 else (pos,wall['start'][1])
                swing=None
                if kind=='door':
                    if idx==1:
                        left=room['x']+room['width']/2>center[0]
                        swing=dict(x=room['x'] if left else room['x']+room['width']-ow,y=pos-ow/2,width=ow,depth=ow)
                    else:
                        top=room['y']+room['depth']/2>center[1]
                        swing=dict(x=pos-ow/2,y=room['y'] if top else room['y']+room['depth']-ow,width=ow,depth=ow)
                    if not (swing['x']>=room['x']-EPS and swing['y']>=room['y']-EPS and swing['x']+ow<=room['x']+room['width']+EPS and swing['y']+ow<=room['y']+room['depth']+EPS):continue
                    if any(o.get('swing_rect') and overlap(o['swing_rect'],swing) for o in floor['openings']):continue
                options.append((priority,-length,wall,center,ow,swing))
        if not options:raise ValueError(f'لا توجد فتحة صالحة بين {source} و{target}')
        _,_,wall,center,ow,swing=min(options,key=lambda v:v[:2])
        if target=='EXTERIOR' and not face:
            face=('west' if center[0]<room['x'] else 'east') if wall['axis']=='vertical' else ('north' if center[1]<room['y'] else 'south')
        floor['openings'].append(dict(id=f"{floor['id']}-O{len(floor['openings'])+1:03}",floor_id=floor['id'],wall_id=wall['id'],kind=kind,center=center,width=ow,height=1.5 if kind=='window' else 2.3,sill=1.6 if kind=='window' and room['kind']=='bathroom' else .75 if kind=='window' else 0,
                                      connects=[source,target],face=face,swing_rect=swing,revision_id=revision,status='DESIGNER_PROPOSED',source_ref='REFERENCE_INFORMED_OPENING_POSITION'))
    for a,b,kind,ratio,width in links:add(a,b,kind,ratio,width)
    for entry in outside:
        a,face,ratio,width=entry[:4];add(a,'EXTERIOR','door',ratio,width,face)
        if len(entry)>4:floor['openings'][-1]['to_outdoor_id']=floor['id']+'-'+entry[4]
    for room in floor['rooms']:
        if room['kind'] not in ('master','bedroom','elderly','kitchen','bathroom','living','majlis','dining','laundry'):continue
        key=room['id'].split('-',1)[1]
        try:add(key,'EXTERIOR','window')
        except ValueError:
            # Kept as failed geometry evidence, never fake ventilation via an internal void.
            floor.setdefault('generation_notes',[]).append(f"نافذة خارجية غير متاحة: {room['id']}")


def overlap(a,b):
    return min(a['x']+a['width'],b['x']+b['width'])-max(a['x'],b['x'])>EPS and min(a['y']+a['depth'],b['y']+b['depth'])-max(a['y'],b['y'])>EPS


def make_reference_candidate(options,family,width,depth,index):
    from .furnishing import furnish_floor
    profile=project_profile();revision=uuid4().hex
    pw,pd=profile['site']['plot_width_m'],profile['site']['plot_depth_m']
    fp=dict(x=pw-width-.8,y=pd-depth-6.3,width=width,depth=depth)
    if fp['x']<.5 or fp['y']<.5:raise ValueError('المقترح لا يترك مساحة الموقع اللازمة لعائلة التوزيع؛ ليست ارتدادات قانونية')
    floors=[]
    for fid,name,level in [('GF','الدور الأرضي',0),('FF','الدور الأول',options.floor_height)]:
        double=options.double_height if options.double_height is not None else family=='garden_gallery'
        cells,links,entries,voids,terraces=room_cells(family,fid,width,depth,options.bedroom_count,double)
        floor=dict(id=fid,name=name,revision_id=revision,level_m=level,rooms=[],walls=[],openings=[],furniture=[],voids=voids,terraces=terraces,decorations=[])
        for c in cells:
            c=copy.deepcopy(c);key=c.pop('key');c['x']+=fp['x']+HALF;c['y']+=fp['y']+HALF;c['width']-=WALL;c['depth']-=WALL
            floor['rooms'].append(dict(id=f'{fid}-{key}',floor_id=fid,**c,area_m2=round(c['width']*c['depth'],3),revision_id=revision,status='DESIGNER_PROPOSED',source_ref='ADOPTED_EXCEL_PROGRAM_PLUS_DISCLOSED_PROPOSALS'))
        for group in ('voids','terraces'):
            for v in floor[group]:v.update(id=fid+'-'+v['id'],x=v['x']+fp['x'],y=v['y']+fp['y'],revision_id=revision,status='DESIGNER_PROPOSED',source_ref='PROPOSED_REFERENCE_INFORMED_MASSING')
        floor['gross_area_proposed_m2']=round(sum(c['width']*c['depth'] for c in cells),3)
        floor['outdoor_furniture']=[]
        for t in floor['terraces']:
            if not t.get('walkable',True) or t['width']<3.0 or t['depth']<2.8:continue
            anchor=t['x']+.25 if family=='garden_gallery' else t['x']+t['width']-3.6
            for i,q in enumerate([dict(kind='sofa',x=anchor,y=t['y']+.25,width=2.4,depth=.85,seats=3,rotation=0),dict(kind='coffee_table',x=anchor+.7,y=t['y']+1.7,width=1.0,depth=.6,rotation=0)],1):
                floor['outdoor_furniture'].append(dict(q,id=f'{fid}-OUT-{i}',outdoor_id=t['id'],revision_id=revision,status='DESIGNER_PROPOSED',source_ref='PROPOSED_OUTDOOR_FURNISHING'))
        floor['guardrails']=[]
        if fid=='FF':
            for t in floor['terraces']:
                if not t.get('walkable',True):continue
                for side in ('south','west','east'):
                    if side=='south':a=(t['x'],t['y']+t['depth']);b=(t['x']+t['width'],t['y']+t['depth'])
                    elif side=='west':a=(t['x'],t['y']);b=(t['x'],t['y']+t['depth'])
                    else:a=(t['x']+t['width'],t['y']);b=(t['x']+t['width'],t['y']+t['depth'])
                    if side=='south' or (side=='west' and family=='garden_gallery') or (side=='east' and family!='garden_gallery'):
                        floor['guardrails'].append(dict(id=f"{fid}-RAIL-{len(floor['guardrails'])+1}",start=a,end=b,height_m=1.1,revision_id=revision,status='PROPOSED_NOT_CODE_VERIFIED',source_ref='PROPOSED_TERRACE_EDGE_PROTECTION'))
        walls_for_floor(floor,revision);openings_for_floor(floor,links,entries,revision)
        furnish_floor(floor,revision)
        floors.append(floor)
    sr=next(r for r in floors[0]['rooms'] if r['kind']=='stairs')
    risers=18 if options.floor_height<=3.4 else 20
    # The rear flight/landing is reserved; front arrival remains clear of door swings.
    stair=dict(id='STAIR-01',floor_id='GF',to_floor_id='FF',room_ids=['GF-stair','FF-stair'],x=sr['x']+.10,y=sr['y']+.12,width=2.4,depth=(risers//2-1)*.28+1.2,
               riser_count=risers,riser_m=options.floor_height/risers,tread_m=.28,flight_width_m=1.1,landing_depth_m=1.2,floor_height_m=options.floor_height,headroom_m=None,
               revision_id=revision,status='DESIGNER_PROPOSED',source_ref='PROPOSED_STAIR_NOT_REGULATORY_APPROVAL')
    parking=dict(id='PARK-01',floor_id='SITE',x=fp['x']+.5,y=pd-5.8,width=2.8,depth=5.4,revision_id=revision,status='STATIC_ENVELOPE_ONLY')
    site_features=[dict(id='GARDEN-01',kind='garden',x=.35,y=.5,width=max(.2,fp['x']-1.35),depth=pd-1.0),
                   dict(id='FORECOURT-01',kind='paving',x=fp['x'],y=fp['y']+depth+.1,width=width,depth=pd-fp['y']-depth-.45),
                   dict(id='WALK-01',kind='paving',x=fp['x']-1.0,y=.5,width=.9,depth=pd-1.0)]
    model=dict(candidate_id=f'ALT-{index}',project_id=profile['project_id'],model_revision_id=revision,model_schema_version='0.4.0',units='m',
                coordinates='x east; y south; origin NW plot corner; north per unverified Excel source',profile=profile,
                requirements_sha256=hashlib.sha256(json.dumps(profile,ensure_ascii=False,sort_keys=True).encode()).hexdigest(),rule_bundle=rules_summary(),
                site=dict(width=pw,depth=pd,boundary=[[0,0],[pw,0],[pw,pd],[0,pd]],verified=False),footprint=fp,
                wall_parameters=dict(external_m=WALL,internal_m=WALL,status='PROPOSED_200MM_NOT_CODE_REQUIREMENT'),floors=floors,stairs=[stair],parking=[parking],site_features=site_features,
                search=dict(family=family,family_label_ar=FAMILIES[family][0],reference_ids=list(FAMILIES[family][1:]),universal_solver=False,orientation_search=False,
                            description_ar='بحث مقترحات ضمن عائلات مختلفة العلاقات والكتلة، مع فحوص هندسية ومسارات فعلية؛ ليس نسخًا لإحداثيات الصور'),
                assumptions=['أرض المحفد 20 × 30 م ودوران؛ الصور مرجع جودة وتنظيم وليست مصدر أبعاد أو اشتراطات.',
                             'أبعاد الفراغات وسماكات الجدران 20 سم وارتفاع الدور والفرش مقترحات تصميمية قابلة للمراجعة.',
                             f'عدد غرف الأبناء المقترح {options.bedroom_count}؛ توزيع أفراد الأسرة وأعمارهم لم يعتمدا.',
                             'الشمال والواجهات والارتدادات ما زالت غير متحققة؛ المساحات حول المبنى ليست اعتمادًا نظاميًا.',
                             'البهو المزدوج والحديقة والأحواش المفتوحة وجلسة السطح مقترحات معلنة بحسب البديل؛ لا تفعيل لمسبح أو مصعد أو تقسيم لوحدتين من الصور.',
                             'المصعد والخادمة ومدخل الخدمة تظل قرارات معلقة. بعض التفضيلات مؤجلة وتظهر في تغطية البرنامج.',
                             'أبعاد خلوص استعمال الفرش وعرض الحركة معايير تصميم مقترحة للاختبار وليست قيماً قانونية محلية.',
                             'الموقف غلاف سيارة مقترح؛ لم يُتحقق من المناورة والبوابة والشارع.'],
                approval=dict(status='UNAPPROVED_DRAFT',execution_claim_allowed=False,engineer_approval=None))
    model['presentation']={'style':options.output_style,'source':'reference_quality_brief_v04'}
    refine_furniture_access(model)
    return model


def generate_reference_candidates(options):
    profile=project_profile()
    if options.project_profile is not None and options.project_profile!=profile:raise ValueError('متطلبات المحفد المعتمدة محفوظة؛ المدخلات المختلفة تحتاج ربطًا واعتمادًا صريحًا')
    families=list(FAMILIES) if options.layout_family=='reference_search' else [options.layout_family]
    defaults={'garden_gallery':(13.6,20.6),'social_hub':(15.6,20.0),'open_court':(15.0,20.8)}
    candidates=[]
    for family in families[:options.candidate_count]:
        w,d=defaults[family]
        candidates.append(make_reference_candidate(options,family,options.footprint_width or w,options.footprint_depth or d,len(candidates)+1))
    return candidates


def refine_furniture_access(model):
    from .walkability import floor_access
    from .furnishing import bathroom_layouts,bed_layouts,valid_group
    attempts=0;repairs=[]
    for floor in model['floors']:
        assessment=floor_access(model,floor)
        for rid in list(assessment['unreachable']):
            room=next(r for r in floor['rooms'] if r['id']==rid)
            if room['kind']!='bathroom':continue
            original=copy.deepcopy(floor['furniture']);others=[q for q in original if q['room_id']!=rid]
            for group in bathroom_layouts(room):
                if not valid_group(floor,room,group,existing=[]):continue
                attempts+=1
                floor['furniture']=copy.deepcopy(others)+[dict(q,id=f"REPAIR-{i}",room_id=rid,floor_id=floor['id'],revision_id=model['model_revision_id'],status='DESIGNER_PROPOSED',source_ref='PROPOSED_FURNITURE_ACCESS_REPAIR') for i,q in enumerate(group)]
                trial=floor_access(model,floor)
                if rid not in trial['unreachable'] and len(trial['unreachable'])<len(assessment['unreachable']):
                    repairs.append(rid);assessment=trial;break
                floor['furniture']=copy.deepcopy(original)
            else:floor['furniture']=original
        for i,q in enumerate(floor['furniture'],1):q['id']=f"{floor['id']}-F{i:03}"
    model['search']['furnishing_access_trials']=attempts
    model['search']['furnishing_access_repairs']=repairs
