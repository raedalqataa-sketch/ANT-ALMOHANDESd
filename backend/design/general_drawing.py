"""Outline-only shared metric scene: no hatch, surface fill, or wall solid."""
import math
from .scene import Scene,furniture_symbol,car_symbol
from .general_engine import EPS
from .general_geometry import annotate



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


def drawing(model,floor,site_view=False):
    siteW,siteD=model['site']['width'],model['site']['depth'];fp=model['footprint']
    if site_view:x0,y0,W,D=0,0,siteW,siteD
    else:
        cells=floor['cells'];t=model['brief']['wall_thickness']
        x0=min(r['x'] for r in cells)-t/2;y0=min(r['y'] for r in cells)-t/2
        W=max(r['x']+r['width'] for r in cells)+t/2-x0;D=max(r['y']+r['depth'] for r in cells)+t/2-y0
    scene=Scene((x0-2,y0-3,W+4,D+7));scene.linework_only=True
    if site_view:
        scene.rect(0,0,siteW,siteD,stroke='#777777',lw=.012,layer='SITE')
        s=model['brief']['setbacks'];x,y=s['west'],s['north'];w=siteW-x-s['east'];d=siteD-y-s['south']
        for a,b in [((x,y),(x+w,y)),((x+w,y),(x+w,y+d)),((x+w,y+d),(x,y+d)),((x,y+d),(x,y))]:scene.line(a,b,stroke='#999999',lw=.009,dash=[.13,.10],layer='SETBACKS')
        for park in model.get('parking',[]):
            scene.rect(park['x'],park['y'],park['width'],park['depth'],stroke='#555555',lw=.018,layer='PARKING')
            if park['width']<park['depth']:car_symbol(scene,park)
            else:scene.rect(park['x']+.5,park['y']+.45,4.5,1.9,stroke='#555555',lw=.018,layer='PARKING',radius=.18)
            scene.text(park['x']+park['width']/2,park['y']+.3,park['id'],.20,color='#333333',layer='PARKING')
    scene.text(x0+W/2,y0-1.8,model['profile']['project_name'],.48,color='#111111',layer='TITLE')
    scene.text(x0+W/2,y0-.95,('الموقع والمواقف' if site_view else model['search']['family_label_ar']+' · '+floor['name']),.30,color='#222222',layer='TITLE')
    scene.text(x0+W/2,y0-.5,f'أرض {siteW:g} × {siteD:g} م · '+(model['brief'].get('city') or 'السعودية — المدينة غير محددة'),.20,color='#555555',layer='TITLE')
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
    for stair in model.get('stairs',[]):
        if stair['floor_id']!=floor['id']:continue
        for flight in stair['flights']:
            x,y,w,d=[flight[k] for k in ('x','y','width','depth')]
            count=stair['riser_count']//2
            for i in range(count):scene.line((x,y+i*stair['tread_depth_m']),(x+w,y+i*stair['tread_depth_m']),'#333333',.013,'STAIR')
            scene.line((x+w/2,y+.1),(x+w/2,y+d-.1),'#333333',.014,'STAIR')
        landing=stair['landing'];scene.rect(landing['x'],landing['y'],landing['width'],landing['depth'],stroke='#333333',lw=.014,layer='STAIR')
        f=stair['flights'][0];scene.poly([(f['x']+f['width']/2-.12,f['y']+f['depth']-.3),(f['x']+f['width']/2,f['y']+f['depth']-.1),(f['x']+f['width']/2+.12,f['y']+f['depth']-.3)],stroke='#333333',lw=.012,layer='STAIR',closed=False)
    legends=[]
    for label in floor.get('annotations',[]) or annotate(floor,model.get('stairs',[])):
        cx=label['x']+label['width']/2;yy=label['y']+label['size']
        scene.text(cx,yy,label['label'],label['size'],color='#111111',layer='ROOM_LABEL',role='room-name')
        if label['dimension']:scene.text(cx,yy+label['size']*1.25,label['dimension'],label['size']*.78,color='#555555',layer='DIMENSION',role='room-size')
        if label.get('legend'):legends.append(label['label']+' · '+label['legend'])
    # Building dimensions for floor boards; site dimensions for the independent site view.
    for yy in (y0-.25,y0+D+.6):
        scene.line((x0,yy),(x0+W,yy),'#555555',.01,'DIMENSION')
        for xx in (x0,x0+W):scene.line((xx-.10,yy+.10),(xx+.10,yy-.10),'#555555',.012,'DIMENSION')
    scene.text(x0+W/2,y0+D+.5,f'{W:.2f} m',.24,color='#333333',layer='DIMENSION')
    scene.text(x0-.8,y0+D/2,f'{D:.2f} m',.25,color='#333333',layer='DIMENSION')
    scene.text(x0+W/2,y0+D+1.3,'مسودة — المطابقة الشاملة للكود السعودي غير معتمدة',.21,color='#333333',layer='TITLE')
    scene.text(x0+W/2,y0+D+1.85,'خطوط فقط · DXF 2010 · الفحوص والمصادر في تقرير JSON',.18,color='#555555',layer='TITLE')
    scene.line((x0,y0+D+2.5),(x0+5,y0+D+2.5),'#111111',.025,'SCALE')
    for i in range(6):
        scene.line((x0+i,y0+D+2.4),(x0+i,y0+D+2.6),'#111111',.015,'SCALE');scene.text(x0+i,y0+D+2.95,str(i),.16,color='#333333',layer='SCALE')
    for i,line in enumerate(legends):scene.text(x0+W,y0+D+3.5+i*.35,line,.20,align='right',layer='ROOM_LEGEND')
    if legends:scene.viewbox=(x0-2,y0-3,W+4,D+7+len(legends)*.35)
    # Furniture is the detailed vector library, stripped of every surface fill.
    # Preserve symbol outlines even for primitives originally specified as fill-only.
    for p in scene.items:
        if p['type']=='text':p['color']='#111111';continue
        if p.get('stroke','none')=='none' and p.get('fill','none')!='none':p['stroke']='#555555'
        p['fill']='none'
        if p.get('stroke','none')!='none':p['stroke']='#111111' if p['layer']=='WALL_OUTLINE' else '#555555'
    return scene


