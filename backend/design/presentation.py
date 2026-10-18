"""SVG, PDF and editable DXF adapters for the same architectural scene."""
import base64
import hashlib
import math
from functools import lru_cache
from pathlib import Path
from xml.etree.ElementTree import Element,SubElement,tostring
import ezdxf
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import arabic_reshaper
from bidi.algorithm import get_display
from .scene import architectural_scene
from .vector_paths import flatten_path, rounded_rect_path

DXF_VERSION='R2010'
DXF_ACADVER='AC1024'

ROOT=Path(__file__).resolve().parents[2]
pdfmetrics.registerFont(TTFont('PlanV04',str(ROOT/'frontend'/'PlanFont.ttf')))


@lru_cache(maxsize=1)
def embedded_font():return base64.b64encode((ROOT/'frontend'/'PlanFont.ttf').read_bytes()).decode('ascii')


def color(value,mono=False):
    if value in (None,'none'):return 'none'
    if not mono:return value
    r,g,b=(int(value[i:i+2],16) for i in (1,3,5));v=round(.25*r+.60*g+.15*b)
    return '#'+f'{v:02x}'*3


def scene_svg(model,floor,site_view=False,drawing=None):
    scene=drawing if drawing is not None else architectural_scene(model,floor,site_view);mono=model.get('presentation',{}).get('style')=='monochrome'
    root=Element('svg',{'xmlns':'http://www.w3.org/2000/svg','viewBox':' '.join(map(str,scene.viewbox)),
                        'role':'img','aria-label':floor['name'],'data-revision':model['model_revision_id'],'data-model-geometry':model.get('geometry_sha256','')})
    SubElement(root,'style').text=f"@font-face{{font-family:PlanV04;src:url(data:font/ttf;base64,{embedded_font()}) format('truetype')}}text{{font-family:PlanV04,Tahoma,sans-serif}}"
    current_layer=None;g=None
    for p in scene.items:
        layer=p['layer']
        if layer!=current_layer:
            g=SubElement(root,'g',{'data-layer':layer});current_layer=layer
        attrs={'fill':color(p.get('fill','none'),mono),'stroke':color(p.get('stroke','none'),mono),'stroke-width':str(p.get('lw',.01))}
        if p['type']=='rect':
            SubElement(g,'rect',dict(attrs,x=str(p['x']),y=str(p['y']),width=str(p['width']),height=str(p['depth']),rx=str(p.get('radius',0))))
        elif p['type']=='line':
            if p.get('dash'):attrs['stroke-dasharray']=' '.join(map(str,p['dash']))
            SubElement(g,'line',dict(attrs,x1=str(p['a'][0]),y1=str(p['a'][1]),x2=str(p['b'][0]),y2=str(p['b'][1])))
        elif p['type']=='ellipse':
            SubElement(g,'ellipse',dict(attrs,cx=str(p['x']+p['width']/2),cy=str(p['y']+p['depth']/2),rx=str(p['width']/2),ry=str(p['depth']/2)))
        elif p['type']=='poly':
            SubElement(g,'polygon' if p['closed'] else 'polyline',dict(attrs,points=' '.join(f'{x},{y}' for x,y in p['points'])))
        elif p['type']=='path':
            data=' '.join(cmd[0]+' '+' '.join(str(v) for v in cmd[1:]) for cmd in p['commands'])
            SubElement(g,'path',dict(attrs,d=data))
        elif p['type']=='curve':
            a,c1,c2,b=p['points'];SubElement(g,'path',dict(attrs,d=f'M {a[0]} {a[1]} C {c1[0]} {c1[1]} {c2[0]} {c2[1]} {b[0]} {b[1]}'))
        else:
            node=SubElement(g,'text',{'x':str(p['x']),'y':str(p['y']),'font-size':str(p['size']),'fill':color(p['color'],mono),
                                     'text-anchor':{'center':'middle','right':'end','left':'start'}[p['align']],
                                     'direction':'rtl' if any('\u0600'<=c<='\u06ff' for c in p['text']) else 'ltr'})
            if p.get('role'):node.set('data-role',p['role'])
            node.text=p['text']
    return tostring(root,encoding='unicode')


