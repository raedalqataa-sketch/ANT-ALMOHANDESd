"""One geometry revision drives SVG, PDF and DXF; openings remove wall runs."""
import html
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring
import ezdxf
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import arabic_reshaper
from bidi.algorithm import get_display

ROOT=Path(__file__).resolve().parents[2]
pdfmetrics.registerFont(TTFont('PlanArabic',str(ROOT/'frontend'/'Arabic.ttf')))
pdfmetrics.registerFont(TTFont('PlanLatin',str(ROOT/'frontend'/'Latin.ttf')))
COLORS={'guest':'#eee6d3','family':'#e3ebdf','private':'#e5e2ef','service':'#e0e9ec'}


def wall_runs(floor,wall):
    idx=1 if wall['axis']=='vertical' else 0
    start,end=sorted((wall['start'][idx],wall['end'][idx]))
    intervals=[(start,end)]
    for o in floor['openings']:
        if o['wall_id']!=wall['id']:continue
        lo,hi=o['center'][idx]-o['width']/2,o['center'][idx]+o['width']/2
        split=[]
        for a,b in intervals:
            if hi<=a or lo>=b:split.append((a,b));continue
            if lo>a:split.append((a,lo))
            if hi<b:split.append((hi,b))
        intervals=split
    for a,b in intervals:
        yield ((wall['start'][0],a),(wall['start'][0],b)) if idx==1 else ((a,wall['start'][1]),(b,wall['start'][1]))


