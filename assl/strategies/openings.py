"""Hosted doors/windows on authoritative polygons; no drawing-only openings."""
import copy
from shapely.ops import unary_union
from assl.openings_009 import centre,opening_fits,swing,cut,exterior_route,window_clear
from .geometry import shape,net_shape,shared_edges,exposed_edges


def construct_clustered(brief,proposal):
    p=copy.deepcopy(proposal);t=brief.wall_thickness
    objects=p['rooms_by_floor'][0]+p['halls_by_floor'][0];ids={r['id']:r for r in objects};doors=[];errors=[]
    primary=p['entries'][0]['guest_entry'] if p['entries'] else None
    def choose(a,b,edges,external=False,roles=None,controlled=False,preferred_fractions=None):
        target=ids[b]
        coordinate_landing=external and b=='guest-foyer-secondary' and brief.entry_plinth_height_m>0
        best_landing=None
        for edge in sorted(edges,key=lambda e:-e['length']):
            width=brief.main_entry_width if external and b=='main-foyer' else 1.0 if external else .9
            if edge['length']<max(1.2,width+.3)-1e-6:continue
            for f in preferred_fractions or (.15,.85,.5,0.,1.,.3,.7):
                d=dict(id=f'door-{len(doors)+1}',kind='door',axis=edge['axis'],center=centre(edge,width,f),width=width,
                       connects=[a,b],receiving_room=b,roles=roles or ['family'],controlled=controlled)
                if external and b=='main-foyer' and brief.main_entry_width>=2:d['leaf_widths']=[width/2,width/2]
                if not net_shape(target,t).buffer(.003).covers(swing(d,target,t)):continue
                sector=swing(d,target,t)
                if any(cut(d,t/2).intersection(cut(q,t/2)).area>1e-6 or sector.intersection(swing(q,ids[q['receiving_room']],t)).area>1e-6 for q in doors):continue
                if external and exterior_route(brief,d,target,objects) is None:continue
                if external and brief.entry_plinth_height_m>0:
                    from .entrances import build_platforms,entrance_issues
                    trial=dict(p,opening_model_009=[dict(doors=doors+[d])])
                    trial['entrance_platforms']=build_platforms(brief,trial)
                    if entrance_issues(brief,trial):continue
                    if coordinate_landing:
                        landing=next(q for q in trial['entrance_platforms'] if q['door_id']==d['id'])
                        approaches=len(landing['approaches'])
                        if approaches<3:
                            if best_landing is None or approaches>best_landing[0]:
                                best_landing=(approaches,d)
                            continue
                doors.append(d);return d
        if best_landing is not None:
            doors.append(best_landing[1]);return best_landing[1]
        errors.append('NO_FEASIBLE_HOSTED_DOOR:'+a+':'+b);return None
    # Internal openings are located before exterior doors; the exterior path is
    # evaluated against the complete occupied mass, not a partial room state.
    for link in p['connection_requirements']:
        a,b=link['a'],link['b'];target=ids[b]
        entry_by_node={e['node']:e['guest_entry'] for e in p['entries']}
        guest_roles=['guest:'+g for g in target.get('guest_entries',[]) if entry_by_node.get(a)==g or (a=='social-node' and g==primary)]
        if target['kind']=='dining' or (target['id']=='social-node' and a=='main-foyer'):guest_roles=['guest:'+primary] if primary else []
        roles=link.get('roles',['family']+guest_roles)
        edges=shared_edges(ids[a],target)
        if link.get('open_passage'):
            edge=max(edges,key=lambda item:item['length'],default=None)
            if edge is None or edge['length']<1.2-1e-6:
                errors.append('NO_FEASIBLE_OPEN_PASSAGE:'+a+':'+b)
                continue
            width=edge['length']-.30
            doors.append(dict(id=f'passage-{len(doors)+1}',kind='passage',axis=edge['axis'],
                              center=centre(edge,width,.5),width=width,wall_span_m=edge['length'],
                              connects=[a,b],receiving_room=b,roles=['family'],open_passage=True))
        else:
            choose(a,b,edges,roles=roles,controlled=link.get('controlled',False),preferred_fractions=link.get('preferred_fractions'))
    for entry in p['entries']:
        r=ids[entry['node']];roles=['family']+(['guest:'+entry['guest_entry']] if entry['guest_entry'] else [])
        edges=exposed_edges(r,objects)
        formal=r['id']=='main-foyer' and brief.main_entry_width>=2
        if formal:
            axis='x' if brief.entrance_face in ('south','north') else 'y'
            fixed=r['y'] if brief.entrance_face=='south' else r['y']+r['depth'] if brief.entrance_face=='north' else r['x'] if brief.entrance_face=='west' else r['x']+r['width']
            edges=[e for e in edges if e['axis']==axis and abs(e['fixed']-fixed)<1e-6]
        # Start at the facade centre, then consider shifts that give the
        # landing more usable approaches without blocking an existing entry.
        preferred=(.5,.15,.85,0.,1.) if r['id']=='guest-foyer-secondary' else None
        d=choose('OUTSIDE',r['id'],edges,True,roles,preferred_fractions=(.5,) if formal else preferred)
        if d:d['id']='entry-'+r['id']
    windows=[]
    for r in p['rooms_by_floor'][0]:
        if not r.get('request_id') or r['kind']=='storage':continue
        found=None
        for edge in sorted(exposed_edges(r,objects),key=lambda e:-e['length']):
            preferred=min(2.4,edge['length']-.4) if r['kind']!='bathroom' else .8
            # Keep the old preferred glazing; also retain a genuine 0.80m
            # opening on short facades when the physical host permits it.
            for width in dict.fromkeys((preferred,.8)):
                if width<.8:continue
                for f in (.5,0.,1.,.25,.75):
                    w=dict(id=f'window-{len(windows)+1}',kind='window',room_id=r['id'],axis=edge['axis'],center=centre(edge,width,f),width=width,height=1.2,operable_fraction=.5)
                    if not opening_fits(w,edge):continue
                    if any(cut(w,.15).intersects(cut(d,.15)) for d in doors):continue
                    if window_clear(w,r,objects,t):found=w;break
                if found:break
            if found:break
        if found:windows.append(found)
        else:errors.append('NO_EXTERIOR_WINDOW:'+r['id'])
    p['opening_model_009']=[dict(floor=0,doors=doors,windows=windows,construction_errors=errors)]
    from .entrances import build_platforms
    p['entrance_platforms']=build_platforms(brief,p)
    return p
