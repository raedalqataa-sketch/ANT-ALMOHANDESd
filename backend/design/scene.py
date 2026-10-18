"""Shared, deterministic metric drawing primitives. No raster plan synthesis."""
import math


class Scene:
    def __init__(self,viewbox):
        self.viewbox=viewbox;self.items=[]
    def rect(self,x,y,w,h,fill='none',stroke='none',lw=.015,layer='FINISH',radius=0,**meta):
        self.items.append(dict(type='rect',x=x,y=y,width=w,depth=h,fill=fill,stroke=stroke,lw=lw,layer=layer,radius=radius,**meta))
    def line(self,a,b,stroke='#777b75',lw=.015,layer='DETAIL',dash=None,**meta):
        self.items.append(dict(type='line',a=a,b=b,stroke=stroke,lw=lw,layer=layer,dash=dash,**meta))
    def poly(self,points,fill='none',stroke='#777b75',lw=.015,layer='DETAIL',closed=True,**meta):
        self.items.append(dict(type='poly',points=points,fill=fill,stroke=stroke,lw=lw,layer=layer,closed=closed,**meta))
    def ellipse(self,x,y,w,h,fill='none',stroke='#777b75',lw=.015,layer='DETAIL'):
        self.items.append(dict(type='ellipse',x=x,y=y,width=w,depth=h,fill=fill,stroke=stroke,lw=lw,layer=layer))
    def text(self,x,y,text,size=.28,color='#303633',align='center',layer='TEXT',role=None):
        self.items.append(dict(type='text',x=x,y=y,text=str(text),size=size,color=color,align=align,layer=layer,role=role))
    def curve(self,points,stroke='#8b887b',lw=.018,layer='DOOR'):
        self.items.append(dict(type='curve',points=points,stroke=stroke,lw=lw,layer=layer))


