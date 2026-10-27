"""Independent measured trade-offs, not a new statutory acceptance system."""
import math
from collections import Counter
from shapely.geometry import Polygon, LineString, mapping
from shapely.ops import unary_union
from .topology import rect, signature
from quality_review.space_efficiency import measure_candidate
from quality_review.unallocated_geometry import measure_model


def _parts(geometry):
    if geometry.is_empty:return []
    if geometry.geom_type=='Polygon':return [geometry]
    return [p for g in getattr(geometry,'geoms',[]) for p in _parts(g)]


def _polygons(geometry):
    return [mapping(p) for p in _parts(geometry)]


def entry_routes(model,floor,zone):
    """Entry-to-destination paths; other private rooms cannot be shortcuts."""
    from ..walkability import floor_access
    targets=[r for r in floor['rooms'] if r['kind']!='reserve' and (r.get('zone')=='guest')==(zone=='guest')]
    transit={r['id'] for r in targets if r['kind']=='corridor' or
             (zone=='family' and r['kind'] not in ('bedroom','master','bathroom','majlis'))}
    shared=floor_access(model,floor,step=.20,body_width=.60,allowed_room_ids=transit) if transit else {'routes':{}}
    paths={};missing=[]
    for target in targets:
        access=shared if target['id'] in transit else floor_access(model,floor,step=.20,body_width=.60,allowed_room_ids=transit|{target['id']})
        points=access['routes'].get(target['id'])
        if points:paths[target['id']]=points
        else:missing.append(target['id'])
    return dict(lengths_m={key:round(sum(math.dist(a,b) for a,b in zip(points,points[1:])),5) for key,points in paths.items()},
                unreachable=missing,paths_m=paths,scope='endpoint-specific paths; other private rooms excluded from transit')


