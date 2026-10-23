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
        for b in floor.get('balconies',[]):
            xx=min(x0,b['x']-.2);yy=min(y0,b['y']-.2);W=max(x0+W,b['x']+b['width']+.2)-xx;D=max(y0+D,b['y']+b['depth']+.2)-yy;x0,y0=xx,yy
    scene=Scene((x0-2,y0-3,W+4,D+7));scene.linework_only=True
    if site_view:
        scene.rect(0,0,siteW,siteD,stroke='#777777',lw=.012,layer='SITE')
        s=model['brief']['setbacks'];x,y=s['west'],s['north'];w=siteW-x-s['east'];d=siteD-y-s['south']
        for a,b in [((x,y),(x+w,y)),((x+w,y),(x+w,y+d)),((x+w,y+d),(x,y+d)),((x,y+d),(x,y))]:scene.line(a,b,stroke='#999999',lw=.009,dash=[.13,.10],layer='SETBACKS')
        scene.line((siteW-1.0,2.0),(siteW-1.0,.8),lw=.02,layer='NORTH')
        scene.line((siteW-1.0,.8),(siteW-1.2,1.15),lw=.02,layer='NORTH')
        scene.line((siteW-1.0,.8),(siteW-.8,1.15),lw=.02,layer='NORTH')
        scene.text(siteW-1.0,.45,'N',.25,layer='NORTH')
        for face,width in model['brief'].get('boundary_widths',{}).items():
            if width<=0:continue
            xx,yy={'north':(siteW*.25,.65),'south':(siteW*.65,siteD-.65),'west':(.8,siteD*.65),'east':(siteW-.8,siteD*.65)}[face]
            scene.text(xx,yy,f'شارع {width:g} م',.22,layer='STREET')
        planning=model.get('planning',{});orientation=planning.get('orientation',{}).get('edge_mapping',{})
        for edge in planning.get('original_intent',{}).get('street_edges',[]):
            face=orientation.get(edge)
            if not face or model['brief'].get('boundary_widths',{}).get(face,0)>0:continue
            xx,yy={'north':(siteW*.25,.65),'south':(siteW*.65,siteD-.65),'west':(.8,siteD*.65),'east':(siteW-.8,siteD*.65)}[face]
            scene.text(xx,yy,'شارع · العرض غير معلوم',.19,layer='STREET')
        placement=model.get('site_placement') or {}
        if placement.get('active'):
            yard=placement['front_open_envelope']
            scene.text(yard['x']+yard['width']/2,yard['y']+yard['depth']/2,'فسحة أمامية · مداخل ومواقف',.26,layer='SITE_LABEL')
            scene.text(siteW/2,-2.5,placement['label_ar'],.24,layer='SITE_LABEL')
            face=placement['front_face']
            label_at={'north':(siteW/2,.45),'south':(siteW/2,siteD-.45),'west':(1,siteD/2),'east':(siteW-1,siteD/2)}[face]
            scene.text(*label_at,'جهة المدخل',.20,layer='SITE_LABEL')
        for park in model.get('parking',[]):
            scene.rect(park['x'],park['y'],park['width'],park['depth'],stroke='#555555',lw=.018,layer='PARKING')
            if park['width']<park['depth']:car_symbol(scene,park)
            else:scene.rect(park['x']+.5,park['y']+.45,4.5,1.9,stroke='#555555',lw=.018,layer='PARKING',radius=.18)
            scene.text(park['x']+park['width']/2,park['y']+.3,park['id'],.20,color='#333333',layer='PARKING')
    # Draw the operator-supplied regulatory geometry as labelled REVIEW OVERLAY,
    # not as constructed walls or automatically generated rooms.
    geo=model.get('regulatory_geometry') or {}
    if site_view:
        overlay=[]
        for well in (geo.get('light_wells') or []) if not any(r['feature']=='lightwell' and r['status']=='GENERATED' for r in model.get('feature_generation',[])) else []:
            if well.get('polygon'):overlay.append(('منور '+well['id'],well['polygon']))
        ann=geo.get('roof_annex')
        if ann and ann.get('polygon') and not any(r['feature']=='roof_annex' and r['status']=='GENERATED' for r in model.get('feature_generation',[])):overlay.append(('ملحق علوي',ann['polygon']))
        for proj in (geo.get('projections') or []) if not any(r['feature']=='balcony' and r['status']=='GENERATED' for r in model.get('feature_generation',[])) else []:
            if proj.get('polygon'):overlay.append(('بروز '+proj['id'],proj['polygon']))
        for label,poly in overlay:
            scene.poly(poly,stroke='#666666',lw=.018,layer='REGULATORY_PROPOSED_GEOMETRY',closed=True)
            xx=sum(p[0] for p in poly)/len(poly)
            yy=sum(p[1] for p in poly)/len(poly)
            scene.text(xx,yy,label,.16,layer='REGULATORY_PROPOSED_LABEL')
        if overlay:
            scene.text(x0+W/2,y0+D+2.2,'مضلعات تنظيمية مقترحة غير معتمدة وليست جدرانًا',.18,layer='TITLE')
    scene.text(x0+W/2,y0-1.8,model['profile']['project_name'],.48,color='#111111',layer='TITLE')
    scene.text(x0+W/2,y0-.95,('الموقع والمواقف' if site_view else model['search']['family_label_ar']+' · '+floor['name']),.30,color='#222222',layer='TITLE')
    scene.text(x0+W/2,y0-.5,f'أرض {siteW:g} × {siteD:g} م · '+(model['brief'].get('city') or ('اليمن' if model['brief'].get('country')=='YE' else 'السعودية')+' — المدينة غير محددة'),.20,color='#555555',layer='TITLE')
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
            elif o.get('door_style')=='sliding':
                scene.line(pt(lo,fixed-t*.2),pt(hi,fixed-t*.2),'#333333',.014,'SLIDING_DOOR')
                scene.line(pt(lo,fixed+t*.2),pt(hi,fixed+t*.2),'#333333',.014,'SLIDING_DOOR')
                scene.line(pt(center,fixed-t/2),pt(center,fixed+t/2),'#333333',.014,'SLIDING_DOOR')
            else:
                from .general_quality import door_geometry
                g=door_geometry(floor,o);h=g['hinge'];u=g['closed_direction'];v=g['open_direction'];radius=g['radius']
                def along(du,dv):return (h[0]+du*u[0]+dv*v[0],h[1]+du*u[1]+dv*v[1])
                tip=along(0,radius);endp=along(radius,0)
                scene.line(h,tip,'#333333',.017,'DOOR')
                k=.5522847498
                scene.curve([endp,along(radius,radius*k),along(radius*k,radius),tip],'#555555',.011,'DOOR')
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
    for well in floor.get('lightwells',[]):
        scene.rect(well['x'],well['y'],well['width'],well['depth'],stroke='#666666',lw=.012,layer='LIGHTWELL')
        scene.text(well['x']+well['width']/2,well['y']+well['depth']/2,'منور مفتوح',.20,layer='LIGHTWELL_LABEL')
    for b in floor.get('balconies',[]):
        scene.poly(b['polygon'],stroke='#333333',lw=.020,layer='BALCONY_SLAB',closed=True)
        xx,yy,ww,dd=b['x']+.07,b['y']+.07,b['width']-.14,b['depth']-.14
        edges={'north':[(xx,yy+dd),(xx,yy),(xx+ww,yy),(xx+ww,yy+dd)],'south':[(xx,yy),(xx,yy+dd),(xx+ww,yy+dd),(xx+ww,yy)],'west':[(xx+ww,yy),(xx,yy),(xx,yy+dd),(xx+ww,yy+dd)],'east':[(xx,yy),(xx+ww,yy),(xx+ww,yy+dd),(xx,yy+dd)]}
        scene.poly(edges[b['face']],stroke='#555555',lw=.012,layer='BALCONY_GUARD',closed=False)
        scene.text(b['x']+b['width']/2,b['y']+b['depth']/2,'شرفة',.17,layer='BALCONY_LABEL')
    if floor.get('roof_annex'):
        core=next(a['void'] for a in model['stair_arrivals'] if a['floor_id']==floor['id'])
        scene.rect(core['x'],core['y'],core['width'],core['depth'],stroke='#666666',lw=.009,dash=[.12,.1],layer='STAIR_VOID')
        scene.text(core['x']+core['width']/2,core['y']+core['depth']*.65,'بئر الدرج · وصول من أسفل',.17,layer='STAIR_VOID')
    yard=model.get('service_yard')
    if site_view and yard:
        scene.rect(yard['x'],yard['y'],yard['width'],yard['depth'],stroke='#333333',lw=.016,layer='SERVICE_YARD')
        for q in yard['equipment']:
            scene.rect(q['x'],q['y'],q['width'],q['depth'],stroke='#333333',lw=.014,layer='HVAC_EQUIPMENT')
            scene.ellipse(q['x']+q['width']/2-.13,q['y']+q['depth']/2-.13,.26,.26,stroke='#555555',lw=.009,layer='HVAC_EQUIPMENT')
        scene.text(yard['x']+yard['width']/2,yard['y']+yard['depth']+.25,'خدمات وتكييف',.17,layer='SERVICE_LABEL')
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
    scene.text(x0+W/2,y0+D+1.3,('مسودة — اشتراطات البناء اليمنية غير موثقة' if model['brief'].get('country')=='YE' else 'مسودة — المطابقة الشاملة للكود السعودي غير معتمدة'),.21,color='#333333',layer='TITLE')
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
    scene.text(19.5,2.0,('مسودة للمراجعة؛ اشتراطات البناء اليمنية المحلية معلقة' if model['brief'].get('country')=='YE' else 'مسودة للمراجعة؛ المطابقة الشاملة للكود السعودي غير معتمدة'),.26,align='right',layer='REPORT')
    brief=model['brief'];place=('الجمهورية اليمنية / ' if brief.get('country')=='YE' else 'المملكة العربية السعودية / ')+(brief.get('region') or '')+' / '+(brief.get('municipality') or 'الأمانة غير محددة')+' / '+(brief.get('city') or 'المدينة غير محددة')
    scene.text(19.5,2.6,place,.23,align='right',layer='REPORT')
    location=' / '.join(brief.get(k,'') for k in ('district','neighborhood') if brief.get(k))
    if location:scene.text(19.5,3.0,location,.20,align='right',layer='REPORT')
    yy=3.5
    option=model.get('design_option')
    if option:
        scene.text(19.5,yy,option['title']+' · '+{'economy':'اقتصادي','standard':'متوسط','luxury':'فاخر'}[option['profile']],.23,align='right',layer='REPORT');yy+=.45
        for text in option['advantages']:
            scene.text(19.5,yy,text,.20,align='right',layer='REPORT');yy+=.35

    if model.get('functional_program_v4'):
        report=model['functional_program_v4'];repair=model.get('auto_repair_v4',{})
        for text in (f"مسارات حول الأثاث: {len(report['movement']['routes'])}؛ غير متصل: {len(report['movement']['unreachable'])}",
                     f"إصلاحات محلية مقبولة: {repair.get('accepted_steps',0)}؛ تفاصيل قبل وبعد في JSON",
                     'مصفوفة تتبع 199 بندًا؛ لا تعني تنفيذ جميع القواعد أو اعتمادها'):
            scene.text(19.5,yy,text,.19,align='right',layer='REPORT');yy+=.36
    names={'PASS':'ناجح جزئيًا','FAIL':'فشل','PENDING':'يحتاج تحققًا','NOT_APPLICABLE':'غير منطبق'}
    for check in model['checks']:
        label=check['label'];source=check.get('source',{}).get('section','')
        scene.text(19.5,yy,label+(' · '+source if source else ''),.19,align='right',layer='REPORT')
        scene.text(1.5,yy,names[check['status']],.18,align='left',layer='REPORT');yy+=.41
    yy+=.3
    references=['المراجع الرسمية: https://momah.gov.sa/ar/node/15715',
                 'https://sbc.gov.sa/ar/BC/Pages/BuildingCode/BC.aspx?year=2024',
                 'دليل الجهات البلدية محمّل؛ اشتراطات جميع قطع المدن ليست موثقة تلقائيًا.',
                 'القواعد المطبقة جزئية؛ الإنشاء والخدمات والحريق والطاقة والاشتراطات المحلية تحتاج اعتمادًا.']
    if brief.get('country')=='YE':references=['اليمن: لا توجد اشتراطات محلية موثقة في المستودع؛ لا يُطبق الكود السعودي.', 'المطلوب: إفادة حدود وارتدادات ونسبة بناء واشتراطات جهة الترخيص المحلية.', 'الارتدادات والأبعاد المقترحة افتراضات تصميمية تحتاج اعتمادًا محليًا.']
    for line in references:
        scene.text(19.5,yy,line,.19,align='right',layer='REPORT');yy+=.4
    if yy>29:scene.viewbox=(0,0,21,yy+.7)
    return scene


def review_pages(model):
    """Keep V4 audit text legible instead of shrinking one unbounded PDF sheet.

    Preserve every title, check and source line; split complete rows (including
    their left-hand status) together. Drawing floors and DXF are unchanged.
    """
    import copy
    source=review_drawing(model)
    if not model.get('functional_program_v4'):return [source]
    grouped={}
    for item in source.items:grouped.setdefault(item['y'],[]).append(item)
    pages=[];page=Scene((0,0,21,29.7));page.linework_only=True
    offset=0.
    for y,items in sorted(grouped.items()):
        if y-offset>27.7:
            pages.append(page);page=Scene((0,0,21,29.7));page.linework_only=True
            page.text(19.5,1.2,'تقرير الفحوص — تابع',.34,align='right',layer='REPORT')
            offset=y-2.2
        for item in items:
            q=copy.deepcopy(item);q['y']-=offset
            q['size']=max(q['size'],.23)
            page.items.append(q)
    if page.items:pages.append(page)
    return pages
