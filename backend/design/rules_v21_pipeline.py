"""Integrated experimental V2.1 pipeline. Never marks unverified geometry accepted."""
from .rules_v21_wings import plan_wings
from .rules_v21_floor_assignment import assign_floors
from .rules_v21_vertical_core import reserve_core
from .rules_v21_mass_proposals import propose_masses
from .rules_v21_subdivision import subdivide_wing
from .rules_v21_walls import extract_wall_network
from .rules_v21_access import check_access

def run(document,envelopes,capacities,core_dimensions=None,obstacles=None):
    report={"accepted":False,"stages":{},"floors":{}}
    s=report["stages"]
    s["wings"]=plan_wings(document)
    if s["wings"]["status"]!="demand_ready":return report
    s["assignment"]=assign_floors(document,capacities)
    if s["assignment"]["status"]!="assignment_ready":return report
    if len(envelopes)>1:
        if not core_dimensions:return report
        s["core"]=reserve_core(envelopes,list(envelopes),*core_dimensions,obstacles=obstacles)
        if s["core"]["status"]!="reservation_ready":return report
    rows={r["id"]:r for r in document["program"]}
    for floor,env in envelopes.items():
        groups={}
        for a in s["assignment"]["assignments"]:
            if a["floor"]!=floor:continue
            r=rows[a["program_id"]]
            g=groups.setdefault(r["privacy_zone"],[])
            g.append(dict(r,id=r["id"]+":"+str(a["instance"])))
        wings=[dict(zone=z,target_m2=sum(r["area_target_m2"] for r in rs)) for z,rs in groups.items()]
        result=propose_masses(wings,env)
        output=report["floors"][floor]={"mass_search":result["status"],"layouts":[]}
        for candidate in result["candidates"]:
            rooms=[];valid=True
            for z,rect in zip(candidate["zones"],candidate["exclusive_rectangles"]):
                sub=subdivide_wing([v*1000 for v in rect],groups[z])
                if not sub["candidates"]:valid=False;break
                rooms.extend(sub["candidates"][0]["rooms"])
            if not valid:continue
            hall=[round(v*1000,6) for v in candidate["circulation_rect"]]
            rooms.append(dict(id="circulation:main",rect_mm=hall,area_m2=hall[2]*hall[3]/1e6))
            for room in rooms:
                room["rect_mm"]=[round(v,6) for v in room["rect_mm"]]
            walls=extract_wall_network(rooms)
            if walls["status"]!="network_ready":continue
            access=check_access(rooms,walls["walls"],["circulation:main"])
            output["layouts"].append(dict(rooms=rooms,walls=walls,access=access,accepted=False))
    report["pending"]=["core clearance","circulation","openings","furniture","constitution coverage","architectural review"]
    return report
