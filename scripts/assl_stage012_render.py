"""Render actual 012 MILP-generated source geometry, no invented door/windows."""
import json, math, textwrap
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from shapely.ops import unary_union
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import landscape,A3
from assl.relationship_first_012 import geo

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/'stage012-experimental'
OUTPUT.mkdir(exist_ok=True)
OUT=OUTPUT/'ANT_STAGE_012_Saudi_Corner_Experimental.pdf'
FONT='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
BOLD='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
W,H=2480,1754
F=ImageFont.truetype(FONT,24)
FS=ImageFont.truetype(FONT,19)
FB=ImageFont.truetype(BOLD,39)
FC=ImageFont.truetype(FONT,28)
FQ=ImageFont.truetype(BOLD,27)
S=53
pa=json.loads((ROOT/'tests'/'fixtures'/'assl_openings_009_valid.json').read_text())
pb=json.loads((ROOT/'tests'/'fixtures'/'assl_milp_012_candidate.json').read_text())

def text(d,x,y,s,font=F,fill='#243141',rtl=True,anchor='ra'):
    if rtl:d.text((x,y),s,font=font,fill=fill,anchor=anchor,direction='rtl')
    else:d.text((x,y),s,font=font,fill=fill,anchor=anchor)

def line(d,x,y,w,fill='#263547',width=4):d.line((x,y,x+w,y),fill=fill,width=width)

def plan(d,p,fi,xoff,yoff,scale=S,show_halls=True):
    d.rectangle((xoff,yoff,xoff+15.3*scale,yoff+20.3*scale),outline='#9aafc2',width=2)
    d.rectangle((xoff-4,yoff-4,xoff+15.3*scale+4,yoff+20.3*scale+4),outline='#cfd6dd',width=1)
    floors=p['rooms_by_floor'][fi];halls=p['halls_by_floor'][fi]
    def coords(r):
        x=xoff+r['x']*scale;y=yoff+(20.3-r['y']-r['depth'])*scale
        return (x,y,x+r['width']*scale,y+r['depth']*scale)
    for h in halls:
        xy=coords(h)
        d.rectangle(xy,fill='#dce5f5',outline='#596b8d',width=3)
    for r in floors:
        kind=r['kind'];guest=r.get('zone')=='guest' or r.get('guest_distributor')
        fill='#f7e5d0' if guest else '#f2dcaf' if kind=='stair' else '#e3f3e5'
        if r.get('guest_distributor'):fill='#f1e5cf'
        xy=coords(r)
        d.rectangle(xy,fill=fill,outline='#344254',width=5)
        label=r['name'] if r.get('name') else r.get('kind','')
        # Keep names inside the actual rectangles; omit only when too small.
        avail=xy[2]-xy[0]-12
        f=FS
        if d.textbbox((0,0),label,font=f,direction='rtl')[2] > avail:
            f=ImageFont.truetype(FONT,15)
        if d.textbbox((0,0),label,font=f,direction='rtl')[2]>avail:
            label={'bathroom':'حمام','corridor':'موزع','stair':'درج',
                   'bedroom':'غرفة نوم','living':'معيشة عائلية','dining':'طعام',
                   'kitchen':'مطبخ','master':'نوم رئيسية','majlis':'مجلس رجال'}.get(kind,kind)
        cx=(xy[0]+xy[2])/2;cy=(xy[1]+xy[3])/2
        d.text((cx,cy-13),label,font=f,fill='#1f2937',direction='rtl',anchor='mm',stroke_width=0)
        if r.get('request_id'):
            value=f"{r['width']:.2f} × {r['depth']:.2f} m"
            d.text((cx,cy+15),value,font=ImageFont.truetype(FONT,13),fill='#4b5b6e',anchor='mm')
    return coords

def header(d,subtitle):
    d.rectangle((0,0,W,140),fill='#16314a')
    text(d,W-100,31,'أنت المهندس | تجربة محرك التكوين 012',FB,'white')
    text(d,W-102,93,subtitle,FC,'#c9dbee')

def footer(d):
    d.rectangle((0,H-100,W,H),fill='#eef3f7')
    text(d,W-80,H-75,'رسومات بحثية غير معتمدة؛ لم تُختبر الأبواب والنوافذ النهائية أو صلاحية التنفيذ',FC,'#7c3434')