def furniture_symbol(scene,q):
    rot=q.get('rotation',0);W,H=(q['depth'],q['width']) if rot in (90,270) else (q['width'],q['depth'])
    def pt(x,y):
        if rot==0:return(q['x']+x,q['y']+y)
        if rot==90:return(q['x']+q['width']-y,q['y']+x)
        if rot==180:return(q['x']+q['width']-x,q['y']+q['depth']-y)
        return(q['x']+y,q['y']+q['depth']-x)
    def box(x,y,w,h,fill='#eee9df',stroke='#777a72',lw=.015,radius=0):
        corners=[pt(x,y),pt(x+w,y),pt(x+w,y+h),pt(x,y+h)]
        xs=[p[0] for p in corners];ys=[p[1] for p in corners]
        scene.rect(min(xs),min(ys),max(xs)-min(xs),max(ys)-min(ys),fill,stroke,lw,'FURNITURE',radius=radius)
    def line(a,b,lw=.012,stroke='#8f9187'):scene.line(pt(*a),pt(*b),stroke,lw,'FURNITURE')
    def ellipse(x,y,w,h,fill='none',stroke='#777a72',lw=.014):
        a=pt(x,y);b=pt(x+w,y+h)
        scene.ellipse(min(a[0],b[0]),min(a[1],b[1]),abs(b[0]-a[0]),abs(b[1]-a[1]),fill,stroke,lw,'FURNITURE')
    kind=q['kind']
    if kind in ('single_bed','double_bed'):
        box(0,0,W,H,'#b9b1a2','#6f736b',.018,.035)
        box(.045,.08,W-.09,H-.13,'#faf8f1','#8a8e83',.013,.035)
        box(.07,.62,W-.14,H-.71,'#d6cbb8','#a39884',.012,.035)
        line((.07,.68),(W-.07,.68),.02)
        pillows=2 if kind=='double_bed' else 1
        for i in range(pillows):
            pw=(W-.22)/pillows-.04;px=.11+i*(pw+.04)
            box(px,.16,pw,.34,'#fffef8','#a5a69b',.013,.045)
        points=[pt(W*.18,.80),pt(W*.25,1.12),pt(W*.14,1.40),pt(W*.22,H-.14)]
        scene.poly(points,'none','#b7aa96',.015,'FURNITURE',False)
    elif kind=='sofa':
        box(0,0,W,H,'#c4bcae','#76786f',.018,.06)
        box(.03,.03,W-.06,.16,'#ada697','#8a8678',.01,.025)
        box(.035,.18,.15,H-.22,'#d2cabd','#8e8b7e',.01,.02)
        box(W-.185,.18,.15,H-.22,'#d2cabd','#8e8b7e',.01,.02)
        n=max(2,q.get('seats',3));sw=(W-.40)/n
        for i in range(n):box(.2+i*sw,.22,sw-.025,H-.27,'#e6dfd2','#9a978a',.011,.025)
    elif kind in ('wardrobe','storage'):
        box(0,0,W,H,'#d3c6b3','#838276',.018)
        n=max(2,int(W/.55));sw=W/n
        for i in range(n):
            line((i*sw,0),(i*sw,H))
            line((i*sw+.04,.05),((i+1)*sw-.04,H-.05),.008,'#a59d8c')
            line(((i+1)*sw-.06,H*.4),((i+1)*sw-.06,H*.65),.018,'#797a70')
    elif kind=='dining_table':
        box(0,0,W,H,'#bca78d','#7c796b',.018,.12)
        box(.04,.04,W-.08,H-.08,'#d0bfa5','#b2a088',.009,.10)
        line((.2,H*.25),(W-.2,H*.25),.008,'#bcae98')
        line((.2,H*.75),(W-.2,H*.75),.008,'#bcae98')
    elif kind=='dining_chair':
        box(0,0,W,H,'#d9d0bf','#8e8d7e',.014,.07)
        box(.04,.02,W-.08,.09,'#b6ad9b','#8e8d7e',.01,.03)
        box(.045,.14,W-.09,H-.18,'#eee7d9','#aaa595',.008,.035)
    elif kind in ('coffee_table','bedside'):
        box(0,0,W,H,'#d0c1a8','#828174',.015,.035)
        box(.035,.035,W-.07,H-.07,'#f1eade','#b7ae9b',.01,.02)
        if kind=='bedside':ellipse(W*.35,H*.3,W*.30,H*.3,'#f7f3e8','#a19883',.012)
        else:
            box(W*.18,H*.24,min(.22,W*.3),min(.18,H*.4),'#aea992','#b0ac97',.008)
            ellipse(W*.65,H*.36,.12,.12,'#faf8ee','#9b9d8a',.01)
    elif kind in ('kitchen_counter','kitchen_island'):
        box(0,0,W,H,'#d3d5cc','#747d75',.02)
        box(.025,.025,W-.05,H-.05,'#f2f1e9','#a8afa5',.01)
        n=max(1,int(W/.6))
        for i in range(1,n):line((W*i/n,.04),(W*i/n,H-.04),.008,'#c1c5ba')
    elif kind=='sink':
        box(.01,.01,W-.02,H-.02,'#adb7b3','#717d79',.018,.03)
        box(.06,.06,W-.12,H-.12,'#edf2ef','#8c9992',.013,.06)
        ellipse(W*.45,H*.40,.08,.08,'#81968c','#81968c',.008)
        line((W*.5,-.03),(W*.5,.13),.025,'#7a8c82')
    elif kind=='cooker':
        box(0,0,W,H,'#d8ddd6','#778479',.015,.02)
        for px in (.25,.75):
            for py in (.28,.72):ellipse(W*px-.075,H*py-.075,.15,.15,'#8b9389','#5d6c60',.013)
    elif kind=='fridge':
        box(0,0,W,H,'#d9ddd5','#7b887c',.02,.025)
        line((0,H*.36),(W,H*.36),.015)
        line((W-.1,.08),(W-.1,H*.28),.025,'#758072')
        line((W-.1,H*.45),(W-.1,H-.08),.025,'#758072')
    elif kind=='toilet':
        box(.045,0,W-.09,.21,'#f4f6f0','#73877c',.018,.035)
        ellipse(.06,.14,W-.12,H-.16,'#fdfef8','#718479',.018)
        ellipse(.14,.25,W-.28,H-.35,'#e4ece5','#91a397',.012)
        ellipse(W/2-.025,.075,.05,.05,'#859a8b','#859a8b',.008)
    elif kind=='basin':
        box(0,0,W,H,'#cbbba4','#8a8c7d',.018)
        box(.035,.035,W-.07,H-.07,'#f5f4eb','#b3b4a6',.012)
        ellipse(W*.16,H*.19,W*.68,H*.63,'#fdfef6','#778c7d',.016)
        line((W*.5,.015),(W*.5,H*.25),.025,'#7f8d7e')
    elif kind=='shower':
        box(0,0,W,H,'#dbe5df','#77968a',.018)
        for i in range(1,4):
            line((W*i/4,0),(W*i/4,H),.007,'#aec1b6');line((0,H*i/4),(W,H*i/4),.007,'#aec1b6')
        line((.025,.025),(W-.025,H-.025),.01,'#8ca89a')
        line((0,H),(W,H),.035,'#7faaa0')
        ellipse(W/2-.05,H/2-.05,.1,.1,'#889f91','#697e70',.012)
        line((W*.8,.02),(W*.8,.2),.035,'#718b7b')
    elif kind=='washing_machine':
        box(0,0,W,H,'#f0f3eb','#7c8b7c',.018,.02)
        line((.03,.14),(W-.03,.14),.012)
        ellipse(W*.15,H*.25,W*.7,H*.65,'#cddbd0','#7d9282',.02)
        ellipse(W*.22,H*.32,W*.56,H*.5,'#e6eee6','#9cb1a0',.012)
    elif kind=='desk':
        box(0,0,W,H,'#c6b99f','#838572',.018,.025)
        box(.12,.13,.5,.33,'#cad4ca','#788c7b',.012,.015)
        box(.2,.48,.35,.08,'#eceee5','#93a18c',.01)
    else:box(0,0,W,H)


