"""Explicit two-storey villa layout family with bounded footprint alternatives.
No claim of universal architectural search; proposed program and dimensions remain traceable.
"""
import copy
import hashlib
import json
from uuid import uuid4
from .models import Rect, RoomEntity, WallEntity, OpeningEntity, Fixture, FloorModel
from .requirements import project_profile, rules_summary
from .spatial_variants import mirror_candidate

EXT = .25
INT = .15


def rect_contains(a, b, eps=1e-7):
    return b.x >= a.x-eps and b.y >= a.y-eps and b.x+b.width <= a.x+a.width+eps and b.y+b.depth <= a.y+a.depth+eps


def attach_walls(floor, footprint, revision):
    sides = {}
    for r in floor.rooms:
        definitions = [('vertical',r.x,r.y,r.y+r.depth,'west'),('vertical',r.x+r.width,r.y,r.y+r.depth,'east'),
                       ('horizontal',r.y,r.x,r.x+r.width,'north'),('horizontal',r.y+r.depth,r.x,r.x+r.width,'south')]
        for axis, coord, lo, hi, side in definitions:
            edge = {'west':footprint.x+EXT,'east':footprint.x+footprint.width-EXT,
                    'north':footprint.y+EXT,'south':footprint.y+footprint.depth-EXT}[side]
            exterior = abs(coord-edge)<1e-6
            half = EXT/2 if exterior else INT/2
            offset = -half if side in ('west','north') else half
            key=(axis,round(coord+offset,6),exterior)
            sides.setdefault(key,[]).append((round(lo,6),round(hi,6),r.id))
    for (axis,coord,exterior), spans in sorted(sides.items()):
        ends=sorted({v for lo,hi,_ in spans for v in (lo,hi)})
        for a,b in zip(ends,ends[1:]):
            adjacent=sorted({rid for lo,hi,rid in spans if lo <= a+1e-6 and hi >= b-1e-6})
            if not adjacent or b-a<1e-6:
                continue
            start=(coord,a) if axis=='vertical' else (a,coord)
            end=(coord,b) if axis=='vertical' else (b,coord)
            floor.walls.append(WallEntity(id=f'{floor.id}-W{len(floor.walls)+1:03}',floor_id=floor.id,axis=axis,start=start,end=end,
                                          thickness=EXT if exterior else INT,room_ids=adjacent,exterior=exterior,revision_id=revision))


def add_opening(floor, source, target, revision, kind='door', face=None):
    rooms={r.id:r for r in floor.rooms}
    r=rooms[source]
    exterior = target=='EXTERIOR'
    possible=[w for w in floor.walls if source in w.room_ids and ((exterior and w.exterior) or (not exterior and target in w.room_ids))]
    if face:
        if face in ('west','east'):
            possible=[w for w in possible if w.axis=='vertical' and abs(w.start[0]-(r.x-EXT/2 if face=='west' else r.x+r.width+EXT/2))<1e-5]
        else:
            possible=[w for w in possible if w.axis=='horizontal' and abs(w.start[1]-(r.y-EXT/2 if face=='north' else r.y+r.depth+EXT/2))<1e-5]
    possible.sort(key=lambda w: (-(abs(w.end[0]-w.start[0])+abs(w.end[1]-w.start[1])),w.id))
    if not possible:
        raise ValueError(f'لا يوجد جدار مشترك صالح: {source} / {target}')
    wall=possible[0]
    length=abs(wall.end[0]-wall.start[0])+abs(wall.end[1]-wall.start[1])
    width=min(1.4 if kind=='window' else .95,length-.3)
    if width < .7:
        raise ValueError('الجدار أقصر من الفتحة المقترحة')
    center=((wall.start[0]+wall.end[0])/2,(wall.start[1]+wall.end[1])/2)
    if r.kind=='stairs' and kind=='door' and wall.axis=='vertical':
        center=(center[0],r.y+r.depth-.5)
    swing=None
    if kind=='door':
        # Door swings into source room. Rectangular envelope conservatively bounds the arc.
        if wall.axis=='vertical':
            left=abs(wall.start[0]-r.x)<abs(wall.start[0]-(r.x+r.width))
            swing=Rect(x=r.x if left else r.x+r.width-width,y=center[1]-width/2,width=width,depth=width)
        else:
            top=abs(wall.start[1]-r.y)<abs(wall.start[1]-(r.y+r.depth))
            swing=Rect(x=center[0]-width/2,y=r.y if top else r.y+r.depth-width,width=width,depth=width)
    opening=OpeningEntity(id=f'{floor.id}-O{len(floor.openings)+1:03}',floor_id=floor.id,wall_id=wall.id,kind=kind,center=center,
                          width=width,height=1.2 if kind=='window' else 2.2,sill=.9 if kind=='window' else 0,
                          connects=[source,target],face=face,swing_rect=swing,revision_id=revision)
    floor.openings.append(opening)


