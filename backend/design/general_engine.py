"""Metric wing search for rectangular villa plots (1–2 floors).

Copyright (c) 2026 ANT ALMOHANDES. New module licensed under MIT; see
web_generator/ENGINE_LICENSE. Beam search assigns the actual requested spaces to
variable wing lanes; there is no pre-filled family program or raster synthesis.
"""
import copy
import hashlib
import json
import math
from pathlib import Path
from uuid import uuid4
from .general_models import VillaBrief
from .furnishing import furnish_floor, overlap, inside
from .furniture_symbols import SYMBOL_VERSION

EPS=1e-6
FAMILIES={'L':'جناحان على شكل L','U':'فناء مفتوح على شكل U','stepped':'كتلة متدرجة'}


def box(x,y,w,d,**kw):return dict(x=x,y=y,width=w,depth=d,**kw)
def area(r):return r['width']*r['depth']


def topology(family,W,D,c,ratio,top):
    """Disjoint cells tile a nonrectangular mass; lanes abut connected halls."""
    a=W*ratio;b=D*top
    if family in ('L','U'):
        halls=[box(a-c,0,c,D),box(a,b-c,W-a,c)]
        lanes=[box(0,0,a-c,D,axis='y',door_side='east'),box(a,0,W-a,b-c,axis='x',door_side='south')]
        if family=='U':
            if W-2*a<2.4:return None
            halls.append(box(W-a,b,c,D-b))
            lanes.append(box(W-a+c,b,a-c,D-b,axis='y',door_side='west'))
        return halls,lanes
    # Two genuine recesses; a continuous spine connects both sides of all steps.
    spine=W*.5-c/2
    halls=[box(spine,0,c,D)]
    lanes=[]
    for lo,hi,x0,x1 in [(0,D*.33,0,W),(D*.33,D*.67,W*.12,W),(D*.67,D,W*.12,W*.80)]:
        lanes += [box(x0,lo,spine-x0,hi-lo,axis='y',door_side='east'),
                  box(spine+c,lo,x1-spine-c,hi-lo,axis='y',door_side='west')]
    return halls,lanes


def length_for(room,lane,t):
    cross=lane['width' if lane['axis']=='y' else 'depth']-t
    if cross+EPS<room['min_side']:return math.inf
    length=max(room['min_side'],room['min_area']/cross,cross/2.8)
    if room['kind']=='bathroom' and cross*length>room['min_area']*2.2:return math.inf
    if max(cross,length)/min(cross,length)>2.8:return math.inf
    return length+t


def allocate(requests,lanes,t):
    """Bounded beam search, rejecting area/width violations before placement."""
    capacities=[r['depth' if r['axis']=='y' else 'width'] for r in lanes]
    states=[([0.]*len(lanes),[[] for _ in lanes])]
    ordered=sorted(requests,key=lambda r:(-r['min_side'],-r['min_area'],r['id']))
    for room in ordered:
        expanded=[]
        for used,groups in states:
            for i,lane in enumerate(lanes):
                length=length_for(room,lane,t)
                if used[i]+length>capacities[i]+EPS:continue
                u=used.copy();u[i]+=length;g=[row.copy() for row in groups];g[i].append(room)
                # Best-fit plus load balance; not an architectural quality score.
                score=sum(((cap-v)*(lanes[j]['width'] if lanes[j]['axis']=='y' else lanes[j]['depth']))**2 for j,(cap,v) in enumerate(zip(capacities,u)))
                expanded.append((score,u,g))
        if not expanded:return None
        expanded.sort(key=lambda state:state[0]);states=[(u,g) for _,u,g in expanded[:20]]
    used,groups=min(states,key=lambda s:sum((cap-v)**2 for cap,v in zip(capacities,s[0])))
    cells=[]
    for i,lane in enumerate(lanes):
        axis=lane['axis'];start=lane['y' if axis=='y' else 'x']
        if not groups[i]:
            cells.append(box(lane['x'],lane['y'],lane['width'],lane['depth'],kind='reserve',name='مساحة احتياطية مقترحة',door_side=lane['door_side']));continue
        extra=capacities[i]-used[i];weights=sum(r['min_area'] for r in groups[i])
        # Functional sequencing along a wing: services then social spaces, bedrooms together.
        order={'bathroom':0,'storage':1,'laundry':2,'kitchen':3,'dining':4,'living':5,'majlis':6,'office':7,'master':8,'bedroom':9}
        for r in sorted(groups[i],key=lambda q:(order[q['kind']],q['id'])):
            length=length_for(r,lane,t)+min(extra*r['min_area']/weights,length_for(r,lane,t)*.15)
            cell=box(lane['x'] if axis=='y' else start,start if axis=='y' else lane['y'],lane['width'] if axis=='y' else length,length if axis=='y' else lane['depth'],**copy.deepcopy(r),door_side=lane['door_side'])
            cells.append(cell);start+=length
        remaining=lane['y' if axis=='y' else 'x']+capacities[i]-start
        if remaining>t+.05:
            if remaining<1.6 and cells and cells[-1].get('request_id'):
                cells[-1]['depth' if axis=='y' else 'width']+=remaining
            else:
                cells.append(box(lane['x'] if axis=='y' else start,start if axis=='y' else lane['y'],lane['width'] if axis=='y' else remaining,remaining if axis=='y' else lane['depth'],kind='reserve',name='مساحة مرنة مقترحة',door_side=lane['door_side']))
    return cells


