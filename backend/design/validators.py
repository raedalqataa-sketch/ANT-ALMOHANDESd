"""Checks inspect model entities, not generator success flags. No legal defaults."""
from collections import defaultdict, deque
import math
from itertools import combinations
from .models import CheckResult

EPS=1e-6


def intersects(a,b):
    return min(a['x']+a['width'],b['x']+b['width'])-max(a['x'],b['x'])>EPS and min(a['y']+a['depth'],b['y']+b['depth'])-max(a['y'],b['y'])>EPS


def contains(a,b):
    return b['x']>=a['x']-EPS and b['y']>=a['y']-EPS and b['x']+b['width']<=a['x']+a['width']+EPS and b['y']+b['depth']<=a['y']+a['depth']+EPS


def path(graph,start,target,allowed=None):
    queue=deque([(start,[start])]);seen={start}
    while queue:
        node,route=queue.popleft()
        if node==target:return route
        for nxt in sorted(graph[node]):
            if nxt not in seen and (allowed is None or nxt in allowed):
                seen.add(nxt);queue.append((nxt,route+[nxt]))
    return None


def validate_model(model, opening_faces=None):
    out=[];rev=model['model_revision_id'];pid=model['project_id']
    floors=model['floors']; rooms={r['id']:r for f in floors for r in f['rooms']}
    def check(cid,rule,label,issues=None,observed=None,evidence=None,pending=None):
        issues=issues or []
        state='FAIL' if issues else 'PENDING' if pending else 'PASS'
        out.append(CheckResult(check_id=cid,rule_id=rule,project_id=pid,model_revision_id=rev,status=state,
                               entity_ids=issues,observed_value=observed,expected_criterion=label,criterion_source=rule,
                               evidence=evidence or {},reason=pending if pending and not issues else ('عناصر مخالفة: '+', '.join(issues) if issues else label)).model_dump())
    extras=[e for f in floors for key in ('voids','terraces','outdoor_furniture','guardrails') for e in f.get(key,[])]
    all_entities=[r for f in floors for r in f['rooms']+f['walls']+f['openings']+f['furniture']]+model['stairs']+model['parking']+extras
    bad_dimensions=[]
    for entity in [dict(model['footprint'],id='BUILDING')]+[r for f in floors for r in f['rooms']+f['furniture']]+model['stairs']+model['parking']:
        if not all(isinstance(entity[k],(int,float)) and math.isfinite(entity[k]) for k in ('x','y','width','depth')) or entity['width']<=0 or entity['depth']<=0:
            bad_dimensions.append(entity['id'])
    check('finite_geometry','SPEC-IN-02','أبعاد وإحداثيات محدودة ومساحات مستطيلات موجبة',bad_dimensions)
    ids=[e['id'] for e in all_entities]
    duplicate=sorted({v for v in ids if ids.count(v)>1})
    refs=[]
    graph=defaultdict(set)
    all_openings=[]
    for f in floors:
        walls={w['id']:w for w in f['walls']}
        for w in f['walls']:
            if any(r not in rooms or rooms[r]['floor_id']!=f['id'] for r in w['room_ids']): refs.append(w['id'])
        for fixture in f['furniture']:
            if fixture['room_id'] not in rooms or rooms.get(fixture['room_id'],{}).get('floor_id')!=f['id']:refs.append(fixture['id'])
        terraces={t['id']:t for t in f.get('terraces',[])}
        for fixture in f.get('outdoor_furniture',[]):
            if fixture.get('outdoor_id') not in terraces:refs.append(fixture['id'])
        for o in f['openings']:
            all_openings.append(o)
            if o.get('to_outdoor_id') and o['to_outdoor_id'] not in terraces:refs.append(o['id'])
            wall=walls.get(o['wall_id'])
            if not wall or len(o['connects'])!=2:
                refs.append(o['id']);continue
            a,b=o['connects']
            if a not in rooms or (b!='EXTERIOR' and b not in rooms) or a not in wall['room_ids'] or (b!='EXTERIOR' and b not in wall['room_ids']) or (b=='EXTERIOR' and not wall['exterior']):
                refs.append(o['id']);continue
            if any(rooms[r]['floor_id']!=f['id'] for r in (a,b) if r!='EXTERIOR'):refs.append(o['id']);continue
            if o['kind'] in ('door','passage'):
                logical_b=b if b!='EXTERIOR' or f['id']=='GF' else f['id']+'-OUTDOOR'
                graph[a].add(logical_b);graph[logical_b].add(a)
    check('references','SPEC-OP-01','معرفات فريدة وروابط العناصر في الدور والمراجعة نفسها',duplicate+refs+[e['id'] for e in all_entities if e.get('revision_id')!=rev])
    bounds=[];overlap=[];areas=[]
    for f in floors:
        for r in f['rooms']:
            if not contains(model['footprint'],r):bounds.append(r['id'])
            if abs(r['area_m2']-r['width']*r['depth'])>.0011:areas.append(r['id'])
        for a,b in combinations(f['rooms'],2):
            if intersects(a,b):overlap.extend([a['id'],b['id']])
    site={'x':0,'y':0,'width':model['site']['width'],'depth':model['site']['depth']}
    if not contains(site,model['footprint']):bounds.append('BUILDING')
    unclosed=[]
    for f in floors:
        for r in f['rooms']:
            for axis,coordinate,lo,hi in [('vertical',r['x'],r['y'],r['y']+r['depth']),('vertical',r['x']+r['width'],r['y'],r['y']+r['depth']),('horizontal',r['y'],r['x'],r['x']+r['width']),('horizontal',r['y']+r['depth'],r['x'],r['x']+r['width'])]:
                idx=0 if axis=='vertical' else 1
                spans=[]
                for w in f['walls']:
                    if r['id'] in w['room_ids'] and w['axis']==axis and abs(abs(w['start'][idx]-coordinate)-w['thickness']/2)<EPS:
                        spans.append((w['start'][1-idx],w['end'][1-idx]))
                cursor=lo
                for a,b in sorted(spans):
                    if a<=cursor+EPS:cursor=max(cursor,b)
                if cursor<hi-EPS:unclosed.append(r['id'])
    check('room_wall_enclosure','SPEC-OP-01','كل جانب غرفة ممثل بجدران مترابطة قبل اقتطاع الفتحات',sorted(set(unclosed)))
    check('bounds','SPEC-IN-04','حدود الغرف والمبنى داخل حدود الأرض المقترحة',sorted(set(bounds)))
    check('overlap','SPEC-GEN-02','لا تداخل بين المساحات الصافية للغرف في الدور نفسه',sorted(set(overlap)))
    check('areas','SPEC-PG-02','المساحات الصافية مشتقة من مستطيلات الغرف',areas)
    missing=[]
    required={r['id']:r for r in model['profile']['required']}
    gf=next((f for f in floors if f['id']=='GF'),None)
    grooms=gf['rooms'] if gf else []
    for key in required:
        if key=='ground_guest_or_elderly_room' and not any(r['kind']=='elderly' for r in grooms):missing.append(key)
        if key=='storage' and not any(r['kind']=='storage' for r in grooms):missing.append(key)
        if key=='parking' and len(model['parking'])<required[key]['quantity']:missing.append(key)
        if key=='separate_family_entrance' and not any(o['kind']=='door' and 'EXTERIOR' in o['connects'] and any(rooms.get(r,{}).get('zone')=='family' for r in o['connects']) for o in (gf['openings'] if gf else [])):missing.append(key)
    check('mandatory_program','SPEC-PG-01','وجود تمثيل مكاني للمتطلبات الإلزامية الأربعة؛ لا يثبت كفاية استعمالها',missing,observed={'required_ids':list(required)})
    staircase_issues=[]
    for stair in model['stairs']:
        connected=stair.get('room_ids',[])
        if len(connected)!=2 or any(r not in rooms for r in connected):
            staircase_issues.append(stair['id']);continue
        a,b=connected;graph[a].add(b);graph[b].add(a)
        if not all(contains(rooms[r],stair) for r in connected):staircase_issues.append(stair['id'])
        if abs(stair['riser_count']*stair['riser_m']-stair['floor_height_m'])>EPS:staircase_issues.append(stair['id'])
    if not model['stairs']:
        staircase_issues.append('MISSING_STAIR')
    for stair in model['stairs']:
        for o in all_openings:
            if o.get('swing_rect') and o['connects'][0] in stair.get('room_ids',[]) and any(intersects(o['swing_rect'],flight) for flight in __import__('backend.design.walkability',fromlist=['stair_flights']).stair_flights(stair)):
                staircase_issues.append(o['id'])
    check('stair_geometry','SPEC-ST-01','غلاف الرحلتين والبسطة داخل حجرة السلم، ومجموع القوائم يساوي الارتفاع المقترح',staircase_issues)
    unreachable=[rid for rid in rooms if not path(graph,'EXTERIOR',rid)]
    check('reachability','SPEC-PR-01','كل فراغ متصل بمدخل خارجي عبر أبواب فعلية أو سلم',unreachable,evidence={'graph':{k:sorted(v) for k,v in graph.items()},'routes':{r:path(graph,'EXTERIOR',r) for r in rooms}})
    guest_ids={r['id'] for r in rooms.values() if r['zone']=='guest'}
    guest_entry=next((o['connects'][0] for o in all_openings if o['kind']=='door' and 'EXTERIOR' in o['connects'] and o['connects'][0] in guest_ids),None)
    guest_toilet=next((r['id'] for r in rooms.values() if r['kind']=='bathroom' and r['zone']=='guest'),None)
    route=path(graph,guest_entry,guest_toilet,guest_ids) if guest_entry and guest_toilet else None
    check('guest_route','IMG-PAT-003','مسار مدخل الرجال إلى خدماتهم داخل نطاق الضيافة فقط',[] if route else ['GUEST_ROUTE'],evidence={'route':route})
    invalid_openings=[];swings=[];window_rooms=set();illegal_windows=[]
    for f in floors:
        walls={w['id']:w for w in f['walls']}
        for o in f['openings']:
            w=walls.get(o['wall_id'])
            if not w:continue
            c=o['center'];fixed=0 if w['axis']=='vertical' else 1;along=1-fixed
            if abs(c[fixed]-w['start'][fixed])>EPS or c[along]-o['width']/2<min(w['start'][along],w['end'][along])-EPS or c[along]+o['width']/2>max(w['start'][along],w['end'][along])+EPS:invalid_openings.append(o['id'])
            if o['kind']=='window' and w['exterior']:
                window_rooms.add(o['connects'][0])
                if opening_faces is not None and o['face'] not in opening_faces:illegal_windows.append(o['id'])
            if o.get('swing_rect'):
                r=rooms.get(o['connects'][0])
                if r and not contains(r,o['swing_rect']):swings.append(o['id'])
                for fixture in f['furniture']:
                    if intersects(fixture,o['swing_rect']):swings.append(o['id'])
        for a,b in combinations([o for o in f['openings'] if o.get('swing_rect')],2):
            if intersects(a['swing_rect'],b['swing_rect']):swings.extend([a['id'],b['id']])
    check('opening_fit','SPEC-OP-01','عرض كل فتحة ومركزها داخل الجدار المرتبط',invalid_openings)
    check('door_envelopes','SPEC-OP-02','لا يتقاطع الغلاف المستطيل المحافظ لدوران الأبواب مع الأثاث أو باب آخر',sorted(set(swings)),evidence={'method':'conservative rectangular envelope, not regulatory clearance'})
    need_windows=[r['id'] for r in rooms.values() if r['kind'] in ('bedroom','master','elderly','bathroom','kitchen')]
    check('physical_windows','USR-01','فتحة نافذة خارجية فعلية لكل غرفة نوم ومطبخ وحمام',[r for r in need_windows if r not in window_rooms])
    check('opening_legality','SPEC-NV-01','كل نافذة على جهة مسموحة حسب بيانات المشروع',illegal_windows,pending='الواجهات المسموحة للفتحات غير متحققة' if opening_faces is None else None,
          evidence={'confirmed_faces':opening_faces,'basis':'user-declared faces only; not a legal determination'})
    check('ventilation_quantity','SPEC-NV-03','كفاية التهوية والإضاءة وفق معيار موثق',pending='نسب ومساحات الفتح الفعلية والمعيار المحلي غير متوفرة؛ وجود النافذة لا يثبت الكفاية')
    fixtures_out=[];fixtures_overlap=[]
    for f in floors:
        for q in f['furniture']:
            if q['room_id'] in rooms and not contains(rooms[q['room_id']],q):fixtures_out.append(q['id'])
        for a,b in combinations(f['furniture'],2):
            allowed={a['kind'],b['kind']} in ({'kitchen_counter','sink'},{'kitchen_counter','cooker'})
            if a.get('physical',True) and b.get('physical',True) and intersects(a,b) and not allowed:fixtures_overlap.extend([a['id'],b['id']])
    missing_fixtures=[]
    for f in floors:
        for r in f['rooms']:
            kinds={q['kind'] for q in f['furniture'] if q['room_id']==r['id']}
            required={'kitchen':{'kitchen_counter','sink','cooker','fridge'},'bathroom':{'toilet','basin'},'storage':{'storage'},'laundry':{'washing_machine'},'dining':{'dining_table','dining_chair'}}.get(r['kind'],set())
            if r['id'].endswith(('family-bath','master-bath')):required=required|{'shower'}
            if not required.issubset(kinds):missing_fixtures.append(r['id'])
    check('fixture_presence','SPEC-FU-03','التجهيزات الأساسية المقترحة موجودة للمطابخ والحمامات والتخزين والطعام والغسيل',missing_fixtures)
    if model.get('model_schema_version')=='0.4.0':
        from .walkability import floor_access,entry_sightlines
        zone_errors=[]
        for f in floors:
            for q in f['furniture']:
                if q['room_id'] not in rooms:continue
                for z in q.get('use_zones',[]):
                    if not contains(rooms[q['room_id']],z) or any(other['id']!=q['id'] and other.get('physical',True) and intersects(z,other) for other in f['furniture']):zone_errors.append(q['id'])
        incomplete=[]
        for f in floors:
            for r in f['rooms']:
                items=[q for q in f['furniture'] if q['room_id']==r['id']]
                kinds={q['kind'] for q in items}
                if r['kind'] in ('bedroom','elderly') and (not kinds.intersection({'single_bed','double_bed'}) or 'wardrobe' not in kinds):incomplete.append(r['id'])
                if r['kind']=='master' and 'double_bed' not in kinds:incomplete.append(r['id'])
                if r['kind'] in ('living','majlis') and ('coffee_table' not in kinds or sum(q.get('seats',0) for q in items)<4):incomplete.append(r['id'])
        check('room_furnishing_completeness','SPEC-FU-02','كل غرفة نوم مقترحة مؤثثة بسعة وخزانة، والمعيشة والمجالس بجلوس وطاولة فعلية',sorted(set(incomplete)))
        check('proposed_use_zones','SPEC-FU-02','خلوص استعمال مقترح للأسرّة والخزائن والحمامات والمطابخ دون عوائق',sorted(set(zone_errors)),evidence={'numeric_authority':'DESIGNER_PROPOSED_NOT_LOCAL_CODE','zone_values_m':{'bed_foot':.7,'accessible_bed_side':.6,'wardrobe_front':.7,'toilet_front':.65}})
        access={f['id']:floor_access(model,f) for f in floors}
        check('walkable_routes','SPEC-PR-01','وصول فعلي حول الأثاث والجدران من المداخل والسلم إلى نقطة حرة بكل فراغ',[r for a in access.values() for r in a['unreachable']],evidence=access)
        sight=entry_sightlines(model,floors[0])
        check('sampled_entry_privacy','SPEC-PR-02','العينات المباشرة من مركز مدخل العائلة لا تكشف مركز المعيشة أو غرف النوم',sight['exposed'],evidence=sight)
        bad_features=[]
        for f in floors:
            for feature in f.get('voids',[])+f.get('terraces',[]):
                if not contains(model['footprint'],feature) or any(intersects(feature,r) for r in f['rooms']):bad_features.append(feature['id'])
        check('void_and_terrace_bounds','SPEC-ST-03','الفراغات المزدوجة والأحواش والتراسات داخل حدود المقترح ودون غرف متداخلة',bad_features)
        outdoor_issues=[]
        for f in floors:
            for t in f.get('terraces',[]):
                if f['id']=='GF' or not t.get('walkable',True):continue
                access_doors=[o for o in f['openings'] if o.get('to_outdoor_id')==t['id'] and o['kind']=='door']
                if not access_doors:outdoor_issues.append(t['id'])
                for q in f.get('outdoor_furniture',[]):
                    if q['outdoor_id']==t['id'] and not contains(t,q):outdoor_issues.append(q['id'])
        check('outdoor_access','SPEC-PR-01','لكل تراس علوي قابل للاستعمال باب مرتبط به وفرش داخل حدوده',outdoor_issues)

    check('furniture_bounds','SPEC-FU-02','الأثاث داخل المساحة الصافية دون تداخل مادي غير مقصود',sorted(set(fixtures_out+fixtures_overlap)))
    beds=[q for f in floors for q in f['furniture'] if q['kind'] in ('single_bed','double_bed')]
    capacity=sum(q['capacity'] for q in beds)
    check('placed_bed_capacity','SPEC-FU-01','عدد أماكن النوم الموضوعة فعليًا يغطي عدد الأفراد',[] if capacity>=model['profile']['household']['members'] else ['BED_CAPACITY'],observed={'capacity':capacity,'household':model['profile']['household']['members']},evidence={'bed_ids':[q['id'] for q in beds]})
    check('household_assignment','SPEC-IN-03','توزيع أفراد الأسرة على الغرف معتمد',pending='أعمار الأسرة ومشاركة غرف النوم لم تُحسم؛ عدد غرف الأبناء والأسرّة مقترح')
    check('furniture_use','SPEC-FU-02','مناطق استعمال الأثاث والفتح والصيانة والوصول كاملة',pending='الفحص التفصيلي الشامل للاستعمال والصيانة والوصول غير مكتمل؛ فحوص الخلوص والحركة المقترحة في V0.4 تغطي نطاقًا جزئيًا فقط')
    check('privacy_sightlines','SPEC-PR-02','عدم كشف المناطق الخاصة من المداخل',pending='التحقق البصري الشامل غير مكتمل؛ عينات V0.4 من مركز مدخل العائلة إلى مراكز بعض الغرف لا تغطي جميع مواضع النظر والمداخل')
    stair_pairs=[]
    for s in model['stairs']:
        rs=[rooms[r] for r in s['room_ids'] if r in rooms]
        if len(rs)!=2 or any(abs(rs[0][k]-rs[1][k])>EPS for k in ('x','y','width','depth')):stair_pairs.append(s['id'])
    check('core_stacking','SPEC-ST-03','تطابق موضع وحجرة السلم بين الدورين',stair_pairs)
    check('stair_headroom','SPEC-ST-02','الخلوص الرأسي ومطابقة السلم للاشتراطات',pending='الارتفاع والأبعاد مقترحة؛ الخلوص الرأسي والاشتراطات والدرابزين غير متحققة')
    bad_parking=[p['id'] for p in model['parking'] if not contains(site,p) or intersects(p,model['footprint'])]
    check('parking_envelope','SPEC-PK-01','غلاف الموقف المقترح داخل الأرض ولا يتداخل مع المبنى',bad_parking)
    check('parking_maneuver','SPEC-PK-01','اتصال الموقف بالشارع ومناورة السيارة والبوابة',pending='مطلوب بالمشروع: اتجاه الشارع وعرضه والبوابة ومسار المناورة غير معتمدة')
    check('local_regulations','SPEC-IN-06','حدود الأرض والارتدادات والاشتراطات الرسمية متحققة',pending='لا يوجد رفع مساحي أو ارتدادات أو اشتراطات موثقة؛ الفراغ المحيط بالمبنى ليس اعتمادًا للارتدادات')
    wet_kinds={'bathroom','kitchen','laundry'}
    lower=[r for r in grooms if r['kind'] in wet_kinds]
    upper=[r for f in floors if f['id']!='GF' for r in f['rooms'] if r['kind'] in wet_kinds]
    wet_alignment=[]
    for u in upper:
        overlaps=[]
        for l in lower:
            area=max(0,min(u['x']+u['width'],l['x']+l['width'])-max(u['x'],l['x']))*max(0,min(u['y']+u['depth'],l['y']+l['depth'])-max(u['y'],l['y']))
            if area>EPS:overlaps.append({'lower_room':l['id'],'overlap_m2':round(area,3)})
        wet_alignment.append({'upper_room':u['id'],'overlaps':overlaps,'overlap_fraction':round(sum(a['overlap_m2'] for a in overlaps)/(u['width']*u['depth']),4) if u['width']*u['depth']>EPS else None})
    check('services_stacking','SPEC-SV-01','تنسيق الخدمات رأسيًا ومسارات الصرف والتغذية',observed={'upper_wet_rooms':len(upper),'aligned_rooms':sum(bool(a['overlaps']) for a in wet_alignment)},evidence={'room_alignment':wet_alignment,'scope':'geometric overlap only; not plumbing or structural approval'},pending='لم تُنمذج شبكة خدمات أو أعمدة أو حسابات دعم؛ قياس التراكب الهندسي لا يثبت صلاحية التمديدات')
    check('decisions','SPEC-PG-01','حسم تعارضات المصعد والخادمة ومدخل الخدمة',pending='القرارات الثلاثة محفوظة كمعلقة؛ لم يُحوّل التفضيل إلى إلزام أو حذف معتمد')
    check('dimensions','SPEC-QC-01','سلاسل أبعاد وتفاصيل تنفيذية كاملة',pending='تُعرض أبعاد الغرف والمبنى فقط؛ سلاسل الفتحات والمناسيب والتفاصيل التنفيذية غير مكتملة')
    return out


def release_decision(checks, requested='DRAFT_REVIEW'):
    failed=[c['check_id'] for c in checks if c['status']=='FAIL']
    pending=[c['check_id'] for c in checks if c['status']=='PENDING']
    return {'requested_profile':requested,'drawing_export_allowed':not failed and requested=='DRAFT_REVIEW',
            'execution_claim_allowed':False,'approval_level':None,'failed_checks':failed,'pending_checks':pending,
            'status':'BLOCKED_FAILURE' if failed else 'DRAFT_WITH_DISCLOSED_PENDING',
            'reason':'فشل هندسي يمنع تصدير الرسم؛ التقرير التشخيصي متاح' if failed else 'مسودة مراجعة فقط؛ لا اعتماد هندسي أو تنفيذي آلي'}
