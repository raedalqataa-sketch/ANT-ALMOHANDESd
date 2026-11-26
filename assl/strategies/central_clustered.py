"""Architect-guided extension of the clustered grammar, not free room scattering.

Prototype families: ground suite at front / ground suite at side. All dimensions
come from the client's program. Saved legacy clustered models remain separate.
"""
import copy,math
from shapely.geometry import box
from shapely.affinity import rotate,translate
from shapely.ops import unary_union
from backend.design.general_engine import expanded_program
from backend.design.general_models import VillaBrief
from assl.guest_groups import prepare_program
from .geometry import entity,shape,sized,chamfer
from .stairs import make_stair, require_clustered_floor_height

SCHEMA='assl-clustered-2'
SCHEMES=('front-ground-suite','side-ground-suite')


def program(brief):
    require_clustered_floor_height(brief)
    if brief.floors!=1:raise ValueError('CENTRAL_CLUSTER_GROUND_FLOOR_ONLY')
    if brief.main_entry_width<1.5:raise ValueError('CENTRAL_MAIN_ENTRY_MIN_1_5M')
    a=brief.automatic_features
    if any((a.lightwell,a.roof_annex,a.balcony,a.service_yard)) or brief.notes.strip() or brief.regulatory_geometry:raise ValueError('CENTRAL_UNSUPPORTED_EXTRAS')
    rows=prepare_program(brief,expanded_program(brief,0));requests={r.id:r for r in brief.rooms}
    for row in rows:row['ensuite_for']=requests[row['request_id']].ensuite_for
    by={}
    for r in rows:by.setdefault(r['kind'],[]).append(r)
    if any(r.count!=1 for r in brief.rooms) or set(by)-{'majlis','dining','living','kitchen','storage','bedroom','master','bathroom'}:raise ValueError('CENTRAL_UNSUPPORTED_PROGRAM')
    if any(len(by.get(k,[]))!=1 for k in ('living','kitchen')) or len(by.get('storage',[]))>1:raise ValueError('CENTRAL_CORE_COUNTS')
    groups=[]
    for entry in sorted({g.entry or g.id for g in brief.guest_groups}):
        owned=[r for r in rows if entry in r.get('guest_entries',[])]
        councils=[r for r in owned if r['kind']=='majlis'];wc=[r for r in owned if r['kind']=='bathroom'];meals=[r for r in owned if r['kind']=='dining']
        if len(councils)!=1 or len(wc)>1 or len(meals)>1 or any(len(r['guest_entries'])!=1 for r in owned):raise ValueError('CENTRAL_GUEST_GROUP_SCOPE')
        groups.append((entry,councils,wc))
    groups.sort(key=lambda g:(-sum(r['kind']=='dining' and g[0] in r.get('guest_entries',[]) for r in rows),g[0]))
    if not 1<=len(groups)<=2:raise ValueError('CENTRAL_GUEST_GROUP_COUNTS')
    meals=[r for r in rows if r['kind']=='dining'];family=[r for r in meals if not r.get('guest_entries')];guest=[r for r in meals if r.get('guest_entries')]
    if len(family)!=1 or len(guest)!=1 or guest[0]['guest_entries']!=[groups[0][0]]:raise ValueError('CENTRAL_REQUIRES_DISTINCT_FAMILY_AND_GUEST_DINING')
    beds=by.get('bedroom',[])+by.get('master',[])
    private_baths=[r for r in by.get('bathroom',[]) if not r.get('guest_entries')]
    suites=[r for r in private_baths if r['ensuite_for']]
    shared=[r for r in private_baths if not r['ensuite_for']]
    if len(beds)>1 or len(shared)>1 or len(suites)!=len(beds) or (beds and suites[0]['ensuite_for']!=beds[0]['request_id']):
        raise ValueError('CENTRAL_GROUND_SUITE_SCOPE')
    return rows,by,groups


def entry_specs(groups):
    entries={'main-foyer':groups[0][0],'family-foyer':None}
    if len(groups)>1:entries['guest-foyer-secondary']=groups[1][0]
    return entries