def expanded_program(brief,floor):
    return [dict(id=f'{r.id}-{n+1}',request_id=r.id,name=r.name+(f' {n+1}' if r.count>1 else ''),kind=r.kind,
                 min_area=r.min_area,min_side=r.min_side,capacity=r.capacity)
            for r in brief.rooms if r.floor==floor for n in range(r.count)]


def search(brief,family):
    aw=brief.plot_width-brief.setbacks.west-brief.setbacks.east
    ad=brief.plot_depth-brief.setbacks.north-brief.setbacks.south
    best=None;attempts=0
    # Each candidate searches dimensions AND allocation, never just scales a fixed plan.
    variations=[(s,d,r,b) for s in (1.,.85,.70) for d in (1.,.82,.68,.55) for r in (.33,.36,.38,.40,.44,.47) for b in (.30,.36,.40,.44,.48)]
    if family=='stepped':variations=[(s,d,.4,.4) for s in (1.,.85,.70) for d in (1.,.82,.68,.55)]
    for ws,ds,ratio,top in variations:
        W,D=aw*ws,ad*ds
        shape=topology(family,W,D,brief.corridor_width+brief.wall_thickness,ratio,top)
        attempts+=1
        if not shape:continue
        halls,lanes=copy.deepcopy(shape)
        if min(min(l['width'],l['depth']) for l in lanes)<1.6:continue
        stair=None
        if brief.floors==2:
            # Reserve an identical vertical core on BOTH floors, before packing rooms.
            eligible=[(i,l) for i,l in enumerate(lanes) if l['axis']=='y' and l['width']-brief.wall_thickness>=2.8 and l['depth']>=4.6]
            if not eligible:continue
            i,l=max(eligible,key=lambda p:p[1]['depth'])
            core_depth=4.6 if l['depth']>=7.0 else l['depth']
            stair=box(l['x'],l['y']+l['depth']-core_depth,l['width'],core_depth,id='stair',kind='stair',name='درج مشترك',door_side=l['door_side'])
            l['depth']-=core_depth
            if l['depth']<EPS:lanes.pop(i)
        floors=[];failed=False
        for f in range(brief.floors):
            cells=allocate(expanded_program(brief,f),lanes,brief.wall_thickness)
            if cells is None:failed=True;break
            floors.append(cells+([copy.deepcopy(stair)] if stair else []))
        if failed:continue
        gross=sum(area(l) for l in shape[0]+shape[1])
        spare=sum(area(r) for rooms in floors for r in rooms if r['kind']=='reserve')
        score=gross*brief.floors+spare*.8
        if best is None or score<best['score']:best=dict(W=W,D=D,halls=halls,floors=floors,score=score,gross=gross)
    if best:best['attempts']=attempts
    return best


