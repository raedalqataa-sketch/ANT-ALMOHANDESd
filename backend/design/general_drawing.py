"""Outline-only shared metric scene: no hatch, surface fill, or wall solid."""
import math
from .scene import Scene,furniture_symbol
from .general_engine import EPS



def wall_outlines(scene,rectangles):
    """Boundary of the union of wall strips: clean L/T joins, real door reveals."""
    exposed={}
    for x,y,w,d,lw in rectangles:
        for axis,fixed,lo,hi,normal in [('h',y,x,x+w,-1),('h',y+d,x,x+w,1),('v',x,y,y+d,-1),('v',x+w,y,y+d,1)]:
            runs=[(lo,hi)]
            for ox,oy,ow,od,_ in rectangles:
                low,high=(oy,oy+od) if axis=='h' else (ox,ox+ow)
                covers=(low<fixed-EPS and high>=fixed-EPS) if normal<0 else (low<=fixed+EPS and high>fixed+EPS)
                if not covers:continue
                a,b=(ox,ox+ow) if axis=='h' else (oy,oy+od)
                next_runs=[]
                for r0,r1 in runs:
                    if b<=r0+EPS or a>=r1-EPS:next_runs.append((r0,r1));continue
                    if a>r0+EPS:next_runs.append((r0,min(a,r1)))
                    if b<r1-EPS:next_runs.append((max(b,r0),r1))
                runs=next_runs
                if not runs:break
            exposed.setdefault((axis,round(fixed,6)),[]).extend((a,b,lw) for a,b in runs)
    for (axis,fixed),runs in exposed.items():
        merged=[]
        for a,b,lw in sorted(runs):
            if merged and a<=merged[-1][1]+EPS:
                aa,bb,ll=merged[-1];merged[-1]=(aa,max(bb,b),max(ll,lw))
            else:merged.append((a,b,lw))
        for a,b,lw in merged:
            start,end=((a,fixed),(b,fixed)) if axis=='h' else ((fixed,a),(fixed,b))
            scene.line(start,end,stroke='#111111',lw=lw,layer='WALL_OUTLINE')


