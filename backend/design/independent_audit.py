"""Independent geometry and door-graph audit for V4 residential candidates.

Uses GEOS/Shapely and NetworkX independently from the generator's rectangle and
raster validators. Only *measurable* geometric overlaps/out-of-bounds are hard
failures. Graph findings are evidence for review, not legal egress approval.
"""
import math
from itertools import combinations

import networkx as nx
from shapely.geometry import box as polygon_box

AREA_TOLERANCE_M2 = 1e-5
EXTERIOR_IDS = frozenset({"EXTERIOR", "OUTSIDE"})


def _rect(entity):
    x, y, width, depth = (float(entity[k]) for k in ("x", "y", "width", "depth"))
    if not all(math.isfinite(v) for v in (x, y, width, depth)) or min(width, depth) <= 0:
        raise ValueError("non-finite or nonpositive rectangle")
    return polygon_box(x, y, x + width, y + depth)


def inspect(model):
    """Return serializable measured evidence. Does not mutate the input model."""
    floor_reports = []
    for floor in model.get("floors", []):
        rooms = floor.get("rooms", [])
        shapes = {}
        invalid = []
        duplicates = []
        for room in rooms:
            identifier = room.get("id")
            if not identifier or identifier in shapes:
                duplicates.append(str(identifier))
                continue
            try:
                shapes[identifier] = _rect(room)
            except (ValueError, TypeError, KeyError, OverflowError):
                invalid.append(str(identifier))

        collisions = []
        for a, b in combinations(sorted(shapes), 2):
            overlap = shapes[a].intersection(shapes[b]).area
            if overlap > AREA_TOLERANCE_M2:
                collisions.append({"room_ids": [a, b], "overlap_m2": round(overlap, 6)})

        outside = []
        envelope = model.get("footprint", {})
        try:
            site = _rect(envelope)
        except (KeyError, TypeError, ValueError, OverflowError):
            site = None
            invalid.append("footprint")
        if site is not None:
            for rid, shape in shapes.items():
                excess = shape.difference(site).area
                if excess > AREA_TOLERANCE_M2:
                    outside.append({"room_id": rid, "outside_envelope_m2": round(excess, 6)})

        door_graph = nx.Graph()
        door_graph.add_nodes_from(sorted(shapes))
        entry_room_ids = set()
        for opening in floor.get("openings", []):
            if opening.get("kind") not in ("door", "passage"):
                continue
            connected = opening.get("connects") or []
            internal = sorted(set(connected) & door_graph.nodes)
            if len(internal) == 2:
                door_graph.add_edge(*internal)
            if any(v in EXTERIOR_IDS for v in connected):
                entry_room_ids.update(internal)

        # Upper floors are entered through their physical stair core rather than
        # a ground-level exterior opening. Mark it as a graph source only.
        if floor.get('id') != 'GF':
            entry_room_ids.update(r['id'] for r in rooms
                                  if r.get('kind') == 'stair' and r.get('id') in shapes)

        # Corridor cells touch across full edges without a door; this is a
        # *topology* edge only and not proof of an unobstructed real-life route.
        halls = [r for r in rooms if r.get("kind") == "corridor" and r.get("id") in shapes]
        for a, b in combinations(halls, 2):
            boundary = shapes[a["id"]].boundary.intersection(shapes[b["id"]].boundary)
            if boundary.length > 0.60:
                door_graph.add_edge(a["id"], b["id"], kind="corridor_contact")

        accessible = set()
        for source in entry_room_ids:
            accessible.update(nx.node_connected_component(door_graph, source))
        requested = sorted(r["id"] for r in rooms if r.get("request_id") and r["id"] in shapes)
        unreachable = sorted(set(requested) - accessible)
        floor_reports.append({
            "floor": floor.get("id"),
            "room_count": len(rooms),
            "invalid_rectangles": invalid,
            "duplicate_room_ids": duplicates,
            "intersections": collisions,
            "outside_envelope": outside,
            "measured_area_m2": round(sum(s.area for s in shapes.values()), 4),
            "graph_nodes": door_graph.number_of_nodes(),
            "graph_edges": door_graph.number_of_edges(),
            "graph_components": nx.number_connected_components(door_graph),
            "entry_room_ids": sorted(entry_room_ids),
            "requested_rooms_without_entry_graph_route": unreachable,
        })
    fail = any(
        row["invalid_rectangles"] or row["duplicate_room_ids"]
        or row["intersections"] or row["outside_envelope"]
        for row in floor_reports
    )
    review = any(row["requested_rooms_without_entry_graph_route"] for row in floor_reports)
    return {
        "revision": "geos-networkx-crosscheck-1",
        "status": "FAIL" if fail else "PASS",
        "requires_circulation_review": review,
        "floors": floor_reports,
        "scope": "GEOS area/containment plus door and corridor-contact graph; not a fire, acoustic, visual or accessible-route certification",
    }