def furnish(floor, revision):
    for r in floor.rooms:
        def item(kind,x,y,w,h,capacity=0):
            f=Fixture(id=f'{floor.id}-F{len(floor.furniture)+1:03}',floor_id=floor.id,room_id=r.id,kind=kind,
                      x=x,y=y,width=w,depth=h,capacity=capacity,revision_id=revision)
            def clash(a,b):
                return min(a.x+a.width,b.x+b.width)-max(a.x,b.x)>1e-7 and min(a.y+a.depth,b.y+b.depth)-max(a.y,b.y)>1e-7
            positions=[(x,y)]+[(cx,cy) for cy in (r.y+.15,r.y+r.depth/2-h/2,r.y+r.depth-h-.15) for cx in (r.x+.15,r.x+r.width/2-w/2,r.x+r.width-w-.15)]
            for cx,cy in positions:
                f.x,f.y=cx,cy
                if not rect_contains(r,f):
                    continue
                if any(o.swing_rect and o.connects[0]==r.id and clash(f,o.swing_rect) for o in floor.openings):
                    continue
                conflicts=[q for q in floor.furniture if q.room_id==r.id and clash(f,q) and {q.kind,kind} not in ({'kitchen_counter','sink'},{'kitchen_counter','cooker'})]
                if not conflicts:
                    floor.furniture.append(f)
                    break
        if r.kind in ('bedroom','elderly'):
            item('single_bed',r.x+.5,r.y+.45,1,2,1)
            item('single_bed',r.x+r.width-1.5,r.y+.45,1,2,1)
        elif r.kind=='master':
            item('double_bed',r.x+1.8,r.y+.4,1.8,2,2)
        elif r.kind in ('living','majlis'):
            item('sofa',r.x+.4,r.y+.4,min(3,r.width-.8),.85)
            if r.depth>4:
                item('sofa',r.x+.4,r.y+r.depth-1.25,min(2,r.width-.8),.85)
        elif r.kind=='dining':
            item('dining_table',r.x+1.8,r.y+1.4,2.6,1.0)
            table=next((q for q in floor.furniture if q.room_id==r.id and q.kind=='dining_table'),None)
            if table:
                for cx in (.1,.75,1.4,2.05):
                    for cy in (-.65,1.2):item('dining_chair',table.x+cx,table.y+cy,.45,.45)
                item('dining_chair',table.x-.65,table.y+.2,.45,.45)
                item('dining_chair',table.x+table.width+.2,table.y+.2,.45,.45)
        elif r.kind=='kitchen':
            item('kitchen_counter',r.x+.15,r.y+.15,r.width-.3,.6)
            item('sink',r.x+.3,r.y+.22,.7,.5)
            item('cooker',r.x+r.width-1,r.y+.22,.6,.5)
            item('fridge',r.x+.15,r.y+1.2,.7,.7)
        elif r.kind=='bathroom':
            item('toilet',r.x+.3,r.y+.25,.7,.75)
            item('basin',r.x+r.width-1.05,r.y+.15,.65,.5)
            if r.id.endswith(('family-bath','master-bath')):
                item('shower',r.x+r.width-1.2,r.y+.15,1,1)
        elif r.kind=='wash':
            item('basin',r.x+.25,r.y+.25,1.1,.55)
        elif r.kind=='laundry':
            item('washing_machine',r.x+.2,r.y+.2,.65,.65)
        elif r.kind in ('storage','dressing'):
            item('storage',r.x+.2,r.y+.2,r.width-.4,.45)
        elif r.kind=='office':
            item('desk',r.x+.4,r.y+.4,1.5,.7)
        if r.kind in ('bedroom','elderly','master'):
            item('wardrobe',r.x+2,r.y+.15,1.6,.55)


