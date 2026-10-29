"""Diagnostic drawings from the exact validated geometry; no furniture symbols."""
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A3,landscape
import arabic_reshaper
from bidi.algorithm import get_display
from .openings_009 import swing

def draw(brief,p,destination,status):
 pdfmetrics.registerFont(TTFont('ANT009','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'))
 c=canvas.Canvas(str(destination),pagesize=landscape(A3));W,H=landscape(A3)
 c.setFont('ANT009',15);c.drawString(25,H-30,f"{p['topology_style']} | {status} | 009 diagnostic review")
 c.setFont('ANT009',9);c.drawString(25,H-49,'NO FURNITURE / NOT FOR CONSTRUCTION / Legal, daylight and airflow: UNRESOLVED')
 all_shapes=[r for floor in p['rooms_by_floor']+p['halls_by_floor'] for r in floor]
 maxx=max(r['x']+r['width'] for r in all_shapes);maxy=max(r['y']+r['depth'] for r in all_shapes)
 for fi,(rooms,halls) in enumerate(zip(p['rooms_by_floor'],p['halls_by_floor'])):
  objects=rooms+halls
  scale=min((W/2-65)/maxx,(H-130)/maxy);bx=30+fi*W/2;by=45
  def xy(x,y):return bx+x*scale,by+y*scale
  c.setFont('ANT009',11);c.drawString(bx,H-72,f'Floor {fi} / metres / North up')
  from shapely.ops import unary_union
  from .openings_009 import shape
  halls_union=unary_union([shape(h) for h in halls]);parts=[halls_union] if halls_union.geom_type=='Polygon' else list(halls_union.geoms)
  for poly in parts:
   path=c.beginPath()
   for ring in [poly.exterior]+list(poly.interiors):
    for i,point in enumerate(ring.coords):
     if i==0:path.moveTo(*xy(*point))
     else:path.lineTo(*xy(*point))
    path.close()
   c.setFillColorRGB(.92,.94,.97);c.setStrokeColorRGB(.2,.22,.26);c.setLineWidth(brief.wall_thickness*scale);c.drawPath(path,fill=1,stroke=1)
  for r in rooms:
   x,y=xy(r['x'],r['y']);w=r['width']*scale;d=r['depth']*scale
   c.setFillColorRGB(*((.92,.94,.97) if r['kind']=='corridor' else (.95,.86,.7) if r['kind']=='stair' else (.88,.94,.88)))
   c.setStrokeColorRGB(.2,.22,.26);c.setLineWidth(max(1,brief.wall_thickness*scale));c.rect(x,y,w,d,fill=1)
   if r in rooms:
    c.setFillColorRGB(.1,.15,.2);c.setFont('ANT009',7)
    name=get_display(arabic_reshaper.reshape(r.get('name',r['kind'])))
    c.drawCentredString(x+w/2,y+d/2+4,name);c.drawCentredString(x+w/2,y+d/2-7,f"{r['width']-brief.wall_thickness:.2f} x {r['depth']-brief.wall_thickness:.2f}")
  if 'opening_model_009' not in p:continue
  floor=p['opening_model_009'][fi];ids={r['id']:r for r in floor['rooms']+floor['halls']}
  for o in floor['doors']+floor['windows']:
   x,y=o['center'];a=o['width']/2
   start,end=((x-a,y),(x+a,y)) if o['axis']=='x' else ((x,y-a),(x,y+a))
   c.setStrokeColorRGB(1,1,1);c.setLineWidth(brief.wall_thickness*scale+2);c.line(*xy(*start),*xy(*end))
   c.setStrokeColorRGB(*((.0,.5,.8) if o['kind']=='window' else (.1,.2,.6)));c.setLineWidth(1.4);c.line(*xy(*start),*xy(*end))
   if o['kind']=='door' and o.get('receiving_room') in ids:
    sector=swing(o,ids[o['receiving_room']],brief.wall_thickness);path=c.beginPath()
    for i,point in enumerate(sector.exterior.coords):
     if i==0:path.moveTo(*xy(*point))
     else:path.lineTo(*xy(*point))
    c.setLineWidth(.6);c.drawPath(path)
  if p.get('validation_009'):
   for route in p['validation_009']['floors'][fi]['routes']:
    c.setStrokeColorRGB(.0,.55,.2);c.setLineWidth(1);points=route['points']
    for a,b in zip(points,points[1:]):c.line(*xy(*a),*xy(*b))
 c.setFont('ANT009',9);c.setFillColorRGB(.2,.2,.2);c.drawString(25,20,'Blue: hosted openings and door sweeps / Green: verified body routes / missing routes remain FAIL')
 c.save()
