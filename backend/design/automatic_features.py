"""Construct optional architectural features before validation, from customer intent.

All positions are proposed geometry. No declaration is promoted to a survey or
permit approval. Requested features that cannot be constructed block release.
"""
import copy
import math
from .furnishing import inside,overlap,furnish_floor
from .general_geometry import union_polygons,signed_area
from .saudi_2024_overlay import covered_by,bounds,exterior_face,on_edge

EPS=1e-6
FACES=('north','south','east','west')

def rect(x,y,w,d,**kw):return dict(x=x,y=y,width=w,depth=d,**kw)
def polygon(q):
    x,y,w,d=(q[k] for k in ('x','y','width','depth'))
    return [[x,y],[x+w,y],[x+w,y+d],[x,y+d]]
def from_polygon(p):
    x,y,xx,yy=bounds(p);return rect(x,y,xx-x,yy-y)
def intersects(a,b,pad=0):
    return a['x']<b['x']+b['width']+pad-EPS and a['x']+a['width']>b['x']-pad+EPS and a['y']<b['y']+b['depth']+pad-EPS and a['y']+a['depth']>b['y']-pad+EPS

def reserve_lightwell(lanes,brief):
    """An aligned open service court consumes real wing length on every floor."""
    lanes=copy.deepcopy(lanes)
    if not brief.automatic_features.lightwell:return lanes,[]
    t=brief.wall_thickness;gap=max(1.8,brief.automatic_features.lightwell_length_m)+t
    eligible=[(i,l) for i,l in enumerate(lanes) if l['axis']=='y' and l['width']-t>=1.8 and l['depth']>=gap+6.4]
    if not eligible:return None
    i,l=max(eligible,key=lambda il:il[1]['depth'])
    before=(l['depth']-gap)*.5;after=l['depth']-before-gap
    lanes[i:i+1]=[{**l,'depth':before},{**l,'y':l['y']+before+gap,'depth':after}]
    void=rect(l['x']+t/2,l['y']+before+t/2,l['width']-t,gap-t,id='AUTO-WELL-1')
    return lanes,[void]

def _record(model,kind,status,reason='',**extra):
    model['feature_generation'].append(dict(feature=kind,status=status,reason=reason,**extra))

def _window_on_court(f,well,revision):
    # The clear void edge is half a wall thickness from a window's host centerline.
    q=from_polygon(well['polygon'])
    for w in f['walls']:
        if not w['exterior']:continue
        a,b=w['start'],w['end'];axis=0 if w['axis']=='horizontal' else 1
        fixed=a[1-axis];lo=q['x' if axis==0 else 'y'];hi=lo+q['width' if axis==0 else 'depth']
        faces=(q['y'],q['y']+q['depth']) if axis==0 else (q['x'],q['x']+q['width'])
        if min(abs(fixed-v) for v in faces)>w['thickness']/2+.001:continue
        aa=max(a[axis]+.25,lo+.05);bb=min(b[axis]-.25,hi-.05)
        if bb-aa<.7:continue
        host=next((r for r in f['rooms'] if r['id'] in w['room_ids'] and (r.get('request_id') or r.get('generated_feature_room'))),None)
        if not host:continue
        existing=[o for o in f['openings'] if o['wall_id']==w['id'] and aa<=o['center'][axis]<=bb and o['kind']=='window']
        if not existing:
            width=min(1.2,bb-aa);center=list(a);center[axis]=(aa+bb)/2
            if any(o['wall_id']==w['id'] and abs(o['center'][axis]-center[axis])<(o['width']+width)/2+.1 for o in f['openings']):continue
            height=.8 if host['kind']=='bathroom' else 1.5;sill=1.5 if host['kind']=='bathroom' else .9
            f['openings'].append(dict(id=f['id']+'-COURT-'+str(len(f['openings'])),floor_id=f['id'],wall_id=w['id'],kind='window',center=center,width=width,height=height,sill=sill,clear_width=width-.12,clear_height=height-.12,operable_fraction=.5,connects=[host['id'],'OUTSIDE'],revision_id=revision))
        for o in f['openings']:
            if o['wall_id']==w['id'] and o['kind']=='window' and o['id'] not in well['window_ids']:well['window_ids'].append(o['id'])