pages=[]
p=Image.new('RGB',(W,H),'#ffffff');d=ImageDraw.Draw(p)
header(d,'الدور الأرضي والأول من التكوين الجديد - إحداثيات فعلية مترية')
text(d,1060,190,'الدور الأرضي - 5 غرف عائلية + جناح الضيوف',FQ)
text(d,2320,190,'الدور الأول - 3 غرف + الدرج',FQ)
plan(d,pb,0,175,285,scale=57)
plan(d,pb,1,1470,285,scale=57)
text(d,1110,1590,'الممرات بالأزرق الفاتح | الضيوف بالبيج | غرف الأسرة بالأخضر | الدرج بالذهبي',F)
footer(d);pages.append(p)

p=Image.new('RGB',(W,H),'white');d=ImageDraw.Draw(p)
header(d,'مقارنة هندسية: الدور الأرضي الأساسي 009 مقابل التكوين التجريبي 012')
text(d,1110,190,'قبل - توزيع المسقط 009',FQ)
text(d,2300,190,'بعد - حل توزيع الغرف المتزامن 012',FQ)
plan(d,pa,0,175,290,scale=57)
plan(d,pb,0,1480,290,scale=57)
text(d,2200,1510,'تنبيه: الجدران المشتركة موجودة، لكن فتحات الأبواب لم تُبنَ بعد وفق 009.',F)
footer(d);pages.append(p)

p=Image.new('RGB',(W,H),'white');d=ImageDraw.Draw(p)
header(d,'تقرير المخرجات والقيود - لا شهادة اعتماد معماري')
base=sum(unary_union([geo(h) for h in halls+[r for r in rooms if r.get('guest_distributor')]]).area for halls,rooms in zip(pa['halls_by_floor'],pa['rooms_by_floor']))
after=sum(unary_union([geo(h) for h in halls+[r for r in rooms if r.get('guest_distributor')]]).area for halls,rooms in zip(pb['halls_by_floor'],pb['rooms_by_floor']))
rows=[
 ('الحالة السكنية','فيلا سعودية زاوية 20 × 25 متر، غلاف قابل للبناء 15.30 × 20.30 متر'),
 ('المصدر','برنامج الغرف والحدود الدنيا من اختبارات 009؛ لم تُحذف غرف'),
 ('المحرك الجديد','SciPy HiGHS Mixed-Integer Linear Programming؛ توزيع الغرف متزامنًا'),
 ('اتحاد مساحات الحركة - الأساس',f'{base:.2f} م² عبر الدورين، شامل موزع الضيوف'),
 ('اتحاد مساحات الحركة - النموذج',f'{after:.2f} م² عبر الدورين، شامل موزع الضيوف'),
 ('الفرق القابل للقياس',f'{base-after:.2f} م² تقليلًا ({100*(base-after)/base:.1f}%) وفق التعريف نفسه'),
 ('أطول امتداد أرضي - 012',f"{pb['independent_audit']['floors'][0]['max_straight_run_m']:.2f} م - لا يحقق بعد هدف 6 م"),
 ('أطول امتداد أول - 012',f"{pb['independent_audit']['floors'][1]['max_straight_run_m']:.2f} م"),
 ('نتائج التدقيق المستقل','حفظ الوظائف والأبعاد والدرج والتلامس وفراغات الواجهة المحتملة'),
 ('التدقيق المتقدم 009','لم يتم تشغيله؛ مكان الباب وخلوص الفتح ومسارات الجسم غير مؤكد'),
 ('اعتماد معماري / كود البناء','غير متحقق؛ السكن غير جاهز للتنفيذ'),
]
y=208
for i,(k,v) in enumerate(rows):
    d.rounded_rectangle((100,y-9,W-100,y+108),radius=13,fill='#f2f6f9' if i%2==0 else '#ffffff',outline='#dce5e9',width=1)
    text(d,W-135,y+8,k,FQ,'#153b5b')
    text(d,W-135,y+58,v,F,'#425367')
    y+=129
footer(d);pages.append(p)

c=canvas.Canvas(str(OUT),pagesize=landscape(A3),pageCompression=1)
from reportlab.lib.utils import ImageReader
for img in pages:
    c.drawImage(ImageReader(img),0,0,width=landscape(A3)[0],height=landscape(A3)[1])
    c.showPage()
c.save()
pages[0].save(OUTPUT/'ANT_STAGE_012_Concept_Preview.png')
print(str(OUT), 'pages',len(pages),'hall before',base,'after',after)