def compose(brief,variant=0,*,grid=None):
    if variant not in (0,1):raise ValueError('UNKNOWN_CENTRAL_SCHEME')
    rows,by,groups=program(brief);t=brief.wall_thickness;rooms=[];halls=[];links=[]
    fw=max(2.2 if brief.main_entry_width>=2 else 2.5,brief.corridor_width+t);main=groups[0];other=groups[1] if len(groups)>1 else None
    family_dining=next(r for r in by['dining'] if not r.get('guest_entries'));guest_dining=next(r for r in by['dining'] if r.get('guest_entries'))
    def room(req,x,y,w,d,corners=(),cut=.5):
        obj=entity(req['id'],req['kind'],chamfer(x,y,w,d,corners,cut),**{k:v for k,v in req.items() if k not in ('id','kind')});rooms.append(obj);return obj
    def hall(rid,name,x,y,w,d,entry=None):
        obj=entity(rid,'corridor',box(x,y,x+w,y+d),name=name,zone='family' if entry is None else 'guest',guest_entry=entry,movement_node=True);halls.append(obj);return obj
    def connect(a,b,roles=None,controlled=False,preferred_fractions=None,open_passage=False):
        link=dict(a=a['id'],b=b['id'])
        if roles is not None:link.update(roles=roles,controlled=controlled)
        if preferred_fractions:link['preferred_fractions']=preferred_fractions
        if open_passage:link['open_passage']=True
        links.append(link)
    gw,gd=sized(guest_dining,t,fixed_depth=guest_dining['min_side']+t)
    # Seat count sets a real lower footprint, in addition to client minima.
    # The physical table/chairs need a 0.60m body strip beyond their envelope.
    from backend.design import furnishing as furniture
    recipe=next(furniture.dining_layouts(dict(x=0,y=0,width=20,depth=20,dining_seats=brief.dining_seats)))
    physical=[q for q in recipe if q.get('physical',True)]
    fx=max(q['x']+q['width'] for q in physical)-min(q['x'] for q in physical)
    fy=max(q['y']+q['depth'] for q in physical)-min(q['y'] for q in physical)
    gw=max(gw,fy+1.2+.1+t);gd=max(gd,fx+1.2+.1+t)
    living_req=by['living'][0];lw,ld=sized(living_req,t,fixed_depth=max(living_req['min_side']+t,gd+2))
    shared=next((r for r in by.get('bathroom',[]) if not r.get('guest_entries') and not r['ensuite_for']),None)
    if shared:ld+=.8
    if grid is not None:
        if ld>grid["living_depth_m"]+1e-6:
            raise ValueError("The fixed family bay cannot fit the requested lounge")
        ld=grid["living_depth_m"]
    living=room(living_req,0,0,lw,ld)
    council=main[1][0];mw,md=sized(council,t,fixed_depth=council['min_side']+t+(.6 if brief.main_entry_width>=2 else 0),corners=('sw',),cut=.65)
    formal=brief.main_entry_width>=2
    reception_width=max(3.6,gw,brief.main_entry_width+1.2+t) if formal else fw
    wc_depth=main[2][0]['min_side']+t if formal and main[2] else 0
    foyer=hall('main-foyer','المدخل الرئيسي · بهو استقبال الضيوف',-reception_width,-md,reception_width,md,main[0])
    men=room(council,-reception_width-mw,-md+wc_depth,mw,md,('sw',),.65);connect(foyer,men)
    guest_meal=room(guest_dining,-gw,0,gw,gd);connect(guest_meal,foyer,['family','guest:'+main[0]],preferred_fractions=(.85,.15,.5,0.,1.,.3,.7))
    if main[2]:
        req=main[2][0];w,d=sized(req,t,fixed_depth=wc_depth if formal else min(md,max(req['min_side']+t,3.1)))
        wc=room(req,-reception_width-w,-md,w,d) if formal else room(req,-w,-md-d,w,d)
        connect(foyer,wc)
    dw,dd=sized(family_dining,t,fixed_depth=max(family_dining['min_side']+t,4.2))
    dining=room(family_dining,-dw,gd,dw,dd);connect(dining,living,['family'],open_passage=True);connect(guest_meal,dining,['family'],True,preferred_fractions=(.85,.15,.5,0.,1.,.3,.7))
    req=by['kitchen'][0];kw,kd=sized(req,t,fixed_depth=max(req['min_side']+t,4.2));kitchen=room(req,-kw,gd+dd,kw,kd);connect(dining,kitchen,['family'],True)
    if by.get('storage'):
        req=by['storage'][0];w,d=sized(req,t,fixed_depth=min(kd,max(req['min_side']+t,3.6)));store=room(req,-kw-w,gd+dd,w,d);connect(kitchen,store,['family'])
    stair=make_stair(brief,0,ld,grid['stair_width_m'] if grid else 3.8,'u-shaped');rooms.append(stair);connect(living,stair,['family'],open_passage=True)
    family=hall('family-foyer','مدخل الأسرة المستقل',0,-2.5,fw,2.5);connect(family,living,['family'],open_passage=True)
    beds=by.get('bedroom',[])+by.get('master',[])
    if beds:
        req=beds[0];bw,bd=sized(req,t,fixed_depth=max(req['min_side']+t,4.2))
        vestibule_width=2.8;vestibule_depth=1.9
        bath_req=next(r for r in by['bathroom'] if r.get('ensuite_for'))
        w,d=sized(bath_req,t,fixed_depth=max(bath_req['min_side']+t,3.7))
        if variant==0:
            # North strip: vestibule on the left, bathroom on the right.
            # The bedroom uses the full width of the suite below both.
            entry_width=1.5
            bath_width=max(bw-entry_width,bath_req['min_side']+t)
            strip_depth=max(bath_req['min_side']+t,
                            bath_req['min_area']/(bath_width-t)+t,2.1)
            suite_width=entry_width+bath_width
            vestibule=hall('elder-suite-vestibule','موزع جناح كبار السن',
                           fw,-strip_depth,entry_width,strip_depth)
            bath=room(bath_req,fw+entry_width,-strip_depth,bath_width,strip_depth)
            bed=room(req,fw,-strip_depth-bd,suite_width,bd)
        else:
            vestibule=hall('elder-suite-vestibule','موزع جناح كبار السن',lw,0,vestibule_width,vestibule_depth)
            bed=room(req,lw+vestibule_width,0,bw,bd)
            bath=room(bath_req,lw,vestibule_depth,vestibule_width,max(d,w))
        connect(living,vestibule,['family'],True,preferred_fractions=(.5,.15,.85))
        connect(vestibule,bed,['family'],True,preferred_fractions=(.5,.15,.85))
        connect(vestibule,bath,['family'],True,preferred_fractions=(.5,.15,.85))
    if other:
        req=other[1][0];ww,wd=sized(req,t,fixed_depth=max(req['min_side']+t,4.2))
        wx,wy=(lw,0) if variant==0 else (fw,-wd)
        women=room(req,wx,wy,ww,wd);connect(living,women,['family'],True)
        hf=max(3.1,brief.corridor_width+t)
        secondary=hall('guest-foyer-secondary','مدخل ضيافة النساء المستقل',wx+ww,wy,fw,hf,other[0]);connect(secondary,women)
        if other[2]:
            req=other[2][0];w,d=sized(req,t,fixed_depth=max(req['min_side']+t,3.1))
            wc=room(req,wx+ww,wy+hf,w,d) if variant==0 else room(req,wx+ww,wy-d,w,d)
            connect(secondary,wc)
    if shared:
        # Extend the east return beside the lounge, clear of the guest wing.
        blockers=[shape(r) for r in rooms+halls if r is not living]
        for depth in (2.5,2.4,2.2,2.0,1.8,1.7):
            if depth < shared['min_side']+t-1e-6:continue
            minimum_width,_=sized(shared,t,fixed_depth=depth)
            width=grid["east_wall_offset_m"]-lw if grid else max(minimum_width,3.7)
            if width<minimum_width-1e-6:continue
            y=ld-depth
            if any(box(lw,y,lw+width,ld).intersection(g).area>1e-6 for g in blockers):continue
            connect(living,room(shared,lw,y,width,depth),["family"],True,preferred_fractions=(.85,.5,.15))
            break
        else:raise ValueError('CENTRAL_FAMILY_WC_NO_CLEAR_HOST')
    objects=rooms+halls;mass=unary_union([shape(r) for r in objects])
    if mass.geom_type!='Polygon' or mass.interiors:raise ValueError('CENTRAL_DISCONNECTED_OR_ENCLOSED_VOID')
    for i,a in enumerate(objects):
        if any(shape(a).intersection(shape(b)).area>1e-6 for b in objects[i+1:]):raise ValueError('CENTRAL_OVERLAP:'+a['id'])
    angle={'south':0,'east':90,'north':180,'west':270}[brief.entrance_face];polygons=[rotate(shape(r),angle,origin=(0,0)) for r in objects]
    x,y,xx,yy=unary_union(polygons).bounds
    dx,dy=-x,-y
    theta=math.radians(angle)
    if isinstance(brief,VillaBrief):
        W=brief.plot_width-brief.setbacks.west-brief.setbacks.east-t
        D=brief.plot_depth-brief.setbacks.north-brief.setbacks.south-t
        if xx-x>W+1e-6 or yy-y>D+1e-6:
            raise ValueError(
                f"CENTRAL_EXCEEDS_ENVELOPE: footprint {xx-x:.2f} x {yy-y:.2f} m, "
                f"available {W:.2f} x {D:.2f} m on wall axes"
            )
        dx=(W-(xx-x))/2-x;dy=(D-(yy-y))/2-y
        if grid is not None:
            dx,dy=grid["stair_origin"];dy-=ld
            if x+dx < -1e-6 or y+dy < -1e-6 or xx+dx>W+1e-6 or yy+dy>D+1e-6:
                raise ValueError("The fixed stair and grid place the ground plan outside the buildable envelope")
    for obj,poly in zip(objects,polygons):
        if obj.get('stair'):obj['stair']['rotation_deg']=angle
        for arc in obj.get('arcs',[]):
            a,b=arc['center'];arc['center']=[a*math.cos(theta)-b*math.sin(theta)+dx,a*math.sin(theta)+b*math.cos(theta)+dy];arc['start_angle']+=angle;arc['end_angle']+=angle
        moved=entity(obj['id'],obj['kind'],translate(poly,dx,dy));obj.update({k:moved[k] for k in ('polygon','x','y','width','depth')})
    return dict(schema=SCHEMA,strategy='clustered',functional_scheme=SCHEMES[variant],composition_profile=SCHEMES[variant],id=SCHEMES[variant],rooms_by_floor=[rooms],halls_by_floor=[halls],connection_requirements=links,entries=[dict(node=n,guest_entry=e,role='principal' if n=='main-foyer' else 'secondary') for n,e in entry_specs(groups).items()],brief_snapshot=brief.model_dump(mode='json'),assumptions=['Prototype for architect review; passes do not constitute architectural approval.','Guest and family daily circulation separated; dining serving connection controlled.','Structure, acoustic/visual privacy, stair headroom and statutory compliance remain pending.'])


