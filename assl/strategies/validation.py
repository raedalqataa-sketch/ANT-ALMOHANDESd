"""Polygon-schema 009 checks; old rect-schema checks remain unchanged.

Same real 1.20m wall contact, .90m door, .15m jamb, .60m body and
.003m sweep numerical tolerance. Privacy is explicit role-based circulation:
required guest routes cannot traverse family rooms; controlled family doors
are disclosed design decisions, not a claim of acoustic/visual certification.
"""
import math
from collections import Counter
from shapely.geometry import box,Point,Polygon
from shapely.ops import unary_union
from backend.design.general_models import VillaBrief
from assl.openings_009 import opening_fits,swing,cut,inward,shortest_path,exterior_route,window_clear
from .geometry import shape,net_shape,shared_edges,exposed_edges
from .furnishing import group_valid


def _graph_path(doors,start,target,role,forbidden=()):
    graph={}
    for d in doors:
        a,b=d['connects']
        if a=='OUTSIDE' or role not in d.get('roles',[]) or a in forbidden or b in forbidden:continue
        graph.setdefault(a,[]).append((b,d));graph.setdefault(b,[]).append((a,d))
    todo=[(start,[],[start])];seen={start}
    while todo:
        node,path,nodes=todo.pop(0)
        if node==target:return path,nodes
        for other,door in graph.get(node,[]):
            if other not in seen:seen.add(other);todo.append((other,path+[door],nodes+[other]))
    return None


def _body_route(brief,p,ids,doors,start,target,role,origin=None,destination=None):
    private={rid for rid,r in ids.items() if r['kind'] in ('bedroom','master','bathroom','office','storage') and rid not in (start,target)}
    if p.get('schema')=='assl-clustered-2' and role=='family':
        target_room=ids.get(target,{})
        # Routine family trips cannot use guest halls or guest-owned activities.
        if not target_room.get('guest_entries'):
            private|={rid for rid,r in ids.items() if r.get('guest_entries') or rid in ('main-foyer','guest-foyer-secondary')}
            private-={start,target}
        request=next((r for r in brief.rooms if r.id==target_room.get('request_id')),None)
        if request is not None and request.ensuite_for:
            private-={rid for rid,r in ids.items() if r.get('request_id')==request.ensuite_for}
    result=_graph_path(doors,start,target,role,private)
    if result is None:return None
    path,nodes=result;t=brief.wall_thickness
    if not path:return None
    origin=origin or inward(path[0],ids[start],.65)
    destination=destination or inward(path[-1],ids[target],.65)
    region=unary_union([net_shape(ids[r],t) for r in nodes]+[cut(d,t) for d in path])
    items=[q for q in p.get('furniture_by_floor',[[]])[0] if q['room_id'] in nodes and q.get('physical',True)]
    if items:region=region.difference(unary_union([box(q['x'],q['y'],q['x']+q['width'],q['y']+q['depth']) for q in items]))
    return shortest_path(region,origin,destination)


