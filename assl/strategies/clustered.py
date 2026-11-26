"""Strategy 2: a parametric hospitality/social/service cluster grammar.

Separate from the orthogonal search. Program-derived net dimensions, real
polygon footprints, bounded variants. Explicit supported topology; no omitted
requests and no promise to solve arbitrary programs.
"""
import math
from shapely.geometry import Polygon,box
from shapely.affinity import translate,rotate
from shapely.ops import unary_union
from backend.design.general_engine import expanded_program
from backend.design.general_models import VillaBrief
from assl.guest_groups import prepare_program
from .geometry import entity,shape,sized,chamfer
from .stairs import make_stair, require_clustered_floor_height

SCHEMA='assl-clustered-1'
PROFILES=(
 dict(key='reference',foyer=2.5,men_depth=0.,living_depth=0.,dining_depth=0.,stair_width=3.8),
 dict(key='recessed-service',foyer=2.3,men_depth=.4,living_depth=.2,dining_depth=.6,stair_width=3.6),
 dict(key='broad-social',foyer=2.7,men_depth=.8,living_depth=.6,dining_depth=.3,stair_width=4.),
)

def _program(brief):
    require_clustered_floor_height(brief)
    if brief.floors!=1:raise ValueError('UNSUPPORTED_CLUSTERED_FLOORS:ground-floor-only')
    if brief.spatial_requirements:raise ValueError('SPATIAL_REQUIREMENTS_NEED_RELATIONAL_STRATEGY')
    a=brief.automatic_features
    if any((a.lightwell,a.roof_annex,a.balcony,a.service_yard)) or brief.regulatory_geometry is not None or brief.notes.strip():
        raise ValueError('UNSUPPORTED_CLUSTERED_EXTRA_REQUIREMENTS:encode-or-review-first')
    if a.main_street_faces and brief.entrance_face not in a.main_street_faces:raise ValueError('UNSUPPORTED_CLUSTERED_STREET_FACE')
    rows=prepare_program(brief,expanded_program(brief,0));by={}
    for r in rows:by.setdefault(r['kind'],[]).append(r)
    if set(by)-{'majlis','living','dining','kitchen','storage','bathroom'} or any(len(by.get(k,[]))!=1 for k in ('living','dining','kitchen')) or len(by.get('storage',[]))>1:
        raise ValueError('UNSUPPORTED_CLUSTERED_PROGRAM')
    if not brief.guest_groups:raise ValueError('UNSUPPORTED_CLUSTERED_PROGRAM:explicit-guest-groups-required')
    entries={g.entry or g.id for g in brief.guest_groups}
    groups=[]
    for entry in entries:
        own=[r for r in rows if entry in r.get('guest_entries',[])]
        cs=sorted([r for r in own if r['kind']=='majlis'],key=lambda r:-r['min_area'])
        wc=[r for r in own if r['kind']=='bathroom']
        if not 1<=len(cs)<=2 or len(wc)>1 or any(len(r.get('guest_entries',[]))!=1 for r in own):
            raise ValueError('UNSUPPORTED_CLUSTERED_GROUP:shared-services-or-size')
        groups.append((entry,cs,wc))
    groups.sort(key=lambda g:(-len(g[1]),-sum(r['min_area'] for r in g[1]),g[0]))
    if not 1<=len(groups)<=2 or (len(groups)>1 and len(groups[1][1])!=1):raise ValueError('UNSUPPORTED_CLUSTERED_GROUP_COUNT')
    assigned={r['id'] for g in groups for r in g[1]+g[2]}
    if any(r['kind'] in ('majlis','bathroom') and r['id'] not in assigned for r in rows):raise ValueError('UNSUPPORTED_CLUSTERED_UNASSIGNED_SERVICE')
    return rows,by,groups

