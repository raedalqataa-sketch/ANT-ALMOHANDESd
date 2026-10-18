"""Source-bound Saudi national baseline checks; missing local rules fail closed."""
import json
import math
from functools import lru_cache
from pathlib import Path
from .furnishing import inside,overlap


@lru_cache(maxsize=1)
def registry():return json.loads((Path(__file__).resolve().parents[2]/'constitution/saudi/national-2024.json').read_text())


def minimum(kind):return registry()['rules']['rooms']['minimums'].get(kind,[0,0])


def parking_count(brief):
    rule=registry()['rules']['parking_count']
    return rule['up_to_threshold'] if brief.plot_width*brief.plot_depth<=rule['area_threshold_m2'] else rule['above_threshold']


def window_targets(kind,net_area):
    rule=registry()['rules']['daylight']
    if kind=='bathroom':return rule['bathroom_glazing_m2'],rule['bathroom_glazing_m2']*rule['bathroom_openable_fraction']
    return net_area*rule['glazing_ratio'],net_area*rule['openable_ratio']


def required_setbacks(brief):
    rule=registry()['rules']['setbacks'];result={}
    for face,road in brief.boundary_widths.items():
        result[face]=(rule['neighbor_min_m'] if road==0 else
                      rule['front_wide_street_min_m'] if face==brief.entrance_face and road>=rule['front_wide_street_from_m'] else
                      max(rule['front_min_m'],road*rule['front_street_ratio']) if face==brief.entrance_face else
                      max(rule['other_street_min_m'],road*rule['other_street_ratio']))
    return result


def parking(model,brief):
    if not brief.apply_saudi_rules:return []
    count=parking_count(brief)
    width,depth=2.8,5.5 # Proposed stall dimensions; count is sourced, turning geometry is not certified.
    cells=model['floors'][0]['cells'];t=brief.wall_thickness
    occupied=[dict(x=c['x']-t/2,y=c['y']-t/2,width=c['width']+t,depth=c['depth']+t) for c in cells]
    entry=next((o for o in model['floors'][0]['openings'] if o.get('main_entry')),None)
    face=brief.entrance_face;vertical=face in ('north','south');w,d=(width,depth) if vertical else (depth,width)
    along=brief.plot_width if vertical else brief.plot_depth
    spaces=[]
    for i in range(max(1,int((along-(w if vertical else d)-.2)/.2)+1)):
        pos=.1+i*.2
        x=pos if vertical else (.1 if face=='west' else brief.plot_width-w-.1)
        y=pos if not vertical else (.1 if face=='north' else brief.plot_depth-d-.1)
        q=dict(x=x,y=y,width=w,depth=d)
        if any(overlap(q,c) for c in occupied+spaces):continue
        if entry:
            ex,ey=entry['center']
            route=(dict(x=ex-.6,y=ey,width=1.2,depth=max(.01,brief.plot_depth-ey)) if face=='south' else
                   dict(x=ex-.6,y=0,width=1.2,depth=ey) if face=='north' else
                   dict(x=ex,y=ey-.6,width=max(.01,brief.plot_width-ex),depth=1.2) if face=='east' else dict(x=0,y=ey-.6,width=ex,depth=1.2))
            if overlap(q,route):continue
        q.update(id='P'+str(len(spaces)+1),kind='parking',proposed_dimensions=True,entry_face=face)
        spaces.append(q)
        if len(spaces)==count:break
    return spaces


