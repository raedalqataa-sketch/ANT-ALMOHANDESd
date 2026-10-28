"""Architecture-first, furniture-free layout quality and composition.

All checks operate on allocated geometric rectangles *before* wall/door/window
symbols and furnishings exist. Therefore an exposed facade is only potential,
never proof of compliant natural daylight or operable ventilation. Advisory
aspect thresholds are internal design guidance, NOT statutory limits.
"""
from __future__ import annotations

import math

EPS=1e-6
DIRECT_EXTERIOR_KINDS=frozenset(("bedroom","master","kitchen","bathroom"))
# (preferred maximum, hard preliminary limit) — design policy, not legal code.
ASPECTS={
    "bedroom":(1.65,2.20),
    "master":(1.70,2.20),
    "majlis":(1.75,2.30),
    "living":(1.90,2.50),
    "dining":(1.80,2.35),
    "kitchen":(1.80,2.35),
    "bathroom":(2.40,3.25),
    "office":(1.85,2.35),
    "laundry":(2.50,3.50),
    "storage":(2.50,3.50),
}


def _num(value):
    return type(value) in (int,float) and math.isfinite(value) and value>=0


def _bounds(rect):
    return (rect["x"],rect["y"],rect["x"]+rect["width"],rect["y"]+rect["depth"])


def shared_edge(a,b):
    """Length of shared orthogonal boundary; corner contacts count as zero."""
    ax0,ay0,ax1,ay1=_bounds(a)
    bx0,by0,bx1,by1=_bounds(b)
    if abs(ax1-bx0)<=EPS or abs(ax0-bx1)<=EPS:
        return max(0.,min(ay1,by1)-max(ay0,by0))
    if abs(ay1-by0)<=EPS or abs(ay0-by1)<=EPS:
        return max(0.,min(ax1,bx1)-max(ax0,bx0))
    return 0.


def _uncovered_length(lo,hi,covered):
    # Union of blocked intervals, accounting for partially shared walls.
    spans=sorted((max(lo,a),min(hi,b)) for a,b in covered if min(hi,b)>max(lo,a)+EPS)
    merged=[] 
    for a,b in spans:
        if merged and a<=merged[-1][1]+EPS:
            merged[-1]=(merged[-1][0],max(b,merged[-1][1]))
        else:
            merged.append((a,b))
    # A usable facade opening needs one continuous clear run, not the
    # sum of several narrow unrelated gaps between neighboring rooms.
    free=[]
    cursor=lo
    for a,b in merged:
        if a>cursor+EPS:free.append(a-cursor)
        cursor=max(cursor,b)
    if hi>cursor+EPS:free.append(hi-cursor)
    return max(free,default=0.)


def facade_exposure(room,others):
    """Potential straight exterior boundary in metres, never confirmed window."""
    x0,y0,x1,y1=_bounds(room)
    widths=[]
    for axis,fixed,lo,hi in (("x",x0,y0,y1),("x",x1,y0,y1),
                             ("y",y0,x0,x1),("y",y1,x0,x1)):
        intervals=[]
        for other in others:
            if other is room:continue
            ox0,oy0,ox1,oy1=_bounds(other)
            if axis=="x" and (abs(ox0-fixed)<=EPS or abs(ox1-fixed)<=EPS):
                intervals.append((oy0,oy1))
            if axis=="y" and (abs(oy0-fixed)<=EPS or abs(oy1-fixed)<=EPS):
                intervals.append((ox0,ox1))
        widths.append(_uncovered_length(lo,hi,intervals))
    return max(widths) if widths else 0.


def architectural_profile(room,lane,t):
    """Choose a room-sized width within a wing without occupying its full strip.

    The room remains anchored on the hallway-facing edge. Freed side width is
    treated as an OUTDOOR MASSING RECESS, not automatically expanded into other
    rooms. No furniture or rendered objects participate in this decision.
    """
    available=lane['width' if lane['axis']=='y' else 'depth']-t
    minimum=room.get('min_side',0)
    if available+EPS<minimum or available<=EPS:return None
    if room.get('guest_distributor'):
        return {'gross_cross':available+t,'gross_length':minimum+t,
                'source':'full_width_guest_distributor'}
    requested=room.get('min_area')
    if not _num(requested) or requested<=0 or minimum<=0:return None
    soft,hard=ASPECTS.get(room.get('kind'),(2.,2.7))
    ideal=math.sqrt(requested)
    values={available,minimum}
    for multiplier in (.8,.9,1.,1.08,1.2,1.35,1.5):
        values.add(ideal*multiplier)
    candidates=[]
    for net_width in sorted(values):
        if net_width<minimum-EPS or net_width>available+EPS:continue
        net_depth=max(minimum,requested/net_width)
        ratio=max(net_width,net_depth)/min(net_width,net_depth)
        if ratio>hard+EPS:continue
        net_area=net_width*net_depth
        if net_area>requested*1.40+EPS:continue
        excess=max(0.,net_area/requested-1.)
        score=(max(0.,ratio-soft)**2*30.0 + excess*8.0 +
               .07*(available-net_width) + .045*net_depth)
        candidates.append((score,net_depth,net_width))
    if not candidates:return None
    _,net_depth,net_width=min(candidates)
    return {'gross_cross':net_width+t,'gross_length':net_depth+t,
            'net_cross':net_width,'net_length':net_depth,
            'source':'request_sized_architectural_wing_recess'}


