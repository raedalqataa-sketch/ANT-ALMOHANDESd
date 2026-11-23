"""Presentation from the same polygon/opening/furniture model as validation."""
from pathlib import Path
import math
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor,Color,white
import arabic_reshaper
from bidi.algorithm import get_display
from shapely.geometry import LineString,Polygon
from shapely.ops import unary_union
from .geometry import shape,net_shape

FONT='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'

def arabic(s):return get_display(arabic_reshaper.reshape(s))

def pdf(brief,p,path,*,show_site=False):
    pdfmetrics.registerFont(TTFont('Arabic',FONT))
    c=canvas.Canvas(str(path),pagesize=(1000,1000));c.setTitle('ANT ALMOHANDES — Clustered strategy 2')
    bg='#F7F5EF';ink='#253B3A';c.setFillColor(HexColor(bg));c.rect(0,0,1000,1000,fill=1,stroke=0)
    c.setFillColor(HexColor(ink));c.setFont('Arabic',23);c.drawRightString(944,950,arabic('أنت المهندس | تكوين الكتل المتداخلة'))
    c.setFont('Helvetica',11);c.drawString(56,921,'STRATEGY 02  /  GROUND FLOOR  /  PARAMETRIC POLYGON GEOMETRY')
    objects=p['rooms_by_floor'][0]+p['halls_by_floor'][0]
    t=brief.wall_thickness;ox=brief.setbacks.west+t/2;oy=brief.setbacks.south+t/2
    frame=(-ox,-oy,brief.plot_width-ox,brief.plot_depth-oy)
    bounds=unary_union([shape(r) for r in objects]+[Polygon(q['landing_polygon']) for q in p.get('entrance_platforms',[])]+[Polygon(v['polygon']) for q in p.get('entrance_platforms',[]) for v in q['treads']]).bounds
    view=frame if show_site else (bounds[0]-1.7,bounds[1]-1.7,bounds[2]+1.7,bounds[3]+1.7)
    vw,vh=view[2]-view[0],view[3]-view[1]
    s=min(880/vw,760/vh);tx=(1000-vw*s)/2-view[0]*s;ty=120+(760-vh*s)/2-view[1]*s
    def pt(p):return tx+p[0]*s,ty+p[1]*s
    def poly(geom,fill,stroke=None,width=1):
        path=c.beginPath();coords=list(geom.exterior.coords);path.moveTo(*pt(coords[0]))
        for q in coords[1:]:path.lineTo(*pt(q))
        path.close();c.setFillColor(HexColor(fill));c.setStrokeColor(HexColor(stroke or fill));c.setLineWidth(width);c.drawPath(path,fill=1,stroke=bool(stroke))
    if show_site:
        x,y=pt(view[:2]);c.setStrokeColor(HexColor('#B5C1B0'));c.setLineWidth(.8);c.setDash(4,4);c.rect(x,y,vw*s,vh*s,fill=0,stroke=1);c.setDash()
    # Wall axes filled once per room; clear interiors leave actual wall thickness.
    colors={'majlis':'#E8DED0','living':'#DDE8E1','dining':'#EEE5D6','kitchen':'#E2E8E5','storage':'#E5E8E4','bathroom':'#DFE9EA','stair':'#E8E5DD','corridor':'#F1EEE5'}
    for platform in p.get('entrance_platforms',[]):
        poly(Polygon(platform['landing_polygon']),'#E7DECB',ink,.7)
        for tread in platform['treads']:poly(Polygon(tread['polygon']),'#EEE9DF',ink,.7)
        for riser in platform['riser_lines']:
            c.setStrokeColor(HexColor(ink));c.setLineWidth(.8);c.line(*pt(riser['points'][0]),*pt(riser['points'][1]))
        q=Polygon(platform['landing_polygon']).centroid;c.setFillColor(HexColor(ink));c.setFont('Helvetica',8);c.drawCentredString(*pt((q.x,q.y)),f"+{platform['level_m']:.2f} m")
    for r in objects:poly(shape(r).buffer(t/2,join_style=2),ink);poly(net_shape(r,t),colors.get(r['kind'],'#FFFFFF'))
    opened=p.get('opening_model_009',[dict(doors=[],windows=[])])[0]
    from assl.openings_009 import cut,inward,leaf_swings,wall_cut
    for d in opened['doors']:
        g=wall_cut(d,t*.7);poly(g,bg)
        target=next(r for r in objects if r['id']==d['receiving_room'])
        for sector in leaf_swings(d,target,t):
            path=c.beginPath();coords=list(sector.exterior.coords);path.moveTo(*pt(coords[0]))
            for q in coords[1:]:path.lineTo(*pt(q))
            c.setStrokeColor(HexColor('#81908A'));c.setLineWidth(.6);c.drawPath(path,fill=0,stroke=1)
            hinge=coords[0];end=coords[-2];c.setStrokeColor(HexColor(ink));c.setLineWidth(1.2);c.line(*pt(hinge),*pt(end))
        if 'OUTSIDE' in d['connects']:
            q=inward(d,target,-1.15);xx,yy=pt(q);c.setFillColor(HexColor('#BD8B4C'));c.circle(xx,yy,5,fill=1,stroke=0)
    for w in opened['windows']:
        poly(cut(w,t*.75),'#ADC5CB');a=0 if w['axis']=='x' else 1;p1=list(w['center']);p2=list(w['center']);p1[a]-=w['width']/2;p2[a]+=w['width']/2
        c.setStrokeColor(HexColor('#4B7B83'));c.setLineWidth(1);c.line(*pt(p1),*pt(p2))
    for q in p.get('furniture_by_floor',[[]])[0]:
        xx,yy=pt((q['x'],q['y']));w=q['width']*s;h=q['depth']*s
        c.setFillColor(HexColor('#C6BCA9' if q['kind'] in ('sofa','dining_chair') else '#FAFAF5'));c.setStrokeColor(HexColor('#8A938B'));c.setLineWidth(.6)
        c.roundRect(xx,yy,w,h,min(3,w/5,h/5),fill=1,stroke=1)
        if q['kind']=='sofa':
            c.setStrokeColor(HexColor('#9C9484'));c.line(xx+2,yy+h/2,xx+w-2,yy+h/2)
        if q['kind'] in ('toilet','basin','sink'):c.ellipse(xx+w*.18,yy+h*.17,xx+w*.82,yy+h*.83,fill=0,stroke=1)
        if q['kind']=='cooker':
            for ix in (.27,.72):
                for iy in (.27,.72):c.circle(xx+w*ix,yy+h*iy,min(w,h)*.12,fill=0,stroke=1)
    for r in objects:
        if r['kind']=='stair' and r.get('arcs'):
            arc=r['arcs'][0];cx,cy=arc['center'];radius=arc['radius'];start=arc['start_angle'];end=arc['end_angle']
            c.setStrokeColor(HexColor('#8F978E'));c.setLineWidth(.7)
            radial=r['stair']['radial_treads'];inner=r['stair']['inner_radius_m']
            for i in range(radial+1):
                a=math.radians(start+(end-start)*i/radial);c.line(*pt((cx+inner*math.cos(a),cy+inner*math.sin(a))),*pt((cx+(radius-t/2)*math.cos(a),cy+(radius-t/2)*math.sin(a))))
            # Rotated straight treads join the fan; counts follow floor height.
            straight=(r['stair']['risers']-1-radial)//2;theta=math.radians(start)
            def rotated(dx,dy):return (cx+dx*math.cos(theta)-dy*math.sin(theta),cy+dx*math.sin(theta)+dy*math.cos(theta))
            for side in (-1,1):
                for i in range(straight+1):
                    dy=-i*r['stair']['straight_going_m'];c.line(*pt(rotated(side*inner,dy)),*pt(rotated(side*(radius-t/2),dy)))
            # Inner analytic arc and two straight flights are schematic tread design.
            xx,yy=pt((cx-inner,cy-inner));c.arc(xx,yy,xx+2*inner*s,yy+2*inner*s,startAng=start,extent=end-start)
            label=net_shape(r,t).representative_point();lx,ly=pt((label.x,label.y-1.0));c.setFillColor(HexColor(ink));c.setFont('Arabic',9);c.drawCentredString(lx,ly,arabic('درج تصوري'))
        if r['kind']=='stair' and r.get('stair',{}).get('layout')=='u-shaped':
            from .stairs import u_treads
            c.setStrokeColor(HexColor('#8F978E'));c.setLineWidth(.7)
            for a,b in u_treads(r,t):c.line(*pt(a),*pt(b))
        g=net_shape(r,t);q=g.representative_point();xx,yy=pt((q.x,q.y));name='حمام ومغاسل' if r['kind']=='bathroom' else r.get('name',r['id'])
        if r.get('request_id'):
            # Label nearer centre, keeping the room's real clear area visible.
            c.setFillColor(HexColor(ink));size=min(11,max(7,(r['width']-.35)*s/max(1,pdfmetrics.stringWidth(arabic(name),'Arabic',1))))
            c.setFont('Arabic',size);c.drawCentredString(xx,yy+5,arabic(name))
            c.setFont('Helvetica',8);c.drawCentredString(xx,yy-9,f'{g.area:.1f} m2')
        elif r['kind']=='corridor':
            c.setFillColor(HexColor('#61756C'));c.setFont('Arabic',9);c.drawCentredString(xx,yy,arabic(name))
    c.setFillColor(HexColor(ink));c.setFont('Arabic',11);c.drawRightString(944,73,arabic('مسقط تصوري من المحرك — غير معتمد للتنفيذ'))
    c.setFont('Helvetica',9);c.drawString(56,53,'TRUE POLYGON AREAS / HOSTED OPENINGS / 0.60 m BODY ROUTES / STRUCTURAL & LOCAL CODE REVIEW PENDING')
    c.setStrokeColor(HexColor(ink));c.setLineWidth(2);xx,yy=pt((view[0]+.35,view[1]+.4));c.line(xx,yy,xx+5*s,yy)
    for k in range(6):c.line(xx+k*s,yy-3,xx+k*s,yy+3)
    c.setFont('Helvetica',8);c.drawString(xx,yy+8,'0');c.drawString(xx+5*s-8,yy+8,'5 m')
    c.save()
