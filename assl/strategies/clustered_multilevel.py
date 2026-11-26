"""Develop the clustered family program above a validated ground proposal."""
from collections import defaultdict
from copy import deepcopy
from itertools import product
from math import ceil, isclose, isfinite
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

import ezdxf
from ezdxf import bbox
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

from assl.openings_009 import cut, inward, leaf_swings
from backend.design.general_models import TransferredSuite, UpperFloorProgram, VillaBrief, VillaProgram
from .central_clustered import solve_central
from .concept_massing import draw_concept_massing
from .export import export_dxf
from .geometry import entity, exposed_edges, net_shape, shape, shared_edges
from .stairs import u_frame, u_treads, validate_u_stair
from .structural_grid import draw_grid, family_grid_profile, unsupported_grid_points, wall_axis_segments


GROUND_WC = dict(id="ground-family-wc", name="حمام العائلة", kind="bathroom",
                 floor=0, count=1, min_area=6, min_side=1.8)

FAMILY_PROFILES = (
    ((1, 1, 1), "east", "BEDROOMS ON THREE SIDES"),
    ((2, 1, 0), "east", "TWO BEDROOMS IN WEST WING"),
    ((1, 1, 1), "south", "SOUTH MASTER TERRACE"),
)
UPPER_ROOM_KINDS = {
    "stair-core": "stair", "upper-living": "living", "upper-family-wc": "bathroom",
    "suite-vestibule": "corridor", "upper-master-wc": "bathroom", "upper-master": "master",
    "family-terrace": "terrace", "master-terrace": "terrace",
}


def upper_connections(children):
    return [
        ("stair-core", "upper-living"), ("upper-living", "upper-family-wc"),
        ("upper-living", "suite-vestibule"), ("suite-vestibule", "upper-master"),
        ("suite-vestibule", "upper-master-wc"), ("upper-living", "family-terrace"),
        ("upper-master", "master-terrace"),
        *(("upper-living", f"child-{index}") for index in range(1, children + 1)),
    ]


def upper_stair_opening(stair, thickness):
    """Cut the stairwell while preserving the upper landing at its doorway."""
    point = u_frame(stair)
    profile = stair["stair"]
    left = thickness / 2
    front = left + profile["entry_apron_m"]
    right = profile["gross_width_m"] - left
    back = profile["gross_depth_m"] - left
    return [list(point(x, y)) for x, y in ((left,front), (right,front), (right,back), (left,back))]