def _roof_annex(model,brief):
    from .general_engine import make_walls,add_windows
    t=brief.wall_thickness;under=model['floors'][-1];core=next((c for c in under['cells'] if c['kind']=='stair'),None)
    if not core:return None,'لم يتوفر درج يصل إلى الملحق'
    stair=copy.deepcopy(core);halls=[c for c in under['cells'] if c['kind']=='corridor' and abs(c['x']+c['width']-stair['x'])<EPS or c['kind']=='corridor' and abs(c['x']-(stair['x']+stair['width']))<EPS]
    extension=max(3.6,brief.automatic_features.annex_lounge_min_m2/(stair['width']-t)+t)
    under_polys=model['footprint']['polygons_by_floor'][under['id']]
    for hall in halls:
        y0=stair['y']-extension;y1=stair['y']+stair['depth'];x0=min(hall['x'],stair['x']);x1=max(hall['x']+hall['width'],stair['x']+stair['width'])
        # Gross wall strips extend t/2 beyond centerline cells.
        physical=rect(x0-t/2,y0-t/2,x1-x0+t,y1-y0+t)
        poly=polygon(physical)
        if not covered_by(poly,under_polys):continue
        parent_area=sum(signed_area(p) for p in under_polys)
        if physical['width']*physical['depth']>parent_area*.7+EPS:continue
        pbox=bounds([p for loop in under_polys for p in loop]);qbox=bounds(poly)
        gaps={'north':qbox[1]-pbox[1],'south':pbox[3]-qbox[3],'west':qbox[0]-pbox[0],'east':pbox[2]-qbox[2]}
        if any(gaps[face]<1.5-EPS for face,width in brief.boundary_widths.items() if width>0):continue
        bath_depth=2.2
        cells=[dict(stair,id='RF-stair',name='وصول الدرج'),rect(stair['x'],y0,stair['width'],extension,id='RF-lounge',kind='living',name='جلسة الملحق',generated_feature_room=True),rect(hall['x'],y0,hall['width'],bath_depth,id='RF-wc',kind='bathroom',name='دورة مياه الملحق',generated_feature_room=True,include_shower=False),rect(hall['x'],y0+bath_depth,hall['width'],y1-y0-bath_depth,id='RF-hall',kind='corridor',name='موزع الملحق')]
        f=dict(id='RF',name='الملحق العلوي',roof_annex=True,level_m=brief.floors*brief.floor_height,cells=cells,rooms=[],walls=[],openings=[],furniture=[],decorations=[])
        for c in cells:
            c['floor_id']='RF';q=copy.deepcopy(c);q.update(x=c['x']+t/2,y=c['y']+t/2,width=c['width']-t,depth=c['depth']-t,revision_id=model['model_revision_id']);q['area_m2']=q['width']*q['depth'];f['rooms'].append(q)
        make_walls(f,t,model['model_revision_id']);add_windows(f,brief,model['model_revision_id']);furnish_floor(f,model['model_revision_id'],{})
        arrival=next(r for r in f['rooms'] if r['kind']=='stair')
        model['stair_arrivals']=[dict(room_id=arrival['id'],floor_id='RF',entry_apron=rect(arrival['x'],arrival['y'],arrival['width'],1.0),void=rect(arrival['x'],arrival['y']+1.0,arrival['width'],arrival['depth']-1.0))]
        model['floors'].append(f);model['footprint']['polygons_by_floor']['RF']=union_polygons(cells,t/2)
        # Proposed roof parapet, not a measured or approved construction detail.
        return dict(polygon=poly,area_m2=physical['width']*physical['depth'],street_setbacks_m=gaps,parapet_height_m=.6,independent_unit=False,additional_parking_space=None,neighbor_direct_windows=None,staircase_continues_to_annex_roof=False),''
    return None,'لم يتسع الملحق مع وصول الدرج والارتداد فوق بصمة الدور السفلي ونسبة 70٪؛ زد الأرض أو خفف البرنامج'

