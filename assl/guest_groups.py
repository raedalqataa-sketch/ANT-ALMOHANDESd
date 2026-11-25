"""Explicit hospitality memberships and bounded packing using existing primitives.

Entry keys represent physical vestibules. Sharing a service adds door obligations
for each entry, not a duplicate room or permission to transit through that service.
"""
import copy
from collections import Counter,deque


def diverse_states(ranked,limit=48):
    """Round robin across node depths, then positions, within the same beam.

    Cost orders alternatives within each configuration. Taking a cheap global
    prefix can consume the beam before a node serving later rooms is visited.
    """
    groups={};seen=set()
    for item in sorted(ranked,key=lambda row:row[0]):
        _,nodes,rooms=item
        configuration=tuple((v['x'],v['y'],v['width'],v['depth']) for v in nodes)
        key=(configuration,tuple((r['x'],r['y'],r['width'],r['depth']) for r in rooms))
        if key in seen:continue
        seen.add(key)
        depths=tuple(v['depth'] for v in nodes)
        groups.setdefault(depths,{}).setdefault(configuration,deque()).append(item)
    queues=deque(deque(rows.values()) for rows in groups.values())
    selected=[]
    while queues and len(selected)<limit:
        configurations=queues.popleft();rows=configurations.popleft()
        selected.append(rows.popleft())
        if rows:configurations.append(rows)
        if configurations:queues.append(configurations)
    return selected


def prepare_program(brief,program):
    rows=copy.deepcopy(program)
    if not brief.guest_groups:return rows
    membership={}
    for group in brief.guest_groups:
        for rid in group.rooms:
            membership.setdefault(rid,[])
            entry=group.entry or group.id
            if entry not in membership[rid]:membership[rid].append(entry)
    for r in rows:
        entries=membership.get(r['request_id'])
        if entries:
            r.update(zone='guest',guest_entries=entries)
        elif r.get('zone')=='guest':
            raise ValueError('UNASSIGNED_GUEST_REQUEST:'+r['request_id'])
    return rows


def memberships(requests):
    guests=[r for r in requests if r.get('zone')=='guest' and not r.get('guest_distributor')]
    councils=[r for r in guests if r['kind']=='majlis']
    result={}
    for r in guests:
        entries=r.get('guest_entries')
        if not entries:
            parent=r.get('guest_parent')
            if r['kind']=='majlis':parent=r['id']
            if not parent and len(councils)==1:parent=councils[0]['id']
            if not parent:raise ValueError('AMBIGUOUS_GUEST_MEMBERSHIP:'+r['id'])
            if parent not in {c['id'] for c in councils}:
                raise ValueError('UNKNOWN_GUEST_PARENT:'+r['id'])
            entries=[parent]
        result[r['id']]=list(dict.fromkeys(entries))
    return result


def entry_door_id(vestibule):
    return 'guest-entry-'+vestibule['guest_entry'] if vestibule.get('guest_entry') else 'guest-entry'


def room_vestibules(room,vestibules):
    if room.get('guest_entries'):
        return [v for v in vestibules if v.get('guest_entry') in room['guest_entries']]
    if room.get('guest_vestibule'):
        return [v for v in vestibules if v['id']==room['guest_vestibule']]
    return []


def reserve_services(requests,nodes,placed,obstacles,W,D,t,*,shapes=None):
    """Find one joint service footprint witness before pruning a room state.

    Uses existing shapes/anchors and final frontage requirements. The witness
    is temporary: it neither inserts rooms into the program nor changes their
    dimensions. None means this state cannot complete the remaining services
    using the existing finite candidate set.
    """
    from .free_layout_solver import room_shapes,anchors,clear
    from .concept_quality_v2 import edge_contact
    from .architectural_composer import facade_exposure
    if not requests:return []
    request=requests[0]
    hosts=[v for v in nodes if v['guest_entry'] in request['guest_entries']]
    if not hosts:return None
    choices=shapes[request['id']] if shapes is not None else room_shapes(request,t)[:6]
    for w,d,_ in choices:
        for candidate in anchors(hosts[0],w,d,0,minimum_contact=1.2):
            if not clear(candidate,list(obstacles)+nodes+placed,W,D):continue
            if any(edge_contact(candidate,v)<1.2-1e-6 for v in hosts):continue
            room={**candidate,**request}
            objects=list(obstacles)+nodes+placed+[room]
            if any(facade_exposure(v,objects)<1.3-1e-6 for v in nodes):continue
            if any(r['kind']=='bathroom' and facade_exposure(r,objects)<.9-1e-6 for r in placed+[room]):continue
            tail=reserve_services(requests[1:],nodes,placed+[room],obstacles,W,D,t,shapes=shapes)
            if tail is not None:return [room]+tail
    return None


