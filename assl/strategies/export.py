"""Gated native DXF; CAD geometry comes from the generated model, not a trace."""
import math
from pathlib import Path
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union
from .geometry import shape


def export_dxf(brief,p,path):
    from assl.openings_009 import validate,wall_cut,leaf_swings
    from assl.layout_critic_010 import critique
    qa=validate(brief,p);qc=critique(brief,p)
    if qa['status']!='PASS' or qc['status']!='ACCEPTABLE_DESIGN_INDICATORS':
        raise ValueError('EXPORT_BLOCKED:009_OR_010_FAILED')
    if p.get("schema") == "assl-clustered-2":
        from .guest_access import check_guest_wc_routes
        if check_guest_wc_routes(p)["status"] == "FAIL":
            raise ValueError("EXPORT_BLOCKED:Z03_GUEST_WC_ROUTE")
    import ezdxf
    doc=ezdxf.new('R2010');doc.units=6;doc.header['$MEASUREMENT']=1;space=doc.modelspace()
    for name in ('WALL_FACES', 'OPENINGS', 'WINDOWS', 'FURNITURE', 'ROOM_LABELS', 'STAIR_CONCEPT', 'REVIEW_NOTES', 'ENTRY_LANDINGS', 'ENTRY_STEPS', 'ENTRY_LEVELS'):
        doc.layers.new(name, dxfattribs={"color": 7})
    opened=p['opening_model_009'][0];objects=p['rooms_by_floor'][0]+p['halls_by_floor'][0];ids={r['id']:r for r in objects}
    holes=unary_union([wall_cut(o, brief.wall_thickness/2 + 1e-6 if o.get('open_passage') else brief.wall_thickness) for o in opened['doors']+opened['windows']])
    def linegeom(g,layer,elevation=0):
        parts=list(g.geoms) if hasattr(g,'geoms') else [g]
        for part in parts:
            if part.geom_type in ('LineString','LinearRing') and part.length>1e-6:space.add_lwpolyline(list(part.coords),dxfattribs={'layer':layer,'elevation':elevation})
    def rect(q,layer):
        x,y,w,d=[q[k] for k in ('x','y','width','depth')]
        space.add_lwpolyline([(x,y),(x+w,y),(x+w,y+d),(x,y+d)],close=True,dxfattribs={'layer':layer})
    from .geometry import net_shape
    walls=unary_union([shape(r).buffer(brief.wall_thickness/2,join_style=2).difference(net_shape(r,brief.wall_thickness)) for r in objects]).difference(holes)
    linegeom(walls.boundary,'WALL_FACES')
    for r in objects:
        g=shape(r)
        if r.get('arcs'):
            arc=r['arcs'][0];cx,cy=arc['center'];rad=arc['radius'];a,b=map(math.radians,(arc['start_angle'],arc['end_angle']))
            space.add_arc((cx,cy),r['stair']['inner_radius_m'],arc['start_angle'],arc['end_angle'],dxfattribs={'layer':'STAIR_CONCEPT'})
            n=r['stair']['radial_treads'];inner=r['stair']['inner_radius_m'];outer=rad-brief.wall_thickness/2
            for i in range(n+1):
                theta=a+(b-a)*i/n;space.add_line((cx+inner*math.cos(theta),cy+inner*math.sin(theta)),(cx+outer*math.cos(theta),cy+outer*math.sin(theta)),dxfattribs={'layer':'STAIR_CONCEPT'})
        if r.get('stair',{}).get('layout')=='u-shaped':
            from .stairs import u_treads
            for a,b in u_treads(r,brief.wall_thickness):space.add_line(a,b,dxfattribs={'layer':'STAIR_CONCEPT'})
            stair = r['stair']
            label = g.representative_point()
            count = stair['risers']
            description = f"{count//2}+{count//2} RISERS @ {1000*stair['floor_height_m']/count:.1f} mm / 1 MID-LANDING"
            space.add_text(description, dxfattribs={'insert': (label.x, label.y), 'height': .12, 'layer': 'STAIR_CONCEPT'})

        q=g.representative_point();text=r.get('name',r['id'])
        space.add_mtext(text,dxfattribs={'insert':(q.x,q.y),'char_height':.22,'layer':'ROOM_LABELS','width':max(1,r['width']-.4)})
    for platform in p.get('entrance_platforms',[]):
        door=next(item for item in opened['doors'] if item['id']==platform['door_id'])
        edge=Polygon(platform['landing_polygon']).boundary.difference(wall_cut(door,brief.wall_thickness))
        linegeom(edge,'ENTRY_LANDINGS',platform['level_m'])
        for step in platform['treads']:space.add_lwpolyline(step['polygon'],close=True,dxfattribs={'layer':'ENTRY_STEPS','elevation':step['level_m']})
        for riser in platform['riser_lines']:
            a,b=riser['points'];z=riser['top_level_m'];space.add_line((*a,z),(*b,z),dxfattribs={'layer':'ENTRY_STEPS'})
        q=platform['landing_polygon'][0];space.add_text(f"+{platform['level_m']:.2f} m",dxfattribs={'insert':(*q,platform['level_m']),'height':.18,'layer':'ENTRY_LEVELS'})
    for d in opened['doors']:
        for sector,width in zip(leaf_swings(d,ids[d['receiving_room']],brief.wall_thickness),d.get('leaf_widths',[d['width']])):
            coords=list(sector.exterior.coords);h=coords[0];first=coords[1];last=coords[-2]
            space.add_line(h,last,dxfattribs={'layer':'OPENINGS'})
            a=math.degrees(math.atan2(first[1]-h[1],first[0]-h[0]))%360;b=math.degrees(math.atan2(last[1]-h[1],last[0]-h[0]))%360
            if (b-a)%360>180:a,b=b,a
            space.add_arc(h,width,a,b,dxfattribs={'layer':'OPENINGS'})
    for w in opened['windows']:
        a=list(w['center']);b=list(w['center']);axis=0 if w['axis']=='x' else 1;a[axis]-=w['width']/2;b[axis]+=w['width']/2
        space.add_line(a,b,dxfattribs={'layer':'WINDOWS'})
    for q in p['furniture_by_floor'][0]:rect(q,'FURNITURE')
    space.add_mtext('CONCEPT ONLY — NOT FOR CONSTRUCTION. WALL FACES IN METRES; thickness '+str(brief.wall_thickness)+'m. Structural, stair, headroom, local-code and daylight review pending.',dxfattribs={'insert':(0,-2),'char_height':.25,'width':20,'layer':'REVIEW_NOTES'})
    doc.saveas(path)
    return dict(path=str(path),units='metres',schema=p['schema'],arc_geometry='analytic stair arcs where applicable; wall faces derived from occupancy polygons',validation_009=qa['status'],quality_010=qc['status'])