def drawing(model,floor):
    W,D=model['site']['width'],model['site']['depth'];scene=Scene((-2,-3,W+4,D+7));scene.linework_only=True
    scene.rect(0,0,W,D,stroke='#777777',lw=.012,layer='SITE')
    s=model['brief']['setbacks']
    x,y=s['west'],s['north'];w=W-x-s['east'];d=D-y-s['south']
    for a,b in [((x,y),(x+w,y)),((x+w,y),(x+w,y+d)),((x+w,y+d),(x,y+d)),((x,y+d),(x,y))]:
        scene.line(a,b,stroke='#999999',lw=.009,dash=[.13,.10],layer='SETBACKS')
    scene.text(W/2,-1.8,model['profile']['project_name'],.48,color='#111111',layer='TITLE')
    scene.text(W/2,-.95,model['search']['family_label_ar']+' · '+floor['name'],.30,color='#222222',layer='TITLE')
    wall_rects=[]
    for wall in floor['walls']:
        axis=0 if wall['axis']=='horizontal' else 1;fixed=wall['start'][1-axis]
        start,end=wall['start'][axis],wall['end'][axis];t=wall['thickness']
        openings=sorted((o for o in floor['openings'] if o['wall_id']==wall['id']),key=lambda o:o['center'][axis])
        runs=[];last=start
        for o in openings:
            lo,hi=o['center'][axis]-o['width']/2,o['center'][axis]+o['width']/2
            if lo>last+EPS:runs.append((last,lo))
            last=max(last,hi)
        if last<end-EPS:runs.append((last,end))
        for lo,hi in runs:
            if axis==0:wall_rects.append((lo,fixed-t/2,hi-lo,t,.027 if wall['exterior'] else .022))
            else:wall_rects.append((fixed-t/2,lo,t,hi-lo,.027 if wall['exterior'] else .022))
        for o in openings:
            center=o['center'][axis];lo,hi=center-o['width']/2,center+o['width']/2
            def pt(u,v):return (u,v) if axis==0 else (v,u)
            if o['kind']=='window':
                for delta in (-t*.27,t*.27):scene.line(pt(lo,fixed+delta),pt(hi,fixed+delta),'#333333',.011,'WINDOW')
                for edge in (lo,hi):scene.line(pt(edge,fixed-t/2),pt(edge,fixed+t/2),'#111111',.016,'WINDOW')
            else:
                room=next((r for r in floor['rooms'] if r['id']==o['connects'][0]),None)
                if room:
                    side=1 if (room['y']+room['depth']/2 if axis==0 else room['x']+room['width']/2)>fixed else -1
                else:side=1
                radius=o['width'];hinge=pt(lo,fixed);tip=pt(lo,fixed+side*radius);endp=pt(hi,fixed)
                scene.line(hinge,tip,'#333333',.017,'DOOR')
                # Quarter circle represented as a cubic in SVG/PDF and an ARC in DXF.
                k=.5522847498
                scene.curve([endp,pt(hi,fixed+side*radius*k),pt(lo+radius*k,fixed+side*radius),tip],'#555555',.011,'DOOR')
    wall_outlines(scene,wall_rects)
    for q in floor['furniture']:furniture_symbol(scene,q)
    for r in floor['rooms']:
        if r['kind']=='stair':
            # Proposed U stair, same coordinates on both floors. Two 1.1 m flights.
            x,y,w,d=r['x'],r['y'],r['width'],r['depth'];flight=1.1;landing=1.2
            risers=math.ceil(model['brief']['floor_height']/.18);one=math.ceil(risers/2);tread=.28;run=(one-1)*tread
            sy=y+d-landing-run
            for i in range(one):
                for sx in (x,x+w-flight):scene.line((sx,sy+i*tread),(sx+flight,sy+i*tread),'#333333',.013,'STAIR')
            scene.rect(x,y+d-landing,w,landing,stroke='#333333',lw=.015,layer='STAIR')
            scene.line((x+flight/2,sy+.2),(x+flight/2,y+d-landing+.3),'#333333',.014,'STAIR')
            scene.poly([(x+flight/2-.12,y+d-landing+.1),(x+flight/2,y+d-landing+.3),(x+flight/2+.12,y+d-landing+.1)],stroke='#333333',lw=.012,layer='STAIR',closed=False)
        if r['kind']=='corridor':continue
        cx=r['x']+r['width']/2;cy=r['y']+r['depth']/2
        label=r['name'];size=min(.26,max(.15,r['width']/max(1,len(label))*.85))
        scene.text(cx,cy,label,size,color='#111111',layer='ROOM_LABEL',role='room-name')
        scene.text(cx,cy+.38,f"{r['width']:.2f} × {r['depth']:.2f} m",.19,color='#555555',layer='DIMENSION',role='room-size')
    # Overall dimensions and scale bar are metric and shared across all exporters.
    for yy in (-.4,D+.6):
        scene.line((0,yy),(W,yy),'#555555',.01,'DIMENSION')
        for xx in (0,W):scene.line((xx-.10,yy+.10),(xx+.10,yy-.10),'#555555',.012,'DIMENSION')
    scene.text(W/2,D+.5,f'{W:.2f} m',.24,color='#333333',layer='DIMENSION')
    scene.text(-.8,D/2,f'{D:.2f} m',.25,color='#333333',layer='DIMENSION')
    scene.text(W/2,D+1.5,'مسودة للمراجعة · خطوط فقط · DXF 2010',.23,color='#333333',layer='TITLE')
    scene.text(W/2,D+2.1,'الملاحظات النصية والاشتراطات المعلقة مذكورة في تقرير JSON',.20,color='#555555',layer='TITLE')
    scene.line((0,D+2.7),(5,D+2.7),'#111111',.025,'SCALE')
    for i in range(6):
        scene.line((i,D+2.6),(i,D+2.8),'#111111',.015,'SCALE')
        scene.text(i,D+3.1,str(i),.16,color='#333333',layer='SCALE')
    # Furniture is the detailed vector library, stripped of every surface fill.
    # Preserve symbol outlines even for primitives originally specified as fill-only.
    for p in scene.items:
        if p['type']=='text':p['color']='#111111';continue
        if p.get('stroke','none')=='none' and p.get('fill','none')!='none':p['stroke']='#555555'
        p['fill']='none'
        if p.get('stroke','none')!='none':p['stroke']='#111111' if p['layer']=='WALL_OUTLINE' else '#555555'
    return scene