def make_walls(floor,t,revision):
    """Split coincident edges into atomic host walls; remove hall-to-hall seams."""
    edges={};cells=floor['cells']
    for r in cells:
        x,y,w,d=r['x'],r['y'],r['width'],r['depth']
        for axis,fixed,lo,hi in [('h',y,x,x+w),('h',y+d,x,x+w),('v',x,y,y+d),('v',x+w,y,y+d)]:
            key=(axis,round(fixed,6));edges.setdefault(key,[]).append((lo,hi,r['id']))
    by_id={r['id']:r for r in cells}
    for (axis,fixed),spans in edges.items():
        cuts=sorted({round(q,6) for lo,hi,_ in spans for q in (lo,hi)})
        for lo,hi in zip(cuts,cuts[1:]):
            ids=sorted({rid for a,b,rid in spans if a< (lo+hi)/2 <b})
            if not ids:continue
            if len(ids)==2 and all(by_id[i]['kind']=='corridor' for i in ids):continue
            a,b=((lo,fixed),(hi,fixed)) if axis=='h' else ((fixed,lo),(fixed,hi))
            floor['walls'].append(dict(id=f"{floor['id']}-W{len(floor['walls'])+1}",floor_id=floor['id'],axis='horizontal' if axis=='h' else 'vertical',start=a,end=b,thickness=t,room_ids=ids,exterior=len(ids)==1,revision_id=revision))
    # Every requested room receives a real door directly to the connected circulation.
    for r in cells:
        if r['kind']=='corridor':continue
        hosts=[w for w in floor['walls'] if r['id'] in w['room_ids'] and any(by_id[i]['kind']=='corridor' for i in w['room_ids'])]
        if not hosts:continue
        wall=max(hosts,key=lambda w:math.dist(w['start'],w['end']))
        length=math.dist(wall['start'],wall['end']);width=min(.90,length-t-.12)
        if width<.75:continue
        center=[(a+b)/2 for a,b in zip(wall['start'],wall['end'])]
        # A door toward one end leaves wall space for furniture; inset beyond corner.
        axis=0 if wall['axis']=='horizontal' else 1
        center[axis]=wall['start'][axis]+t/2+.18+width/2
        if center[axis]+width/2>wall['end'][axis]-t/2: center[axis]=(wall['start'][axis]+wall['end'][axis])/2
        x,y=center
        if axis==0:
            top=y<r['y']+r['depth']/2;swing=box(x-width/2,y if top else y-width,width,width)
        else:
            left=x<r['x']+r['width']/2;swing=box(x if left else x-width,y-width/2,width,width)
        floor['openings'].append(dict(id=f"{floor['id']}-O{len(floor['openings'])+1}",wall_id=wall['id'],floor_id=floor['id'],kind='door',center=center,width=width,height=2.2,sill=0,connects=[r['id']]+[i for i in wall['room_ids'] if i!=r['id']],swing_rect=swing,revision_id=revision))
    for r in floor['rooms']:
        if r['kind'] in ('corridor','reserve','stair'):continue
        hosts=[w for w in floor['walls'] if w['exterior'] and r['id'] in w['room_ids'] and math.dist(w['start'],w['end'])>1.25]
        if not hosts:continue
        w=max(hosts,key=lambda q:math.dist(q['start'],q['end']));length=math.dist(w['start'],w['end']);width=min(1.5,length-.5)
        floor['openings'].append(dict(id=f"{floor['id']}-O{len(floor['openings'])+1}",wall_id=w['id'],floor_id=floor['id'],kind='window',center=[(a+b)/2 for a,b in zip(w['start'],w['end'])],width=width,height=.6 if r['kind']=='bathroom' else 1.2,sill=1.5 if r['kind']=='bathroom' else .9,connects=[r['id'],'OUTSIDE'],revision_id=revision))