def upper_layout_options(stair, thickness, children, min_area, min_side, grid, terrace_side="east", transferred_suite=None):
    """Explore room groupings and wing dimensions in the stair's local frame."""
    stair_width = stair["stair"]["gross_width_m"]
    for west, east, south in product(range(3), range(3), range(2)):
        if west+east+south != children or (grid is not None and not east):
            continue
        for lounge_width, depth_extra, terrace_depth in product(
                (stair_width+1.7, stair_width+1.8, stair_width+2.2, stair_width+2.8),
                (0, .6, 1.2), (1.7, 2.0)):
            band = min_side+thickness
            depth = max(4.5, west*band+terrace_depth, east*band)+depth_extra
            suite_split = lounge_width-1.8
            master_width = 4.6
            suite_depth = 4.3
            if transferred_suite:
                bedroom, bathroom = transferred_suite.bedroom, transferred_suite.bathroom
                bath_width = max(1.8, bathroom.min_side+thickness)
                suite_split = lounge_width-bath_width
                if suite_split <= thickness:
                    continue
                bath_depth = max(2.4, bathroom.min_side+thickness,
                                 bathroom.min_area/(bath_width-thickness)+thickness)
                suite_depth = max(1.9+bath_depth, bedroom.min_side+thickness)
                master_width = max(master_width, bedroom.min_side+thickness,
                                   bedroom.min_area/(suite_depth-thickness)+thickness)
            plan = [
                ("upper-living", "living", "صالة العائلة والموزع", (0,-depth,lounge_width,0)),
                ("upper-family-wc","bathroom","حمام الأبناء المشترك",(stair_width,0,lounge_width,2.75)),
                ("suite-vestibule","corridor","موزع جناح الماستر",(suite_split,-depth-1.9,lounge_width,-depth)),
                ("upper-master-wc","bathroom","حمام الماستر",(suite_split,-depth-suite_depth,lounge_width,-depth-1.9)),
                ("upper-master","master","غرفة نوم الماستر",(lounge_width,-depth-suite_depth,lounge_width+master_width,-depth)),
                ("family-terrace","terrace","تراس صالة العائلة",(-3.2,-terrace_depth,0,0)),
                ("master-terrace","terrace","تراس الماستر",(lounge_width+master_width,-depth-suite_depth,lounge_width+master_width+1.8,-depth)),
            ]
            if terrace_side == "south":
                plan[-1] = ("master-terrace","terrace","تراس الماستر",
                            (lounge_width,-depth-suite_depth-1.8,
                             lounge_width+master_width,-depth-suite_depth))
            child_boxes = []
            for side, count in (("west",west),("east",east)):
                if not count:
                    continue
                bottom,top = -depth, -terrace_depth if side=="west" else 0
                if grid is not None and side=="east" and count==1:
                    bottom,top = grid["east_bedroom_south_offset_m"], 0
                segment = (top-bottom)/count
                width = (grid["east_wall_offset_m"]-lounge_width if grid is not None and side=="east" else
                         ceil(10*(max(min_side,min_area/(segment-thickness))+thickness))/10)
                if width<=thickness:
                    break
                for index in range(count):
                    low = bottom+index*segment
                    high = bottom+(index+1)*segment
                    child_boxes.append((-width,low,0,high) if side=="west" else
                                       (lounge_width,low,lounge_width+width,high))
            if len(child_boxes)!=west+east:
                continue
            if south:
                if suite_split-thickness<min_side:
                    continue
                room_depth = max(min_side,min_area/(suite_split-thickness))+thickness
                child_boxes.append((0,-depth-room_depth,suite_split,-depth))
            for index, bounds in enumerate(child_boxes,1):
                rid=f"child-{index}"
                plan.append((rid,"bedroom",f"غرفة الأبناء {index}",bounds))
            yield (west,east,south),plan,upper_connections(children)