def validate_clustered(brief,p):
    from .clustered import _program
    relational=p.get('schema')=='assl-relational-1'
    central=p.get('schema')=='assl-clustered-2'
    if central:
        from .central_clustered import program,entry_specs
        expected,_,groups=program(brief)
        byreq={req.id:[r['id'] for r in expected if r['request_id']==req.id] for req in brief.rooms}
        graph=dict(entries=entry_specs(groups),relations=[dict(sources=byreq[r.source],targets=byreq[r.target],relation=r.relation,max_distance_m=r.max_distance_m) for r in brief.spatial_requirements])
    elif relational:
        from .relational import program_view,compile_program
        expected,_,groups=program_view(brief);graph=compile_program(brief)
    else:expected,_,groups=_program(brief)
    issues=[];routes=[];window_evidence=[];t=brief.wall_thickness
    if brief.floors!=1:issues.append('UNSUPPORTED_RELATIONAL_VERTICAL_COMPOSITION')
    rooms=p['rooms_by_floor'][0];nodes=p['halls_by_floor'][0];objects=rooms+nodes;ids={r['id']:r for r in objects}
    if len(ids)!=len(objects):issues.append('DUPLICATE_ENTITY_ID')
    expected_entries=graph['entries'] if relational or central else {'main-foyer':groups[0][0],'family-foyer':groups[1][0] if len(groups)>1 else None}
    permitted={}
    for index,group in enumerate(groups):
        permitted[group[0]]={r['id'] for r in expected if group[0] in r.get('guest_entries',[])}|{n for n,e in expected_entries.items() if e==group[0]}
        if index==0 and not central:permitted[group[0]].add('social-node')
        if index==0 and not central:permitted[group[0]]|={r['id'] for r in expected if r['kind']=='dining'}
    expected_ids={r['id'] for r in expected};actual=Counter(r['id'] for r in rooms if r.get('request_id'))
    if Counter(expected_ids)!=actual:issues.append('PROGRAM_MISMATCH')
    envelope=None
    if isinstance(brief,VillaBrief):
        W=brief.plot_width-brief.setbacks.west-brief.setbacks.east-t
        D=brief.plot_depth-brief.setbacks.north-brief.setbacks.south-t
        envelope=box(0,0,W,D).buffer(1e-7)
    for r in objects:
        g=shape(r)
        bounds=g.bounds
        if max(abs(a-b) for a,b in zip(bounds,(r['x'],r['y'],r['x']+r['width'],r['y']+r['depth'])))>1e-6:issues.append('POLYGON_BBOX_MISMATCH:'+r['id'])
        if not g.is_valid or g.is_empty or g.interiors:issues.append('INVALID_POLYGON:'+r['id'])
        if envelope is not None and not envelope.covers(g):issues.append('OUTSIDE_BUILDABLE_ENVELOPE:'+r['id'])
    for req in expected:
        r=ids.get(req['id'])
        if r is None:continue
        if central and r.get('ensuite_for')!=req.get('ensuite_for'):issues.append('ENSUITE_IDENTITY_MISMATCH:'+r['id'])
        n=net_shape(r,t);x,y,xx,yy=n.bounds
        if r.get('request_id')!=req['request_id'] or r['kind']!=req['kind'] or r.get('guest_entries',[])!=req.get('guest_entries',[]) or r.get('min_area')!=req['min_area'] or r.get('min_side')!=req['min_side']:issues.append('REQUEST_IDENTITY_MISMATCH:'+r['id'])
        if n.area<req['min_area']-1e-6:issues.append('ROOM_NET_AREA:'+r['id'])
        if min(xx-x,yy-y)<req['min_side']-1e-6:issues.append('ROOM_MIN_SIDE:'+r['id'])
    for i,a in enumerate(objects):
        for b in objects[i+1:]:
            if shape(a).intersection(shape(b)).area>1e-6:issues.append('GEOMETRY_OVERLAP:'+a['id']+':'+b['id'])
    mass=unary_union([shape(r) for r in objects])
    if mass.geom_type!='Polygon':issues.append('DISCONNECTED_BUILDING_FOOTPRINT')
    if mass.geom_type=='Polygon' and mass.interiors:issues.append('UNPROGRAMMED_ENCLOSED_VOID')
    opened=p.get('opening_model_009',[{}])[0];doors=opened.get('doors',[]);valid=[]
    issues+=opened.get('construction_errors',[])
    open_pairs={frozenset((link['a'],link['b'])) for link in p['connection_requirements'] if link.get('open_passage')}
    for d in doors:
        if len(d.get('connects',[]))!=2:issues.append('BAD_DOOR_CONNECTION');continue
        a,b=d['connects'];r=ids.get(b)
        if r is None or d.get('receiving_room')!=b:issues.append('BAD_RECEIVING_ROOM:'+d['id']);continue
        edges=exposed_edges(r,objects) if a=='OUTSIDE' else shared_edges(ids[a],r) if a in ids else []
        if not any(e['length']>=1.2-1e-6 and opening_fits(d,e) and (d['center'][0 if e['axis']=='x' else 1]-d['width']/2>=e['lo']+.15-1e-6) and (d['center'][0 if e['axis']=='x' else 1]+d['width']/2<=e['hi']-.15+1e-6) for e in edges) or d['width']<.9-1e-6:
            issues.append('INVALID_DOOR_HOST:'+d['id']);continue
        passage=d.get('open_passage',False)
        if passage != (frozenset((a,b)) in open_pairs) or (passage and (
            d.get('roles')!=['family'] or not any(
                math.isclose(d.get('wall_span_m',0),e['length'],abs_tol=1e-6)
                and opening_fits(dict(d,width=d['wall_span_m']),e) for e in edges))):
            issues.append('INVALID_OPEN_PASSAGE:'+d['id']);continue
        try:
            swept=swing(d,r,t)
        except (ValueError,TypeError):
            issues.append('INVALID_DOOR_LEAVES:'+d['id']);continue
        if not passage and not net_shape(r,t).buffer(.003).covers(swept):issues.append('DOOR_SWEEP_OUTSIDE_NET_ROOM:'+d['id']);continue
        for role in d.get('roles',[]):
            if role=='family':continue
            if not role.startswith('guest:'):issues.append('UNKNOWN_ACCESS_ROLE:'+d['id']);continue
            entry=role.split(':',1)[1]
            for rid in (a,b):
                if rid=='OUTSIDE':continue
                if entry not in permitted or rid not in permitted[entry]:issues.append('GUEST_PRIVATE_TRANSIT:'+d['id'])
        if any(ids.get(rid,{}).get('kind')=='living' for rid in (a,b)) and not (passage or d.get('controlled')):issues.append('MISSING_CONTROLLED_FAMILY_TRANSITION:'+d['id'])
        valid.append(d)
    for i,a in enumerate(valid):
        for b in valid[i+1:]:
            if cut(a,t/2).intersection(cut(b,t/2)).area>1e-6 or swing(a,ids[a['receiving_room']],t).intersection(swing(b,ids[b['receiving_room']],t)).area>1e-6:
                issues.append('DOOR_OPENING_OR_SWEEP_COLLISION:'+a['id']+':'+b['id'])
    entry_specs=expected_entries
    if {e['node']:e['guest_entry'] for e in p['entries']}!=expected_entries:issues.append('ENTRY_PROGRAM_MISMATCH')
    for d in [d for d in valid if d['connects'][0]=='OUTSIDE']:
        rid=d['connects'][1]
        if rid not in entry_specs:issues.append('UNAUTHORIZED_EXTERIOR_ENTRY:'+d['id']);continue
        required_roles={'family'}|({'guest:'+expected_entries[rid]} if expected_entries[rid] else set())
        if set(d.get('roles',[]))!=required_roles:issues.append('EXTERIOR_ENTRY_ROLE_MISMATCH:'+d['id'])
        route=exterior_route(brief,d,ids[rid],objects)
        if route is None:issues.append('NO_OUTDOOR_APPROACH:'+d['id'])
        else:routes.append(dict(room_id=d['id']+'-EXTERIOR',**route))
    exterior={d['connects'][1]:d for d in valid if d['connects'][0]=='OUTSIDE'}
    if 'main-foyer' in exterior and exterior['main-foyer']['width']<brief.main_entry_width-1e-6:issues.append('MAIN_ENTRY_CLEAR_WIDTH')
    if central and brief.main_entry_width>=2 and 'main-foyer' in exterior:
        main=exterior['main-foyer'];leaves=main.get('leaf_widths',[])
        if len(leaves)!=2 or any(abs(w-brief.main_entry_width/2)>1e-6 for w in leaves):issues.append('MAIN_ENTRY_DOUBLE_LEAVES')
        hall=ids['main-foyer'];axis='x' if brief.entrance_face in ('south','north') else 'y'
        fixed=hall['y'] if brief.entrance_face=='south' else hall['y']+hall['depth'] if brief.entrance_face=='north' else hall['x'] if brief.entrance_face=='west' else hall['x']+hall['width']
        if main['axis']!=axis or abs(main['center'][1 if axis=='x' else 0]-fixed)>1e-6:issues.append('MAIN_ENTRY_NOT_STREET_FACING')
    from .entrances import entrance_issues
    issues.extend(entrance_issues(brief,p))
    for node in entry_specs:
        if node not in exterior:issues.append('NO_VALID_ENTRY:'+node)
    # Each guest service/council is reached from its own physical entrance,
    # using roles that exclude living, kitchen, stairs and other guest groups.
    for req in expected:
        obligations=[('family','family-foyer')]
        for entry in req.get('guest_entries',[]):
            start=next((node for node,key in expected_entries.items() if key==entry),None)
            obligations.append(('guest:'+entry,start))
        for role,start in obligations:
            d=exterior.get(start)
            route=_body_route(brief,p,ids,valid,start,req['id'],role,origin=inward(d,ids[start],.65)) if d else None
            if route is None:issues.append('NO_BODY_ROUTE:'+role+':'+req['id'])
            else:routes.append(dict(room_id=req['id'],role=role,entry_id=d['id'],**route))
    if 'stair-core' in ids and 'family-foyer' in exterior:
        entry=exterior['family-foyer']
        route=_body_route(brief,p,ids,valid,'family-foyer','stair-core','family',origin=inward(entry,ids['family-foyer'],.65))
        if route is None:issues.append('NO_BODY_ROUTE:family:stair-core')
        else:routes.append(dict(room_id='stair-core',role='family',entry_id=entry['id'],**route))
    for req in expected:
        r=ids.get(req['id'])
        if not r:continue
        if req['kind']!='storage':
            found=[]
            for w in opened.get('windows',[]):
                if w.get('room_id')!=r['id']:continue
                if w.get('height',0)<=0 or not 0<w.get('operable_fraction',0)<=1:continue
                if not any(opening_fits(w,e) for e in exposed_edges(r,objects)):continue
                if any(cut(w,.15).intersects(cut(d,.15)) for d in doors):continue
                if window_clear(w,r,objects,t):found.append(w['id'])
            if not found:issues.append('NO_VERIFIED_EXTERIOR_WINDOW:'+r['id'])
            window_evidence.append(dict(room_id=r['id'],windows=found))
        items=[q for q in p.get('furniture_by_floor',[[]])[0] if q['room_id']==r['id']]
        from .furnishing import fixture_issues
        issues.extend(fixture_issues(req,items,brief))
        if not items or not group_valid(p,r,items,t):issues.append('NO_USABLE_FURNISHING:'+r['id'])
    stair=ids.get('stair-core')
    if stair is None:issues.append('MISSING_STAIR_RESERVATION')
    else:
        st=stair.get('stair',{});risers=st.get('risers',0)
        if not isinstance(risers,int) or isinstance(risers,bool) or not 4<=risers<=64 or any(not isinstance(st.get(k),(int,float)) or not math.isfinite(st[k]) for k in ('floor_height_m','flight_width_m','landing_m')) or abs(st.get('floor_height_m',0)-brief.floor_height)>1e-6 or brief.floor_height/max(1,risers)>.18+1e-6 or st.get('flight_width_m',0)<1.1 or st.get('landing_m',0)<1.1:
            issues.append('INVALID_STAIR_RESERVATION')
        if st.get('layout')=='u-shaped':
            from .stairs import validate_u_stair
            if not validate_u_stair(stair,brief):issues.append('STAIR_U_GEOMETRY_MISMATCH')
        else:
            try:
                arc=stair['arcs'][0];cx,cy=arc['center'];rad=arc['radius'];a,b=arc['start_angle'],arc['end_angle'];n=len(stair['polygon'])-3
                if not all(math.isfinite(v) for v in (cx,cy,rad,a,b)) or rad<=0 or n<4 or abs(b-a-180)>1e-6:raise ValueError('arc')
                cap=[(cx+rad*math.cos(math.radians(a+(b-a)*i/n)),cy+rad*math.sin(math.radians(a+(b-a)*i/n))) for i in range(n+1)]
                reconstructed=Polygon(stair['polygon'][:2]+cap)
                sagitta=rad*(1-math.cos(math.pi/(2*n)))
                if shape(stair).symmetric_difference(reconstructed).area>1e-6 or arc.get('computational_segments')!=n or abs(arc.get('max_sagitta_m',0)-sagitta)>1e-8:raise ValueError('arc-polygon divergence')
                if abs(rad-t/2-st['inner_radius_m']-st['flight_width_m'])>1e-6:raise ValueError('flight width')
                radial=st['radial_treads']
                if not isinstance(radial,int) or isinstance(radial,bool) or not 1<=radial<=63:raise ValueError('radial treads')
                straight=risers-1-radial
                going=math.pi*(st['inner_radius_m']+st['flight_width_m']/2)/radial
                if straight<0 or straight%2 or not .28<=going<=.34 or st['straight_going_m']<.28:raise ValueError('tread geometry')
            except (KeyError,TypeError,ValueError,ZeroDivisionError,IndexError):issues.append('STAIR_ARC_OR_TREAD_GEOMETRY_MISMATCH')
    if relational or central:
        from .relational import geometric_relation_issues
        issues.extend(geometric_relation_issues(brief,p,compiled=graph))
        for relation in graph['relations']:
            if relation['relation']!='near':continue
            for source in relation['sources']:
                options=[_body_route(brief,p,ids,valid,source,target,'family') for target in relation['targets'] if source in ids and target in ids]
                distances=[route['length_m'] for route in options if route]
                if not distances or min(distances)>relation['max_distance_m']+1e-6:issues.append('CLIENT_NEAR:'+source)
    issues=list(dict.fromkeys(issues))
    return dict(status='FAIL' if issues else 'PASS',issues=issues,floors=[dict(floor=0,routes=routes,windows=window_evidence)],
                schema=p['schema'],body_width_m=.6,minimum_contact_m=1.2,door_width_design_m=.9,furniture_used=True,
                privacy_policy='Controlled family lounge doors; guest routes exclude private rooms; shared dining allowed.',
                site_status='SITE_ASSIGNED' if envelope is not None else 'SITE_NOT_ASSESSED',
                legal='UNRESOLVED',daylight_airflow='UNRESOLVED',visual_privacy='UNRESOLVED',stair_construction='REQUIRES_DETAILED_REVIEW')