def inspect(model):
    legacy=measure_candidate(model);gaps=measure_model(model)
    v4=model.get('functional_program_v4',{});movement=v4.get('movement',{})
    floors=[];aspects=[];missing_windows=[];window_count=0;requested_count=0;guest_lengths=[];family_lengths=[]
    for floor,net in zip(model['floors'],legacy['floors']):
        corridor=unary_union([rect(c) for c in floor['cells'] if c['kind']=='corridor'])
        useful=unary_union([rect(r) for r in floor['rooms'] if r.get('request_id')])
        paths=[r for r in movement.get('routes',[]) if r.get('floor')==floor['id'] and r.get('status')=='MEASURED']
        buffers=[LineString(r['points']).buffer(.30,cap_style=2,join_style=2) for r in paths if len(r.get('points',[]))>=2]
        internal=unary_union(buffers).intersection(useful).difference(corridor) if buffers else Polygon()
        for r in floor['rooms']:
            if not r.get('request_id'):continue
            requested_count+=1
            windows=[o for o in floor['openings'] if o['kind']=='window' and r['id'] in o.get('connects',[]) and any(w['id']==o.get('wall_id') and w.get('exterior') for w in floor.get('walls',[]))]
            if windows:window_count+=1
            else:missing_windows.append(r['id'])
        for room in net['rooms']:
            # Comparative flag at twice the short side, never a legal maximum or gate.
            aspects.append({**room,'floor':floor['id'],'status':'REVIEW' if room['aspect_ratio']>2 else 'MEASURED',
                           'basis':'shape screening only; furniture and program determine usability'})
        floor_routes={'guest':{},'family':{}}
        # Existing raster routing sees actual doors and furniture; do not substitute
        # Euclidean centre distances when the route is absent.
        if floor.get('walls') and model.get('stairs') is not None:
            for name in floor_routes:
                access=entry_routes(model,floor,name)
                floor_routes[name]=access
                (guest_lengths if name=='guest' else family_lengths).extend(access['lengths_m'].values())
        floors.append(dict(floor_id=floor['id'],gross_floor_area_m2=round(model.get('metrics',{}).get('floor_built_by_id',{}).get(floor['id'],unary_union([rect(c) for c in floor['cells']]).area),5),
            gross_cell_union_m2=round(unary_union([rect(c) for c in floor['cells']]).area,5),
            net_usable_room_area_m2=round(useful.area,5),circulation_union_m2=round(corridor.area,5),
            net_corridor_area_m2=net['corridor_area_m2'],net_corridor_ratio=net['corridor_share_of_usable'],
            circulation_polygons=_polygons(corridor),internal_required_path_union_m2=round(internal.area,5),
            internal_required_path_polygons=_polygons(internal),movement_with_measured_internal_paths_m2=round(corridor.union(internal).area,5),
            routes=floor_routes,legacy=net))
    program=model['brief']['rooms'];counts=Counter(r.get('request_id') for f in model['floors'] for r in f['rooms'] if r.get('request_id'))
    missing=[dict(request=r['id'],expected=r['count'],actual=counts[r['id']]) for r in program if counts[r['id']]!=r['count']]
    regions=[dict(floor=f['floor_id'],**r) for f in gaps['floors'] for r in f['unallocated_regions']]
    lengths=[r['route_m'] for r in movement.get('routes',[]) if r.get('route_m') is not None]
    failures=[c['check_id'] for c in model.get('checks',[]) if c['status']=='FAIL']
    return dict(version='architectural-measurements-004',floors=floors,
        gross_floor_area_m2=round(sum(f['gross_floor_area_m2'] for f in floors),5),
        net_usable_room_area_m2=round(sum(f['net_usable_room_area_m2'] for f in floors),5),
        circulation_union_m2_total=round(sum(f['circulation_union_m2'] for f in floors),5),
        movement_with_measured_internal_paths_m2_total=round(sum(f['movement_with_measured_internal_paths_m2'] for f in floors),5),
        internal_required_path_union_m2_total=round(sum(f['internal_required_path_union_m2'] for f in floors),5),
        net_corridor_area_m2=round(sum(f['net_corridor_area_m2'] for f in floors),5),
        net_corridor_ratio=(sum(f['net_corridor_area_m2'] for f in floors)/sum(f['legacy']['net_usable_area_m2'] for f in floors)) if sum(f['legacy']['net_usable_area_m2'] for f in floors) else None,
        unassigned_sliver_area_m2=round(sum(r['gross_area_m2'] for r in regions if r['type']=='narrow_slit'),5),
        unassigned_area_m2=round(sum(f['unallocated_gross_area_m2'] for f in gaps['floors']),5),
        dead_space_m2=None,dead_space_status='REVIEW: geometry gaps measured; furnished unused floor is not automatically dead space',
        dead_space_polygon_evidence=regions,declared_reserve_m2=round(sum(f['declared_reserve_area_m2'] for f in gaps['floors']),5),
        longest_required_travel_path_m=max(lengths,default=None),guest_route_length_m=max(guest_lengths,default=None),
        family_route_length_m=max(family_lengths,default=None),room_aspect_ratios=aspects,
        furniture_clearance_failures=v4.get('furniture_issues'),
        natural_light_ventilation_coverage=dict(rooms_with_modeled_window=window_count,required_rooms=requested_count,
            coverage_ratio=window_count/requested_count if requested_count else None,rooms_without_modeled_window=missing_windows,
            adequacy='REVIEW',scope='modeled exterior-window presence only, not daylight factor, airflow or legal sufficiency'),
        privacy_conflicts=v4.get('visual_privacy',{}),program_completeness=dict(status='FAIL' if missing else 'PASS',errors=missing),
        unreachable_required_routes=movement.get('unreachable'),critical_failures=failures,structural_signature=signature(model),
        scope=dict(circulation='gross corridor polygon union incl guest distributor, partition invariant',
            internal_paths='0.60m buffer of V4 sampled required paths, clipped to requested net rooms; partial, not all movement',
            gaps='existing 0.5m morphological diagnostic, intentional voids excluded; wider recesses REVIEW',
            legal_approval=False,legacy_net_metrics_preserved=True))