def _balcony(model,brief):
    from .general_engine import add_windows
    f=next(f for f in model['floors'] if f['id']=='FF');t=brief.wall_thickness;depth=brief.automatic_features.balcony_depth_m
    wanted=brief.automatic_features.balcony_face
    allowed=rect(0,0,brief.plot_width,brief.plot_depth)
    rooms={r['id']:r for r in f['rooms']}
    walls=[w for w in f['walls'] if w['exterior'] and any(rooms[i]['kind'] in ('living','master','bedroom') for i in w['room_ids'])]
    court_windows={i for q in model['regulatory_geometry'].get('light_wells') or [] for i in q.get('window_ids',[])}
    walls=[w for w in walls if not any(o['id'] in court_windows and o['wall_id']==w['id'] for o in f['openings'])]
    walls.sort(key=lambda w:-math.dist(w['start'],w['end']))
    for w in walls:
        face=exterior_face(w,f)
        if wanted!='auto' and wanted!=face:continue
        axis=0 if face in ('north','south') else 1;length=math.dist(w['start'],w['end']);span=min(3.,length-.5)
        if span<1.8:continue
        fixed=w['start'][1-axis];mid=(w['start'][axis]+w['end'][axis])/2
        x,y=(mid-span/2,fixed-depth) if face=='north' else (mid-span/2,fixed) if face=='south' else (fixed-depth,mid-span/2) if face=='west' else (fixed,mid-span/2)
        q=rect(x,y,span if axis==0 else depth,depth if axis==0 else span)
        if not inside(allowed,q):continue
        # A projection must remain outside all existing rooms, not fill a reentrant wing.
        if any(intersects(q,c,pad=-.01) for c in f['cells']):continue
        offset={'north':y,'south':brief.plot_depth-y-q['depth'],'west':x,'east':brief.plot_width-x-q['width']}[face]
        within=offset<getattr(brief.setbacks,face)-EPS
        road=brief.boundary_widths.get(face)
        if within and (road is None or road<10):continue
        host=rooms[w['room_ids'][0]];opening_center=list(w['start']);opening_center[axis]=mid
        other=[o for o in f['openings'] if o['wall_id']==w['id'] and o['kind']=='door']
        if any(abs(o['center'][axis]-mid)<(o['width']+.9)/2+.15 for o in other):continue
        # A real sliding glazed door replaces windows on this host; daylight is rebuilt.
        old_windows=[o for o in f['openings'] if o['wall_id']==w['id'] and o['kind']=='window']
        f['openings']=[o for o in f['openings'] if o not in old_windows]
        clear=rect(mid-.45,fixed-.65,.9,.65) if face=='south' else rect(mid-.45,fixed,.9,.65) if face=='north' else rect(fixed-.65,mid-.45,.65,.9) if face=='east' else rect(fixed,mid-.45,.65,.9)
        o=dict(id='FF-BALCONY-DOOR',floor_id='FF',wall_id=w['id'],kind='door',door_style='sliding',center=opening_center,width=.9,height=2.2,sill=0,connects=[host['id'],'BALCONY-1'],swing_rect=clear,revision_id=model['model_revision_id'],balcony_access=True)
        f['openings'].append(o);add_windows(f,brief,model['model_revision_id']);f['furniture']=[];furnish_floor(f,model['model_revision_id'],{})
        f['balconies']=[dict(q,id='BALCONY-1',name='شرفة',door_id=o['id'],host_room_id=host['id'],face=face,guard_height_m=1.1,polygon=polygon(q))]
        return dict(id='AUTO-BALCONY-1',floor_id='FF',face=face,kind='balcony',depth_m=depth,within_setback=within,crosses_property_line=False,clearance_m=brief.floor_height,polygon=polygon(q))
    return None