def floor_plan(fid,name,level,fp,revision):
    floor=FloorModel(id=fid,name=name,level_m=level,rooms=[])
    x,y=fp.x+EXT,fp.y+EXT
    wing=(fp.width-2*EXT-2-2*INT)/2
    center=x+wing+INT
    right=center+2+INT
    # Original reference dimensions are not copied. Bands scale with proposed footprint.
    sy=(fp.depth-2*EXT-4*INT)/18.9
    def room(key,label,kind,zone,rx,ry,w,h):
        gaps={0:0,4.65:1,7.2:2,9.75:3,14.4:4,9.3:2,12.35:3,16:4}
        n=gaps.get(ry,0)
        clear_y=(ry-n*INT)*sy+n*INT
        clear_h=(h-4*INT)*sy+4*INT if h==19.5 else ((h-INT)*sy+INT if h==7.15 else h*sy)
        r=RoomEntity(id=f'{fid}-{key}',floor_id=fid,name=label,kind=kind,zone=zone,x=rx,y=y+clear_y,
                     width=w,depth=clear_h,area_m2=round(w*clear_h,3),revision_id=revision,source_ref='EXCEL_PROGRAM_OR_DISCLOSED_DESIGN_PROPOSAL')
        floor.rooms.append(r)
        return r.id
    hall=room('hall','ممر ومدخل العائلة' if fid=='GF' else 'موزع الدور الأول','corridor','family',center,0,2,19.5)
    core=room('stair','حجرة السلم','stairs','family',right,0,3,4.5)
    links=[(core,hall)]
    if fid=='GF':
        elder=room('elderly','غرفة ضيف أو كبير سن','elderly','private',x,0,wing,4.5)
        bath=room('family-bath','حمام عائلي','bathroom','family',x,4.65,3,2.4)
        lobby=room('service-lobby','ردهة الخدمات','corridor','family',x+3+INT,4.65,wing-3-INT,2.4)
        laundry=room('laundry','غسيل','laundry','service',x,7.2,3,2.4)
        store=room('storage','مستودع','storage','service',x+3+INT,7.2,wing-3-INT,2.4)
        living=room('living','صالة العائلة','living','family',x,9.75,wing,4.5)
        women=room('women','مجلس النساء','majlis','family',x,14.4,wing,5.1)
        kitchen=room('kitchen','مطبخ رئيسي','kitchen','service',right+3+INT,0,wing-3-INT,4.5)
        dining=room('dining','طعام عائلي','dining','family',right,4.65,wing,4.5)
        vestibule=room('men-lobby','ردهة ضيوف الرجال','corridor','guest',right,9.3,1.9,2.9)
        wash=room('men-wash','مغاسل الرجال','wash','guest',right+1.9+INT,9.3,1.7,2.9)
        toilet=room('men-bath','حمام الرجال','bathroom','guest',right+1.9+INT+1.7+INT,9.3,wing-3.9,2.9)
        men=room('men','مجلس الرجال','majlis','guest',right,12.35,wing,7.15)
        links.extend([(elder,hall),(lobby,hall),(bath,lobby),(laundry,store),(store,hall),(living,hall),(women,hall),
                      (dining,hall),(kitchen,dining),(vestibule,men),(wash,vestibule),(toilet,wash)])
        exterior=[(hall,'south'),(men,'south')]
    else:
        child1=room('child1','نوم أبناء 1 — مقترح','bedroom','private',x,0,wing,4.5)
        bath=room('family-bath','حمام عائلي','bathroom','private',x,4.65,3,2.4)
        lobby=room('service-lobby','ردهة الخدمات','corridor','family',x+3+INT,4.65,wing-3-INT,2.4)
        office=room('office','مكتب منزلي — مقترح','office','family',x,7.2,wing,2.4)
        living=room('living','معيشة يومية','living','family',x,9.75,wing,4.5)
        child2=room('child2','نوم أبناء 2 — مقترح','bedroom','private',x,14.4,wing,5.1)
        masterbath=room('master-bath','حمام رئيسي','bathroom','private',right+3+INT,0,wing-3-INT,4.5)
        master=room('master','غرفة النوم الرئيسية','master','private',right,4.65,wing,4.5)
        dressing=room('dressing','ملابس رئيسية','dressing','private',right,9.3,wing,2.9)
        child3=room('child3','نوم أبناء 3 — مقترح','bedroom','private',right,12.35,wing,3.5)
        child4=room('child4','نوم أبناء 4 — مقترح','bedroom','private',right,16,wing,3.5)
        links.extend([(child1,hall),(lobby,hall),(bath,lobby),(office,hall),(living,hall),(child2,hall),
                      (master,hall),(masterbath,master),(dressing,master),(child3,hall),(child4,hall)])
        exterior=[]
    attach_walls(floor,fp,revision)
    for source,target in links:
        add_opening(floor,source,target,revision)
    for rid,face in exterior:
        add_opening(floor,rid,'EXTERIOR',revision,face=face)
    # Only place windows on physical external walls; legal opening permission is separately PENDING.
    for r in floor.rooms:
        if r.kind not in ('bedroom','master','elderly','bathroom','kitchen','living','majlis','dining','laundry'):
            continue
        face='west' if abs(r.x-(fp.x+EXT))<1e-6 else 'east'
        add_opening(floor,r.id,'EXTERIOR',revision,kind='window',face=face)
    furnish(floor,revision)
    return floor


