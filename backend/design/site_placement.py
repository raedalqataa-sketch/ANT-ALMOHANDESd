"""Rear-corner siting of a compact mass inside the existing legal buildable envelope."""
import math

EPS=1e-5
OPPOSITE={'north':'south','south':'north','east':'west','west':'east'}
FACE_AR={'north':'الشمال','south':'الجنوب','east':'الشرق','west':'الغرب'}

def bounds(cells,pad=0):
    return (min(c['x'] for c in cells)-pad,min(c['y'] for c in cells)-pad,
            max(c['x']+c['width'] for c in cells)+pad,max(c['y']+c['depth'] for c in cells)+pad)

def alternatives(brief,layout,group):
    if brief.site_placement=='legacy':return [layout]
    floors=layout['floors'];halls=layout.get('halls_by_floor',[layout['halls']]*len(floors))
    cells=[r for floor,hh in zip(floors,halls) for r in floor+hh]
    # Gross cells gain half a wall on both edges when materialized.
    x0,y0,x1,y1=bounds(cells);w=x1-x0+brief.wall_thickness;d=y1-y0+brief.wall_thickness
    left=brief.setbacks.west;top=brief.setbacks.north
    right=brief.plot_width-brief.setbacks.east;bottom=brief.plot_depth-brief.setbacks.south
    horizontal=brief.entrance_face in ('north','south')
    front_extra=(bottom-top-d) if horizontal else (right-left-w)
    side_extra=(right-left-w) if horizontal else (bottom-top-d)
    envelope_ratio=w*d/((right-left)*(bottom-top))
    spacious=front_extra>=3-EPS and side_extra>=2-EPS and envelope_ratio<=.8+EPS
    if not spacious:
        return [{**layout,'placement_group':group,'site_placement':{'active':False,'reason':'insufficient_front_or_side_surplus','front_extra_m':front_extra,'side_extra_m':side_extra,'envelope_ratio':envelope_ratio}}]
    rear=OPPOSITE[brief.entrance_face];sides=('west','east') if horizontal else ('north','south')
    variants=[]
    for side in sides:
        anchors=[rear,side]
        target_x=left if 'west' in anchors else right-w
        target_y=top if 'north' in anchors else bottom-d
        variants.append({**layout,'origin_x':target_x-x0,'origin_y':target_y-y0,'placement_group':group,
            'site_placement':{'active':True,'strategy':'rear-corner-1','anchor_faces':anchors,'rear_face':rear,'front_face':brief.entrance_face,
            'front_extra_m':front_extra,'side_extra_m':side_extra,'envelope_ratio':envelope_ratio,
            'spacious_rule':{'min_extra_front_m':3,'min_extra_side_m':2,'max_envelope_ratio':.8,'status':'design heuristic, not a Saudi legal limit'},
            'other_corner_compared':True,'setbacks_waived':False}})
    return variants

def evidence(model,brief,requested):
    result=dict(requested)
    if not result.get('active'):return result
    points=[p for polys in model['footprint']['polygons_by_floor'].values() for poly in polys for p in poly]
    x0=min(p[0] for p in points);x1=max(p[0] for p in points);y0=min(p[1] for p in points);y1=max(p[1] for p in points)
    result['building_bounds']=[x0,y0,x1,y1]
    result['actual_clearances_m']={'west':x0,'east':brief.plot_width-x1,'north':y0,'south':brief.plot_depth-y1}
    face=brief.entrance_face
    yard=({'x':0,'y':0,'width':brief.plot_width,'depth':y0} if face=='north' else
          {'x':0,'y':y1,'width':brief.plot_width,'depth':brief.plot_depth-y1} if face=='south' else
          {'x':0,'y':0,'width':x0,'depth':brief.plot_depth} if face=='west' else
          {'x':x1,'y':0,'width':brief.plot_width-x1,'depth':brief.plot_depth})
    result['front_open_envelope']=yard
    entry=next((o['center'] for o in model['floors'][0]['openings'] if o.get('main_entry')),None)
    midpoint=({'north':(brief.plot_width/2,0),'south':(brief.plot_width/2,brief.plot_depth),'west':(0,brief.plot_depth/2),'east':(brief.plot_width,brief.plot_depth/2)})[face]
    result['entrance_to_street_midpoint_m']=math.dist(entry,midpoint) if entry else None
    result['comparison_scope']='Euclidean distance to a proposed street-midpoint gate; actual vehicle maneuvering and external access still require review'
    result['label_ar']='ركن خلفي باتجاه '+FACE_AR[result['rear_face']]+' و'+FACE_AR[next(f for f in result['anchor_faces'] if f!=result['rear_face'])]
    return result

def recheck(model,brief):
    placement=model.get('site_placement') or {}
    if not placement.get('active'):return None
    points=[p for f in model['floors'] for c in f['cells'] for p in ((c['x']-brief.wall_thickness/2,c['y']-brief.wall_thickness/2),(c['x']+c['width']+brief.wall_thickness/2,c['y']+c['depth']+brief.wall_thickness/2))]
    clear={'west':min(p[0] for p in points),'east':brief.plot_width-max(p[0] for p in points),'north':min(p[1] for p in points),'south':brief.plot_depth-max(p[1] for p in points)}
    anchors=placement.get('anchor_faces',[]);rear=OPPOSITE[brief.entrance_face]
    ok=len(anchors)==2 and len(set(anchors))==2 and all(f in clear for f in anchors) and rear in anchors and brief.entrance_face not in anchors
    ok=ok and all(abs(clear[f]-getattr(brief.setbacks,f))<=EPS for f in anchors)
    ok=ok and all(clear[f]+EPS>=getattr(brief.setbacks,f) for f in clear)
    return {'check_id':'SITE-rear-corner','status':'PASS' if ok else 'FAIL','label':'تموضع المبنى في الركن الخلفي داخل حدود الارتدادات','evidence':{'actual_clearances_m':clear,'anchor_faces':anchors,'front_face':brief.entrance_face,'setbacks_waived':False}}
