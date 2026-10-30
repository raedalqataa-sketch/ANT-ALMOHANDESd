"""Independent, non-mutating measurements for draft residential candidates.

Opt-in audit utility; does not change generator ranking or approved drawings.
"""
from __future__ import annotations

import math
from shapely.geometry import box
from shapely.ops import unary_union


def _rect(record):
    vals = [float(record[k]) for k in ("x", "y", "width", "depth")]
    if not all(math.isfinite(v) for v in vals) or vals[2] <= 0 or vals[3] <= 0:
        raise ValueError("invalid rectangle")
    x, y, w, h = vals
    return box(x, y, x + w, y + h)


def audit_floor(floor, footprint, *, pocket_threshold_m2=0.5, ratio_review=1.8):
    """Return measured geometry and review flags; never claim legal compliance.

    Footprint is an explicit rectangular *interior measurement envelope*.
    Leftover polygons may contain walls or other intentional areas and are
    REVIEW evidence only, not automatically 'waste'.
    """
    if pocket_threshold_m2 < 0 or ratio_review < 1:
        raise ValueError("invalid thresholds")
    boundary = _rect(footprint)
    rooms = floor.get("rooms", [])
    shapes = {}
    ratios = []
    invalid = []
    for i, room in enumerate(rooms):
        rid = str(room.get("id") or f"missing-{i}")
        if rid in shapes:
            invalid.append({"room_id": rid, "reason": "DUPLICATE_ID"})
            continue
        try:
            shape = _rect(room)
        except (KeyError, TypeError, ValueError, OverflowError):
            invalid.append({"room_id": rid, "reason": "INVALID_GEOMETRY"})
            continue
        shapes[rid] = shape
        w, d = float(room["width"]), float(room["depth"])
        ratio = max(w, d) / min(w, d)
        if ratio > ratio_review:
            ratios.append({"room_id": rid, "ratio": round(ratio, 3),
                           "status": "REVIEW_FURNITURE_FIT"})
    # Real generated layouts include corridor cells that are not in rooms.
    cells = floor.get("cells", [])
    cell_shapes = []
    invalid_cells = []
    for i, cell in enumerate(cells):
        try:
            cell_shapes.append((cell, _rect(cell)))
        except (KeyError, TypeError, ValueError, OverflowError):
            invalid_cells.append(i)
    coverage = list(shapes.values()) + [p for _, p in cell_shapes]
    occupied = unary_union(coverage) if coverage else boundary.difference(boundary)
    corridors = [shapes[str(r.get("id"))] for r in rooms
                 if r.get("kind") == "corridor" and str(r.get("id")) in shapes]
    corridors += [p for c, p in cell_shapes if c.get("kind") == "corridor"]
    corridor = unary_union(corridors) if corridors else boundary.difference(boundary)
    overlaps = []
    keys = list(shapes)
    for i, a in enumerate(keys):
        for b in keys[i+1:]:
            area = shapes[a].intersection(shapes[b]).area
            if area > 1e-5:
                overlaps.append({"rooms": [a, b], "area_m2": round(area, 4)})
    outside = [{"room_id": rid, "area_m2": round(poly.difference(boundary).area, 4)}
               for rid, poly in shapes.items()
               if poly.difference(boundary).area > 1e-5]
    leftover = boundary.difference(occupied)
    parts = list(leftover.geoms) if hasattr(leftover, "geoms") else [leftover]
    pockets = [{"area_m2": round(p.area, 4),
                "bounds": [round(v, 4) for v in p.bounds]}
               for p in parts if p.area > pocket_threshold_m2]
    return {
        "floor": floor.get("id"),
        "measurement_envelope_m2": round(boundary.area, 4),
        "room_union_m2": round(occupied.intersection(boundary).area, 4),
        "room_area_sum_m2": round(sum(p.area for p in shapes.values()), 4),
        "corridor_union_m2": round(corridor.intersection(boundary).area, 4),
        "leftover_m2": round(leftover.area, 4),
        "leftover_review_regions": pockets,
        "elongated_room_reviews": ratios,
        "invalid_rooms": invalid,
        "invalid_cells": invalid_cells,
        "corridor_geometry_source": "rooms_and_cells" if cells else "rooms_only",
        "room_overlaps": overlaps,
        "rooms_outside_envelope": outside,
        "status": "INVALID_GEOMETRY" if invalid or invalid_cells or overlaps or outside else
                  "REVIEW" if pockets or ratios else "MEASURED",
        "limitations": [
            "Leftover area includes possible wall thickness and intentional voids",
            "Room ratio is a design-review heuristic, not a building-code limit",
            "Does not validate door paths, furniture, light, ventilation, or privacy",
        ],
    }