def stair_lines(stair):
    x,y,w,d=stair['x'],stair['y'],stair['width'],stair['depth']
    yield (x,y),(x+w,y)
    for i in range(stair['riser_count']//2):
        yy=y+stair['landing_depth_m']+i*stair['tread_m']
        if yy<=y+d+1e-6:
            yield (x,yy),(x+stair['flight_width_m'],yy)
            yield (x+w-stair['flight_width_m'],yy),(x+w,yy)
    yield (x,y+stair['landing_depth_m']),(x+w,y+stair['landing_depth_m'])
    yield (x+w/2,y),(x+w/2,y+d)


def door_symbol(floor, opening):
    wall=next(w for w in floor['walls'] if w['id']==opening['wall_id'])
    room=next(r for r in floor['rooms'] if r['id']==opening['connects'][0])
    x,y=opening['center'];width=opening['width']
    if wall['axis']=='vertical':
        direction=1 if room['x']+room['width']/2>x else -1
        hinge=(x,y-width/2);closed=(x,y+width/2);leaf=(x+direction*width,y-width/2)
    else:
        direction=1 if room['y']+room['depth']/2>y else -1
        hinge=(x-width/2,y);closed=(x+width/2,y);leaf=(x-width/2,y+direction*width)
    k=.5522847498
    c1=(closed[0]+k*(leaf[0]-hinge[0]),closed[1]+k*(leaf[1]-hinge[1]))
    c2=(leaf[0]+k*(closed[0]-hinge[0]),leaf[1]+k*(closed[1]-hinge[1]))
    return hinge,leaf,closed,c1,c2


def svg(model,floor,site_view=False):
    width,depth=model['site']['width'],model['site']['depth']
    fp=model['footprint']
    viewbox=f'-1.5 -2.5 {width+3} {depth+5}' if site_view else f"{fp['x']-.8} {fp['y']-2.0} {fp['width']+1.6} {fp['depth']+3.3}"
    root=Element('svg',{'xmlns':'http://www.w3.org/2000/svg','viewBox':viewbox,
                        'role':'img','aria-label':floor['name'],'data-revision':model['model_revision_id']})
    SubElement(root,'style').text="@font-face{font-family:PlanArabic;src:url('/assets/Arabic.ttf')}text{font-family:PlanArabic,Tahoma,sans-serif}"
    def rect(q,**attrs):SubElement(root,'rect',{**{k:str(q[k]) for k in ('x','y','width')},'height':str(q['depth']),**{k:str(v) for k,v in attrs.items()}})
    def line(a,b,**attrs):SubElement(root,'line',{'x1':str(a[0]),'y1':str(a[1]),'x2':str(b[0]),'y2':str(b[1]),**{k:str(v) for k,v in attrs.items()}})
    def text(x,y,value,size=.3,color='#405446'):
        el=SubElement(root,'text',{'x':str(x),'y':str(y),'font-size':str(size),'fill':color,'text-anchor':'middle','direction':'rtl'});el.text=value
    if site_view:
        rect({'x':0,'y':0,'width':width,'depth':depth},fill='#fcfdf9',stroke='#83977d',**{'stroke-width':.05})
    tx=width/2 if site_view else fp['x']+fp['width']/2
    ty=-1.4 if site_view else fp['y']-1.15
    text(tx,ty,floor['name']+' — '+model['profile']['project_name'],.5)
    text(tx,ty+.65,f'أرض {width:g} × {depth:g} م · مقترح غير تنفيذي',.27)
    for p in model['parking'] if site_view else []:
        rect(p,fill='#edf0e7',stroke='#8b9c7c',**{'stroke-width':.04,'stroke-dasharray':'.2 .15'})
        text(p['x']+p['width']/2,p['y']+p['depth']/2,'موقف مقترح',.23)
    for r in floor['rooms']:
        rect(r,fill=COLORS.get(r['zone'],'#edf0e8'))
    for q in floor['furniture']:
        rect(q,fill='#fafbf8',stroke='#8d9a8b',**{'stroke-width':.025})
        if q['kind'] in ('single_bed','double_bed'):
            rect({'x':q['x']+.06,'y':q['y']+.06,'width':q['width']-.12,'depth':.3},fill='#e4e9e1',stroke='#a7b1a1',**{'stroke-width':.02})
    for stair in model['stairs']:
        for a,b in stair_lines(stair):line(a,b,stroke='#718074',**{'stroke-width':.025})
    for wall in floor['walls']:
        for a,b in wall_runs(floor,wall):line(a,b,stroke='#384940',**{'stroke-width':wall['thickness'],'stroke-linecap':'butt'})
    for o in floor['openings']:
        wall=next(w for w in floor['walls'] if w['id']==o['wall_id'])
        x,y=o['center'];w=o['width']
        if o['kind']=='window':
            for off in (-.04,.04):
                a,b=((x+off,y-w/2),(x+off,y+w/2)) if wall['axis']=='vertical' else ((x-w/2,y+off),(x+w/2,y+off))
                line(a,b,stroke='#2c9da6',**{'stroke-width':.035})
        else:
            hinge,leaf,closed,c1,c2=door_symbol(floor,o)
            line(hinge,leaf,stroke='#b88c5f',**{'stroke-width':.025})
            path=f'M {closed[0]} {closed[1]} C {c1[0]} {c1[1]} {c2[0]} {c2[1]} {leaf[0]} {leaf[1]}'
            SubElement(root,'path',{'d':path,'fill':'none','stroke':'#c9a67c','stroke-width':'.02'})
    for r in floor['rooms']:
        short=r['name'].replace(' — مقترح','')
        size=min(.3,max(.15,r['width']/(len(short)*.65+2)))
        text(r['x']+r['width']/2,r['y']+r['depth']/2,short,size)
        text(r['x']+r['width']/2,r['y']+r['depth']/2+.4,f"{r['area_m2']:.1f} م²",.2,'#78866f')
    text(tx,depth+1 if site_view else fp['y']+fp['depth']+.8,'مواقع وأبعاد مقترحة · اشتراطات الموقع والتهوية والخلوص معلّقة',.25)
    return tostring(root,encoding='unicode')


def draw_pdf_label(c,x,y,label,size=8):
    # A Unicode font with Arabic and Latin coverage avoids the former missing Latin labels.
    c.setFont('PlanLatin',size)
    c.drawCentredString(x,y,get_display(arabic_reshaper.reshape(str(label))))


def export_pdf(model,path):
    c=canvas.Canvas(str(path),pagesize=(1191,842))
    c.setTitle(model['profile']['project_name'])
    for floor in model['floors']:
        draw_pdf_label(c,595,806,model['profile']['project_name']+' — '+floor['name'],16)
        draw_pdf_label(c,595,781,'مسودة مراجعة غير تنفيذية — الأبعاد والفتحات والموقع مقترحات غير معتمدة',10)
        pw,pd=model['site']['width'],model['site']['depth']
        scale=min(700/pw,660/pd);ox=70;oy=70
        def pt(point):return ox+point[0]*scale,oy+(pd-point[1])*scale
        def rect(q,fill=0):
            x,y=pt((q['x'],q['y']+q['depth']));c.rect(x,y,q['width']*scale,q['depth']*scale,fill=fill,stroke=1)
        c.setStrokeColorRGB(.5,.6,.48);c.setLineWidth(.5)
        rect({'x':0,'y':0,'width':pw,'depth':pd})
        for parking in model['parking']:
            c.setStrokeColorRGB(.65,.7,.6);rect(parking)
        for r in floor['rooms']:
            c.setFillColorRGB(.95,.97,.93);c.setStrokeColorRGB(.9,.92,.88);rect(r,1)
        for q in floor['furniture']:
            c.setFillColorRGB(.98,.99,.97);c.setStrokeColorRGB(.65,.7,.62);c.setLineWidth(.4);rect(q,1)
        for stair in model['stairs']:
            c.setStrokeColorRGB(.45,.5,.43);c.setLineWidth(.5)
            for a,b in stair_lines(stair):c.line(*pt(a),*pt(b))
        for wall in floor['walls']:
            c.setStrokeColorRGB(.2,.28,.23);c.setLineWidth(wall['thickness']*scale)
            for a,b in wall_runs(floor,wall):c.line(*pt(a),*pt(b))
        for o in floor['openings']:
            wall=next(w for w in floor['walls'] if w['id']==o['wall_id'])
            x,y=o['center'];w=o['width']
            c.setLineWidth(.7)
            if o['kind']=='window':
                c.setStrokeColorRGB(.15,.6,.65)
                for off in (-.04,.04):
                    a,b=((x+off,y-w/2),(x+off,y+w/2)) if wall['axis']=='vertical' else ((x-w/2,y+off),(x+w/2,y+off))
                    c.line(*pt(a),*pt(b))
            else:
                c.setStrokeColorRGB(.7,.5,.3)
                hinge,leaf,closed,c1,c2=door_symbol(floor,o)
                c.line(*pt(hinge),*pt(leaf))
                c.bezier(*pt(closed),*pt(c1),*pt(c2),*pt(leaf))
        c.setFillColorRGB(.2,.3,.23)
        for r in floor['rooms']:
            xx,yy=pt((r['x']+r['width']/2,r['y']+r['depth']/2))
            label=r['name'].replace(' — مقترح','')
            text=get_display(arabic_reshaper.reshape(label))
            size=min(8,max(4,r['width']*scale*.85/max(1,pdfmetrics.stringWidth(text,'PlanLatin',1))))
            draw_pdf_label(c,xx,yy+4,label,size)
            dimensions=f"{r['width']:.2f} x {r['depth']:.2f} m | {r['area_m2']:.1f} m²" if r['width']>=3 else f"{r['area_m2']:.1f} m²"
            dsize=min(6,max(3,(r['width']-.25)*scale/max(1,pdfmetrics.stringWidth(dimensions,'PlanLatin',1))))
            draw_pdf_label(c,xx,yy-9,dimensions,dsize)
        draw_pdf_label(c,900,735,'ملخص المراجعة',13)
        messages=['أرض 20 × 30 م — دوران — أسرة 9 أفراد','كل أبعاد الغرف والسلم مقترحات تصميمية','المسح والارتدادات والواجهات غير متحققة','تقسيم غرف الأبناء والأسرّة يحتاج مراجعة','المصعد والخادمة ومدخل الخدمة معلقة','الموقف غلاف فقط دون تحقق المناورة','التهوية وخطوط النظر والخلوص غير مكتملة','لا اعتماد تنفيذي أو توقيع هندسي تلقائي']
        for i,msg in enumerate(messages):draw_pdf_label(c,900,700-i*28,msg,9)
        draw_pdf_label(c,900,400,f"المراجعة: {model['model_revision_id'][:12]}",9)
        draw_pdf_label(c,900,375,f"البديل: {model['candidate_id']}",9)
        draw_pdf_label(c,900,348,'مساحات وأبعاد مقترحة — بالمتر',10)
        for i,r in enumerate(floor['rooms']):
            yrow=326-i*15
            c.setFont('PlanLatin',7)
            c.drawRightString(1120,yrow,get_display(arabic_reshaper.reshape(r['name'].replace(' — مقترح',''))))
            c.drawString(730,yrow,f"{r['width']:.2f} x {r['depth']:.2f} | {r['area_m2']:.1f} m²")
        draw_pdf_label(c,595,28,'الأبعاد مشتقة من النموذج؛ طباعة للمراجعة دون مقياس تنفيذي معتمد',8)
        c.showPage()
    c.save()


def export_dxf(model,path):
    doc=ezdxf.new('R2010');doc.header['$INSUNITS']=6
    for layer,color in [('SITE',8),('WALL',7),('ROOM',3),('DOOR',30),('WINDOW',4),('FURNITURE',8),('STAIR',2),('TEXT',7),('PARKING',5)]:
        doc.layers.new(layer,dxfattribs={'color':color})
    m=doc.modelspace()
    for index,floor in enumerate(model['floors']):
        offset=index*(model['site']['width']+6)
        def pt(p):return p[0]+offset,model['site']['depth']-p[1]
        def rect(q,layer):
            x,y,w,h=q['x'],q['y'],q['width'],q['depth']
            m.add_lwpolyline([pt(p) for p in [(x,y),(x+w,y),(x+w,y+h),(x,y+h)]],close=True,dxfattribs={'layer':layer})
        rect({'x':0,'y':0,'width':model['site']['width'],'depth':model['site']['depth']},'SITE')
        for r in floor['rooms']:
            rect(r,'ROOM')
            m.add_text(r['name'],dxfattribs={'height':.2,'insert':pt((r['x']+.15,r['y']+r['depth']/2)),'layer':'TEXT'})
        for w in floor['walls']:
            for a,b in wall_runs(floor,w):
                m.add_lwpolyline([pt(a),pt(b)],dxfattribs={'layer':'WALL','const_width':w['thickness']})
        for o in floor['openings']:
            w=next(w for w in floor['walls'] if w['id']==o['wall_id']);x,y=o['center'];half=o['width']/2
            a,b=((x,y-half),(x,y+half)) if w['axis']=='vertical' else ((x-half,y),(x+half,y))
            if o['kind']=='window':
                m.add_line(pt(a),pt(b),dxfattribs={'layer':'WINDOW'})
            else:
                import math
                hinge,leaf,closed,c1,c2=door_symbol(floor,o)
                hp,lp,cp=pt(hinge),pt(leaf),pt(closed)
                m.add_line(hp,lp,dxfattribs={'layer':'DOOR'})
                a1=math.degrees(math.atan2(cp[1]-hp[1],cp[0]-hp[0]))%360
                a2=math.degrees(math.atan2(lp[1]-hp[1],lp[0]-hp[0]))%360
                if (a2-a1)%360>180:a1,a2=a2,a1
                m.add_arc(hp,o['width'],a1,a2,dxfattribs={'layer':'DOOR'})
        for q in floor['furniture']:rect(q,'FURNITURE')
        for p in model['parking']:rect(p,'PARKING')
        for s in model['stairs']:
            for a,b in stair_lines(s):m.add_line(pt(a),pt(b),dxfattribs={'layer':'STAIR'})
        m.add_text(f"{floor['id']} / DRAFT NOT FOR CONSTRUCTION / {model['model_revision_id']}",dxfattribs={'height':.25,'insert':(offset,model['site']['depth']+1),'layer':'TEXT'})
    doc.saveas(path)
    reread=ezdxf.readfile(path)
    audit=reread.audit()
    expected=sum(len(f['rooms']) for f in model['floors'])
    if audit.errors or len(reread.modelspace().query('LWPOLYLINE[layer=="ROOM"]'))!=expected:
        raise ValueError('فشل تدقيق DXF بعد التصدير')
    return {'audit_errors':len(audit.errors),'room_count':expected,'units':reread.header['$INSUNITS'],'model_revision_id':model['model_revision_id']}