def solve_central(brief,*,progress=None,on_candidate=None,on_frame=None,grid=None,variant=0):
    """Exactly one front-suite concept. No alternate-layout/retry loop."""
    from .preview import emit_preview
    from .openings import construct_clustered
    from .furnishing import furnish_clustered
    from assl.openings_009 import validate
    from assl.layout_critic_010 import critique
    if progress:progress('composition',0,1,'تكوين المجموعات حول الصالة العائلية')
    try:p=compose(brief,variant,grid=grid)
    except ValueError as e:return dict(strategy='clustered',generation_mode='central',requested_results=1,status='UNSUPPORTED_OR_UNRESOLVED',proposals=[],rejected=[],failures=[dict(reason=str(e))])
    emit_preview(on_frame,p['rooms_by_floor'][0]+p['halls_by_floor'][0],'composition','الصالة في القلب ومجموعات مترابطة')
    if progress:progress('composition',1,1,'اكتمل تكوين المقترح الوحيد')
    p=construct_clustered(brief,p)
    emit_preview(on_frame,p['rooms_by_floor'][0]+p['halls_by_floor'][0],'openings',f'المدخل الرئيسي {brief.main_entry_width:g} م والمداخل المستقلة',p['opening_model_009'])
    if progress:progress('checking',.25,1,'تأثيث المقترح الوحيد')
    p=furnish_clustered(brief,p)
    emit_preview(on_frame,p['rooms_by_floor'][0]+p['halls_by_floor'][0],'furnishing','اختبار الأثاث ومساحات استخدامه',p['opening_model_009'],p['furniture_by_floor'])
    if progress:progress('checking',.5,1,'التحقق من الأبواب والخصوصية 009')
    p['validation_009']=validate(brief,p)
    if progress:progress('checking',.75,1,'التحقق من العلاقات والحركة 010')
    p['quality_010']=critique(brief,p)
    from .guest_access import check_guest_wc_routes
    guest_access = check_guest_wc_routes(p)
    p["unified_checks"] = {"Z03": guest_access}
    if guest_access["status"] == "FAIL":
        p["validation_009"]["issues"].append("Z03_GUEST_WC_ROUTE")
        p["validation_009"]["status"] = "FAIL"
    accepted=p['validation_009']['status']=='PASS' and p['quality_010']['status']=='ACCEPTABLE_DESIGN_INDICATORS'
    if accepted and on_candidate:on_candidate(p)
    return dict(strategy='clustered',generation_mode='central',requested_results=1,status='CONCEPT_READY_FOR_ARCHITECT_REVIEW' if accepted else 'REJECT_AND_REPLAN',proposals=[p] if accepted else [],rejected=[] if accepted else [p],failures=[] if accepted else [dict(reason=(p['validation_009']['issues'] or [d['type'] for d in p['quality_010']['defects']])[0])])


