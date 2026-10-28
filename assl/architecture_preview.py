"""Conceptual SVG architectural blocks only: no furnishings or door symbols.

This is an editorial concept preview, NOT an architectural working drawing.
"""
from __future__ import annotations
from xml.etree.ElementTree import Element,SubElement,tostring

FILL={'guest':'#dcebf4','family':'#e3eddd','private':'#e9dff0',
      'service':'#ede8d7','corridor':'#f0f1f3'}
INK='#354052'


def render_concept_svg(option,*,title='ANT — Preliminary Architecture'):
    floors=option.get('rooms_by_floor',[])
    halls=option.get('halls_by_floor',[])
    if not floors:
        raise ValueError('Concept option has no floors')
    W,H=1400,780
    root=Element('svg',xmlns='http://www.w3.org/2000/svg',
                 width=str(W),height=str(H),viewBox=f'0 0 {W} {H}')
    SubElement(root,'rect',x='0',y='0',width=str(W),height=str(H),fill='#ffffff')
    SubElement(root,'text',x='700',y='46',fill=INK,
               style='font-family:Tahoma,Arial,sans-serif;font-size:26px;text-anchor:middle').text=title
    SubElement(root,'text',x='700',y='77',fill='#aa642f',
               style='font-family:Tahoma,Arial,sans-serif;font-size:14px;text-anchor:middle').text=(
                'CONCEPT ONLY · NO FURNITURE · DOORS/WINDOWS NOT CERTIFIED')
    panels=min(len(floors),2)
    for fi in range(panels):
        rooms=floors[fi]
        floor_halls=halls[fi] if fi<len(halls) else []
        rects=rooms+floor_halls
        if not rects:continue
        x0=min(r['x'] for r in rects)
        y0=min(r['y'] for r in rects)
        x1=max(r['x']+r['width'] for r in rects)
        y1=max(r['y']+r['depth'] for r in rects)
        base_x=35+(W-70)/panels*fi
        panel_width=(W-70)/panels
        s=min((panel_width-70)/max(x1-x0,.01),570/max(y1-y0,.01))
        sx=lambda v:base_x+36+(v-x0)*s
        sy=lambda v:132+(v-y0)*s
        SubElement(root,'text',x=str(base_x+panel_width/2),y='112',fill=INK,
                   style='font-family:Tahoma,Arial,sans-serif;font-size:18px;text-anchor:middle').text=(
                       'Ground floor' if fi==0 else 'First floor')
        for r in floor_halls:
            SubElement(root,'rect',x=str(sx(r['x'])),y=str(sy(r['y'])),
                       width=str(r['width']*s),height=str(r['depth']*s),
                       fill=FILL['corridor'],stroke='#9b9b9b',**{'stroke-width':'2'})
        for r in rooms:
            fill=FILL.get(r.get('zone'),'#e9e9e9')
            SubElement(root,'rect',x=str(sx(r['x'])),y=str(sy(r['y'])),
                       width=str(r['width']*s),height=str(r['depth']*s),
                       fill=fill,stroke=INK,**{'stroke-width':'2.3'})
            cx=sx(r['x']+r['width']/2)
            cy=sy(r['y']+r['depth']/2)
            name=r.get('name') or r.get('kind','Space')
            SubElement(root,'text',x=str(cx),y=str(cy-4),fill=INK,
                       style='font-family:Tahoma,Arial,sans-serif;font-size:13px;text-anchor:middle').text=str(name)[:37]
            SubElement(root,'text',x=str(cx),y=str(cy+15),fill='#586b74',
                       style='font-family:Tahoma,Arial,sans-serif;font-size:11px;text-anchor:middle').text=(
                           f"{r['width']:.2f} × {r['depth']:.2f} m (gross)")
    quality=option.get('quality',{})
    SubElement(root,'text',x='700',y='746',fill='#64748b',
               style='font-family:Tahoma,Arial,sans-serif;font-size:14px;text-anchor:middle').text=(
                f"Hall rectangles: {quality.get('hall_rectangle_area_m2','?')} m² · "
                f"Status: {quality.get('status','UNRESOLVED')}")
    return tostring(root,encoding='unicode')