def _compose(brief,variant=0):
    rows,by,groups=_program(brief);t=brief.wall_thickness;rooms=[];nodes=[];links=[]
    main,second=groups[0],groups[1] if len(groups)>1 else None
    profile=PROFILES[variant]
    foyer_w=max(profile['foyer'],brief.corridor_width+.3);F=6.0
    def put(req,x,y,w,d,corners=(),cut=.65,**extra):
        r=entity(req['id'],req['kind'],chamfer(x,y,w,d,corners,cut),**{k:v for k,v in req.items() if k not in ('id','kind')},**extra);rooms.append(r);return r
    def node(rid,name,poly,entry=None):
        r=entity(rid,'corridor',poly,name=name,zone='shared',movement_node=True,guest_entry=entry);nodes.append(r);return r
    def link(a,b,**meta):links.append(dict(a=a['id'],b=b['id'],**meta))
    mainfoyer=node('main-foyer','بهو الضيافة',box(0,0,foyer_w,F),main[0])
    # Project the front council and turn the distributor sideways. Its rear
    # neighbour (dining) shares a real >=1.4m wall with the foyer. The layout
    # therefore does not grow the old long front-to-rear hall spine.
    council=main[1][0];w,d=sized(council,t,fixed_depth=council['min_side']+t+profile['men_depth'],corners=('sw',),cut=.8)
    projection=max(.6,d-(F-1.4));my=-projection;dining_y=my+d
    men=put(council,-w,my,w,d,('sw',),.8);link(mainfoyer,men)
    small_top=0
    if len(main[1])==2:
        req=main[1][1];w,d=sized(req,t,corners=('sw','se','ne'),cut=.55)
        small=put(req,foyer_w,0,w,d,('sw','se','ne'),.55);small_top=d;link(mainfoyer,small)
    if len(main[1])==1:
        service_side=max(2.5,main[2][0]['min_side']+t) if main[2] else 2.5
        small_top=F-service_side
    # Reserve a transverse distributor before choosing the primary WC width.
    sw=max(profile['stair_width'],foyer_w+1.3);cut_l=min(.75,6.-sw-1.2);core_right=sw+cut_l+1.2
    if cut_l<.3:raise ValueError('CANNOT_FIT_SHORT_DISTRIBUTOR')
    if core_right>6.:raise ValueError('CLUSTER_TRANSVERSE_NODE_TOO_LONG')
    if small_top>F-1.2:raise ValueError('UNSUPPORTED_CLUSTERED_MAIN_DISTRIBUTOR')
    if main[2]:
        req=main[2][0]
        if F-small_top<req['min_side']+t:raise ValueError('UNSUPPORTED_CLUSTERED_MAIN_SERVICE_HOST')
        w,d=sized(req,t,fixed_depth=F-small_top)
        wc=put(req,core_right,small_top,w,d)
    else:wc=None
    living_req=by['living'][0];lw,ld=sized(living_req,t,fixed_depth=living_req['min_side']+t+profile['living_depth'])
    ly=F;living=put(living_req,sw,ly,lw,ld)
    core_poly=box(foyer_w,small_top,core_right,F)
    core=node('social-node','بهو التوزيع',core_poly);link(mainfoyer,core)
    if wc:link(core,wc)
    link(core,living,controlled=True,roles=['family'])
    dining_req=by['dining'][0];dw,dd=sized(dining_req,t,fixed_depth=max(dining_req['min_side']+t,4.2)+profile['dining_depth'])
    dining=put(dining_req,-dw,dining_y,dw,dd,zone_override='shared');link(mainfoyer,dining)
    cy=dining_y+dd
    # The stair touches the side distributor; its mass is reserved before the
    # kitchen and remains separate from horizontal circulation measurements.
    stairs=make_stair(brief,0,F,sw,'u-shaped')
    rooms.append(stairs);link(core,stairs,controlled=True,roles=['family'])
    req=by['kitchen'][0];kw,kd=sized(req,t,fixed_depth=max(req['min_side']+t,4.2))
    kitchen=put(req,-kw,cy,kw,kd);link(dining,kitchen)
    if by.get('storage'):
        req=by['storage'][0]
        # Size this service independently instead of forcing the full kitchen
        # depth onto a narrow pantry (which produced an excessive aspect ratio).
        pw,pd=sized(req,t,fixed_depth=min(kd,max(req['min_side']+t,3.6)))
        pantry=put(req,-kw-pw,cy,pw,pd);link(kitchen,pantry)
    ly2=ly+ld;right=sw+lw
    women=None
    if second:
        req=second[1][0];ww,wd=sized(req,t,fixed_depth=max(req['min_side']+t,4.2),corners=('ne','nw'),cut=.5)
        women=put(req,sw,ly2,ww,wd,('ne','nw'),.5);right=max(right,sw+ww)
    vy=ly+2.4;vy2=ly2+1.5;vx2=right+2.5
    vestib=box(sw+lw-cut_l,vy,vx2,vy2)
    vestib=vestib.difference(shape(living))
    if women:vestib=vestib.difference(shape(women))
    family=node('family-foyer','مدخل الأسرة والنساء',vestib,second[0] if second else None)
    link(family,living,open_passage=not second,controlled=bool(second),roles=['family'])
    if women:link(family,women)
    if second and second[2]:
        req=second[2][0];ww,wd=sized(req,t,fixed_depth=max(req['min_side']+t,3.1))
        wc=put(req,right,vy2,ww,wd);link(family,wc)
    # A topology is fully constructed before any global connectivity decision.
    objects=rooms+nodes;mass=unary_union([shape(r) for r in objects])
    if mass.geom_type!='Polygon':raise ValueError('CLUSTER_COMPOSITION_DISCONNECTED')
    for i,a in enumerate(objects):
        if any(shape(a).intersection(shape(b)).area>1e-6 for b in objects[i+1:]):raise ValueError('CLUSTER_COMPOSITION_OVERLAP:'+a['id'])
    # Rotate the complete geometry to requested street orientation, including ARC metadata.
    angle={'south':0,'east':90,'north':180,'west':270}[brief.entrance_face]
    def turn(pt):
        theta=math.radians(angle);return [pt[0]*math.cos(theta)-pt[1]*math.sin(theta),pt[0]*math.sin(theta)+pt[1]*math.cos(theta)]
    rotated=[rotate(shape(r),angle,origin=(0,0)) for r in objects];bounds=unary_union(rotated).bounds
    dx,dy=-bounds[0],-bounds[1]
    if isinstance(brief,VillaBrief):
        W=brief.plot_width-brief.setbacks.west-brief.setbacks.east-t
        D=brief.plot_depth-brief.setbacks.south-brief.setbacks.north-t
        bw,bd=bounds[2]-bounds[0],bounds[3]-bounds[1]
        if bw>W+1e-6 or bd>D+1e-6:raise ValueError('CLUSTER_EXCEEDS_BUILDABLE_ENVELOPE')
        dx=(W-bw)/2-bounds[0];dy=(D-bd)/2-bounds[1]
    for r,poly in zip(objects,rotated):
        meta={k:v for k,v in r.items() if k not in ('id','kind','x','y','width','depth','polygon')}
        if 'stair' in meta:meta['stair']['rotation_deg']=angle
        for arc in meta.get('arcs',[]):
            px,py=turn(arc['center']);arc['center']=[px+dx,py+dy];arc['start_angle']+=angle;arc['end_angle']+=angle
        r.update(entity(r['id'],r['kind'],translate(poly,dx,dy),**meta))
    return dict(id=f'clustered-{variant+1}',composition_profile=profile['key'],schema=SCHEMA,strategy='clustered',rooms_by_floor=[rooms],halls_by_floor=[nodes],
                connection_requirements=links,entries=[dict(node='main-foyer',guest_entry=main[0]),dict(node='family-foyer',guest_entry=second[0] if second else None)],
                assumptions=['Ground-floor conceptual composition; no municipal approval.',
                             'Family/women share a vestibule, as in the reference; family lounge doors are controlled transitions.',
                             'Stair vertical position reserved; headroom/structure and upper floors require separate design.',
                             'Parking, landscape and pool are outside this ground-floor strategy; the default parking request is pending site design.'],
                brief_snapshot=brief.model_dump(mode='json'))

