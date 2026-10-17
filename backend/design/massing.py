"""Concept-stage nonrectangular building-envelope exploration.

Returns proposed massing only, NOT validated rooms, wall segments or floor plans.
A polygon is assembled from axis-aligned rectangles using a local grid, so no
geometry library is required. A proposed cutout may become a courtyard or
recess only after light, ventilation, circulation and code review.
"""


def _boundary(rectangles):
    xs = sorted({x for r in rectangles for x in (r[0], r[0] + r[2])})
    ys = sorted({y for r in rectangles for y in (r[1], r[1] + r[3])})
    occupied = {(i, j) for i in range(len(xs)-1) for j in range(len(ys)-1)
                if any(r[0] <= xs[i] and xs[i+1] <= r[0]+r[2] and
                       r[1] <= ys[j] and ys[j+1] <= r[1]+r[3] for r in rectangles)}
    area = sum((xs[i+1]-xs[i])*(ys[j+1]-ys[j]) for i,j in occupied)
    return round(area, 4)


def propose_massing(site_width, site_depth, origin_x, origin_y, width, depth):
    """Produce bounded rectangular, L, U and stepped envelopes.

    Dimensions are proposals, never assumed statutory setbacks. Each envelope
    consists of nonoverlapping rectangles for later geometry construction.
    """
    if min(site_width, site_depth, width, depth) <= 0:
        raise ValueError("All dimensions must be positive")
    if origin_x < 0 or origin_y < 0 or origin_x+width > site_width or origin_y+depth > site_depth:
        raise ValueError("Envelope must remain inside the supplied plot")
    wing = round(max(2.8, min(width, depth) * .30), 3)
    notch_w = round(width-wing, 3)
    notch_d = round(depth-wing, 3)
    middle = round(width-2*wing, 3)
    variants = [
        ("RECTANGULAR", [(origin_x,origin_y,width,depth)]),
        ("L_SHAPE", [(origin_x,origin_y,wing,depth),
                     (origin_x+wing,origin_y,notch_w,wing)]),
        ("U_SHAPE", [(origin_x,origin_y,wing,depth),
                     (origin_x+wing,origin_y,notch_w,wing),
                     (origin_x+width-wing,origin_y+wing,wing,notch_d)]),
        ("STEPPED", [(origin_x,origin_y,width,wing),
                     (origin_x,origin_y+wing,width-wing,notch_d)]),
    ]
    result = []
    for name, rects in variants:
        if any(w <= 0 or d <= 0 for _,_,w,d in rects):
            continue
        if name == "U_SHAPE" and middle <= 1.8:
            continue
        if name == "STEPPED" and width-wing <= 1.8:
            continue
        area = _boundary(rects)
        if area <= 0:
            continue
        result.append({
            "family": name,
            "rectangles": [{"x":x,"y":y,"width":w,"depth":d} for x,y,w,d in rects],
            "envelope_area_m2": area,
            "status": "CONCEPT_UNVALIDATED",
            "requires": ["functional_program", "room_geometry", "circulation",
                         "privacy", "external_openings", "local_regulations",
                         "plot_boundaries_and_access", "structural_feasibility"],
        })
    return result
