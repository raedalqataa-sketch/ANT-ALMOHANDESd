"""Experimental joint social-group packing; authoritative gates remain009/010.

Only requested social rooms and their ground-floor tail nodes are repartitioned.
No furnishings. Ranking is a proposal heuristic, never engineering acceptance.
"""
import copy
import itertools
import math
from collections import Counter
from shapely.geometry import Polygon
from shapely.ops import unary_union
from .free_layout_solver import rect,room_shapes,anchors,clear,area,overlap_area
from .openings_009 import shape,shared_edge,exposed_edges,validate,_opening_revision,centre
from .structural_replanner_011 import physical_hash,stair_valid
from .layout_critic_010 import critique
from .replan_010 import acceptable_change

SOCIAL=('living','dining','kitchen')


def enclosed_voids(objects):
    """Enclosed holes only. Open exterior pockets require an allocable envelope."""
    union=unary_union([shape(r) for r in objects])
    polys=[union] if union.geom_type=='Polygon' else list(getattr(union,'geoms',[]))
    holes=[Polygon(ring) for p in polys for ring in getattr(p,'interiors',[])]
    return dict(area_m2=sum(p.area for p in holes),holes=[list(p.exterior.coords) for p in holes],
                open_pockets='UNRESOLVED_NO_FIXED_ALLOCABLE_ENVELOPE')


def residual_diagnostic(objects):
    from quality_review.unallocated_geometry import measure_model
    cells=[dict(r,id=r.get('id',f'cell-{i}')) for i,r in enumerate(objects)]
    return measure_model(dict(floors=[dict(id='diagnostic-floor',cells=cells)]))['floors'][0]


def new_residual_area(before,after):
    def geometry(objects):
        return unary_union([Polygon(r['polygon_m']) for r in residual_diagnostic(objects)['unallocated_regions']])
    return geometry(after).difference(geometry(before).buffer(1e-6)).area


def node_candidates(hub,obstacles):
    # Four real sides, not a forced architectural L/U template. Each candidate
    # touches the retained hub and replaces its old outward tail, never the entry.
    depths={2.,2.5,3.,3.5,4.,4.5,5.,5.5}
    for obj in obstacles:
        for axis,extent in (('x','width'),('y','depth')):
            value=obj[axis]+obj[extent]+1.2-hub[axis]-hub[extent]
            if 1.5<=value<=7:depths.add(round(value,4))
    for depth in sorted(depths):
        for width in (1.5,2.5,3.5):
            for side in ('north','west','east','south'):
                if side=='north':x,y,w,d=hub['x']+(hub['width']-width)/2,hub['y']+hub['depth'],width,depth
                elif side=='south':x,y,w,d=hub['x']+(hub['width']-width)/2,hub['y']-depth,width,depth
                elif side=='east':x,y,w,d=hub['x']+hub['width'],hub['y']+(hub['depth']-width)/2,depth,width
                else:x,y,w,d=hub['x']-depth,hub['y']+(hub['depth']-width)/2,depth,width
                yield rect(x,y,w,d,kind='corridor',id='social-node-012'),dict(side=side,width=width,depth=depth)


def _rough_cost(rooms,halls,t):
    movement=unary_union([shape(h) for h in halls]).area
    centers={r['kind']:(r['x']+r['width']/2,r['y']+r['depth']/2) for r in rooms}
    relation=sum(math.dist(centers[a],centers[b]) for a,b in [('kitchen','dining'),('dining','living')] if a in centers and b in centers)
    excess=sum(max(0,(r['width']-t)*(r['depth']-t)-r['min_area']) for r in rooms)
    return movement*2+relation+excess*2


def group_anchors(hall,w,d,objects):
    """Portal-aware sliding along a wall, including obstacle endpoint events."""
    seen=set()
    for axis in ('x','y'):
        size=w if axis=='x' else d
        other='y' if axis=='x' else 'x'
        extent='width' if axis=='x' else 'depth'
        oextent='depth' if axis=='x' else 'width'
        starts={hall[axis],hall[axis]+hall[extent]-size,
                hall[axis]+(hall[extent]-size)/2,
                hall[axis]+hall[extent]-1.2,hall[axis]+1.2-size}
        for obj in objects:
            starts.update((obj[axis]-size,obj[axis]+obj[extent]))
        for start in sorted(starts):
            for fixed in (hall[other]-(d if axis=='x' else w),hall[other]+hall[oextent]):
                c=rect(start,fixed,w,d) if axis=='x' else rect(fixed,start,w,d)
                key=tuple(c[k] for k in ('x','y','width','depth'))
                if axis=='x':contact=max(0,min(hall['x']+hall['width'],c['x']+w)-max(hall['x'],c['x']))
                else:contact=max(0,min(hall['y']+hall['depth'],c['y']+d)-max(hall['y'],c['y']))
                if key not in seen and contact>=1.2-1e-6:
                    seen.add(key);yield c