def generate_clustered(brief,*,max_results=1):
    _program(brief)
    proposals=[];failures=[]
    for variant in range(min(max_results,len(PROFILES))):
        try:proposals.append(_compose(brief,variant))
        except ValueError as exc:failures.append(dict(variant=variant,reason=str(exc)))
    return dict(strategy='clustered',proposals=proposals,failures=failures)


def solve_clustered(brief,*,max_results=1,progress=None,on_candidate=None,on_frame=None):
    if _uses_central_program(brief):
        from .central_clustered import solve_central
        return solve_central(brief,progress=progress,on_candidate=on_candidate,on_frame=on_frame)
    from .openings import construct_clustered
    from .furnishing import furnish_clustered
    from assl.openings_009 import validate
    from assl.layout_critic_010 import critique
    if progress:progress('composition',0,1,'تكوين البدائل من برنامج العميل')
    from .preview import emit_preview
    raw=generate_clustered(brief,max_results=max_results);accepted=[];rejected=[]
    if progress:progress('composition',1,1,'اكتمل تكوين الكتل')
    total=len(raw['proposals']) or 1
    for index,proposal in enumerate(raw['proposals']):
        emit_preview(on_frame,proposal['rooms_by_floor'][0]+proposal['halls_by_floor'][0],'composition','تكوين الكتل — البديل '+str(index+1))
        if progress:progress('checking',index,total,'إنشاء الأبواب والنوافذ')
        p=construct_clustered(brief,proposal)
        emit_preview(on_frame,p['rooms_by_floor'][0]+p['halls_by_floor'][0],'openings','إنشاء الأبواب والنوافذ',p['opening_model_009'])
        if progress:progress('checking',index+.25,total,'توزيع الأثاث والتحقق من استعمال الفراغات')
        p=furnish_clustered(brief,p)
        emit_preview(on_frame,p['rooms_by_floor'][0]+p['halls_by_floor'][0],'furnishing','تجربة توزيع الأثاث',p['opening_model_009'],p['furniture_by_floor'])
        emit_preview(on_frame,p['rooms_by_floor'][0]+p['halls_by_floor'][0],'checking','التحقق من الحركة والخصوصية',p['opening_model_009'],p['furniture_by_floor'])
        if progress:progress('checking',index+.5,total,'فحص الاتصال والخصوصية والأبواب 009')
        p['validation_009']=validate(brief,p)
        if progress:progress('checking',index+.75,total,'فحص العلاقات ومسافات الحركة 010')
        p['quality_010']=critique(brief,p)
        if progress:progress('checking',index+1,total,'اكتمل فحص المقترح')
        if p['validation_009']['status']=='PASS' and p['quality_010']['status']=='ACCEPTABLE_DESIGN_INDICATORS':
            accepted.append(p)
            if on_candidate:on_candidate(p)
        else:rejected.append(p)
    return dict(strategy='clustered',status='CONCEPTS_READY_FOR_REVIEW' if accepted else 'REJECT_AND_REPLAN',
                proposals=accepted,rejected=rejected,failures=raw['failures'],
                supported_scope='Ground floor; 1–2 explicit guest entry groups, primary 1–2 councils, secondary 1 council, at most one WC per group, one living/dining/kitchen and optional pantry; no shared services yet.')


def _uses_central_program(brief):
    guest_ids = {room_id for group in brief.guest_groups for room_id in group.rooms}
    return any(room.kind == 'dining' and room.id in guest_ids for room in brief.rooms)


def solve_client_clustered(brief, *, max_results=1, progress=None):
    """Return only alternatives with measured functional differences."""
    if brief.spatial_requirements:
        raise ValueError('SPATIAL_REQUIREMENTS_NEED_RELATIONAL_STRATEGY')
    if max_results == 2 and _uses_central_program(brief):
        from .central_clustered import solve_central_alternatives
        return solve_central_alternatives(brief, progress=progress)
    result = solve_clustered(brief, max_results=1, progress=progress)
    if max_results == 2:
        result['failures'].append({'reason': 'NO_VERIFIED_SECOND_FUNCTIONAL_SCHEME'})
        result['requested_results'] = max_results
    return result
