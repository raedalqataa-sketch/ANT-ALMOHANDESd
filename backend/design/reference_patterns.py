"""Design preferences derived from 6 retained user-supplied projects, never statutory rules.

Raw drawings, names and contact details are not runtime data. The checked visual
inventory and its uncertainties live in quality_review/reference_library/catalog.json.
"""
import heapq
import math
from itertools import combinations

REVISION='reference-principles-2'
UNIQUE_IMAGES=19
EXCLUDED_PROJECTS=('P02','P05')
PROJECTS=('P01','P03','P04','P06','P07','P08')
RULES=(
 {'id':'REF-guest-sequence','sources':['P01','P04','P07','P08'],'kind':'existing_geometric_invariant','meaning_ar':'مدخل ضيوف وموزع يخدم المجلس والحمام دون المرور بالأسرة'},
 {'id':'REF-family-node','sources':list(PROJECTS),'kind':'design_preference','meaning_ar':'ترابط المعيشة والطعام والنواة مع تقليل الحركة العابرة للغرف الخاصة'},
 {'id':'REF-service-route','sources':list(PROJECTS),'kind':'geometric_invariant','meaning_ar':'خدمة المطبخ للطعام والحمام للنوم دون المرور بغرفة نوم أخرى أو منطقة الضيوف'},
 {'id':'REF-wet-stack','sources':['P01','P03','P04','P06','P07','P08'],'kind':'design_preference','meaning_ar':'تقارب وتراكب الخدمات بين الأدوار؛ ليس تصميم تمديدات معتمدًا'},
 {'id':'REF-core','sources':['P01','P03','P04','P06','P07','P08'],'kind':'existing_geometric_invariant','meaning_ar':'استمرار موضع النواة الرأسية؛ قراءة الصور تقريبية ويعاد الفحص في النموذج'},
 {'id':'REF-outlook','sources':list(PROJECTS),'kind':'design_preference','meaning_ar':'توجيه نوافذ المعيشة إلى فسحة أو فناء؛ لا يثبت حق الفتح أو معدلات التهوية'},
 {'id':'REF-upper-retreat','sources':['P01','P03','P06','P07','P08'],'kind':'capability_limit','meaning_ar':'الملحق متراجع والتراسات جزء من التكوين؛ لا تستخلص نسب بناء قانونية'},
 {'id':'REF-double-height','sources':['P01','P03','P06'],'kind':'deferred','meaning_ar':'الفراغ المزدوج عنصر اختياري يحتاج نموذج فتحات بلاطات ودرابزين وإنشاء'},
 {'id':'REF-basement','sources':['P03','P06'],'kind':'deferred','meaning_ar':'القبو يحتاج دعم مناسيب وإخلاء وتهوية وعزل وليس طابقًا عاديًا باسم جديد'},
)
WET={'bathroom','kitchen','laundry'}
PRIVATE={'bedroom','master','bathroom'}

def graph(floor):
    rooms={r['id']:r for r in floor['rooms']};g={k:{} for k in rooms}
    walls={w['id']:w for w in floor['walls']}
    def center(r):return (r['x']+r['width']/2,r['y']+r['depth']/2)
    for o in floor['openings']:
        ids=o.get('connects',[]);w=walls.get(o.get('wall_id'))
        if o['kind']!='door' or len(ids)!=2 or not w or any(i not in rooms or i not in w['room_ids'] for i in ids):continue
        axis=0 if w['axis']=='horizontal' else 1
        if abs(o['center'][1-axis]-w['start'][1-axis])>1e-5:continue
        if o['center'][axis]-o['width']/2<min(w['start'][axis],w['end'][axis])-1e-5 or o['center'][axis]+o['width']/2>max(w['start'][axis],w['end'][axis])+1e-5:continue
        a,b=ids;weight=math.dist(center(rooms[a]),o['center'])+math.dist(o['center'],center(rooms[b]))
        g[a][b]=g[b][a]=weight
    halls=[r for r in floor['cells'] if r['kind']=='corridor' and not r.get('guest_distributor')]
    for a,b in combinations(halls,2):
        dx=min(a['x']+a['width'],b['x']+b['width'])-max(a['x'],b['x'])
        dy=min(a['y']+a['depth'],b['y']+b['depth'])-max(a['y'],b['y'])
        if (abs(dx)<1e-6 and dy>.6) or (abs(dy)<1e-6 and dx>.6):
            weight=math.dist(center(a),center(b));g[a['id']][b['id']]=g[b['id']][a['id']]=weight
    return rooms,g

def route(rooms,g,start,target):
    """Physical door graph with private and guest rooms forbidden as transit nodes."""
    distances={start:0};queue=[(0,start)]
    while queue:
        cost,node=heapq.heappop(queue)
        if cost>distances[node]:continue
        if node==target:return cost
        for nxt,weight in g.get(node,{}).items():
            if nxt not in (start,target) and (rooms[nxt]['kind'] in PRIVATE or rooms[nxt].get('zone')=='guest'):continue
            value=cost+weight
            if value<distances.get(nxt,math.inf):distances[nxt]=value;heapq.heappush(queue,(value,nxt))
    return None