def entrance(floor,face,revision):
    halls={r['id'] for r in floor['rooms'] if r['kind']=='corridor'}
    horizontal=face in ('north','south');coordinate=1 if horizontal else 0
    walls=[w for w in floor['walls'] if w['exterior'] and set(w['room_ids'])&halls and (w['axis']=='horizontal')==horizontal and math.dist(w['start'],w['end'])>1.2]
    if not walls:return
    sign=-1 if face in ('south','east') else 1
    w=min(walls,key=lambda w:sign*w['start'][coordinate])
    floor['openings'].append(dict(id=f"{floor['id']}-ENTRY",wall_id=w['id'],floor_id=floor['id'],kind='door',center=[(a+b)/2 for a,b in zip(w['start'],w['end'])],width=1.0,height=2.3,sill=0,connects=w['room_ids']+['OUTSIDE'],revision_id=revision,main_entry=True))


def materialize(brief,family,result):
    revision=uuid4().hex;t=brief.wall_thickness
    model=dict(schema_version='0.5-general',model_revision_id=revision,candidate_id=family,status='DRAFT_REVIEW',
               brief=brief.model_dump(),profile={'project_name':brief.project_name},site={'width':brief.plot_width,'depth':brief.plot_depth},
               footprint=box(brief.setbacks.west,brief.setbacks.north,result['W'],result['D']),
               search={'family':family,'family_label_ar':FAMILIES[family],'dimensions_tested':result['attempts'],'method':'bounded wing allocation beam search','optimality_proven':False},
               presentation={'style':'linework','furniture_symbols':SYMBOL_VERSION},floors=[],stairs=[])
    W,D=result['W'],result['D'];a=result['halls'][0]['x']+result['halls'][0]['width']
    if family=='L':
        b=result['halls'][1]['y']+result['halls'][1]['depth'];outline=[(0,0),(W,0),(W,b),(a,b),(a,D),(0,D)]
    elif family=='U':
        b=result['halls'][1]['y']+result['halls'][1]['depth'];outline=[(0,0),(W,0),(W,D),(W-a,D),(W-a,b),(a,b),(a,D),(0,D)]
    else:outline=[(0,0),(W,0),(W,D*.67),(W*.80,D*.67),(W*.80,D),(W*.12,D),(W*.12,D*.33),(0,D*.33)]
    model['footprint']['polygon']=[(x+brief.setbacks.west,y+brief.setbacks.north) for x,y in outline]
    for fi,cells in enumerate(result['floors']):
        fid=['GF','FF'][fi];f=dict(id=fid,name=['الدور الأرضي','الدور الأول'][fi],level_m=fi*brief.floor_height,rooms=[],walls=[],openings=[],furniture=[],decorations=[],cells=[])
        for n,cell in enumerate(cells+[dict(r,id=f'hall-{i}',kind='corridor',name='موزع الحركة') for i,r in enumerate(result['halls'])]):
            q=copy.deepcopy(cell);q['id']=fid+'-'+q.get('id',f'reserve-{n}');q['floor_id']=fid
            q['x']+=brief.setbacks.west;q['y']+=brief.setbacks.north
            f['cells'].append(q)
            net=copy.deepcopy(q);net.update(x=q['x']+t/2,y=q['y']+t/2,width=q['width']-t,depth=q['depth']-t,revision_id=revision)
            net['area_m2']=round(area(net),4);f['rooms'].append(net)
        make_walls(f,t,revision)
        if fi==0:entrance(f,brief.entrance_face,revision)
        # Detailed, original furniture symbols and use-zone placement are shared with V0.4.1.
        furnish_floor(f,revision)
        model['floors'].append(f)
    model['metrics']={'floor_built_m2':round(result['gross'],2),'requested_spaces':sum(r.count for r in brief.rooms),
                      'circulation_m2':round(sum(area(r) for f in model['floors'] for r in f['rooms'] if r['kind']=='corridor'),2),
                      'bed_capacity':sum(q.get('capacity',0) for f in model['floors'] for q in f['furniture']),
                      'proposed_flexible_m2':round(sum(area(r) for f in model['floors'] for r in f['rooms'] if r['kind']=='reserve'),2)}
    canonical={'floors':[{k:v for k,v in f.items() if k not in ('decorations',)} for f in model['floors']]}
    def clean(obj):
        if isinstance(obj,dict):return {k:clean(v) for k,v in obj.items() if k!='revision_id'}
        if isinstance(obj,list):return [clean(v) for v in obj]
        return obj
    model['geometry_sha256']=hashlib.sha256(json.dumps(clean(canonical),sort_keys=True).encode()).hexdigest()
    return model


