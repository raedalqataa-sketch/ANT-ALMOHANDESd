"""Bounded room-first architectural constraint packing, without fixed wing lanes.

This is an independently testable *concept* solver, not a CAD/permit engine.
It places requested room rectangles against a connected family hall graph and
reserves the same stair across storeys. Guest suite has its own vestibule, no
family-through route. All unverified openings are explicitly UNRESOLVED.

No furnishings, legal compliance claims, DXF, PDFs or production hooks.
"""
from __future__ import annotations

import copy
import math
from dataclasses import dataclass

from .architectural_composer import assess_layout, ASPECTS, spatial_signature
from .concept_quality_v2 import edge_contact, union_area, gap

EPS=1e-6
GRID=.25


def up(value):
    return math.ceil((value-EPS)/GRID)*GRID


def snap(value):
    return round(value/GRID)*GRID


def rect(x,y,w,d,**kw):
    return dict(x=round(x,4),y=round(y,4),width=round(w,4),
                depth=round(d,4),**kw)


def area(r):
    return r["width"]*r["depth"]


def overlap_area(a,b):
    return max(0,min(a["x"]+a["width"],b["x"]+b["width"])-max(a["x"],b["x"])) * max(
        0,min(a["y"]+a["depth"],b["y"]+b["depth"])-max(a["y"],b["y"]))


def inside(r,W,D):
    return r["x"]>=-EPS and r["y"]>=-EPS and (
        r["x"]+r["width"]<=W+EPS and r["y"]+r["depth"]<=D+EPS)


def clear(r,objects,W,D):
    return inside(r,W,D) and all(overlap_area(r,v)<=EPS for v in objects)


def room_shapes(request,t):
    """Multiple orthogonal proportions from min net area; never reduce it."""
    requested=request["min_area"]
    side=request["min_side"]
    preferred,hard=ASPECTS.get(request["kind"],(2.,2.7))
    shapes={}
    for factor in (.76,.88,1.,1.10,1.23,1.40):
        netw=up(max(side,math.sqrt(requested)*factor))
        netd=up(max(side,requested/netw))
        ratio=max(netw,netd)/min(netw,netd)
        if ratio>hard+EPS or netw*netd>requested*1.4+EPS:
            continue
        for w,d in ((netw+t,netd+t),(netd+t,netw+t)):
            w,d=up(w),up(d)
            if (w-t)*(d-t)+EPS<requested:continue
            if (w-t)*(d-t)>requested*1.42+EPS:continue
            shapes[(w,d)]=min(shapes.get((w,d),math.inf),
                             abs(math.log(max(netw,netd)/min(netw,netd)))+
                             max(0,(netw*netd/requested)-1))
    return [(*dims,shape_score) for dims,shape_score in
            sorted(shapes.items(),key=lambda x:x[1])[:10]]