def make_candidate(profile, width, depth, floor_height, index):
    revision=uuid4().hex
    pw,pd=profile['site']['plot_width_m'],profile['site']['plot_depth_m']
    if width+1>pw or depth+1>pd:
        raise ValueError('عائلة التوزيع تحتاج مساحة حول المبنى للمراجعة؛ ليست قيم ارتداد قانونية')
    fp=Rect(x=(pw-width)/2,y=min((pd-depth)/2,pd-depth-5.5),width=width,depth=depth)
    gf=floor_plan('GF','الدور الأرضي',0,fp,revision)
    ff=floor_plan('FF','الدور الأول',floor_height,fp,revision)
    stairroom=next(r for r in gf.rooms if r.kind=='stairs')
    risers=18 if floor_height<=3.4 else 20
    stair={'id':'STAIR-01','floor_id':'GF','to_floor_id':'FF','room_ids':['GF-stair','FF-stair'],
           'x':stairroom.x+.15,'y':stairroom.y+.05,'width':2.6,'depth':(risers//2-1)*.26+1.1,
           'riser_count':risers,'riser_m':floor_height/risers,'tread_m':.26,'flight_width_m':1.2,
           'landing_depth_m':1.1,'floor_height_m':floor_height,'headroom_m':None,'status':'DESIGNER_PROPOSED',
           'revision_id':revision,'source_ref':'PROPOSED_STAIR_PARAMETERS_NOT_LOCAL_CODE'}
    parking={'id':'PARK-01','floor_id':'SITE','x':.25,'y':pd-5.25,'width':2.5,'depth':5,
             'status':'PROPOSED_STATIC_ENVELOPE_ONLY','revision_id':revision}
    return {'candidate_id':f'ALT-{index}','project_id':profile['project_id'],'model_revision_id':revision,
            'model_schema_version':'0.3.0','units':'m','coordinates':'x east; y south; origin NW plot corner; north per unverified source',
            'profile':copy.deepcopy(profile),'requirements_sha256':hashlib.sha256(json.dumps(profile,ensure_ascii=False,sort_keys=True).encode()).hexdigest(),
            'rule_bundle':rules_summary(),'site':{'width':pw,'depth':pd,'boundary':[[0,0],[pw,0],[pw,pd],[0,pd]],'verified':False},
            'footprint':fp.model_dump(),'wall_parameters':{'external_m':EXT,'internal_m':INT,'status':'DESIGNER_PROPOSED'},
            'floors':[gf.model_dump(),ff.model_dump()],'stairs':[stair],'parking':[parking],
            'search':{'family':'TWO_WINGS_CENTRAL_FAMILY_ROUTE_SEPARATE_GUEST_ENTRY','universal_solver':False,
                      'orientation_search':False,'description_ar':'بدائل محدودة لأبعاد المبنى ضمن عائلة توزيع واحدة؛ لم يُثبت أنها أفضل الحلول الممكنة'},
            'assumptions':[
                'أبعاد المبنى وموقعه وسماكات الجدران وارتفاع الدور مقترحات تصميمية، لا اشتراطات رسمية.',
                'أربع غرف أبناء بأسرّة مزدوجة العدد اقتراح قابل للتعديل؛ أعمار الأسرة وتوزيع النوم لم يعتمدا.',
                'الممرات والسلم والخدمات إضافات وظيفية مقترحة؛ لا تغير أولوية الطلبات الأصلية.',
                'الشمال أعلى الرسم بحسب المصدر، والشوارع والواجهات المسموحة للفتحات غير متحققة.',
                'المصعد وغرفة الخادمة ومدخل خدمة المطبخ قرارات معلقة وغير مدرجة في البديل.',
                'بعض الفراغات المفضلة مؤجلة؛ لا تُحذف من سجل متطلبات المشروع.',
                'الموقف مستطيل مقترح فقط؛ مسار السيارة والبوابة لم يُصمما.'
            ],'approval':{'status':'UNAPPROVED_DRAFT','execution_claim_allowed':False,'engineer_approval':None}}


def generate_candidates(options):
    profile=project_profile()
    if options.project_profile is not None and options.project_profile != profile:
        raise ValueError('النسخة الحالية مرتبطة بمتطلبات المحفد المعتمدة؛ لا تستبدلها بيانات غير معتمدة')
    candidates=[]
    sizes=[(14.8,20),(15.6,21.2),(14,19.2)]
    if options.footprint_width or options.footprint_depth:
        sizes=[(options.footprint_width or 14.8,options.footprint_depth or 20)]
    for i,(w,d) in enumerate(sizes[:options.candidate_count],1):
        candidate = make_candidate(profile,w,d,options.floor_height,i)
        if i == 2:
            candidate = mirror_candidate(candidate)
        candidates.append(candidate)
    return candidates