def retained_hall_network(source,retained):
    """Keep actual retained-room hosts AND the transit linking them to the hub."""
    halls=source['halls_by_floor'][0]
    hub=next(i for i,h in enumerate(halls) if h.get('id')=='family-hub')
    keep={hub}|{i for i,h in enumerate(halls) if h.get('id')=='family-entry-spur'}
    retained_ids={r['id'] for r in retained if r.get('zone')!='guest' and not r.get('guest_distributor')}
    for door in source['opening_model_009'][0]['doors']:
        host,target=door['connects']
        if target in retained_ids and host.startswith('hall-0-'):
            keep.add(int(host.rsplit('-',1)[1]))
    graph={i:[j for j in range(len(halls)) if j!=i and (shared_edge(halls[i],halls[j]) or overlap_area(halls[i],halls[j])>1e-6)] for i in range(len(halls))}
    parent={hub:None};todo=[hub]
    for i in todo:
        for j in graph[i]:
            if j not in parent:parent[j]=i;todo.append(j)
    for target in tuple(keep):
        if target not in parent:raise ValueError('BASELINE_HALL_NETWORK_DISCONNECTED')
        while target is not None:
            keep.add(target);target=parent[target]
    return [copy.deepcopy(h) for i,h in enumerate(halls) if i in keep]


def proposals(brief,source,*,beam_width=8,node_limit=None):
    """Joint beam over permutations, shapes and node geometry; source immutable.

    Retained hub/entry preserve the upper-floor and guest routes. Every selected
    room is removed before placing the group; there is no stale-room collision.
    Node limit bounds feasible node configurations, not empty failed attempts.
    """
    rooms=source['rooms_by_floor'][0];halls=source['halls_by_floor'][0]
    social=[r for r in rooms if r.get('zone')!='guest' and r.get('request_id') and r['kind'] in SOCIAL]
    if len(social)!=3 or {r['kind'] for r in social}!=set(SOCIAL):return
    hub=next((h for h in halls if h.get('id')=='family-hub'),None)
    if hub is None:return
    retained=[r for r in rooms if r not in social]
    # Do not delete tail nodes serving a retained room.009 still rechecks all routes.
    keep=retained_hall_network(source,retained)
    W=brief.plot_width-brief.setbacks.west-brief.setbacks.east-brief.wall_thickness
    D=brief.plot_depth-brief.setbacks.north-brief.setbacks.south-brief.wall_thickness
    t=brief.wall_thickness;seen={physical_hash(source)};feasible=0
    for node,details in node_candidates(hub,retained):
        if not clear(node,retained,W,D):continue
        if not shared_edge(node,hub) or shared_edge(node,hub)['length']<1.2-1e-6:continue
        if node_limit is not None and feasible>=node_limit:return
        feasible+=1;walk=keep+[node]
        # Equal opportunity to kitchen-first, dining-first and living-first groups.
        for order in itertools.permutations(social):
            states=[([],0.)]
            for request in order:
                expansions=[]
                for placed,_ in states:
                    local=set()
                    for w,d,_ in room_shapes(request,t,grid=.05)[:6]:
                        for host in walk:
                            for candidate in group_anchors(host,w,d,retained+walk+placed):
                                key=tuple(candidate[k] for k in ('x','y','width','depth'))
                                if key in local:continue
                                local.add(key)
                                if not clear(candidate,retained+walk+placed,W,D):continue
                                r={**copy.deepcopy(request),**candidate}
                                new=placed+[r]
                                # Keep exterior intervals before doors/windows are built.
                                if request['kind']=='kitchen' and not any(e['length']>=1.1 for e in exposed_edges(r,retained+walk+new)):continue
                                expansions.append((new,_rough_cost(new,walk,t)))
                expansions.sort(key=lambda x:x[1]);states=expansions[:beam_width]
                if not states:break
            for placed,cost in states:
                if len(placed)!=3:continue
                q=copy.deepcopy(source);byid={r['id']:r for r in placed}
                q['rooms_by_floor'][0]=[byid.get(r['id'],copy.deepcopy(r)) for r in rooms]
                q['halls_by_floor'][0]=copy.deepcopy(walk)
                for stale in ('quality','topology_evidence','structural_signature','placement_trace'):
                    q.pop(stale,None)
                q['geometry_metadata_012']='Source quality/trace removed; use regenerated009 validation and010 critique'
                q['building_envelope_basis_012']='Buildable site limits, not measured occupied footprint'
                h=physical_hash(q)
                if h in seen:continue
                seen.add(h)
                yield q,dict(**details,operation='joint_social_repartition',order=[r['kind'] for r in order],proposal_cost=cost)


def opening_variants(proposal):
    """Bounded independent kitchen/dining door positions on existing real hosts.

    These are not standalone improvements; only a changed group geometry may
    reach acceptance. All variants need009 and the same actual-path critique.
    """
    floor=proposal['opening_model_009'][0]
    ids={r['id']:r for r in floor['rooms']+floor['halls']}
    selected=[]
    for kind in ('kitchen','dining'):
        room=next((r for r in floor['rooms'] if r['kind']==kind and r.get('zone')!='guest'),None)
        index=next((i for i,d in enumerate(floor['doors']) if room and d['connects'][1]==room['id']),None)
        if index is None:return
        selected.append(index)
    for fractions in itertools.product((0.,.25,.75,1.),repeat=2):
        q=copy.deepcopy(proposal);q.pop('validation_009',None)
        for i,fraction in zip(selected,fractions):
            door=q['opening_model_009'][0]['doors'][i]
            a,b=door['connects'];edge=shared_edge(ids[a],ids[b])
            door['center']=centre(edge,door['width'],fraction)
        yield q


