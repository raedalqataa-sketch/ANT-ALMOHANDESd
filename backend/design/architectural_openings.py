"""Independent opening geometry and access checks adapted from ANT-ALMOHANDES-ENGINE.

Source: dev/unified-core at 535590e607b2b448e6434cf279a28ec7c3994cde,
engine/validate.py. The residential model stores wall centrelines and net
rectangles, so a host face can be offset by half the wall thickness.
"""
import math
from collections import defaultdict
from itertools import combinations

import networkx as nx
from shapely.geometry import LineString

EXTERIOR_IDS = frozenset({"EXTERIOR", "OUTSIDE"})
DISTANCE_TOLERANCE_M = 1e-5


def _aperture(opening, wall, hosts):
    """Return the full aperture segment if it lies on its wall and hosts."""
    axes = {"horizontal": 0, "vertical": 1}
    along = axes[wall["axis"]]
    normal = 1 - along
    start, end = wall["start"], wall["end"]
    center = opening["center"]
    width = opening["width"]
    thickness = wall["thickness"]
    values = (*start, *end, *center, width, thickness)
    if not all(math.isfinite(value) for value in values) or width <= 0 or thickness < 0:
        raise ValueError("invalid_dimensions")

    tolerance = DISTANCE_TOLERANCE_M
    low, high = center[along] - width / 2, center[along] + width / 2
    fixed = start[normal]
    wall_low, wall_high = sorted((start[along], end[along]))
    if (abs(end[normal] - fixed) > tolerance or abs(center[normal] - fixed) > tolerance
            or low < wall_low - tolerance or high > wall_high + tolerance):
        raise ValueError("off_wall")

    sides = []
    for shape in hosts:
        bounds = shape.bounds
        if low < bounds[along] - tolerance or high > bounds[along + 2] + tolerance:
            raise ValueError("off_room_face")
        if abs(bounds[normal] - fixed) <= thickness / 2 + tolerance and shape.centroid.coords[0][normal] > fixed:
            sides.append(1)
        elif abs(bounds[normal + 2] - fixed) <= thickness / 2 + tolerance and shape.centroid.coords[0][normal] < fixed:
            sides.append(-1)
        else:
            raise ValueError("off_room_face")
    if len(sides) == 2 and sides[0] == sides[1]:
        raise ValueError("hosts_on_same_side")

    a, b = list(center), list(center)
    a[along], b[along] = low, high
    a[normal] = b[normal] = fixed
    return LineString([a, b])


def inspect_openings(floor, shapes, corridor_graph):
    """Build routes from verified apertures and established corridor contacts."""
    walls = {wall["id"]: wall for wall in floor["walls"]}
    issues = defaultdict(set)
    by_wall = defaultdict(list)
    valid = []
    for opening in floor.get("openings", []):
        identifier = opening["id"]
        if opening.get("kind") not in {"door", "passage", "window"}:
            continue
        try:
            wall = walls[opening["wall_id"]]
            connected = opening["connects"]
            hosts = [rid for rid in connected if rid not in EXTERIOR_IDS]
            if (len(connected) != 2 or len(set(connected)) != 2 or not hosts
                    or any(rid not in shapes or rid not in wall["room_ids"] for rid in hosts)
                    or (len(hosts) == 1) != wall["exterior"]):
                raise ValueError("invalid_hosts")
            segment = _aperture(opening, wall, [shapes[rid] for rid in hosts])
        except (KeyError, TypeError, IndexError, ValueError) as error:
            issues[identifier].add(str(error) if isinstance(error, ValueError) else "invalid_geometry")
            continue
        if any(segment.intersection(shape).length > DISTANCE_TOLERANCE_M
               for rid, shape in shapes.items() if rid not in hosts):
            issues[identifier].add("blocked_by_room")
        by_wall[wall["id"]].append((identifier, segment))
        valid.append((opening, hosts))

    for openings in by_wall.values():
        for (a_id, a), (b_id, b) in combinations(openings, 2):
            if a.intersection(b).length > DISTANCE_TOLERANCE_M:
                issues[a_id].add("overlapping_aperture")
                issues[b_id].add("overlapping_aperture")

    graph = corridor_graph.copy()
    guest_graph = corridor_graph.copy()
    entries, guest_entries = set(), set()
    for opening, hosts in valid:
        if opening["id"] in issues or opening["kind"] == "window":
            continue
        guest_access = opening.get("access_control") != "family_only"
        if len(hosts) == 2:
            graph.add_edge(*hosts)
            if guest_access:
                guest_graph.add_edge(*hosts)
        elif floor.get("id") == "GF" and opening["kind"] == "door":
            entries.update(hosts)
            if guest_access and opening.get("guest_entry"):
                guest_entries.update(hosts)

    if floor.get("id") != "GF":
        entries.update(room["id"] for room in floor["rooms"]
                       if room.get("kind") == "stair" and room["id"] in graph)

    def reached(network, sources):
        return {room for source in sources for room in nx.node_connected_component(network, source)}

    requested = {room["id"] for room in floor["rooms"] if room.get("request_id")}
    guest_rooms = {room["id"] for room in floor["rooms"]
                   if room.get("zone") == "guest" and room["id"] in graph}
    declared_guest_entry = any(opening.get("guest_entry") for opening in floor.get("openings", []))
    privacy = None
    if floor.get("id") == "GF" and declared_guest_entry:
        guest_reachable = reached(guest_graph, guest_entries)
        guest_only = reached(guest_graph.subgraph(guest_rooms), guest_entries & guest_rooms)
        protected = {room["id"] for room in floor["rooms"]
                     if room.get("zone") in {"family", "private", "service"}}
        privacy = {
            "verified_guest_entry_rooms": sorted(guest_entries),
            "guest_rooms_without_guest_only_route": sorted(guest_rooms - guest_only),
            "protected_rooms_reachable": sorted(guest_reachable & protected),
        }

    return {
        "opening_issues": [{"opening_id": key, "reasons": sorted(values)}
                           for key, values in sorted(issues.items())],
        "verified_entry_rooms": sorted(entries),
        "requested_rooms_without_verified_route": sorted(requested - reached(graph, entries)),
        "guest_privacy": privacy,
    }