def build_features(model,brief,result):
    model['feature_generation']=[];geo=model.get('regulatory_geometry') or {};model['regulatory_geometry']=geo
    a=brief.automatic_features;t=brief.wall_thickness
    if a.lightwell:
        wells=[]
        for local in result.get('wells',[]):
            q=copy.deepcopy(local);q['x']+=result.get('origin_x',brief.setbacks.west)+t/2;q['y']+=result.get('origin_y',brief.setbacks.north)+t/2
            well=dict(id=q['id'],width_m=q['width'],length_m=q['depth'],storeys_served=brief.floors,opposing_windows=True,polygon=polygon(q),window_ids=[],open_to_sky=True,cleaning_door=None,drains_provided=None,light_wall_finish=None)
            for f in model['floors']:
                f.setdefault('lightwells',[]).append(dict(q,name='منور مفتوح'))
                _window_on_court(f,well,model['model_revision_id'])
                # Ground maintenance access is an actual sliding door in the hall wall.
                if f['id']=='GF':
                    for w in f['walls']:
                        hall=next((r for r in f['rooms'] if r['kind']=='corridor' and r['id'] in w['room_ids']),None)
                        if not hall or not w['exterior'] or w['axis']!='vertical':continue
                        edge=min(abs(w['start'][0]-q['x']),abs(w['start'][0]-(q['x']+q['width'])))
                        lo=max(w['start'][1],q['y']);hi=min(w['end'][1],q['y']+q['depth'])
                        if edge<=t/2+.001 and hi-lo>=1.1:
                            center=[w['start'][0],(lo+hi)/2]
                            f['openings'].append(dict(id='GF-COURT-MAINTENANCE',floor_id='GF',wall_id=w['id'],kind='door',door_style='sliding',center=center,width=.9,height=2.2,sill=0,connects=[hall['id'],q['id']],revision_id=model['model_revision_id']));well['cleaning_door']=True;break
            wells.append(well)
        geo['light_wells']=wells;_record(model,'lightwell','GENERATED' if wells else 'UNAVAILABLE',window_ids=[i for w in wells for i in w['window_ids']])
    if a.roof_annex:
        annex,reason=_roof_annex(model,brief)
        if annex:geo['roof_annex']=annex;geo['roof_annex_absent']=False
        _record(model,'roof_annex','GENERATED' if annex else 'UNAVAILABLE',reason)
    if a.balcony:
        pr=_balcony(model,brief)
        if pr:geo['projections']=[pr]
        _record(model,'balcony','GENERATED' if pr else 'UNAVAILABLE','' if pr else 'لم يتوفر جدار وشرفة بباب داخل الأرض مع تصنيف شارع مناسب؛ حدد عروض الشوارع أو غيّر جهة الشرفة')
    model['generated_geometry_scope']='PROPOSED_DESIGN_NOT_SURVEYED_OR_APPROVED'

def place_services(model,brief):
    if not brief.automatic_features.service_yard:return
    building=[c for f in model['floors'] for c in f['cells']];obstacles=building+model.get('parking',[])
    obstacles += [from_polygon(w['polygon']) for w in (model['regulatory_geometry'].get('light_wells') or []) if w.get('polygon')]
    entry=next((o for o in model['floors'][0]['openings'] if o.get('main_entry')),None)
    if entry:
        x,y=entry['center'];face=brief.entrance_face
        path=rect(x-.65,y,1.3,brief.plot_depth-y) if face=='south' else rect(x-.65,0,1.3,y) if face=='north' else rect(0,y-.65,x,1.3) if face=='west' else rect(x,y-.65,brief.plot_width-x,1.3)
        obstacles.append(path)
    found=None
    for w,d in ((2.4,1.4),(1.4,2.4)):
        for yi in range(1,int((brief.plot_depth-d-.2)*2)):
            for xi in range(1,int((brief.plot_width-w-.2)*2)):
                q=rect(xi*.5,yi*.5,w,d)
                if not any(intersects(q,b,.25) for b in obstacles):found=q;break
            if found:break
        if found:break
    if not found:
        _record(model,'service_yard','UNAVAILABLE','لا توجد مساحة خدمة خارجية خالية من البناء والمواقف ومسار المدخل');return
    units=[rect(found['x']+.15,found['y']+.15,.75,.45,id='AC-1',floor_id='GF'),rect(found['x']+found['width']-.9,found['y']+found['depth']-.6,.75,.45,id='AC-2',floor_id='GF')]
    if intersects(units[0],units[1]):units[1].update(y=found['y']+found['depth']-.6)
    model['service_yard']=dict(found,id='SERVICE-1',equipment=units,name='ساحة خدمة وتكييف')
    faces=[];declared=brief.automatic_features.main_street_faces
    for face in FACES:
        faces.append(dict(face=face,faces_main_street=face in declared if declared is not None else None,visible_ac_or_services=False,ac_or_services_on_facade=False,equipment=copy.deepcopy(units),inventory_complete=True))
    model['regulatory_geometry']['facades']=faces
    _record(model,'service_yard','GENERATED',equipment_ids=[q['id'] for q in units])

def finalize_features(model,brief):
    # Recompute all physical areas after adding the roof floor and balcony slab.
    areas={}
    for f in model['floors']:
        polys=union_polygons(f['cells'],brief.wall_thickness/2)
        # Balcony slab area is additional to the occupied wall footprint, less its wall overlap.
        areas[f['id']]=round(sum(signed_area(p) for p in polys)+sum(b['width']*b['depth']-max(b['width'],b['depth'])*brief.wall_thickness/2 for b in f.get('balconies',[])),2)
        model['footprint']['polygons_by_floor'][f['id']]=polys
    model['metrics']['floor_built_by_id']=areas;model['metrics']['floor_built_m2']=max(areas.values())
    model['metrics']['annex_built_m2']=areas.get('RF',0)
    model['metrics']['balcony_m2']=round(sum(b['width']*b['depth'] for f in model['floors'] for b in f.get('balconies',[])),2)