def tree_symbol(scene,cx,cy,r,seed=0):
    points=[]
    for i in range(32):
        angle=2*math.pi*i/32;rr=r*(.82+.13*math.sin(i*2.3+seed)+.05*math.cos(i*4.1))
        points.append((cx+math.cos(angle)*rr,cy+math.sin(angle)*rr))
    scene.poly(points,'#dce3cd','#a3af92',.014,'LANDSCAPE')
    for i in range(12):
        a=2*math.pi*i/12+.12*seed
        scene.line((cx,cy),(cx+math.cos(a)*r*.72,cy+math.sin(a)*r*.72),'#b3bea2',.011,'LANDSCAPE')
    scene.ellipse(cx-.06,cy-.06,.12,.12,'#b3ad90','#9a9f84',.012,'LANDSCAPE')


def car_symbol(scene,p):
    x=p['x']+(p['width']-1.9)/2;y=p['y']+(p['depth']-4.5)/2
    scene.rect(x,y,1.9,4.5,'#d3d7d0','#788178',.025,'PARKING',radius=.28)
    scene.rect(x+.12,y+.16,1.66,4.18,'#f8f8f0','#8d9488',.015,'PARKING',radius=.23)
    scene.rect(x+.22,y+1.15,1.46,1.65,'#d4dfda','#97a799',.017,'PARKING',radius=.09)
    scene.line((x+.28,y+1.65),(x+1.62,y+1.65),'#b0bbae',.012,'PARKING')
    scene.line((x+.28,y+2.45),(x+1.62,y+2.45),'#b0bbae',.012,'PARKING')
    for side in (-.07,1.85):
        for py in (.8,3.0):scene.rect(x+side,y+py,.12,.6,'#69786c','#69786c',.01,'PARKING',radius=.03)
    for sx in (.12,1.48):
        scene.rect(x+sx,y+.14,.3,.14,'#e7e9c8','#aeb299',.01,'PARKING',radius=.035)


def dimension(scene,a,b,label,offset=.45):
    horizontal=abs(a[1]-b[1])<1e-6
    if horizontal:
        aa=(a[0],a[1]+offset);bb=(b[0],b[1]+offset)
        for p in (a,b):scene.line((p[0],p[1]+offset-.15),(p[0],p[1]+offset+.15),'#858a80',.012,'DIMENSION')
        scene.text((aa[0]+bb[0])/2,aa[1]-.10,label,.25,'#646d61',layer='DIMENSION')
    else:
        aa=(a[0]+offset,a[1]);bb=(b[0]+offset,b[1])
        for p in (a,b):scene.line((p[0]+offset-.15,p[1]),(p[0]+offset+.15,p[1]),'#858a80',.012,'DIMENSION')
        scene.text(aa[0]-.18,(aa[1]+bb[1])/2,label,.24,'#646d61',layer='DIMENSION')
    scene.line(aa,bb,'#858a80',.012,'DIMENSION')
    for p in (aa,bb):scene.line((p[0]-.07,p[1]+.10),(p[0]+.07,p[1]-.10),'#6a7468',.025,'DIMENSION')