def pack_groups(requests,hub,W,D,t,obstacles=(),*,diagnostics=None,placement_check=None):
    """Bounded beam, same room shapes/clearance/contact primitives as ASSL.

    Search several exterior nodes, then attach every requested room to all
    its assigned nodes. A failed placement returns evidence; nothing is dropped.
    """
    from .free_layout_solver import rect,room_shapes,anchors,clear,area,inside,overlap_area
    from .concept_quality_v2 import edge_contact
    from .architectural_composer import facade_exposure
    trace=diagnostics if diagnostics is not None else {}
    trace.update(beam_limit=48,node_stages=[],room_stages=[],
                 primary_contact_filter='anchors enforces >=1.2m before enumeration; contact counter below covers additional hosts',
                 pruning_counts_include_duplicates=True)

    def result(rooms,error):
        trace['outcome']=error or 'PLACED_GUEST_PROGRAM'
        return rooms,error
    try:membership=memberships(requests)
    except ValueError as exc:return result(None,str(exc))
    guests=[copy.deepcopy(r) for r in requests if r['id'] in membership]
    entries=list(dict.fromkeys(e for es in membership.values() for e in es))
    if not guests:return result([],None)
    fixed=list(obstacles) or [hub]
    shapes={r['id']:room_shapes(r,t)[:6] for r in guests}
    if any(not shapes[r['id']] for r in guests):return result(None,'GUEST_ROOM_HAS_NO_VALID_DIMENSION')

    def shared_service_fits(request,nodes):
        """Necessary look-ahead before discarding a shared service's hosts.

        Adding rooms cannot make an impossible shared boundary available.
        Use the same shapes/contacts/facades as actual placement, not area sums.
        """
        hosts=[v for v in nodes if v['guest_entry'] in membership[request['id']]]
        for w,d,_ in shapes[request['id']]:
            for candidate in anchors(hosts[0],w,d,0,minimum_contact=1.2):
                if not clear(candidate,fixed+nodes,W,D):continue
                if any(edge_contact(candidate,v)<1.2-1e-6 for v in hosts):continue
                objects=fixed+nodes+[candidate]
                if any(facade_exposure(v,objects)<1.3-1e-6 for v in nodes):continue
                if request['kind']=='bathroom' and facade_exposure(candidate,objects)<.9-1e-6:continue
                return True
        return False
    # Keep node-depth alternatives alive before room packing, rather than
    # greedily reserving a single long hospitality corridor.
    states=[[]]
    for entry in entries:
        rs=[r for r in guests if entry in membership[r['id']]]
        maxw=max(w for r in rs for w,d,_ in shapes[r['id']])
        xs={0.,max(0,W-2.25),maxw,hub['x']-2.25,max(0,W-maxw-2.25)}
        options=[]
        for depth in (2.5,3.5,5.,7.):
            for x in sorted(xs):
                for y in (0.,hub['y'],D-depth):
                    v=rect(x,y,2.25,depth,id='guest-vestibule-'+entry,
                           kind='corridor',zone='guest',guest_distributor=True,
                           guest_entry=entry,name='موزع ضيافة مستقل',guest_entrance_potential=True)
                    if clear(v,fixed,W,D):options.append(v)
        grown=[s+[v] for s in states for v in options if clear(v,s,W,D)]
        # Preserve feasible sharing from the preceding round: diverse node
        # depths alone must not replace every pair with disjoint service hosts.
        shared=[r for r in guests if len(membership[r['id']])>1 and
                set(membership[r['id']])<=set(v['guest_entry'] for v in grown[0])] if grown else []
        blocked=0
        if shared:
            filtered=[]
            for vs in grown:
                if all(shared_service_fits(r,vs) for r in shared):filtered.append(vs)
                else:blocked+=1
            grown=filtered
        # Preserve spatial/depth diversity while bounding all subsequent work.
        ranked=[(sum(area(v)+.1*abs(v['x']-hub['x']) for v in vs),vs,[]) for vs in grown]
        states=[vs for _,vs,_ in diverse_states(ranked)]
        trace['node_stages'].append(dict(entry=entry,feasible=len(grown),retained=len(states),
                                        future_shared_service_blocked=blocked,
                                        search_pruned=len(grown)-len(states),
                                        retained_depths=dict(Counter(str(tuple(v['depth'] for v in vs)) for vs in states))))
        if not states:return result(None,'GUEST_ENTRY_NODES_DO_NOT_FIT:'+entry)
    states=[(vs,[]) for vs in states]
    # Shared services must satisfy every host simultaneously, before a
    # council can consume the only common boundary.
    guests.sort(key=lambda r:(-len(membership[r['id']]),-r['min_area'],r['id']))
    for position,request in enumerate(guests):
        grown=[];counts=Counter(dict.fromkeys(('considered','outside_envelope','overlap',
                'weak_distributor_contact','entry_facade_blocked','room_facade_missing','feasible'),0));blockers=Counter()
        stage=dict(room_id=request['id'],incoming_states=len(states))
        trace['room_stages'].append(stage)
        for vs,placed in states:
            hosts=[v for v in vs if v['guest_entry'] in membership[request['id']]]
            for w,d,penalty in shapes[request['id']]:
                for candidate in anchors(hosts[0],w,d,0,minimum_contact=1.2):
                    counts['considered']+=1
                    if not inside(candidate,W,D):counts['outside_envelope']+=1;continue
                    hits=[q for q in fixed+vs+placed if overlap_area(candidate,q)>1e-6]
                    if hits:
                        counts['overlap']+=1;blockers.update(q.get('id','UNNAMED_OBSTACLE') for q in hits);continue
                    if any(edge_contact(candidate,v)<1.2-1e-6 for v in hosts):
                        counts['weak_distributor_contact']+=1;continue
                    r={**candidate,**request,'guest_entries':membership[request['id']],
                       'guest_vestibules':[v['id'] for v in hosts]}
                    # Reserve a real outdoor entrance while growing the pod;
                    # do not let a cheap final room seal every vestibule side.
                    if any(facade_exposure(v,fixed+vs+placed+[r])<1.3-1e-6 for v in vs):
                        counts['entry_facade_blocked']+=1;continue
                    if r['kind']=='bathroom' and facade_exposure(r,fixed+vs+placed+[r])<.9-1e-6:
                        counts['room_facade_missing']+=1;continue
                    rooms=placed+[r]
                    cost=sum(area(v) for v in vs)+sum(area(q) for q in rooms)+penalty
                    grown.append((cost,vs,rooms))
        counts['feasible']=len(grown)
        stage.update(counts=dict(counts),overlap_blockers=dict(blockers.most_common(5)))
        if position==len(guests)-1 and placement_check is not None and grown:
            attached=[item for item in grown if placement_check(item[2]+item[1])]
            stage['composition_rejected']=len(grown)-len(attached)
            stage['composition_feasible']=len(attached)
            if not attached:
                stage.update(retained=0,search_pruned=len(grown))
                return result(None,'NO_ATTACHED_ACCESSIBLE_GUEST_CONFIGURATION')
            grown=attached
        pending=[dict(r,guest_entries=membership[r['id']]) for r in guests[position+1:]
                 if r['kind']=='bathroom']
        if pending and grown:
            reservable=[item for item in grown if reserve_services(
                pending,item[1],item[2],fixed,W,D,t,shapes=shapes) is not None]
            stage['service_reservation_rejected']=len(grown)-len(reservable)
            stage['service_reservation_feasible']=len(reservable)
            if not reservable:
                stage.update(retained=0,search_pruned=len(grown))
                return result(None,'NO_REMAINING_GUEST_SERVICE_SPACE_AFTER:'+request['id'])
            grown=reservable
        if not grown:
            stage.update(retained=0,search_pruned=0,
                         incoming_node_depths=dict(Counter(str(tuple(v['depth'] for v in vs)) for vs,placed in states)),
                         example_states=[dict(nodes=vs,rooms=placed) for vs,placed in states[:2]])
            return result(None,'CANNOT_PLACE_GUEST_ROOM:'+request['id'])
        states=[(vs,rooms) for _,vs,rooms in diverse_states(grown)]
        stage.update(retained=len(states),search_pruned=counts['feasible']-len(states),
                     retained_node_configurations=len({tuple((v['x'],v['y'],v['depth']) for v in vs) for vs,rs in states}),
                     retained_node_depths=dict(Counter(str(tuple(v['depth'] for v in vs)) for vs,rs in states)))
    for vs,rooms in states:
        objects=fixed+vs+rooms
        if any(facade_exposure(v,objects)<1.3-1e-6 for v in vs):continue
        if any(r['kind']=='bathroom' and facade_exposure(r,objects)<.9-1e-6 for r in rooms):continue
        return result(rooms+vs,None)
    return result(None,'NO_INDEPENDENT_GUEST_ENTRY_FACADE')