def checks(model,brief):
    if not brief.apply_saudi_rules:return []
    data=registry();rules=data['rules'];results=[]
    def add(key,status,label,evidence,rule):
        source=rules[rule]
        results.append(dict(check_id='SA-'+key,status=status,label=label,evidence=evidence,source={'id':source['source'],'section':source['section'],'section_locator':source['section'],'url':data['sources'][0]['url']}))
    present={r['kind'] for f in model['floors'] for r in f['rooms'] if r.get('request_id')}
    missing=[label for label,kinds in [('غرفة نوم',{'bedroom','master'}),('معيشة أو مجلس',{'living','majlis'}),('مطبخ',{'kitchen'}),('حمام',{'bathroom'})] if not present&kinds]
    add('dwelling-program','FAIL' if missing else 'PASS','السعودية: الحد الأدنى لعناصر الوحدة السكنية',{'missing':missing},'rooms')
    for f in model['floors']:
        rooms=[r for r in f['rooms'] if r.get('request_id')]
        bad=[r['id'] for r in rooms if r['width']*r['depth']+1e-6<minimum(r['kind'])[0] or min(r['width'],r['depth'])+1e-6<minimum(r['kind'])[1]]
        add(f['id']+'-room-minima','FAIL' if bad else 'PASS','السعودية: الحدود الدنيا لمساحات وأبعاد الفراغات',{'invalid':bad},'rooms')
        measured=model['metrics']['floor_built_by_id'][f['id']]/(brief.plot_width*brief.plot_depth)
        add(f['id']+'-coverage','PASS' if measured<=rules['coverage']['max_ratio']+1e-6 else 'FAIL','السعودية: نسبة بناء الدور ضمن الحد العام 75٪',{'measured_ratio':round(measured,5),'limit':rules['coverage']['max_ratio'],'scope':'national baseline, detached villa; approved local/parcel limits may be stricter'},'coverage')
        failures=[];observations=[]
        for r in rooms:
            windows=[o for o in f['openings'] if o['kind']=='window' and r['id'] in o['connects']]
            glazing=sum(o.get('clear_width',0)*o.get('clear_height',0) for o in windows)
            opening=sum(o.get('clear_width',0)*o.get('clear_height',0)*o.get('operable_fraction',0) for o in windows)
            required,air=window_targets(r['kind'],r['width']*r['depth'])
            observations.append({'room_id':r['id'],'clear_glazing_m2':round(glazing,4),'openable_m2':round(opening,4),'required_glazing_m2':round(required,4),'required_openable_m2':round(air,4)})
            if glazing+1e-6<required or opening+1e-6<air:failures.append(r['id'])
        add(f['id']+'-daylight','FAIL' if failures else 'PASS','السعودية: مساحة الزجاج والجزء القابل للفتح — قياس هندسي للمقترح',{'invalid':failures,'rooms':observations,'scope':rules['daylight']['scope_note']},'daylight')
    count=parking_count(brief)
    valid=[q for q in model.get('parking',[]) if inside(dict(x=0,y=0,width=brief.plot_width,depth=brief.plot_depth),q)]
    add('parking-count','PASS' if len(valid)>=count else 'FAIL','السعودية: عدد المواقف داخل حدود الملكية',{'required':count,'actual':len(valid),'stall_geometry':'proposed 2.8 x 5.5 m, turning and gates require approval'},'parking_count')
    if model['stairs']:
        bad=[s['id'] for s in model['stairs'] if s['flight_width_m']<rules['stairs']['flight_min_m'] or s['landing_depth_m']<max(rules['stairs']['landing_min_m'],s['flight_width_m'])]
        add('stair-width','FAIL' if bad else 'PASS','السعودية: عرض الدرج والبسطة في الفيلا',{'invalid':bad,'measured':[(s['flight_width_m'],s['landing_depth_m']) for s in model['stairs']]},'stairs')
    boundaries=brief.boundary_widths
    if set(boundaries)=={'north','south','east','west'} and boundaries.get(brief.entrance_face,0)>0:
        required={};failures=[]
        for face,road in boundaries.items():
            req=required_setbacks(brief)[face]
            required[face]=req
            if getattr(brief.setbacks,face)+1e-6<req:failures.append(face)
        add('setbacks-baseline','FAIL' if failures else 'PASS','السعودية: الارتدادات العامة وفق حدود وشوارع العميل',{'required_m':required,'invalid':failures,'scope':'all floors kept within baseline; no ground setback-building exceptions used'},'setbacks')
    else:add('setbacks-baseline','PENDING','السعودية: الارتدادات تحتاج تصنيف الحدود وعروض الشوارع',{'missing':['أدخل حدود الأرض الأربعة: صفر جار أو عرض الشارع بالمتر؛ اختر جهة الدخول على شارع']},'setbacks')
    street_faces={f for f,w in boundaries.items() if w>0}
    if any({a,b}<=street_faces for a,b in [('north','east'),('north','west'),('south','east'),('south','west')]):
        results.append(dict(check_id='SA-corner-cut',status='PENDING',label='قطعة زاوية: الشطفة ومداخل السيارات تحتاج مخطط القطعة المعتمد',evidence={'street_faces':sorted(street_faces),'required_action':'يلزم شكل القطعة والشطفة المعتمدة؛ النموذج الحالي أرض مستطيلة، فلا تعتبر حدوده قرارًا مساحيًا.'},source={'id':'MOMAH-RES-2024','section':'5-1-16','url':data['sources'][0]['url']}))
    for key,label,action in [
        ('parcel','اشتراطات المدينة والمخطط وقطعة الأرض','يلزم التحقق من بطاقة اشتراطات القطعة والكود العمراني المحلي؛ اختيار المدينة وحده لا يثبت ذلك.'),
        ('full-sbc','المراجعة الكاملة لبنود SBC 2024','لم يُنقل نص الكود الكامل؛ تفاصيل الهروب والحريق والزجاج الآمن والدرابزين والإنشاء والطاقة والخدمات غير معتمدة.'),
        ('facades','اتصال فتحات الإضاءة والتهوية بهواء خارجي متاح نظاميًا','أبعاد الفتحات المقترحة محسوبة؛ يلزم اعتماد إتاحة الواجهات والمناور والعوائق الخارجية ونوع النافذة الفعلي.'),
        ('vehicle-access','مناورة المركبات واعتماد بوابات المواقف','المواقف المرسومة تحقق العدد والاحتواء هندسيًا؛ يلزم مسار دوران فعلي واعتماد المداخل والشطفات.')]:
        results.append(dict(check_id='SA-'+key,status='PENDING',label=label,evidence={'city':brief.city,'municipality':brief.municipality,'parcel_reference':brief.parcel_reference,'required_action':action},source={'id':'MOMAH-RES-2024 / SBC-2024-CATALOG','url':data['sources'][0]['url']}))
    return results