def _eligible_metrics(before,after):
    # Cheap exclusion before the bounded opening refinement; both doors belong
    # to the reconfigured social group and cannot improve geometry-only metrics.
    return all(b[k]<=a[k]+1e-5 for a,b in zip(before['floors'],after['floors'])
               for k in ('union_m2','longest_run_m','room_excess_m2'))


def replan(brief,source,*,max_validations=32,beam_width=8,node_limit=None,max_opening_trials=64):
    if type(max_opening_trials) is not int or max_opening_trials<0 or type(max_validations) is not int or max_validations<0 or type(beam_width) is not int or beam_width<1 or (node_limit is not None and (type(node_limit) is not int or node_limit<0)):
        raise ValueError('Search budget must use nonnegative integers and a positive beam width')
    if validate(brief,source)['status']!='PASS':raise ValueError('BASELINE_MUST_PASS_009')
    original=physical_hash(source);best=copy.deepcopy(source);before=critique(brief,source);current=before
    history=[];stats=Counter();before_void=[rs+hs for rs,hs in zip(source['rooms_by_floor'],source['halls_by_floor'])]
    if max_validations:
        # Keep several configurations per node and permutation, so cheap ranking
        # cannot consume every slot with one almost-identical geometry.
        pool=list(proposals(brief,source,beam_width=beam_width,node_limit=node_limit))
        groups={}
        for q,op in pool:
            key=(op['side'],op['width'],op['depth'],tuple(op['order']))
            groups.setdefault(key,[]).append((q,op))
        streams=[iter(sorted(v,key=lambda x:x[1]['proposal_cost'])) for v in groups.values()]
        candidates=[]
        while streams and len(candidates)<max_validations:
            remaining=[]
            for stream in streams:
                item=next(stream,None)
                if item is not None:candidates.append(item);remaining.append(stream)
                if len(candidates)>=max_validations:break
            streams=remaining
        stats['geometric_proposals']=len(pool)
        for q,op in candidates:
            entry=dict(**op,candidate_hash=physical_hash(q),accepted=False,geometry={k:q[k] for k in ('rooms_by_floor','halls_by_floor')})
            trial=_opening_revision(brief,q);qa=validate(brief,trial);entry['validation']=qa;entry['opening_model']=trial['opening_model_009']
            if qa['status']!='PASS':entry['reason']='HARD_CONSTRAINT'
            elif not stair_valid(source,trial,True):entry['reason']='STAIR_CHANGED'
            elif any(new_residual_area(old,rs+hs)>1e-5 for rs,hs,old in zip(trial['rooms_by_floor'],trial['halls_by_floor'],before_void)):entry['reason']='NEW_RESIDUAL_VOID_OR_SLIT'
            else:
                after=critique(brief,trial);entry['critique']=after
                if acceptable_change(current,after):
                    best=trial;current=after;entry['accepted']=True;entry['reason']='MEASURED_NONREGRESSING_GROUP_GAIN'
                else:
                    entry['reason']='NO_GAIN_OR_REGRESSION';entry['opening_refinements']=[]
                    if _eligible_metrics(current,after) and stats['opening_variants_tested']<max_opening_trials:
                        for variant in opening_variants(trial):
                            if stats['opening_variants_tested']>=max_opening_trials:break
                            vqa=validate(brief,variant)
                            refinement=dict(doors=variant['opening_model_009'][0]['doors'],validation=vqa,accepted=False)
                            if vqa['status']=='PASS':
                                vc=critique(brief,variant);refinement['critique']=vc
                                if acceptable_change(current,vc):
                                    variant['validation_009']=vqa;best=variant;current=vc
                                    entry['accepted']=True;entry['reason']='MEASURED_NONREGRESSING_GROUP_GAIN';entry['critique']=vc
                                    refinement['accepted']=True;entry['opening_model']=variant['opening_model_009'];entry['validation']=vqa
                            entry['opening_refinements'].append(refinement)
                            stats['opening_variants_tested']+=1
                            if entry['accepted']:break
            stats[entry['reason']]+=1;history.append(entry)
    return dict(status='ACCEPT' if not current['defects'] else 'REJECT_AND_REPLAN_UNRESOLVED',best=best,before=before,after=current,history=history,
                search_budget=dict(max_validations=max_validations,max_opening_trials=max_opening_trials,beam_width=beam_width,node_limit=node_limit),statistics=dict(stats),accepted_changes=sum(e['accepted'] for e in history),original_hash=original,final_hash=physical_hash(best),
                original_preserved=physical_hash(source)==original,stair_locked=True,
                limitations=['No furnishings','Visual privacy, daylight/airflow adequacy and law UNRESOLVED','Open exterior pockets UNRESOLVED without fixed allocable envelope','Upper floor deliberately retained in first012 experiment'])