def build_family_stack(brief, *, children=3, child_area_m2=11.5, child_min_side_m=2.7, wing_group=None, terrace_side="east", progress=None, transferred_suite=None):
    """Generate and validate the ground floor before composing upper levels."""
    if terrace_side not in ("east", "south"):
        raise ValueError("Unsupported master terrace side")
    if type(children) is not int or not 1<=children<=5:
        raise ValueError("Upper program supports one to five children's bedrooms")
    if not all(isfinite(v) and v>0 for v in (child_area_m2, child_min_side_m)):
        raise ValueError("Child bedroom size must be finite and positive")
    if child_area_m2<9 or child_min_side_m<2.5:
        raise ValueError("Child bedroom size is below the search profile limits")
    existing = [room for room in brief.rooms if room.id == GROUND_WC["id"]]
    if not existing:
        data = brief.model_dump()
        data["rooms"].append(GROUND_WC)
        brief = type(brief).model_validate(data)
    grid = family_grid_profile(brief) if isinstance(brief,VillaBrief) else None
    if progress:
        progress(12, "تكوين الدور الأرضي وفحصه")
    ground_result = solve_central(brief, grid=grid)
    if not ground_result["proposals"]:
        raise ValueError(f"Ground floor rejected: {ground_result['failures']}")
    ground = ground_result["proposals"][0]
    ground_rooms = ground["rooms_by_floor"][0] + ground["halls_by_floor"][0]
    stair = next(room for room in ground_rooms if room["id"] == "stair-core")
    ground_footprint = unary_union(list(map(shape,ground_rooms)))
    thickness=brief.wall_thickness
    ground_openings=ground["opening_model_009"][0]
    ground_axes=wall_axis_segments(ground_rooms,ground_openings["doors"]+ground_openings["windows"],thickness)
    roof_axes=wall_axis_segments([stair],[],thickness)
    ground_misses=unsupported_grid_points(grid,ground_axes) if grid is not None else []
    roof_misses=unsupported_grid_points(grid,roof_axes,roof_only=True) if grid is not None else []
    if ground_misses or roof_misses:
        raise ValueError(f"Fixed grid misses wall runs: ground={ground_misses}; stair enclosure={roof_misses}")
    if progress:
        progress(55, "توزيع الدور الأول حول الدرج وفحص المسارات")
    best = None
    failures = {}
    tested = accepted = 0
    feasible_groups = set()
    for group, program, links in upper_layout_options(stair,brief.wall_thickness,children,child_area_m2,child_min_side_m,grid,terrace_side,transferred_suite):
        tested += 1
        try:
            first,doors,footprint = check_upper(brief,stair,program,links)
        except ValueError as error:
            reason=str(error).split(":")[0]
            failures[reason]=failures.get(reason,0)+1
            continue
        child_rooms=[net_shape(room,brief.wall_thickness) for room in first if room["id"].startswith("child-")]
        if len(child_rooms)!=children or any(
                room.area<child_area_m2-1e-6 or min(room.bounds[2]-room.bounds[0],room.bounds[3]-room.bounds[1])<child_min_side_m-1e-6
                for room in child_rooms):
            failures["Child room below requested clear size"]=failures.get("Child room below requested clear size",0)+1
            continue
        accepted += 1
        covered=footprint.intersection(ground_footprint).area
        unsupported=footprint.area-covered
        # Prefer lower overhang and simpler profiles. Account for the terraces
        # separately because an exposed slab also requires structural review.
        terraces=unary_union([shape(room) for room in first if room["kind"]=="terrace"])
        score=unsupported+terraces.difference(ground_footprint).area+.05*footprint.length
        upper_rooms=[room for room in first if room["kind"]!="terrace"]
        upper_windows=[window for window,_ in level_windows(upper_rooms,doors,thickness)]
        upper_axes=wall_axis_segments(first,doors+upper_windows,thickness)
        if grid is not None and unsupported_grid_points(grid,upper_axes):
            accepted-=1
            reason="Fixed support point crosses an upper room or opening"
            failures[reason]=failures.get(reason,0)+1
            continue
        feasible_groups.add(group)
        if wing_group is not None and wing_group != group:
            continue
        if best is None or score<best[0]:
            best=(score,first,doors,covered,footprint.area,upper_axes,group)
    if best is None:
        raise ValueError(f"No upper layout meets the program after {tested} attempts: {failures}")
    if progress:
        progress(86, "تم فحص ارتباط الدورين")
    _,first,doors,covered,area,upper_axes,group=best
    ground_parts=unary_union([ground_footprint.buffer(thickness/2,join_style=2)]+[
        Polygon(platform["landing_polygon"]) for platform in ground.get("entrance_platforms",[])]+[
        Polygon(step["polygon"]) for platform in ground.get("entrance_platforms",[]) for step in platform["treads"]])
    first_enclosed=unary_union([shape(room) for room in first if room["kind"]!="terrace"])
    building=unary_union([ground_parts,first_enclosed.buffer(thickness/2,join_style=2)]+[
        shape(room) for room in first if room["kind"]=="terrace"])
    xmin,ymin,xmax,ymax=building.bounds
    footprint_metrics=dict(width_m=round(xmax-xmin,3),depth_m=round(ymax-ymin,3),
                           ground_enclosed_m2=round(ground_footprint.area,3),
                           first_enclosed_m2=round(area,3),stair_enclosure_m2=round(shape(stair).area,3))
    return dict(brief=brief, ground=ground, first=first, doors=doors,
                roof=[deepcopy(stair)], levels_m=[0,brief.floor_height,2*brief.floor_height],
                upper_covered_by_ground_m2=covered, upper_enclosed_m2=area,
                site_status="SITE_ASSIGNED" if grid is not None else "SITE_NOT_ASSESSED",
                footprint_metrics=footprint_metrics,
                structural_grid=grid,
                structural_wall_axes=[ground_axes,upper_axes,roof_axes],
                wing_group=group, upper_search=dict(attempted=tested,accepted=accepted,rejections=failures,
                                  feasible_groups=sorted(feasible_groups)))