def rgb(hexcolor):return tuple(int(hexcolor[i:i+2],16)/255 for i in (1,3,5))


def scene_pdf(model,path,drawings=None,include_report=True):
    pw,ph=1190.55,1683.78 # A2 portrait; the metric scale bar survives printing/viewer resizing.
    c=canvas.Canvas(str(path),pagesize=(pw,ph));c.setTitle(model['profile']['project_name']+' — مراجعة معمارية V0.4.1')
    mono=model.get('presentation',{}).get('style')=='monochrome'
    for index,floor in enumerate(model['floors']):
        scene=drawings[index] if drawings is not None else architectural_scene(model,floor);vx,vy,vw,vh=scene.viewbox
        scale=min((pw-75)/vw,(ph-80)/vh);ox=(pw-vw*scale)/2;oy=(ph-vh*scale)/2
        def pt(point):return ox+(point[0]-vx)*scale,ph-oy-(point[1]-vy)*scale
        for p in scene.items:
            fill=color(p.get('fill','none'),mono);stroke=color(p.get('stroke','none'),mono)
            c.setLineWidth(p.get('lw',.01)*scale)
            if fill!='none':c.setFillColorRGB(*rgb(fill))
            if stroke!='none':c.setStrokeColorRGB(*rgb(stroke))
            c.setDash([v*scale for v in p['dash']] if p.get('dash') else [])
            if p['type'] in ('rect','ellipse'):
                x,y=pt((p['x'],p['y']+p['depth']));w,h=p['width']*scale,p['depth']*scale
                if p['type']=='ellipse':c.ellipse(x,y,x+w,y+h,fill=fill!='none',stroke=stroke!='none')
                elif p.get('radius'):c.roundRect(x,y,w,h,p['radius']*scale,fill=fill!='none',stroke=stroke!='none')
                else:c.rect(x,y,w,h,fill=fill!='none',stroke=stroke!='none')
            elif p['type']=='line':c.line(*pt(p['a']),*pt(p['b']))
            elif p['type']=='path':
                path=c.beginPath()
                for cmd in p['commands']:
                    if cmd[0]=='M':path.moveTo(*pt((cmd[1],cmd[2])))
                    elif cmd[0]=='L':path.lineTo(*pt((cmd[1],cmd[2])))
                    elif cmd[0]=='C':path.curveTo(*pt((cmd[1],cmd[2])),*pt((cmd[3],cmd[4])),*pt((cmd[5],cmd[6])))
                    elif cmd[0]=='Z':path.close()
                c.drawPath(path,stroke=stroke!='none',fill=fill!='none')
            elif p['type']=='curve':
                a,c1,c2,b=p['points'];c.bezier(*pt(a),*pt(c1),*pt(c2),*pt(b))
            elif p['type']=='poly':
                path=c.beginPath();path.moveTo(*pt(p['points'][0]))
                for q in p['points'][1:]:path.lineTo(*pt(q))
                if p['closed']:path.close()
                c.drawPath(path,stroke=stroke!='none',fill=fill!='none')
            else:
                c.setFillColorRGB(*rgb(color(p['color'],mono)));c.setFont('PlanV04',p['size']*scale)
                text=get_display(arabic_reshaper.reshape(p['text']));x,y=pt((p['x'],p['y']))
                {'center':c.drawCentredString,'left':c.drawString,'right':c.drawRightString}[p['align']](x,y,text)
        c.setFillColorRGB(.48,.53,.46);c.setFont('PlanV04',7)
        c.drawString(42,20,f"{model['candidate_id']} / {model['model_revision_id']} / {floor['id']} / DRAFT - NOT FOR CONSTRUCTION")
        c.showPage()
    if not include_report:
        c.save();return
    # The review sheet carries evidence and unresolved items, leaving the plans legible.
    def text(x,y,t,size=13,fill='#3a4c3b',align='right'):
        c.setFillColorRGB(*rgb(fill));c.setFont('PlanV04',size)
        {'right':c.drawRightString,'left':c.drawString,'center':c.drawCentredString}[align](x,y,get_display(arabic_reshaper.reshape(str(t))))
    text(pw-65,ph-75,'تقرير مراجعة المقترح — '+model['profile']['project_name'],22)
    text(pw-65,ph-112,model['search']['family_label_ar'],15)
    text(pw-65,ph-144,'اجتياز الفحوص الجزئية لا يثبت جودة معمارية شاملة أو مطابقة نظامية.',11,'#8c6b52')
    yy=ph-195
    for check in model.get('checks',[]):
        state={'PASS':'ناجح جزئيًا','PENDING':'معلّق','FAIL':'فشل','NOT_APPLICABLE':'غير منطبق'}[check['status']]
        text(pw-65,yy,check['expected_criterion'],10)
        text(80,yy,state,10,'#688058' if check['status']=='PASS' else '#a2825b',align='left')
        yy-=25
    yy-=15;text(pw-65,yy,'أبعاد الفراغات الصافية المقترحة',14);yy-=28
    for floor in model['floors']:
        text(pw-65,yy,floor['name'],12);yy-=22
        for r in floor['rooms']:
            if yy<65:
                c.showPage();yy=ph-75
            text(pw-65,yy,r['name'].replace(' — مقترح',''),10)
            text(80,yy,f"{r['width']:.2f} × {r['depth']:.2f} m | {r['area_m2']:.1f} m²",10,align='left');yy-=19
        yy-=15
    def paragraph(value):
        nonlocal yy
        lines=[];line=''
        for word in str(value).split():
            trial=(line+' '+word).strip()
            visual=get_display(arabic_reshaper.reshape(trial))
            if line and pdfmetrics.stringWidth(visual,'PlanV04',11)>pw-150:
                lines.append(line);line=word
            else:line=trial
        if line:lines.append(line)
        for line in lines:
            if yy<65:c.showPage();yy=ph-75
            text(pw-65,yy,line,11);yy-=22
        yy-=8
    if yy<140:c.showPage();yy=ph-75
    text(pw-65,yy,'افتراضات وحدود تحتاج المراجعة',15);yy-=35
    for assumption in model.get('assumptions',[]):paragraph(assumption)
    for check in model.get('checks',[]):
        if check['status']=='PENDING':paragraph(check['expected_criterion']+' — '+check['reason'])
    deferred=[p['label'] for p in model.get('preference_coverage',[]) if p['status']=='DEFERRED_PREFERENCE']
    if deferred:paragraph('فراغات مفضلة مؤجلة: '+ '، '.join(deferred))
    c.save()