def validate_general(model,brief):
    """Recalculate constraints from emitted geometry, independent of allocator state."""
    checks=[]
    def add(id,ok,label,evidence=None):checks.append(dict(check_id=id,status='PASS' if ok else 'FAIL',label=label,evidence=evidence or {}))
    for fi,f in enumerate(model['floors']):
        expected={r['id']:r for r in expanded_program(brief,fi)}
        actual={r['id'].removeprefix(f['id']+'-'):r for r in f['rooms'] if r.get('request_id')}
        add(f'{f["id"]}-program',set(expected)==set(actual),'تغطية جميع الفراغات المطلوبة في دورها',{'expected':len(expected),'actual':len(actual)})
        bad=[r['id'] for key,r in actual.items() if area(r)+EPS<expected[key]['min_area'] or min(r['width'],r['depth'])+EPS<expected[key]['min_side']]
        add(f'{f["id"]}-sizes',not bad,'الحد الأدنى للمساحات والأبعاد الصافية',{'invalid':bad})
        rooms=f['rooms'];collisions=[(a['id'],b['id']) for i,a in enumerate(rooms) for b in rooms[i+1:] if overlap(a,b)]
        add(f'{f["id"]}-overlap',not collisions,'عدم تداخل الغرف والممرات',{'collisions':collisions})
        bounds=box(brief.setbacks.west,brief.setbacks.north,brief.plot_width-brief.setbacks.west-brief.setbacks.east,brief.plot_depth-brief.setbacks.north-brief.setbacks.south)
        add(f'{f["id"]}-site',all(inside(bounds,r) for r in rooms),'الالتزام بحدود الأرض والارتدادات المدخلة')
        corridors={r['id'] for r in rooms if r['kind']=='corridor'}
        # Connectivity uses touching gross hall cells, not near-by room centers.
        halls=[r for r in f['cells'] if r['kind']=='corridor'];seen={halls[0]['id']};changed=True
        def touches(a,b):
            dx=min(a['x']+a['width'],b['x']+b['width'])-max(a['x'],b['x'])
            dy=min(a['y']+a['depth'],b['y']+b['depth'])-max(a['y'],b['y'])
            return (abs(dx)<EPS and dy>EPS) or (abs(dy)<EPS and dx>EPS)
        while changed:
            changed=False
            for a in halls:
                if a['id'] not in seen and any(b['id'] in seen and touches(a,b) for b in halls):seen.add(a['id']);changed=True
        missing=[r['id'] for r in rooms if r['kind']!='corridor' and not any(o['kind']=='door' and r['id'] in o['connects'] and set(o['connects'])&corridors for o in f['openings'])]
        add(f'{f["id"]}-doors',not missing and len(seen)==len(halls),'كل فراغ يتصل بباب بممر مترابط',{'missing_doors':missing,'connected_halls':len(seen)})
        missing_windows=[r['id'] for r in rooms if r.get('request_id') and not any(o['kind']=='window' and r['id'] in o['connects'] for o in f['openings'])]
        add(f'{f["id"]}-windows',not missing_windows,'نافذة خارجية فعلية لكل فراغ مطلوب',{'missing':missing_windows})
        entry=any(o.get('main_entry') for o in f['openings'])
        if fi==0:add('entrance',entry,'باب دخول خارجي متصل بالموزع')
        short=[]
        walls={w['id']:w for w in f['walls']}
        for o in f['openings']:
            w=walls.get(o['wall_id']);axis=0 if w and w['axis']=='horizontal' else 1
            if not w or o['center'][axis]-o['width']/2<w['start'][axis]-EPS or o['center'][axis]+o['width']/2>w['end'][axis]+EPS:short.append(o['id'])
        add(f'{f["id"]}-openings',not short,'تطابق عرض وموقع الفتحات مع الجدار المضيف',{'invalid':short})
        capacities={r['id']:sum(q.get('capacity',0) for q in f['furniture'] if q['room_id']==r['id']) for r in rooms if r.get('capacity',0)}
        add(f'{f["id"]}-beds',all(capacities[r['id']]>=r['capacity'] for r in rooms if r.get('capacity',0)),'سعة الأسرة المرسومة المطلوبة',{'actual':capacities})
    if brief.floors==2:
        cores=[next(r for r in f['rooms'] if r['kind']=='stair') for f in model['floors']]
        add('vertical-core',all(abs(cores[0][k]-cores[1][k])<EPS for k in ('x','y','width','depth')),'تطابق حدود بئر الدرج بين الدورين')
    for id,label in [('privacy','الخصوصية وفصل الضيوف والمداخل المستقلة'),('walkability','خلوص الحركة التفصيلي وتعارض أقواس الأبواب مع الأثاث'),('local-code','اعتماد الارتدادات والاشتراطات المحلية ومعدلات التهوية'),('structure','الإنشاء والخدمات والتنسيق الرأسي للحمامات'),('stairs-code','مطابقة السلم والارتفاع الصافي للاشتراطات'),('flexible-spaces','اعتماد استعمال المساحات المرنة المقترحة الزائدة عن البرنامج')]:
        checks.append(dict(check_id=id,status='PENDING',label=label,evidence={}))
    if brief.notes.strip():checks.append(dict(check_id='free-text',status='PENDING',label='طلبات النص تحتاج تحويلًا واعتمادًا في جدول البرنامج',evidence={'unmapped_notes':brief.notes}))
    return checks