def review_drawing(model):
    """Portable review page carried inside the PDF, including unresolved Saudi checks."""
    scene=Scene((0,0,21,29.7));scene.linework_only=True
    scene.text(19.5,1.3,'تقرير الفحوص والمصادر — '+model['profile']['project_name'],.40,align='right',layer='REPORT')
    scene.text(19.5,2.0,'مسودة للمراجعة؛ المطابقة الشاملة للكود السعودي غير معتمدة',.26,align='right',layer='REPORT')
    brief=model['brief'];place=(brief.get('municipality') or 'الأمانة غير محددة')+' / '+(brief.get('city') or 'المدينة غير محددة')
    scene.text(19.5,2.6,place,.23,align='right',layer='REPORT')
    yy=3.3
    names={'PASS':'ناجح جزئيًا','FAIL':'فشل','PENDING':'يحتاج تحققًا','NOT_APPLICABLE':'غير منطبق'}
    for check in model['checks']:
        label=check['label'];source=check.get('source',{}).get('section','')
        scene.text(19.5,yy,label+(' · '+source if source else ''),.19,align='right',layer='REPORT')
        scene.text(1.5,yy,names[check['status']],.18,align='left',layer='REPORT');yy+=.41
    yy+=.3
    for line in ['المراجع الرسمية: https://momah.gov.sa/ar/node/15715',
                 'https://sbc.gov.sa/ar/BC/Pages/BuildingCode/BC.aspx?year=2024',
                 'دليل الجهات البلدية محمّل؛ اشتراطات جميع قطع المدن ليست موثقة تلقائيًا.',
                 'القواعد المطبقة جزئية؛ الإنشاء والخدمات والحريق والطاقة والاشتراطات المحلية تحتاج اعتمادًا.']:
        scene.text(19.5,yy,line,.19,align='right',layer='REPORT');yy+=.4
    if yy>29:scene.viewbox=(0,0,21,yy+.7)
    return scene