def label_position(room,floor):
    text=room['name'].replace(' — مقترح','');text=text.replace('غرفة ضيف أو كبير سن','ضيف / كبير سن').replace('غرفة النوم الرئيسية','النوم الرئيسية')
    size=max(.21,min(.31,room['width']/(max(4,len(text))*.5+1)))
    w=min(room['width']-.15,max(1,len(text)*size*.50));h=.75
    obstacles=[q for q in floor['furniture'] if q['room_id']==room['id'] and q.get('physical',True)]
    def area_overlap(q,b):return max(0,min(q['x']+q['width'],b['x']+b['width'])-max(q['x'],b['x']))*max(0,min(q['y']+q['depth'],b['y']+b['depth'])-max(q['y'],b['y']))
    candidates=[]
    for fy in (.58,.74,.43,.86,.22):
        for fx in (.5,.3,.7):
            x=max(room['x']+.08,min(room['x']+room['width']-w-.08,room['x']+fx*room['width']-w/2))
            y=max(room['y']+.08,min(room['y']+room['depth']-h-.08,room['y']+fy*room['depth']-h/2))
            box=dict(x=x,y=y,width=w,depth=h)
            score=sum(area_overlap(q,box) for q in obstacles)
            candidates.append((score,abs(fy-.58),abs(fx-.5),box))
    best=min(candidates,key=lambda c:c[:3]);return text,size,best[-1],best[0]