def functional_routes(model):
    rows=[]
    for f in model['floors']:
        rooms,g=graph(f)
        required=[r for r in rooms.values() if r.get('request_id')]
        for kind,target in [('kitchen','dining'),('living','dining'),('bedroom','bathroom'),('master','bathroom')]:
            targets=[r for r in required if r['kind']==target and r.get('zone')!='guest']
            if not targets:continue # User's program may have no dining/ensuite on this floor.
            for a in (r for r in required if r['kind']==kind):
                choices=[(route(rooms,g,a['id'],b['id']),b) for b in targets]
                choices=[(d,b) for d,b in choices if d is not None]
                if not choices:
                    rows.append({'floor':f['id'],'from':a['id'],'target_kind':target,'reachable':False,'route_m':None,'direct_m':None});continue
                d,b=min(choices,key=lambda p:p[0]);direct=math.dist((a['x']+a['width']/2,a['y']+a['depth']/2),(b['x']+b['width']/2,b['y']+b['depth']/2))
                rows.append({'floor':f['id'],'from':a['id'],'to':b['id'],'target_kind':target,'reachable':True,'route_m':round(d,4),'direct_m':round(direct,4)})
    return rows

def wet_alignment(model):
    aligned=total=0;pairs=[]
    for lower,upper in zip(model['floors'],model['floors'][1:]):
        below=[r for r in lower['rooms'] if r['kind'] in WET and r.get('request_id')]
        above=[r for r in upper['rooms'] if r['kind'] in WET and r.get('request_id')]
        for r in above:
            area=r['width']*r['depth'];overlap=0
            for q in below:
                hit=max(0,min(r['x']+r['width'],q['x']+q['width'])-max(r['x'],q['x']))*max(0,min(r['y']+r['depth'],q['y']+q['depth'])-max(r['y'],q['y']))
                if hit:pairs.append({'lower':q['id'],'upper':r['id'],'overlap_m2':round(hit,4)});overlap+=hit
            total+=area;aligned+=min(area,overlap)
    return {'ratio':round(aligned/total,5) if total else None,'overlap_m2':round(aligned,4),'upper_wet_area_m2':round(total,4),'pairs':pairs,
        'scope':'2D net wet-room overlap only; shafts, drainage gradients and structure are NOT verified'}

def outlook(model):
    result=[]
    for f in model['floors']:
        walls={w['id']:w for w in f['walls']}
        for r in f['rooms']:
            if r['kind']!='living' or not r.get('request_id'):continue
            clearances=[]
            for o in f['openings']:
                w=walls.get(o.get('wall_id'))
                if o['kind']!='window' or r['id'] not in o.get('connects',[]) or not w or not w.get('exterior'):continue
                axis=1 if w['axis']=='horizontal' else 0;cross=1-axis
                point=o['center'][axis];side=-1 if point<r['y' if axis else 'x']+(r['depth' if axis else 'width']/2) else 1
                limit=(model['site']['depth'] if axis else model['site']['width'])
                distance=point if side<0 else limit-point
                for c in f['cells']:
                    if c['id']==r['id']:continue
                    start=c['y' if axis else 'x'];end=start+c['depth' if axis else 'width']
                    lo=c['x' if axis else 'y'];hi=lo+c['width' if axis else 'depth']
                    if not lo-1e-6<=o['center'][cross]<=hi+1e-6:continue
                    gap=(start-point) if side>0 else (point-end)
                    if gap>=-1e-6:distance=min(distance,max(0,gap))
                clearances.append(max(0,distance))
            result.append({'floor':f['id'],'room_id':r['id'],'best_unobstructed_own_plot_depth_m':round(max(clearances),4) if clearances else None})
    return result

def measure(model):
    paths=functional_routes(model);stack=wet_alignment(model);views=outlook(model)
    usable=[r for r in paths if r['reachable']];failures=[r for r in paths if not r['reachable']]
    # Numeric scales are explicit engineering preferences, NOT extracted laws.
    detours=[max(0,r['route_m']/max(r['direct_m'],1)-1) for r in usable]
    penalties=[min(sum(detours)/max(1,len(detours))/2,1)] if usable else []
    if stack['ratio'] is not None:penalties.append(1-stack['ratio'])
    depths=[v['best_unobstructed_own_plot_depth_m'] for v in views if v['best_unobstructed_own_plot_depth_m'] is not None]
    if depths:penalties.append(1-sum(min(d/4,1) for d in depths)/len(depths))
    return {'revision':REVISION,'sources':list(PROJECTS),'legal_rule':False,'functional_routes':paths,'missing_functional_routes':failures,
        'wet_alignment':stack,'living_outlook':views,'design_penalty':round(sum(penalties)/len(penalties),6) if penalties else 0,
        'scales':{'route_detour_scale':2,'outlook_depth_scale_m':4,'status':'design heuristics, not dimensions read from images or legal requirements'},
        'scope':'visual design patterns only; no owner data, survey reconstruction, 3D daylight, privacy certification or local-code approval'}

def checks(model,brief):
    if brief.reference_strategy=='none':return []
    invalid=[r for r in functional_routes(model) if not r['reachable']]
    return [{'check_id':'REF-functional-route','status':'FAIL' if invalid else 'PASS','label':'العلاقات الوظيفية دون عبور غرف نوم أخرى أو منطقة الضيوف',
        'evidence':{'invalid':invalid,'scope':'hosted doors and open corridor seams; not an egress or legal certification'},
        'source':{'id':REVISION,'section':'design-invariant','projects':list(PROJECTS),'legal_rule':False}}]