def check_upper(brief, stair, program, links):
    frame = u_frame(stair)
    first = [deepcopy(stair)]
    for rid, kind, name, (x0, y0, x1, y1) in program:
        polygon = Polygon([frame(x0,y0), frame(x1,y0), frame(x1,y1), frame(x0,y1)])
        first.append(entity(rid, kind, polygon, name=name))
    doors, footprint = inspect_upper(brief, first, links)
    return first, doors, footprint


def inspect_upper(brief, first, links):
    """Check the given upper geometry and find compatible opening hosts."""
    t = brief.wall_thickness
    ids = {room["id"]: room for room in first}
    doors = []
    connected = defaultdict(set)
    first_footprint = unary_union([shape(room) for room in first if room["kind"] != "terrace"])
    if isinstance(brief,VillaBrief):
        plot = box(0,0,brief.plot_width-brief.setbacks.west-brief.setbacks.east-t,
                   brief.plot_depth-brief.setbacks.south-brief.setbacks.north-t)
        if not plot.buffer(1e-6).covers(unary_union(list(map(shape,first)))):
            raise ValueError("Upper program exceeds the buildable envelope")
    for index, room in enumerate(first):
        if any(shape(room).intersection(shape(other)).area>1e-6 for other in first[index+1:]):
            raise ValueError(f"Upper program overlap: {room['id']}")
    if first_footprint.geom_type != "Polygon" or first_footprint.interiors:
        raise ValueError("Upper occupied footprint is disconnected or encloses a void")
    sweeps = []
    for source, target in links:
        width = 1.2 if source == "stair-core" or ids[target]["kind"] == "terrace" else .9
        edges = [edge for edge in shared_edges(ids[source], ids[target])
                 if edge["length"] >= width+.3-1e-6]
        if not edges:
            raise ValueError(f"No upper-floor door host: {source} / {target}")
        edge = max(edges, key=lambda e:e["length"])
        midpoint = (edge["lo"]+edge["hi"])/2
        center = [midpoint,edge["fixed"]] if edge["axis"]=="x" else [edge["fixed"],midpoint]
        door = dict(axis=edge["axis"], center=center, width=width,
                    connects=[source,target], receiving_room=target)
        sectors = [] if source == "stair-core" or ids[target]["kind"] == "terrace" else leaf_swings(
            door,ids[target],t)
        if not all(net_shape(ids[target],t).buffer(.003).covers(sector) for sector in sectors):
            raise ValueError(f"Upper door sweep exceeds room: {target}")
        if any(cut(door,t/2).intersection(cut(other,t/2)).area>1e-6 for other in doors):
            raise ValueError(f"Upper door openings collide: {target}")
        if any(a.intersection(b).area>1e-6 for a in sectors for b in sweeps):
            raise ValueError(f"Upper door sweeps collide: {target}")
        sweeps.extend(sectors)
        doors.append(door)
        connected[source].add(target)
        connected[target].add(source)
    reached = {"stair-core"}
    pending = ["stair-core"]
    while pending:
        next_rooms = connected[pending.pop()] - reached
        reached.update(next_rooms)
        pending.extend(next_rooms)
    if reached != ids.keys():
        raise ValueError("Unreachable upper rooms")
    for room in first:
        if room["kind"] not in ("living","corridor"):
            continue
        ports=[inward(door,room,.65) for door in doors if room["id"] in door["connects"]]
        clearance=net_shape(room,t).buffer(-.3,join_style=2).buffer(1e-6)
        if not all(clearance.covers(LineString([ports[0],port])) for port in ports[1:]):
            raise ValueError(f"No 0.60 m upper circulation route: {room['id']}")
    for room in first:
        if room["kind"] in ("bedroom","master") and not any(
            edge["length"]>=1.25 for edge in exposed_edges(room,[r for r in first if r["kind"]!="terrace"])):
            raise ValueError(f"No exposed facade for bedroom: {room['id']}")
    return doors,first_footprint