def scene_dxf(model,path):
    doc=ezdxf.new(DXF_VERSION);doc.header['$INSUNITS']=6
    mono=model.get('presentation',{}).get('style')=='monochrome'
    doc.styles.new('ANT_ARABIC',dxfattribs={'font':'DejaVuSans.ttf'})
    m=doc.modelspace();layers=set()
    def layer(name):
        if name not in layers:
            doc.layers.new(name);layers.add(name)
        return name
    def attrs(p):
        value=p.get('stroke','none')
        if value=='none':value=p.get('fill','#a3ad9a')
        if value=='none':value='#a3ad9a'
        return {'layer':layer(p['layer']),'true_color':int(color(value,mono)[1:],16)}
    for fi,floor in enumerate(model['floors']):
        scene=architectural_scene(model,floor);off=fi*(model['site']['width']+8)
        def pt(point):return off+point[0],model['site']['depth']-point[1]
        for p in scene.items:
            if p['layer'] in ('PAPER','SHADOW','UNDERLAY','FINISH_GRID','DECORATION'):continue
            a=attrs(p)
            if p['type']=='text':
                m.add_text(p['text'],dxfattribs={'insert':pt((p['x'],p['y'])),'height':p['size'],'style':'ANT_ARABIC','layer':layer(p['layer']),'true_color':int(color(p['color'],mono)[1:],16)})
            elif p['type']=='line':
                if p['layer']=='WALL':m.add_lwpolyline([pt(p['a']),pt(p['b'])],dxfattribs=dict(a,const_width=p['lw']))
                else:m.add_line(pt(p['a']),pt(p['b']),dxfattribs=a)
            elif p['type']=='curve':
                start,c1,c2,end=p['points']
                hinge=(start[0],end[1]) if abs(c1[0]-start[0])>abs(c1[1]-start[1]) else (end[0],start[1])
                hp=pt(hinge);sp=pt(start);ep=pt(end)
                start_angle=math.degrees(math.atan2(sp[1]-hp[1],sp[0]-hp[0]))%360;end_angle=math.degrees(math.atan2(ep[1]-hp[1],ep[0]-hp[0]))%360
                if (end_angle-start_angle)%360>180:start_angle,end_angle=end_angle,start_angle
                m.add_arc(hp,math.dist(hp,sp),start_angle,end_angle,dxfattribs=a)
            elif p['type']=='ellipse':
                center=pt((p['x']+p['width']/2,p['y']+p['depth']/2))
                major=(p['width']/2,0) if p['width']>=p['depth'] else (0,p['depth']/2)
                ratio=min(p['width'],p['depth'])/max(p['width'],p['depth'])
                if p.get('fill','none')!='none':
                    hatch=m.add_hatch(color=256,dxfattribs={'layer':layer(p['layer']+'_FILL'),'true_color':int(color(p['fill'],mono)[1:],16)})
                    hatch.paths.add_edge_path().add_ellipse(center,major,ratio)
                if p.get('stroke','none')!='none':m.add_ellipse(center,major,ratio,dxfattribs=a)
            else:
                if p['type']=='path':points,closed=flatten_path(p['commands'])
                elif p['type']=='rect':
                    x,y,w,h=p['x'],p['y'],p['width'],p['depth']
                    if p.get('radius'):points,closed=flatten_path(rounded_rect_path(x,y,w,h,p['radius']))
                    else:points=[(x,y),(x+w,y),(x+w,y+h),(x,y+h)];closed=True
                else:points=p['points'];closed=p['closed']
                # Filled room/site surfaces stay on switchable presentation layers.
                if p.get('fill','none')!='none' and closed:
                    hatch=m.add_hatch(color=256,dxfattribs={'layer':layer(p['layer']+'_FILL'),'true_color':int(color(p['fill'],mono)[1:],16)})
                    hatch.paths.add_polyline_path([pt(q) for q in points],is_closed=True)
                if p.get('stroke','none')!='none':m.add_lwpolyline([pt(q) for q in points],close=closed,dxfattribs=a)
        for r in floor['rooms']:
            x,y,w,h=r['x'],r['y'],r['width'],r['depth'];m.add_lwpolyline([pt(q) for q in [(x,y),(x+w,y),(x+w,y+h),(x,y+h)]],close=True,dxfattribs={'layer':layer('ROOM')})
        m.add_text(model['model_revision_id'],dxfattribs={'height':.16,'insert':(off,-2.3),'layer':layer('REVISION')})
    doc.layers.get('ROOM').off()
    doc.saveas(path);read=ezdxf.readfile(path);audit=read.audit()
    expected=sum(len(f['rooms']) for f in model['floors'])
    actual=len(read.modelspace().query('LWPOLYLINE[layer=="ROOM"]'))
    if audit.errors or actual!=expected or read.dxfversion!=DXF_ACADVER:raise ValueError('فشل فحص DXF 2010')
    return dict(audit_errors=len(audit.errors),room_count=actual,units=read.header['$INSUNITS'],dxf_version=read.dxfversion,format='AutoCAD 2010 DXF',model_revision_id=model['model_revision_id'],
                graphic_source='shared metric architectural scene',independent_cad_application_verified=False)