def architectural_scene(model,floor,site_view=False):
    from .export import wall_runs,door_symbol,stair_lines
    pw,pd=model['site']['width'],model['site']['depth']
    scene=Scene((-1.4,-2.4,pw+2.8,pd+4.8))
    scene.rect(-1.4,-2.4,pw+2.8,pd+4.8,'#fffef9',layer='PAPER')
    scene.rect(0,0,pw,pd,'#f5f4ec','#9ba38f',.025,'SITE')
    for feature in model.get('site_features',[]):
        x,y,w,h=(feature[k] for k in ('x','y','width','depth'))
        scene.rect(x,y,w,h,'#e5ead8' if feature['kind']=='garden' else '#e8e5db',stroke='none',layer='LANDSCAPE')
        if feature['kind']=='garden':
            for i,ty in enumerate([y+1.4,y+h*.31,y+h*.56,y+h*.80,y+h-1.4]):
                tree_symbol(scene,x+w/2,ty,min(w*.41,1.25),i)
        else:
            for i in range(1,int(h/.8)):
                scene.line((x,y+i*.8),(x+w,y+i*.8),'#d1d1c4',.01,'LANDSCAPE')
    # First-floor underlay exposes alignment and the relation to the actual ground plan.
    if floor['id']=='FF':
        for r in model['floors'][0]['rooms']:
            scene.rect(r['x'],r['y'],r['width'],r['depth'],'#ecece4','#dadcd1',.015,'UNDERLAY')
    for t in floor.get('terraces',[]):
        scene.rect(t['x'],t['y'],t['width'],t['depth'],'#e7eadf' if not t.get('walkable',True) else '#e0dbcb','#999f8e',.025,'TERRACE')
        for i in range(1,int(t['depth']/.18)):
            scene.line((t['x']+.05,t['y']+i*.18),(t['x']+t['width']-.05,t['y']+i*.18),'#c4beaa',.008,'TERRACE')
        scene.text(t['x']+t['width']/2,t['y']+t['depth']*.6,t['name'],.26,'#687160',layer='TERRACE')
    for r in floor['rooms']:
        if site_view:
            scene.rect(r['x']-.1,r['y']-.1,r['width']+.2,r['depth']+.2,'#e4dfd0',layer='SITE_MASS');continue
        wet=r['kind'] in ('kitchen','bathroom','wash','laundry');wood=r['kind'] in ('bedroom','master','elderly','majlis','office','dressing')
        scene.rect(r['x'],r['y'],r['width'],r['depth'],'#dfe6e0' if wet else '#eae1d2' if wood else '#eeece3',layer='ROOM_FINISH')
        spacing=.20 if wood else .38 if wet else .75
        for i in range(1,int(r['depth']/spacing)):
            scene.line((r['x'],r['y']+i*spacing),(r['x']+r['width'],r['y']+i*spacing),'#d5ccb9' if wood else '#cedbd0' if wet else '#d9dacd',.008,'FINISH_GRID')
        if not wood:
            for i in range(1,int(r['width']/spacing)):
                scene.line((r['x']+i*spacing,r['y']),(r['x']+i*spacing,r['y']+r['depth']),'#cedbd0' if wet else '#d9dacd',.008,'FINISH_GRID')
    for v in floor.get('voids',[]):
        scene.rect(v['x'],v['y'],v['width'],v['depth'],'#f7f6f0','#a9af9e',.018,'VOID')
        gf=next((r for r in model['floors'][0]['rooms'] if r['id']==v['below_room']),None)
        if gf:
            for q in model['floors'][0]['furniture']:
                if q['room_id']==gf['id']:
                    # True model-derived underlay, not a separately invented room illustration.
                    scene.rect(q['x'],q['y'],q['width'],q['depth'],'#efeee5','#d3d7ca',.013,'UNDERLAY')
        scene.line((v['x'],v['y']),(v['x']+v['width'],v['y']+v['depth']),'#b6bdac',.014,'VOID',[.10,.09])
        scene.line((v['x']+v['width'],v['y']),(v['x'],v['y']+v['depth']),'#b6bdac',.014,'VOID',[.10,.09])
        scene.text(v['x']+v['width']/2,v['y']+v['depth']/2,v['name'],.27,'#737f6a',layer='VOID')
    for rail in floor.get('guardrails',[]):
        scene.line(rail['start'],rail['end'],'#7a8774',.085,'RAILING')
        scene.line((rail['start'][0]+.06,rail['start'][1]+.06),(rail['end'][0]+.06,rail['end'][1]+.06),'#bac2ae',.025,'RAILING')
    for q in floor.get('outdoor_furniture',[]) if not site_view else []:furniture_symbol(scene,q)
    for q in floor.get('decorations',[]) if not site_view else []:
        if q['kind']=='rug':
            scene.rect(q['x'],q['y'],q['width'],q['depth'],'#ddd5c4','#c6baa2',.018,'DECORATION',radius=.025)
            scene.rect(q['x']+.1,q['y']+.1,q['width']-.2,q['depth']-.2,'none','#c3b69c',.012,'DECORATION')
    for q in floor['furniture'] if not site_view else []:furniture_symbol(scene,q)
    for s in model['stairs'] if not site_view else []:
        for a,b in stair_lines(s):scene.line(a,b,'#6d796a',.022,'STAIR')
        left=s['x']+s['flight_width_m']/2;right=s['x']+s['width']-s['flight_width_m']/2
        yb=s['y']+s['depth']-.2;yt=s['y']+s['landing_depth_m']/2
        going_up=floor['id']==s['floor_id'];start,end=(left,right) if going_up else (right,left)
        scene.poly([(start,yb),(start,yt),(end,yt),(end,yb)],'none','#566a5a',.025,'STAIR',closed=False)
        scene.poly([(end,yb),(end-.11,yb-.24),(end+.11,yb-.24)],'#566a5a','#566a5a',.012,'STAIR')
        scene.text(start-.05,(yb+yt)/2,'صعود' if going_up else 'نزول',.22,'#536752',layer='STAIR')
    for wall in floor['walls']:
        if site_view and not wall['exterior']:continue
        for a,b in wall_runs(floor,wall):
            if wall.get('boundary_type')=='guardrail':
                scene.line(a,b,'#6f8977',.045,'RAILING')
                continue
            scene.line((a[0]+.055,a[1]+.055),(b[0]+.055,b[1]+.055),'#b1b6a5',wall['thickness']+.06,'SHADOW')
            scene.line(a,b,'#303c32',wall['thickness'],'WALL')
    for o in floor['openings']:
        if site_view and 'EXTERIOR' not in o['connects']:continue
        wall=next(w for w in floor['walls'] if w['id']==o['wall_id']);x,y=o['center'];ow=o['width']
        if o['kind']=='window':
            for off in (-.065,0,.065):
                a,b=((x+off,y-ow/2),(x+off,y+ow/2)) if wall['axis']=='vertical' else ((x-ow/2,y+off),(x+ow/2,y+off))
                scene.line(a,b,'#6f9690',.018,'WINDOW')
            for d in (-ow/2,ow/2):
                a,b=((x-.10,y+d),(x+.10,y+d)) if wall['axis']=='vertical' else ((x+d,y-.10),(x+d,y+.10))
                scene.line(a,b,'#566e5b',.025,'WINDOW')
        elif o['kind']=='door':
            hinge,leaf,closed,c1,c2=door_symbol(floor,o)
            scene.line(hinge,leaf,'#929077',.025,'DOOR')
            scene.curve([closed,c1,c2,leaf],'#b0aa91',.018,'DOOR')
    if floor['id']=='GF':
        for o in floor['openings']:
            if o['kind']!='door' or 'EXTERIOR' not in o['connects'] or not o['connects'][0].endswith(('-hall','-men')):continue
            x,y=o['center'];face=o['face'];dx,dy={'south':(0,-1),'north':(0,1),'west':(1,0),'east':(-1,0)}[face]
            tip=(x-dx*.1,y-dy*.1);tail=(x-dx*.75,y-dy*.75)
            scene.line(tail,tip,'#a9846b',.035,'ENTRY')
            perp=(-dy,dx)
            scene.poly([tip,(tip[0]-dx*.20+perp[0]*.10,tip[1]-dy*.20+perp[1]*.10),(tip[0]-dx*.20-perp[0]*.10,tip[1]-dy*.20-perp[1]*.10)],'#a9846b','#a9846b',.01,'ENTRY')
    for r in floor['rooms']:
        if site_view or r['kind']=='stairs':continue
        label,size,b,overlap_area=label_position(r,floor)
        xx=b['x']+b['width']/2;yy=b['y']+.28
        scene.text(xx,yy,label,size,'#253b2d',role='room-label')
        scene.text(xx,yy+.34,f"{r['width']:.2f} × {r['depth']:.2f}",.20,'#7a8470',role='room-dimensions')
    for p in model['parking']:
        scene.rect(p['x'],p['y'],p['width'],p['depth'],'#e9e7dc','#b7beaa',.014,'PARKING')
        car_symbol(scene,p)
    # Titles and dimensions form a clean board; detailed caveats belong to the report sheet.
    dimension(scene,(0,0),(pw,0),f'{pw:.2f}',-.7)
    dimension(scene,(0,0),(0,pd),f'{pd:.2f}',-.7)
    fp=model['footprint'];dimension(scene,(fp['x'],fp['y']),(fp['x']+fp['width'],fp['y']),f"{fp['width']:.2f}",-.35)
    scene.text(pw/2,-1.55,model['profile']['project_name']+' — '+floor['name'],.52,'#243d2c',layer='TITLE')
    scene.text(pw/2,-1.02,model['search'].get('family_label_ar','مقترح معماري'),.25,'#7b866e',layer='TITLE')
    scene.text(pw/2,pd+.65,'مسودة تصميم للمراجعة — غير صالحة للتنفيذ',.28,'#9a6a51',layer='TITLE')
    scene.text(pw/2,pd+1.10,'الأبعاد والفرش مقترحة · اتجاه الموقع والارتدادات والفتحات النظامية غير متحققة',.20,'#8a927c',layer='TITLE')
    # Metric scale bar is valid independent of fitting or viewer zoom.
    bx=pw-5.5;by=pd+1.65
    for i in range(5):scene.rect(bx+i,by,1,.10,'#586a56' if i%2==0 else '#fbfbf4','#6f7f65',.008,'SCALE')
    for i in (0,1,3,5):scene.text(bx+i,by-.12,str(i),.19,'#6a785f',layer='SCALE')
    scene.text(bx+2.5,by+.40,'متر',.18,'#7e8a70',layer='SCALE')
    scene.text(1.9,pd+1.8,'N ↑ بحسب المصدر',.20,'#8a927c',layer='TITLE')
    return scene