def initial_core(W,D,seed,t):
    """Core location is a searched variable, not a mandatory housing template."""
    # 3x4.6m stair is reserved before distributing any room, on all floors.
    hx=snap(W*(.50+.045*(seed%3-1)))
    hy=snap(3.75+.5*(seed//3))
    hub=rect(hx,hy,2.5,2.5,kind="corridor",id="family-hub")
    stair=rect(hx+2.5,hy-1,3.,4.6,kind="stair",id="shared-stair",
               name="درج ثابت بين الدورين")
    # Family entry candidate: 1.5m-wide continuous short path from frontage
    # to family hall. Exterior/street reachability must be verified later.
    entry=rect(hx+.50,0.,1.5,hy,kind="corridor",id="family-entry-spur")
    # A short protected growth node prevents the first living room from
    # sealing every corridor outlet. The continuation is then free to bend
    # left, right or continue only when actual program needs more space.
    rear=rect(hx+.50,hy+2.5,1.5,3.0,kind="corridor",id="family-growth-node")
    if not all(inside(r,W,D) for r in (hub,stair,entry,rear)):
        return None
    return [hub,entry,rear],stair


def guest_suite(requests,hub,W,D,t):
    guests=[r for r in requests if r.get("zone")=="guest"]
    if not guests:return [],None
    council=[r for r in guests if r["kind"]=="majlis"]
    bathroom=[r for r in guests if r["kind"]=="bathroom"]
    if len(guests)!=2 or len(council)!=1 or len(bathroom)!=1:
        return None,"UNSUPPORTED_GUEST_PROGRAM_UNRESOLVED"
    m,b=council[0],bathroom[0]
    mw,md,_=room_shapes(m,t)[0]
    bw,bd,_=room_shapes(b,t)[0]
    # Guest entry vestibule is between council and bath, directly accessing
    # both by shared boundary. There is no connection to family hall.
    vw=max(2.25,min(mw,bw));vd=2.0
    gx=snap(hub["x"]-mw)
    gy=0.
    if gx<0 or gy+md+vd+bd>D:
        return None,"GUEST_SUITE_DOES_NOT_FIT"
    maj=rect(gx,gy,mw,md,**copy.deepcopy(m),guest_vestibule="men-vestibule")
    v=rect(gx,gy+md,vw,vd,id="men-vestibule",zone="guest",
           kind="corridor",name="موزع ضيوف مستقل",
           guest_distributor=True,guest_entrance_potential=True)
    bath=rect(gx,gy+md+vd,bw,bd,**copy.deepcopy(b),
              guest_vestibule="men-vestibule")
    if edge_contact(maj,v)<.90 or edge_contact(v,bath)<.90:
        return None,"GUEST_SUITE_NOT_CONNECTED"
    if not all(inside(r,W,D) for r in (maj,v,bath)):
        return None,"GUEST_SUITE_OUTSIDE_ENVELOPE"
    if any(overlap_area(a,b)>EPS for a,b in
           ((maj,v),(maj,bath),(v,bath))):
        return None,"GUEST_SUITE_INTERNAL_OVERLAP"
    return [maj,v,bath],None


def anchors(hall,w,d,seed):
    """Attach a free rectangle along a *real* hall wall (>=0.90m contact)."""
    hx,hy,hw,hd=(hall[k] for k in ("x","y","width","depth"))
    order=("south","west","north","east")
    for direction in (order[seed%4:]+order[:seed%4]):
        if direction in ("north","south"):
            xs=(hx+(hw-w)/2,hx,hx+hw-w,
                hx+hw-1.,hx+1.-w)
            y=hy-d if direction=="north" else hy+hd
            for x in xs:
                c=rect(snap(x),snap(y),w,d)
                if edge_contact(hall,c)>=.9:
                    yield c
        else:
            ys=(hy+(hd-d)/2,hy,hy+hd-d,
                hy+hd-1.,hy+1.-d)
            x=hx-w if direction=="west" else hx+hw
            for y in ys:
                c=rect(snap(x),snap(y),w,d)
                if edge_contact(hall,c)>=.9:
                    yield c


def hall_extensions(halls,objects,W,D,seed):
    """Generate short, collision-free branches only where room packing needs one."""
    for h in halls[-4:]:
        # The original entry spur should not grow back into a mandatory
        # axial corridor; branch from the compact hub/most recent nodes.
        if h.get("id")=="family-entry-spur":continue
        for length in (2.5,4.,5.5):
            for axis in range(4):
                if axis==0:
                    c=rect(snap(h["x"]+h["width"]/2-.75),
                           snap(h["y"]+h["depth"]),1.5,length,kind="corridor")
                elif axis==1:
                    c=rect(snap(h["x"]+h["width"]/2-.75),
                           snap(h["y"]-length),1.5,length,kind="corridor")
                elif axis==2:
                    c=rect(snap(h["x"]+h["width"]),snap(h["y"]+h["depth"]/2-.75),
                           length,1.5,kind="corridor")
                else:
                    c=rect(snap(h["x"]-length),snap(h["y"]+h["depth"]/2-.75),
                           length,1.5,kind="corridor")
                if edge_contact(h,c)<1.2-EPS:continue
                if not clear(c,objects,W,D):continue
                yield c


@dataclass
class State:
    rooms:list
    halls:list
    score:float
    trace:list


def relation_distance(candidate,placed):
    weights={"kitchen":{"dining":9.},"dining":{"kitchen":9.,"living":4.},
             "living":{"dining":4.},"master":{"bathroom":3.},
             "bedroom":{"bathroom":1.5},"bathroom":{"master":3.,"bedroom":1.5}}
    group=weights.get(candidate["kind"],{})
    return sum(weight*max(0.,gap(candidate,p)-1.0)
               for p in placed if p.get("zone")!="guest"
               for kind,weight in group.items() if p.get("kind")==kind)


def state_cost(rooms,halls):
    requested=[r for r in rooms if r.get("request_id") and r.get("zone")!="guest"]
    rects=rooms+halls
    if not rects:return math.inf
    xmin=min(r["x"] for r in rects)
    xmax=max(r["x"]+r["width"] for r in rects)
    ymin=min(r["y"] for r in rects)
    ymax=max(r["y"]+r["depth"] for r in rects)
    hull=(xmax-xmin)*(ymax-ymin)
    movement=union_area(halls)
    adj=sum(relation_distance(r,requested) for r in requested)*.5
    return (3.*movement+.035*hull+.45*adj+
            .17*sum(area(r) for r in requested)+
            8.*max(0,len(halls)-3))


def pack_floor(requests,W,D,t,seed,core,guest_ground,*,beam_width=12,
               max_branches=4):
    base_halls,stair=core
    occupied=[stair]+guest_ground
    if any(overlap_area(stair,g)>EPS for g in guest_ground):
        return None,"STAIR_OVERLAPS_GUEST_ZONE"
    if any(overlap_area(h,stair)>EPS for h in base_halls):
        return None,"STAIR_OVERLAPS_FAMILY_HALL"
    if any(overlap_area(h,g)>EPS for h in base_halls for g in guest_ground):
        return None,"GUEST_OVERLAPS_FAMILY_HALL"
    family=[r for r in requests if r.get("zone")!="guest"]
    # Priority reflects a preconstructed relationship graph, not fixed lane
    # order. Seed changes which relationship cluster wins first.
    priority={"living":0,"dining":1,"kitchen":2,"master":3,
              "bedroom":4,"bathroom":5,"office":6,"laundry":7,"storage":8}
    family=sorted(family,key=lambda r:(priority.get(r["kind"],10)+
                 (seed%3-1)*({"kitchen":1,"master":-1,"bathroom":-1}.get(r["kind"],0)),
                 -r["min_area"],r["id"]))
    states=[State(copy.deepcopy(occupied),copy.deepcopy(base_halls),0.,[])]
    failed=None
    for idx,room in enumerate(family):
        expansions=[]
        shapes=room_shapes(room,t)
        if not shapes:
            return None,"ROOM_HAS_NO_VALID_DIMENSION:"+room["id"]
        for state in states:
            old=state.rooms+state.halls
            proposed=[]
            for w,d,shape_penalty in shapes[:6]:
                for hall in state.halls:
                    for candidate in anchors(hall,w,d,seed):
                        if not clear(candidate,old,W,D):continue
                        r={**candidate,**copy.deepcopy(room)}
                        proposed.append((r,None,shape_penalty))
                # On-demand additional hallway branches; not prescribed wings.
                if len(state.halls)<2+max_branches:
                    for branch in hall_extensions(state.halls,old,W,D,seed):
                        for candidate in anchors(branch,w,d,seed):
                            if not clear(candidate,old+[branch],W,D):
                                continue
                            r={**candidate,**copy.deepcopy(room)}
                            proposed.append((r,branch,shape_penalty+.5))
            # Prefer measured closeness and minimal added hall area, but retain
            # diverse options to avoid greedy one-configuration traps.
            proposed.sort(key=lambda item:(
                relation_distance(item[0],state.rooms)*.60+
                (area(item[1])*3 if item[1] else 0)+item[2]*2+
                .03*(item[0]["x"]+item[0]["y"])))
            seen=set()
            # A purely greedy cost ranking filled all beam slots with
            # no-branch rooms and later trapped the remaining program.
            # Preserve a bounded minority of corridor-growth hypotheses.
            direct=[p for p in proposed if p[1] is None]
            branched=[p for p in proposed if p[1] is not None]
            considered=direct[:40]+branched[:45]
            for new_room,new_hall,shape_cost in considered:
                key=(new_room["x"],new_room["y"],new_room["width"],
                     new_room["depth"],new_hall["x"] if new_hall else -1,
                     new_hall["y"] if new_hall else -1)
                if key in seen:continue
                seen.add(key)
                new_rooms=state.rooms+[new_room]
                new_halls=state.halls+([new_hall] if new_hall else [])
                cost=state_cost(new_rooms,new_halls)+shape_cost
                expansions.append(State(new_rooms,new_halls,cost,
                                        state.trace+[(room["id"],bool(new_hall))]))
        if not expansions:
            failed="CANNOT_PLACE_ROOM:"+room["id"]
            break
        expansions.sort(key=lambda s:s.score)
        next_states=[];seen=set();bucket_counts={}
        # Keep several different circulation-growth depths alive rather
        # than allowing the cheapest first bedroom to block the only exit.
        for item in expansions:
            group=len(item.halls)
            if bucket_counts.get(group,0)>=max(2,beam_width//3):continue
            key=tuple(sorted((r.get("id"),r["x"],r["y"],r["width"],r["depth"])
                             for r in item.rooms))
            if key in seen:continue
            next_states.append(item);seen.add(key)
            bucket_counts[group]=bucket_counts.get(group,0)+1
            if len(next_states)>=beam_width:break
        if len(next_states)<beam_width:
            for item in expansions:
                key=tuple(sorted((r.get("id"),r["x"],r["y"],r["width"],r["depth"])
                                 for r in item.rooms))
                if key in seen:continue
                next_states.append(item);seen.add(key)
                if len(next_states)>=beam_width:break
        states=next_states
    if failed:return None,failed
    candidates=[]
    from .architectural_composer import facade_exposure
    for state in states:
        # Guest and family topology are intentionally separate. Validate
        # their room-wall opportunities before claiming any concept is valid.
        rooms=state.rooms
        halls=state.halls
        all_shapes=rooms+halls
        if any(not inside(r,W,D) for r in all_shapes):continue
        if any(overlap_area(a,b)>EPS for i,a in enumerate(all_shapes)
               for b in all_shapes[i+1:]
               if not (a in halls and b in halls)):continue
        if any(not any(edge_contact(room,h)>=.9 for h in halls)
               for room in rooms if room.get("request_id")
               and room.get("zone")!="guest"):continue
        if any(facade_exposure(r,all_shapes)<.9-EPS for r in rooms
               if r.get("request_id") and r["kind"] in
               ("bedroom","master","kitchen","bathroom")):
            continue
        candidates.append(state)
    if not candidates:
        return None,"NO_VALID_EXTERNAL_FRONTAGE_OR_ACCESS_FINAL_STATE"
    return min(candidates,key=lambda s:s.score),None


def solve_free_concepts(brief,*,seeds=range(8),max_results=3):
    """Return real geometric proposals or explicit named failures.

    The candidate generator is independent of the existing fixed-lane search.
    Its shapes remain preliminary until actual wall/door/window/privacy and
    municipal checks are separately executed.
    """
    from backend.design.general_engine import expanded_program
    t=brief.wall_thickness
    W=brief.plot_width-brief.setbacks.east-brief.setbacks.west-t
    D=brief.plot_depth-brief.setbacks.north-brief.setbacks.south-t
    requested=[expanded_program(brief,f) for f in range(brief.floors)]
    failures=[];solutions=[];signatures=set()
    for seed in seeds:
        core=initial_core(W,D,seed,t)
        if core is None:
            failures.append({"seed":seed,"reason":"CORE_OUTSIDE_BUILDABLE_AREA"})
            continue
        guest,error=guest_suite(requested[0],core[0][0],W,D,t)
        if error:
            failures.append({"seed":seed,"reason":error});continue
        floors=[];halls_by_floor=[]
        problem=None;traces=[]
        for floor_idx,program in enumerate(requested):
            stair=core[1]
            guest_on_floor=guest if floor_idx==0 else []
            state,reason=pack_floor(program,W,D,t,seed,core,guest_on_floor)
            if not state:
                problem={"floor":floor_idx,"reason":reason};break
            floors.append(state.rooms)
            halls_by_floor.append(state.halls)
            traces.append(state.trace)
        if problem:
            failures.append({"seed":seed,**problem});continue
        candidate={"floors":floors,"halls_by_floor":halls_by_floor}
        quality=assess_layout(candidate,t)
        expected=[[r["id"] for r in req] for req in requested]
        actual=[[r["id"] for r in floor if r.get("request_id")]
                for floor in floors]
        if any(sorted(a)!=sorted(b) for a,b in zip(expected,actual)):
            failures.append({"seed":seed,"reason":"PROGRAM_LOST_OR_DUPLICATED"})
            continue
        if quality["hard_issues"]:
            failures.append({"seed":seed,"reason":"QUALITY_GATE",
                             "issues":quality["hard_issues"][:9]})
            continue
        signature=spatial_signature(candidate)
        if signature in signatures:continue
        signatures.add(signature)
        solutions.append({"seed":seed,
            "family":"free_constraints","quality":quality,
            "rooms_by_floor":floors,"halls_by_floor":halls_by_floor,
            "placement_trace":traces,"building_envelope_m":[W,D],
            "structural_signature":str(signature)})
    solutions.sort(key=lambda s:s["quality"]["architecture_score"])
    return {"status":"PRELIMINARY_CONCEPT_ONLY","proposals":solutions[:max_results],
            "valid_found":len(solutions),"requested_count":max_results,
            "rejected_seeds":failures,"program_integrity_gate":True,
            "stair_consistency_gate":True,"furniture_used":False,
            "door_and_window_geometry_verified":False,
            "street_access_verified":False,
            "legal_compliance_certified":False}