def architectural_length(room,lane,t):
    profile=architectural_profile(room,lane,t)
    return profile['gross_length'] if profile else math.inf


def limit_growth(room,lane,t,base,proposed_growth,*,area_factor=1.08):
    """Prevent unused wing capacity from silently bloating customer rooms."""
    if not room.get('request_id') or room.get('guest_distributor'):
        return 0.
    profile=architectural_profile(room,lane,t)
    if profile is None:return 0.
    cross=profile['net_cross']
    requested=room['min_area']
    allowed=max(0.,requested*area_factor/cross+t-base)
    return min(max(0.,proposed_growth),allowed)


def assess_layout(layout,t,*,facade_clear_m=.90):
    """Architectural assessment only: hard program/facade/adjacency warnings.

    A failure means this PRELIMINARY topology is unsuitable for advancement,
    not that a construction code has been infringed.
    """
    floors=layout.get('floors',[])
    halls_by_floor=layout.get('halls_by_floor',[])
    issues=[];rooms_evidence=[];total_halls=0.;total_gross=0.;ratio_penalty=0.
    excessive_penalty=0.;elongated_halls=0
    for fi,cells in enumerate(floors):
        halls=halls_by_floor[fi] if fi<len(halls_by_floor) else []
        all_rects=list(cells)+list(halls)
        total_gross+=sum(r['width']*r['depth'] for r in all_rects)
        total_halls+=sum(r['width']*r['depth'] for r in halls) + sum(r['width']*r['depth'] for r in cells if r.get('guest_distributor'))
        elongated_halls+=sum(max(h['width'],h['depth'])>6.0 and
                             max(h['width'],h['depth'])/max(min(h['width'],h['depth']),.1)>3.
                             for h in halls)
        # Search topology hallway rectangles have no 'kind' field until
        # materialization. Treat halls_by_floor as corridor geometry directly.
        corridors=list(halls)+[r for r in cells if r.get('kind')=='corridor']
        for room in cells:
            if not room.get('request_id'):continue
            width,depth=room['width']-t,room['depth']-t
            rid=room.get('id','UNNAMED')
            if min(width,depth)<=EPS:
                issues.append({'floor':fi,'room_id':rid,'reason':'INVALID_NET_DIMENSIONS'})
                continue
            kind=room['kind'];net_area=width*depth
            requested=room.get('min_area')
            if not _num(requested) or net_area+EPS<requested:
                issues.append({'floor':fi,'room_id':rid,'reason':'BELOW_CLIENT_MIN_AREA'})
            if min(width,depth)+EPS<room.get('min_side',0):
                issues.append({'floor':fi,'room_id':rid,'reason':'BELOW_CLIENT_MIN_SIDE'})
            aspect=max(width,depth)/min(width,depth)
            soft,hard=ASPECTS.get(kind,(2.,2.7))
            if aspect>hard+EPS:
                issues.append({'floor':fi,'room_id':rid,'reason':'ROOM_TOO_ELONGATED'})
            ratio_penalty+=max(0.,aspect-soft)**2
            if _num(requested):
                excessive_penalty+=max(0.,net_area-1.12*requested)
            facade=facade_exposure(room,all_rects)
            if kind in DIRECT_EXTERIOR_KINDS and facade+EPS<facade_clear_m:
                issues.append({'floor':fi,'room_id':rid,'reason':'NO_DIRECT_EXTERIOR_FACADE_POTENTIAL'})
            # Shared wall long enough for an eventual door, before actual
            # door placement; guest rooms must meet a guest distributor.
            possible=[hall for hall in corridors if shared_edge(room,hall)>=.90]
            if room.get('zone')=='guest' and room.get('guest_vestibule'):
                possible=[h for h in possible if h.get('guest_distributor')]
            if not possible:
                issues.append({'floor':fi,'room_id':rid,'reason':'NO_CORRIDOR_CONNECTION_POTENTIAL'})
            rooms_evidence.append({'floor':fi,'room_id':rid,'kind':kind,
                                   'net_area_m2':round(net_area,3),
                                   'aspect_ratio':round(aspect,3),
                                   'exposed_facade_potential_m':round(facade,3),
                                   'corridor_contact_potential':bool(possible)})
    if not floors:
        issues.append({'reason':'NO_FLOORS'})
    movement_share=total_halls/max(total_gross,EPS)
    # No assumption that hallway rectangles equal union-of-physical-walkways.
    score=(total_gross+2.*excessive_penalty+35.*ratio_penalty+
           1.3*total_halls+9.*elongated_halls+1000.*len(issues))
    return {'status':'ARCHITECTURAL_REVIEW' if issues else 'PRELIMINARY_GEOMETRY_ELIGIBLE',
            'hard_issues':issues,'rooms':rooms_evidence,
            'gross_rectangles_m2':round(total_gross,3),
            'hall_rectangle_area_m2':round(total_halls,3),
            'hall_rectangle_fraction':round(movement_share,4),
            'hall_rectangles_long_count':elongated_halls,
            'space_excess_m2':round(excessive_penalty,3),
            'proportion_penalty':round(ratio_penalty,5),
            'architecture_score':round(score,5),
            'furniture_used':False,'windows_verified':False,
            'external_facade_only_potential':True,
            'legal_compliance_certified':False}


