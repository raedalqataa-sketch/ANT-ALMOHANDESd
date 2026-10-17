from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, ConfigDict
from pathlib import Path
from uuid import uuid4
from io import BytesIO
from openpyxl import load_workbook
import ezdxf, json
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import arabic_reshaper
from bidi.algorithm import get_display

app = FastAPI(title='ANT ALMOHANDES - Prototype', version='0.1.0')
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs'; OUT.mkdir(exist_ok=True)
pdfmetrics.registerFont(TTFont('Arabic',str(ROOT/'frontend'/'Arabic.ttf')))
def arabic(text):
    return get_display(arabic_reshaper.reshape(str(text)))
class Room(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    name:str=Field(min_length=1,max_length=100)
    width:float=Field(gt=0)
    depth:float=Field(gt=0)
    kind:str='other'
class Project(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    title:str=Field(default='مشروع جديد',max_length=150)
    plot_width:float=Field(gt=0)
    plot_depth:float=Field(gt=0)
    rooms:list[Room]=Field(min_length=1,max_length=200)

def validate(p):
    checks=[]
    if not p.rooms: checks.append({'gate':'program','status':'FAIL','reason':'لا توجد فراغات'})
    else: checks.append({'gate':'program','status':'PASS'})
    checks.append({'gate':'local_regulations','status':'PENDING','reason':'لم تقدم اشتراطات محلية معتمدة'})
    checks.append({'gate':'circulation_privacy','status':'PENDING','reason':'لم يتم نمذجة الحركة والخصوصية'})
    checks.append({'gate':'doors_windows_ventilation','status':'PENDING','reason':'لم يتم تصميم فتحات فعلية أو التحقق من التهوية الطبيعية'})
    checks.append({'gate':'construction_details','status':'PENDING','reason':'الجدران والتفاصيل التنفيذية لم تُنمذج'})
    return checks

def layout(p):
    # Deterministic shelf packing for visualization only; no claim of architectural fitness.
    x=y=row_h=0.0; placed=[]
    for r in sorted(p.rooms,key=lambda a:a.depth,reverse=True):
        if r.width>p.plot_width or r.depth>p.plot_depth: raise ValueError('أبعاد أحد الفراغات أكبر من الأرض')
        if x+r.width>p.plot_width+1e-8: x=0;y+=row_h;row_h=0
        if y+r.depth>p.plot_depth+1e-8: raise ValueError('الفراغات لا تتسع داخل الأبعاد المدخلة وفق الترتيب التجريبي')
        placed.append({'name':r.name,'kind':r.kind,'x':x,'y':y,'width':r.width,'depth':r.depth})
        x+=r.width;row_h=max(row_h,r.depth)
    return placed

@app.get('/api/health')
def health():return {'status':'ok','mode':'prototype'}
@app.post('/api/import-excel')
async def import_excel(file:UploadFile=File(...)):
    if not (file.filename or '').lower().endswith('.xlsx'):raise HTTPException(400,'ارفع ملف XLSX')
    data=await file.read()
    if len(data)>5_000_000:raise HTTPException(413,'حجم الملف كبير')
    try:
        wb=load_workbook(BytesIO(data),read_only=True,data_only=True)
        ws=wb.active; rows=list(ws.values)
        # A1=title, B1=value; A2=plot_width, B2=value; A3=plot_depth, B3=value
        meta={str(r[0]).strip():r[1] for r in rows[:3] if len(r)>1 and r[0] is not None}
        rooms=[{'name':str(r[0]),'width':float(r[1]),'depth':float(r[2]),'kind':str(r[3] or 'other') if len(r)>3 else 'other'} for r in rows[6:] if len(r)>=3 and r[0] and r[1] is not None and r[2] is not None]
        wb.close()
        return Project(title=str(meta.get('title','مشروع جديد')),plot_width=float(meta['plot_width']),plot_depth=float(meta['plot_depth']),rooms=rooms).model_dump()
    except Exception as e:raise HTTPException(422,f'قالب Excel غير مطابق: {e}')
@app.post('/api/generate')
def generate(p:Project):
    try:rooms=layout(p)
    except ValueError as e:raise HTTPException(422,str(e))
    job=uuid4().hex
    doc=ezdxf.new('R2010');doc.header['$INSUNITS']=6
    for layer,color in [('PLOT',7),('ROOM',3),('TEXT',2)]:doc.layers.new(layer,dxfattribs={'color':color})
    m=doc.modelspace();m.add_lwpolyline([(0,0),(p.plot_width,0),(p.plot_width,p.plot_depth),(0,p.plot_depth)],close=True,dxfattribs={'layer':'PLOT'})
    for r in rooms:
        x,w,h=r['x'],r['width'],r['depth']
        y=p.plot_depth-r['y']-h
        m.add_lwpolyline([(x,y),(x+w,y),(x+w,y+h),(x,y+h)],close=True,dxfattribs={'layer':'ROOM'})
        m.add_text(r['name'],dxfattribs={'height':0.22,'insert':(x+0.1,y+h/2),'layer':'TEXT'})
    dx=OUT/f'{job}.dxf';doc.saveas(dx)
    check=ezdxf.readfile(dx)
    assert len(check.modelspace().query('LWPOLYLINE'))==len(rooms)+1
    pdf=OUT/f'{job}.pdf';c=canvas.Canvas(str(pdf),pagesize=(842,595))
    c.setTitle(p.title);c.setFont('Arabic',15)
    c.drawRightString(800,555,arabic('أنت المهندس: '+p.title))
    c.setFont('Arabic',9)
    c.drawRightString(800,530,arabic('مخطط تجريبي غير معتمد للتنفيذ، دون جدران أو فتحات أو تحقق هندسي'))
    c.drawRightString(800,510,arabic(f'أبعاد الأرض: {p.plot_width:g} في {p.plot_depth:g} متر، عدد الفراغات: {len(rooms)}'))
    scale=min(720/p.plot_width,410/p.plot_depth)
    c.setStrokeColorRGB(.25,.4,.3)
    c.rect(45,60,p.plot_width*scale,p.plot_depth*scale)
    for r in rooms:
        x=45+r['x']*scale; y=60+(p.plot_depth-r['y']-r['depth'])*scale
        w=r['width']*scale;h=r['depth']*scale
        c.setFillColorRGB(.92,.95,.9);c.rect(x,y,w,h,fill=1)
        label=arabic(r['name']);size=min(10,max(1,w/max(1,pdfmetrics.stringWidth(label,'Arabic',1))*0.85))
        if h>18 and w>15:
            c.setFillColorRGB(.18,.3,.2);c.setFont('Arabic',size)
            c.drawCentredString(x+w/2,y+h/2+3,label)
            c.setFont('Helvetica',min(8,size))
            c.drawCentredString(x+w/2,y+h/2-9,f"{r['width']:g} x {r['depth']:g} m")
    c.setFillColorRGB(.4,.45,.4);c.setFont('Arabic',8)
    c.drawRightString(800,25,arabic('راجع مختصًا قبل تطوير هذا التوزيع إلى مخطط معماري.'))
    c.save()
    report={'job_id':job,'project':p.model_dump(),'status':'DRAFT_NOT_EXECUTIVE','checks':validate(p),'rooms':rooms,'warning':'مخطط تجريبي غير صالح للتنفيذ أو التسليم المهني؛ لا توجد أبواب ونوافذ وجدران وحركة مكتملة'}
    (OUT/f'{job}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    return {**report,'downloads':{k:f'/api/files/{job}.{k}' for k in ('dxf','pdf','json')}}
@app.get('/api/files/{filename}')
def get_file(filename:str):
    if not filename.endswith(('.pdf','.dxf','.json')) or '/' in filename or '..' in filename:raise HTTPException(400)
    path=OUT/filename
    if not path.is_file():raise HTTPException(404)
    return FileResponse(path,filename=filename)

@app.get('/api/template.xlsx')
def excel_template():
    from openpyxl import Workbook
    from fastapi.responses import Response
    wb=Workbook(); ws=wb.active; ws.title='Project'
    for row in [('title','مشروع سكني'),('plot_width',20),('plot_depth',25),(),(),('name','width','depth','kind'),('مجلس',5,6,'living'),('غرفة نوم',4,4,'bedroom'),('مطبخ',4,3,'kitchen')]:
        ws.append(row)
    data=BytesIO(); wb.save(data); wb.close()
    return Response(data.getvalue(),media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers={'Content-Disposition':'attachment; filename="project-template.xlsx"'})

@app.get('/')
def frontend():
    return FileResponse(ROOT/'frontend'/'index.html')

from fastapi.staticfiles import StaticFiles
app.mount('/assets',StaticFiles(directory=ROOT/'frontend'),name='assets')