def feature_checks(model,brief):
    checks=[];a=brief.automatic_features
    for kind in ('lightwell','roof_annex','balcony','service_yard'):
        if not getattr(a,kind):continue
        row=next((r for r in model.get('feature_generation',[]) if r['feature']==kind),None)
        actual={'lightwell':bool(model.get('regulatory_geometry',{}).get('light_wells')),'roof_annex':any(f.get('roof_annex') for f in model['floors']),'balcony':any(f.get('balconies') for f in model['floors']),'service_yard':bool(model.get('service_yard'))}[kind]
        ok=row is not None and row['status']=='GENERATED' and actual
        checks.append(dict(check_id='AUTO-'+kind,status='PASS' if ok else 'FAIL',label='إنشاء الإضافة المطلوبة — '+{'lightwell':'المنور','roof_annex':'الملحق العلوي','balcony':'الشرفة','service_yard':'ساحة الخدمات'}[kind],evidence=row or {'reason':'لم ينشأ العنصر المطلوب'}))
    if a.lightwell:
        wells=model.get('regulatory_geometry',{}).get('light_wells') or []
        links={fid:any(i.startswith(fid+'-') for w in wells for i in w.get('window_ids',[])) for fid in ('GF','FF')[:brief.floors]}
        checks.append(dict(check_id='AUTO-well-windows',status='PASS' if links and all(links.values()) else 'FAIL',label='نافذة فعلية مرتبطة بالمنور في كل دور',evidence={'served_floors':links}))
    if a.roof_annex:
        f=next((f for f in model['floors'] if f['id']=='RF'),None)
        core=next((r for r in (f or {}).get('cells',[]) if r['kind']=='stair'),None)
        lower=model['floors'][brief.floors-1];under=next((r for r in lower['cells'] if r['kind']=='stair'),None)
        connected=core and under and all(abs(core[k]-under[k])<EPS for k in ('x','y','width','depth'))
        lounge=next((r for r in (f or {}).get('rooms',[]) if r['kind']=='living'),None)
        valid=bool(lounge and lounge['width']*lounge['depth']>=a.annex_lounge_min_m2-EPS and min(lounge['width'],lounge['depth'])>=2.8)
        checks.append(dict(check_id='AUTO-annex-core',status='PASS' if connected and valid else 'FAIL',label='وصول الدرج إلى الملحق ومساحة الجلسة المطلوبة',evidence={'aligned_stair_arrival':bool(connected),'lounge_min_m2':a.annex_lounge_min_m2,'lounge_valid':valid}))
    if a.service_yard and model.get('service_yard'):
        q=model['service_yard'];conflicts=[c['id'] for f in model['floors'] for c in f['cells'] if intersects(q,c)]+[c['id'] for c in model.get('parking',[]) if intersects(q,c)]
        if not inside(rect(0,0,brief.plot_width,brief.plot_depth),q):conflicts.append('outside-plot')
        if not all(inside(q,e) for e in q.get('equipment',[])) or len(q.get('equipment',[]))!=2:conflicts.append('equipment-missing-or-outside')
        checks.append(dict(check_id='AUTO-service-placement',status='FAIL' if conflicts else 'PASS',label='ساحة خدمات منفصلة عن الغرف والمواقف والمدخل',evidence={'building_intersections':conflicts,'scope':'موقع وتجهيزات مقترحة؛ مواصفات الأجهزة والخلوص والصوت والصرف تحتاج تصميمًا متخصصًا'}))
    if a.balcony:
        balconies=[b for f in model['floors'] for b in f.get('balconies',[])]
        checks.append(dict(check_id='AUTO-balcony-access',status='PASS' if len(balconies)==1 and any(o.get('balcony_access') for f in model['floors'] for o in f['openings']) else 'FAIL',label='شرفة مرسومة وباب زجاجي منزلق ودرابزين مقترح',evidence={'balconies':balconies,'guard_and_structural_approval':False}))
    return checks