def spatial_signature(layout):
    """Coarse position/connectivity fingerprint for non-identical proposals."""
    pts=[]
    for fi,cells in enumerate(layout.get('floors',[])):
        active=[r for r in cells if r.get('request_id')]
        if not active:continue
        x0=min(r['x'] for r in active)
        x1=max(r['x']+r['width'] for r in active)
        y0=min(r['y'] for r in active)
        y1=max(r['y']+r['depth'] for r in active)
        for r in active:
            cx=(r['x']+r['width']/2-x0)/max(x1-x0,EPS)
            cy=(r['y']+r['depth']/2-y0)/max(y1-y0,EPS)
            pts.append((fi,r['kind'],r.get('request_id'),
                        min(3,int(cx*4)),min(3,int(cy*4))))
    return tuple(sorted(pts))


def compose_architecture(brief,*,families=("adaptive","freeform","cluster","cross","spine","meander"),
                         max_options=3):
    """Generate preliminary geometries without furniture, PDF, DXF, or V4.

    This is the distinct architectural IDEA stage; final door, staircase,
    natural ventilation, visual privacy, and legal checks remain mandatory
    at later release gates.
    """
    from backend.design.general_engine import search
    options=[];signatures=set();failed=[]
    for family in families:
        try:
            layout=search(brief,family,policy='relationship_aware',
                          architecture_first=True)
        except (ValueError,ZeroDivisionError,OverflowError) as exc:
            failed.append({'family':family,'reason':type(exc).__name__})
            continue
        if not layout:
            # Diagnostic-only legacy search: reveal WHY the stricter
            # architectural composition was rejected, without accepting it.
            baseline=search(brief,family,policy='relationship_aware',
                            architecture_first=False)
            if baseline:
                quality=assess_layout(baseline,brief.wall_thickness)
                reasons=sorted({item['reason'] for item in quality['hard_issues']})
                failed.append({'family':family,'reason':'NO_FEASIBLE_TOPOLOGY',
                               'legacy_candidate_rejected_for':reasons,
                               'legacy_issues_count':len(quality['hard_issues'])})
            else:
                failed.append({'family':family,'reason':'NO_FEASIBLE_TOPOLOGY',
                               'legacy_candidate_available':False})
            continue
        candidates=[layout]+layout.get('alternatives',[])
        for row in candidates:
            quality=row.get('architectural_quality') or assess_layout(row,brief.wall_thickness)
            if quality['hard_issues']:continue
            signature=spatial_signature(row)
            if signature in signatures:continue
            signatures.add(signature)
            options.append((quality['architecture_score'],family,row,quality))
    options.sort(key=lambda obj:obj[0])
    proposals=[]
    used_families=set()
    # Prefer genuinely different geometric families, not 3 perturbations
    # of the same corridor template.
    for score,family,row,quality in options:
        if family in used_families:continue
        used_families.add(family)
        proposals.append({'family':family,'quality':quality,
                          # Display the reserved stair and guest distributor.
                          # Omitting them gave a misleading impression of
                          # disconnected rooms in previously generated SVGs.
                          'rooms_by_floor':[[dict(r) for r in rooms if
                              r.get('request_id') or r.get('guest_distributor')
                              or r.get('kind')=='stair']
                              for rooms in row['floors']],
                          'halls_by_floor':row['halls_by_floor'],
                          'structural_signature':str(spatial_signature(row))})
        if len(proposals)>=max_options:break
    return {'status':'PRELIMINARY_NOT_FOR_CONSTRUCTION',
            'requested_count':max_options,'generated_count':len(proposals),
            'options':proposals,'unavailable_families':failed,
            'stage':'ARCHITECTURAL_COMPOSITION_ONLY',
            'furniture_generated':False,'doors_generated':False,
            'windows_generated':False,'legal_approval':False}