def critique_clustered(brief,p,limits=None):
    from assl.layout_critic_010 import DEFAULTS,corridor_metrics
    limits={**DEFAULTS,**(limits or {})};qa=validate_clustered(brief,p);defects=[];t=brief.wall_thickness
    if qa['status']!='PASS':defects.append(dict(type='HARD_VALIDATION',evidence=qa['issues']))
    rooms=p['rooms_by_floor'][0];nodes=p['halls_by_floor'][0];ids={r['id']:r for r in rooms+nodes};doors=p['opening_model_009'][0]['doors']
    # Touching room polygons share wall centerlines. Join clear circulation
    # only at real openings between two circulation rooms.
    node_ids={node['id'] for node in nodes}
    circulation=unary_union([net_shape(node,t) for node in nodes]+[
        cut(door,t) for door in doors if set(door['connects'])<=node_ids])
    m=corridor_metrics(nodes,region=circulation);m['configuration_m2']=unary_union([shape(r) for r in rooms+nodes]).area;m['movement_ratio']=m['union_m2']/m['configuration_m2']
    if m['longest_run_m']>limits['long_run_m']:defects.append(dict(type='LONG_CORRIDOR',value=m['longest_run_m'],limit=limits['long_run_m']))
    m['relationships']=[]
    for kind,target,limit in [('kitchen','dining',limits['kitchen_dining_m']),('dining','living',12.),('bedroom','bathroom',limits['bed_bath_m']),('master','bathroom',limits['bed_bath_m'])]:
        for a in [r for r in rooms if r['kind']==kind]:
            choices=[]
            for b in [r for r in rooms if r['kind']==target and not (kind in ('bedroom','master') and r.get('guest_entries'))]:
                route=_body_route(brief,p,ids,doors,a['id'],b['id'],'family')
                if route:choices.append((route['length_m'],b['id']))
            distance,target_id=min(choices) if choices else (None,None)
            m['relationships'].append(dict(source=a['id'],target=target_id,distance_m=distance))
            if distance is None or distance>limit:defects.append(dict(type='FUNCTIONAL_DISTANCE',room=a['id'],distance_m=distance,limit_m=limit))
    m['proportions']=[]
    for r in rooms:
        if not r.get('request_id'):continue
        n=net_shape(r,t);x,y,xx,yy=n.bounds;aspect=max(xx-x,yy-y)/min(xx-x,yy-y);excess=n.area/r['min_area']
        m['proportions'].append(dict(id=r['id'],aspect=aspect,area_factor=excess))
        if aspect>limits['max_aspect'] or excess>limits['max_excess']:defects.append(dict(type='ROOM_PROPORTION_OR_EXCESS',room=r['id'],aspect=aspect,area_factor=excess))
    lengths=[r['length_m'] for r in qa['floors'][0]['routes'] if not r['room_id'].endswith('EXTERIOR')]
    m['mean_access_m']=sum(lengths)/len(lengths) if lengths else None;m['max_access_m']=max(lengths,default=None)
    return dict(status='REJECT_AND_REPLAN' if defects else 'ACCEPTABLE_DESIGN_INDICATORS',defects=defects,floors=[m],limits=limits,
                scope='Polygon-aware 010: dissolved circulation runs, physical furnished relationship paths, actual net proportions. Numeric thresholds unchanged.',legal='UNRESOLVED')