def solve_central_alternatives(brief, *, progress=None):
    """Run the two supported functional arrangements against the same brief."""
    proposals, rejected, failures = [], [], []
    for variant, scheme in enumerate(SCHEMES):
        def report(phase, done, total, detail):
            if progress:
                stage = .4 + .6 * done / total if phase == 'checking' else .4 * done / total
                progress('alternatives', variant + stage, len(SCHEMES), detail)

        result = solve_central(brief, variant=variant, progress=report)
        proposals.extend(result['proposals'])
        rejected.extend(result['rejected'])
        failures.extend({**failure, 'scheme': scheme} for failure in result['failures'])

    if len(proposals) == 2:
        # The schemes can collapse to the same layout if neither optional
        # wing is requested. Compare zoning relative to the family lounge.
        def zones(proposal):
            rooms = proposal['rooms_by_floor'][0]
            lounge = next(room for room in rooms if room['kind'] == 'living')
            origin = shape(lounge).centroid
            result = {}
            for room in rooms:
                if room['kind'] not in ('bedroom', 'master', 'majlis'):
                    continue
                center = shape(room).centroid
                dx, dy = center.x - origin.x, center.y - origin.y
                result[room['id']] = (
                    ('east' if dx > 0 else 'west') if abs(dx) > abs(dy)
                    else ('north' if dy > 0 else 'south')
                )
            return result

        first, second = map(zones, proposals)
        differences = [
            {'space_id': key, 'first': first[key], 'second': second[key]}
            for key in first if first[key] != second[key]
        ]
        if differences:
            proposals[0]['functional_differences'] = [
                {'space_id': row['space_id'], 'direction': row['first']} for row in differences
            ]
            proposals[1]['functional_differences'] = [
                {'space_id': row['space_id'], 'direction': row['second']} for row in differences
            ]
        else:
            proposals.pop()
            failures.append({'scheme': SCHEMES[1], 'reason': 'NO_FUNCTIONAL_ZONING_DIFFERENCE'})

    return {
        'strategy': 'clustered', 'generation_mode': 'central',
        'requested_results': 2,
        'status': 'CONCEPTS_READY_FOR_REVIEW' if proposals else 'REJECT_AND_REPLAN',
        'proposals': proposals, 'rejected': rejected, 'failures': failures,
    }
