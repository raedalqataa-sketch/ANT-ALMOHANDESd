"""Measure the space immediately outside already generated external windows."""
from shapely.geometry import box
from shapely.ops import unary_union


def inspect_window_clearance(model, depth_m=0.61):
    """Find same-level room solids in an outward strip of the actual opening.

    Inspired by the 012 relationship-first clearance screen. This review
    estimates local obstruction only; spaces outside this design are unknown.
    """
    rows = []
    for floor in model["floors"]:
        walls = {wall["id"]: wall for wall in floor["walls"]}
        rooms = {room["id"]: room for room in floor["rooms"]}
        solids = [box(r["x"], r["y"], r["x"] + r["width"], r["y"] + r["depth"])
                  for r in rooms.values()]
        occupancy = unary_union(solids)
        for opening in floor["openings"]:
            if opening["kind"] != "window" or "OUTSIDE" not in opening["connects"]:
                continue
            wall = walls.get(opening["wall_id"])
            room = next((rooms[rid] for rid in opening["connects"] if rid in rooms), None)
            axis = wall.get("axis") if wall else None
            if not room or not wall or not wall.get("exterior") or axis not in {"horizontal", "vertical"}:
                rows.append({"opening": opening["id"], "status": "not_measured"})
                continue
            x, y = opening["center"]
            along = opening.get("clear_width", opening["width"]) / 2
            half_wall = wall["thickness"] / 2
            if axis == "vertical":
                sign = -1 if room["x"] + room["width"] / 2 > x else 1
                a, b = sorted((x + sign * half_wall, x + sign * (half_wall + depth_m)))
                strip = box(a, y - along, b, y + along)
            else:
                sign = -1 if room["y"] + room["depth"] / 2 > y else 1
                a, b = sorted((y + sign * half_wall, y + sign * (half_wall + depth_m)))
                strip = box(x - along, a, x + along, b)
            overlap = strip.intersection(occupancy).area
            rows.append({"opening": opening["id"], "floor": floor["id"],
                         "status": "review_obstruction" if overlap > 1e-5 else "no_modelled_obstruction",
                         "obstructed_m2": round(overlap, 5)})
    return {"depth_m": depth_m, "windows": rows}