def generate_general(brief:VillaBrief,output_dir=None):
    from .general_drawing import drawing
    from .presentation import scene_svg,scene_pdf,scene_dxf
    out=Path(output_dir) if output_dir else Path(__file__).resolve().parents[2]/'outputs'
    out.mkdir(parents=True,exist_ok=True);candidates=[];unavailable=[]
    for family,label in FAMILIES.items():
        result=search(brief,family)
        if not result:
            unavailable.append({'family':family,'label':label,'reason':'لم يجد البحث المحدود توزيعًا يحقق عدد ومساحات وأبعاد الفراغات مع الممر والدرج في حدود الارتدادات المدخلة. جرّب تخفيف البرنامج أو زيادة المسطح المتاح.'});continue
        model=materialize(brief,family,result);model['checks']=validate_general(model,brief)
        failures=[c for c in model['checks'] if c['status']=='FAIL']
        model['release']={'status':'BLOCKED' if failures else 'DRAFT_REVIEW','drawing_export_allowed':not failures,'executive_issue_allowed':False}
        rev=model['model_revision_id'];model['downloads']={'json':f'/api/files/{rev}.json'};model['previews']={}
        if not failures:
            scenes=[drawing(model,f) for f in model['floors']]
            for f,s in zip(model['floors'],scenes):
                name=f'{rev}-{f["id"]}.svg';(out/name).write_text(scene_svg(model,f,drawing=s),encoding='utf-8');model['previews'][f['id']]=f'/api/files/{name}'
            scene_pdf(model,out/f'{rev}.pdf',drawings=scenes,include_report=False)
            model['export_audit']=scene_dxf(model,out/f'{rev}.dxf',drawings=scenes)
            model['downloads'].update({ext:f'/api/files/{rev}.{ext}' for ext in ('pdf','dxf')})
        (out/f'{rev}.json').write_text(json.dumps(model,ensure_ascii=False,indent=2),encoding='utf-8');candidates.append(model)
    return {'status':'DRAFT_REVIEW','candidates':candidates,'unavailable':unavailable,
            'scope':'أرض مستطيلة، دور أو دوران، برنامج صريح، بحث محدود L/U/متدرج؛ لا ضمان لإيجاد كل حل ممكن.',
            'ai':{'mode':'geometric_search','language_model_connected':False}}
