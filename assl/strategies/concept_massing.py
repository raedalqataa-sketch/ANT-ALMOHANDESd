"""Append conceptual volumes built from the same floor polygons as the DXF."""
import shapely
from shapely.geometry.polygon import orient
from shapely.ops import triangulate, unary_union

from .geometry import shape


def draw_concept_massing(space, floors, levels, height, thickness, offset):
    for rows, level in zip(floors, levels):
        footprint = unary_union([shape(r) for r in rows if r["kind"]!="terrace"]).buffer(
            thickness/2, join_style=2)
        for polygon in getattr(footprint,"geoms",[footprint]):
            polygon = orient(polygon,sign=1)
            constrained = getattr(shapely,"constrained_delaunay_triangles",None)
            triangles = (list(constrained(polygon).geoms) if constrained else
                         [face for face in triangulate(polygon) if polygon.covers(face)])
            if not triangles or polygon.symmetric_difference(unary_union(triangles)).area>1e-7:
                raise ValueError("Concept mesh does not preserve the footprint")
            def xyz(point,z):
                return point[0]+offset,point[1],z
            top = level+height
            layer = {"layer":"CONCEPT_MASSING"}
            for triangle in triangles:
                a,b,c = list(orient(triangle,sign=1).exterior.coords)[:3]
                space.add_3dface([xyz(q,top) for q in (a,b,c)],dxfattribs=layer)
                space.add_3dface([xyz(q,level) for q in (c,b,a)],dxfattribs=layer)
            for ring in (polygon.exterior,*polygon.interiors):
                for a,b in zip(ring.coords,list(ring.coords)[1:]):
                    space.add_3dface([xyz(a,level),xyz(b,level),xyz(b,top),xyz(a,top)],dxfattribs=layer)