def level_windows(enclosed, doors, thickness):
    windows = []
    for room in enclosed:
        if room["kind"] not in {"bedroom","master","bathroom","living"}:
            continue
        edges = [e for e in exposed_edges(room,enclosed) if e["length"]>=1.25]
        for edge in sorted(edges,key=lambda e:-e["length"]):
            width = min(.9 if room["kind"]=="bathroom" else 2.1,edge["length"]-.4)
            mid = (edge["lo"]+edge["hi"])/2
            if edge["axis"]=="x":
                center=[mid,edge["fixed"]]
                points=[(mid-width/2,edge["fixed"]),(mid+width/2,edge["fixed"])]
            else:
                center=[edge["fixed"],mid]
                points=[(edge["fixed"],mid-width/2),(edge["fixed"],mid+width/2)]
            window=dict(axis=edge["axis"],center=center,width=width)
            if not any(LineString(points).intersects(cut(door,thickness)) for door in doors):
                windows.append((window,points))
                break
    return windows


def family_proposals(brief, max_results, progress=None, *, upper_program=None, transferred_suite=None, terrace_side="east"):
    """Generate one default stack or two specified functional arrangements."""
    proposals, failures = [], []
    program = (upper_program or UpperFloorProgram()).model_dump()
    groups = ((1, 1, 0), (0, 1, 1)) if program["children"] == 2 else (
        FAMILY_PROFILES[0][0], FAMILY_PROFILES[1][0],
    )
    profiles = groups if max_results == 2 else (None,)
    for index, group in enumerate(profiles):
        def report(percent, detail):
            progress((100 * index + percent) // len(profiles), detail)

        try:
            stack = build_family_stack(
                brief, **program, wing_group=group, progress=report if progress else None,
                transferred_suite=transferred_suite, terrace_side=terrace_side
            )
            ground = stack["ground"]
            upper = stack["first"]
            enclosed = [room for room in upper if room["kind"] != "terrace"]
            windows = [w for w, _ in level_windows(enclosed, stack["doors"], brief.wall_thickness)]
            proposal = {
                **ground,
                "id": f'{ground["id"]}-upper-{"".join(map(str, stack["wing_group"]))}',
                "rooms_by_floor": [ground["rooms_by_floor"][0], upper],
                "halls_by_floor": [ground["halls_by_floor"][0], []],
                "opening_model_009": [
                    ground["opening_model_009"][0], {"doors": stack["doors"], "windows": windows},
                ],
                "upper_wing_group": stack["wing_group"],
                "upper_program": program,
            }
            if transferred_suite:
                proposal["transferred_suite"] = transferred_suite.model_dump()
                names = {"upper-master": transferred_suite.bedroom.name,
                         "upper-master-wc": transferred_suite.bathroom.name}
                for room in upper:
                    if room["id"] in names:
                        room["name"] = names[room["id"]]
            proposals.append(check_family_proposal(stack["brief"], proposal))
        except ValueError as error:
            failures.append({"upper_wing_group": group, "reason": str(error)})
    return {
        "status": "CONCEPT_READY_FOR_ARCHITECT_REVIEW" if proposals else "REJECT_AND_REPLAN",
        "requested_results": max_results,
        "proposals": proposals,
        "failures": failures,
    }


def check_family_proposal(brief, proposal):
    """Validate the selected geometry itself and keep both floors in one model."""
    rooms = proposal["rooms_by_floor"]
    halls = proposal["halls_by_floor"]
    openings = proposal["opening_model_009"]
    if "first_floor" in proposal:
        if len(rooms) != 1 or len(halls) != 1 or len(openings) != 1:
            raise ValueError("MASSING_AMBIGUOUS_FIRST_FLOOR")
        first = proposal["first_floor"]
        rooms = [*rooms, first["rooms"]]
        halls = [*halls, []]
        openings = [*openings, {"doors": first["doors"], "windows": first["windows"]}]
        proposal = {key: value for key, value in proposal.items() if key != "first_floor"}
    if len(rooms) != 2 or len(halls) != 2 or len(openings) != 2 or halls[1]:
        raise ValueError("MASSING_FAMILY_LEVELS_INVALID")

    ground, upper = rooms
    stair = next((room for room in ground if room["id"] == "stair-core"), None)
    upper_stair = next((room for room in upper if room["id"] == "stair-core"), None)
    if (stair is None or stair != upper_stair or stair.get("kind") != "stair"
            or stair.get("stair", {}).get("layout") != "u-shaped"
            or not validate_u_stair(stair, brief)):
        raise ValueError("MASSING_STAIR_LEVELS_MISALIGNED")
    profile = stair["stair"]
    if (profile["risers_per_flight"] * 2 != profile["risers"]
            or profile["intermediate_landing_count"] != 1
            or not isclose(profile["riser_height_m"] * profile["risers"], brief.floor_height, abs_tol=1e-6)
            or not isclose(profile["intermediate_landing_level_m"], brief.floor_height / 2, abs_tol=1e-6)):
        raise ValueError("MASSING_STAIR_LANDING_LEVEL_INVALID")

    program = UpperFloorProgram.model_validate(proposal.get("upper_program", {}))
    kinds = {**UPPER_ROOM_KINDS, **{f"child-{i}": "bedroom" for i in range(1, program.children + 1)}}
    if len(upper) != len(kinds) or {room["id"]: room["kind"] for room in upper} != kinds:
        raise ValueError("MASSING_UPPER_PROGRAM_MISMATCH")
    thickness = brief.wall_thickness
    for room in upper:
        polygon = shape(room)
        if (not polygon.is_valid or polygon.is_empty or polygon.area <= 1e-6
                or len(room["polygon"]) != 4):
            raise ValueError("MASSING_UPPER_ROOM_GEOMETRY_INVALID")
        x, y, right, top = polygon.bounds
        if not all(isclose(room[key], value, abs_tol=1e-6, rel_tol=0)
                   for key, value in zip(("x", "y", "width", "depth"), (x, y, right-x, top-y))):
            raise ValueError("MASSING_UPPER_ROOM_BOUNDS_MISMATCH")
        if room["kind"] == "bedroom":
            clear = net_shape(room, thickness)
            if clear.is_empty:
                raise ValueError("MASSING_UPPER_BEDROOM_DIMENSIONS")
            x, y, right, top = clear.bounds
            if (clear.area < program.child_area_m2 - 1e-6
                    or min(right-x, top-y) < program.child_min_side_m - 1e-6):
                raise ValueError("MASSING_UPPER_BEDROOM_DIMENSIONS")

    if "transferred_suite" in proposal:
        suite = TransferredSuite.model_validate(proposal["transferred_suite"])
        by_id = {room["id"]: room for room in upper}
        for request, room_id in ((suite.bedroom, "upper-master"), (suite.bathroom, "upper-master-wc")):
            clear = net_shape(by_id[room_id], thickness)
            if (by_id[room_id]["name"] != request.name or clear.is_empty
                    or clear.area < request.min_area-1e-6
                    or min(clear.bounds[2]-clear.bounds[0], clear.bounds[3]-clear.bounds[1]) < request.min_side-1e-6):
                raise ValueError("VERTICAL_TRANSFER_REQUIREMENTS_NOT_MET")

    doors, _ = inspect_upper(brief, upper, upper_connections(program.children))
    enclosed = [room for room in upper if room["kind"] != "terrace"]
    windows = [w for w, _ in level_windows(enclosed, doors, thickness)]
    if openings[1] != {"doors": doors, "windows": windows}:
        raise ValueError("MASSING_UPPER_OPENINGS_MISMATCH")

    grid = family_grid_profile(brief) if isinstance(brief, VillaBrief) else None
    if grid is not None:
        ground_axes = wall_axis_segments(ground+halls[0], openings[0]["doors"]+openings[0]["windows"], thickness)
        if (unsupported_grid_points(grid, ground_axes)
                or unsupported_grid_points(grid, wall_axis_segments(upper, doors+windows, thickness))
                or unsupported_grid_points(grid, wall_axis_segments([stair], [], thickness), roof_only=True)):
            raise ValueError("MASSING_FAMILY_GRID_MISMATCH")

    opening = upper_stair_opening(stair, thickness)
    cutout = Polygon(opening)
    clear_stair = net_shape(stair, thickness)
    landing = clear_stair.difference(cutout)
    approach = Point(inward(doors[0], stair, .65)).buffer(.30)
    if cutout.area <= 0 or not clear_stair.buffer(1e-6).covers(cutout) or not landing.buffer(1e-6).covers(approach):
        raise ValueError("MASSING_STAIR_OPENING_OR_LANDING_INVALID")
    slab_openings = [[], [opening]]
    if proposal.get("slab_openings_by_floor", slab_openings) != slab_openings:
        raise ValueError("MASSING_SLAB_OPENING_MISMATCH")
    return {
        **proposal, "rooms_by_floor": rooms, "halls_by_floor": halls,
        "opening_model_009": openings, "slab_openings_by_floor": slab_openings,
    }


def draw_level(space, rooms, doors, thickness, offset):
    ids = {room["id"]:room for room in rooms}
    enclosed = [room for room in rooms if room["kind"] != "terrace"]
    wall_band = unary_union([shape(room).buffer(thickness/2,join_style=2).difference(
                                  net_shape(room,thickness)) for room in enclosed])
    windows = level_windows(enclosed,doors,thickness)
    openings = doors+[window for window,_ in windows]
    walls = wall_band.difference(unary_union([cut(opening,thickness) for opening in openings]))
    def move(point):
        return point[0]+offset,point[1]
    def outline(line,layer):
        space.add_lwpolyline([move(q) for q in line.coords],dxfattribs={"layer":layer})
    boundary = walls.boundary
    for line in getattr(boundary,"geoms",[boundary]):
        outline(line,"WALL_FACES")
    for room in rooms:
        polygon = shape(room)
        marker = polygon.representative_point()
        space.add_mtext(room["name"],dxfattribs={"insert":move((marker.x,marker.y)),
                        "char_height":.2,"width":max(1,room["width"]-.35),"layer":"ROOM_LABELS"})
        if room["kind"] == "terrace":
            outline(polygon.exterior,"TERRACES")
        if room["kind"] == "stair":
            for a,b in u_treads(room,thickness):
                space.add_line(move(a),move(b),dxfattribs={"layer":"STAIR_CONCEPT"})
    for door in doors:
        target = ids[door["receiving_room"]]
        if door["connects"][0] == "stair-core" or target["kind"] == "terrace":
            continue
        for sector in leaf_swings(door,target,thickness):
            outline(sector.exterior,"OPENINGS")
    for _,points in windows:
        space.add_line(*map(move,points),dxfattribs={"layer":"WINDOWS"})


def export_family_stack(brief, archive_path, **upper_program):
    """Export the three coordinated plans together in one white R2010 DXF."""
    plan = build_family_stack(brief, **upper_program)
    brief = plan["brief"]
    with TemporaryDirectory() as folder:
        path = Path(folder)/"ANT-Clustered-family-stack-R2010.dxf"
        export_dxf(brief,plan["ground"],path)
        doc = ezdxf.readfile(path)
        doc.layers.new("TERRACES",dxfattribs={"color":7})
        doc.linetypes.new("ANT_AXIS",dxfattribs={"description":"Structural axes","pattern":[.6,.35,-.15,.02,-.08]})
        doc.layers.new("STRUCTURAL_GRID",dxfattribs={"color":7,"linetype":"ANT_AXIS"})
        doc.layers.new("STRUCTURAL_GRID_LABELS",dxfattribs={"color":7})
        doc.layers.new("SUPPORT_CANDIDATES",dxfattribs={"color":7})
        space = doc.modelspace()
        span = max(plan["footprint_metrics"]["width_m"],bbox.extents(space).size.x)+6
        for index,(rooms,doors) in enumerate(((plan["first"],plan["doors"]),(plan["roof"],[])),1):
            draw_level(space,rooms,doors,brief.wall_thickness,index*span)
        ground_rooms=plan["ground"]["rooms_by_floor"][0]+plan["ground"]["halls_by_floor"][0]
        bounds=unary_union(list(map(shape,ground_rooms+plan["first"]))).bounds
        if plan["structural_grid"] is not None:
            for index in range(3):
                draw_grid(space,plan["structural_grid"],bounds,index*span,roof_only=index==2)
        else:
            doc.layers.new("CONCEPT_MASSING",dxfattribs={"color":7})
            draw_concept_massing(space,[ground_rooms,plan["first"],plan["roof"]],
                                 plan["levels_m"],brief.floor_height,brief.wall_thickness,3*span)
            space.add_text("3D CONCEPT MASSING",
                           dxfattribs={"insert":(3*span,bounds[1]-3.5),"height":.45,"layer":"REVIEW_NOTES"})
            space.add_text("SITE NOT ASSESSED | PROGRAM CONCEPT",
                           dxfattribs={"insert":(0,bounds[1]-1.5),"height":.3,"layer":"REVIEW_NOTES"})
        for index,label in enumerate(("GROUND FLOOR","FIRST FLOOR","SECOND FLOOR - STAIR ENCLOSURE")):
            space.add_text(f"{label} | +{plan['levels_m'][index]:.2f} m",
                           dxfattribs={"insert":(index*span,-3.5),"height":.45,"layer":"REVIEW_NOTES"})
        doc.saveas(path)
        revised = ezdxf.readfile(path)
        if revised.dxfversion != "AC1024" or revised.units != 6 or revised.audit().errors:
            raise ValueError("Multilevel drawing failed DXF reopen checks")
        with ZipFile(archive_path,"w",ZIP_DEFLATED,compresslevel=9) as archive:
            archive.write(path,path.name)
    return plan


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("brief", type=Path, help="Ground-floor VillaBrief JSON")
    parser.add_argument("output", type=Path, help="Destination ZIP")
    parser.add_argument("--program-only",action="store_true",help="Compose without land dimensions or setbacks")
    parser.add_argument("--children", type=int, default=3)
    parser.add_argument("--child-area-m2", type=float, default=11.5)
    parser.add_argument("--child-min-side-m", type=float, default=2.7)
    arguments = parser.parse_args()
    brief_type=VillaProgram if arguments.program_only else VillaBrief
    result = export_family_stack(brief_type.model_validate_json(arguments.brief.read_text()), arguments.output,
        children=arguments.children, child_area_m2=arguments.child_area_m2,
        child_min_side_m=arguments.child_min_side_m)
    print(json.dumps({key:result[key] for key in (
        "levels_m","upper_covered_by_ground_m2","upper_enclosed_m2","upper_search","structural_grid","site_status","footprint_metrics")}))
