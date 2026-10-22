"""Translate household needs into a proposed architectural program, then geometric search.

Design recommendations are distinct from source-bound national rules and parcel approval.
"""
import json,math
from pathlib import Path
from typing import Literal
from pydantic import Field,model_validator
from .general_models import Strict,VillaBrief,SpaceRequest
from .saudi_rules import required_setbacks,registry

class SiteEvidence(Strict):
    source: Literal['scaled_image','gps_corners']
    area_m2: float = Field(gt=0,le=5000)
    point_count: Literal[4]
    review_required: Literal[True]


class ClientIntent(Strict):
    width: float = Field(ge=8,le=60)
    depth: float = Field(ge=8,le=80)
    country: Literal['SA','YE']='SA'
    region: str = Field(default='',max_length=100)
    city: str = Field(default='',max_length=100)
    north_edge: Literal['top','right','bottom','left']='top'
    street_edges: list[Literal['top','right','bottom','left']]=Field(min_length=1,max_length=4)
    main_street: Literal['top','right','bottom','left']='bottom'
    street_widths: dict[str,float]=Field(default_factory=dict)
    family: int = Field(ge=1,le=12)
    building: Literal['villa','house','investment']='villa'
    output_level: Literal['economy','standard','luxury']='standard'
    design_priority: Literal['efficiency','usability','prestige']='usability'
    floors: Literal['auto','one','two']='auto'
    comfort: Literal['compact','balanced','generous']='balanced'
    majlis: bool=True
    office: bool=False
    accessible_bedroom: bool=False
    notes: str=Field(default='',max_length=1500)
    site_evidence: SiteEvidence | None = None

    @model_validator(mode='after')
    def consistent(self):
        if not (self.city.strip() or self.region.strip()):
            raise ValueError('حدد المحافظة أو المنطقة، أو اكتب اسم الموقع يدويًا')
        if len(set(self.street_edges))!=len(self.street_edges) or self.main_street not in self.street_edges:
            raise ValueError('حدد الشارع الرئيسي ضمن جهات الشوارع دون تكرار')
        if any(k not in self.street_edges or not 1<=v<=100 for k,v in self.street_widths.items()):
            raise ValueError('عرض الشارع المعروف بين 1 و100 م ولجهة شارع محددة فقط')
        if self.site_evidence and abs(self.width*self.depth-self.site_evidence.area_m2)>0.08*self.width*self.depth:
            raise ValueError('مساحة القياس المبدئي لا تتفق مع الأبعاد؛ أعد فحص الأركان')
        return self

def propose(intent:ClientIntent):
    if intent.building=='investment':
        raise ValueError('المبنى السكني الاستثماري يحتاج محرك وحدات مستقلة ومداخل وسلالم مشتركة؛ لا يجوز توليد فيلا وتسميتها مبنى استثماريًا. هذا النوع متاح لإدخال البيانات فقط حتى اكتمال محرك الوحدات.')
    edges=['top','right','bottom','left'];directions=['north','east','south','west']
    rotation=edges.index(intent.north_edge)
    mapping={edge:directions[(i-rotation)%4] for i,edge in enumerate(edges)}
    width,depth=(intent.depth,intent.width) if rotation%2 else (intent.width,intent.depth)
    if width>60 or depth>80:
        raise ValueError('الأبعاد بعد توجيه الشمال تتجاوز نطاق المحرك الحالي؛ يدعم عرضًا حتى 60 م وعمقًا حتى 80 م في المسقط المتجه شمالًا')
    floors=1 if intent.floors=='one' or (intent.floors=='auto' and intent.family<=3 and width*depth>=350) else 2
    entry=mapping[intent.main_street]
    known={mapping[e]:(intent.street_widths[e] if e in intent.street_widths else 0) for e in edges if e not in intent.street_edges or e in intent.street_widths}
    # Calculate known boundaries through the existing, source-bound rule engine.
    from types import SimpleNamespace
    calculated=required_setbacks(SimpleNamespace(boundary_widths=known,entrance_face=entry)) if intent.country=='SA' else {}
    # Yemen: indicative design clearances only; never mislabel as Yemen legal setbacks.
    unknown=[mapping[e] for e in intent.street_edges if e not in intent.street_widths]
    setbacks={face:calculated.get(face,(6.0 if face==entry else 3.0) if intent.country=='SA' else (4.0 if face==entry else 2.0)) for face in directions}
    rows=[];reasoning=[]
    scale={'compact':.92,'balanced':1.,'generous':1.15}[intent.comfort]*{'economy':.92,'standard':1.,'luxury':1.12}[intent.output_level]
    def add(id,name,kind,floor,count,area,side,capacity=0):
        minimum=registry()['rules']['rooms']['minimums'].get(kind,[0,0]) if intent.country=='SA' else [0,0]
        rows.append(SpaceRequest(id=id,name=name,kind=kind,floor=floor,count=count,min_area=round(max(area*scale,minimum[0]),2),min_side=max(side,minimum[1]),capacity=capacity))
    sleeping=floors-1
    master_floor=0 if intent.accessible_bedroom else sleeping
    add('auto-master','غرفة النوم الرئيسية','master',master_floor,1,20,3.5,min(2,intent.family))
    remaining=max(0,intent.family-2)
    if remaining//2:add('auto-children','غرف نوم الأسرة','bedroom',sleeping,remaining//2,16,3.2,2)
    if remaining%2:add('auto-single','غرفة نوم فردية','bedroom',sleeping,1,14,3.2,1)
    if floors==2 and not any(r.floor==1 for r in rows):
        # An accessible main bedroom still needs an actual upper-floor family program.
        add('auto-upper-living','جلسة عائلية علوية','living',1,1,18,3.2)
    add('auto-living','المعيشة العائلية','living',0,1,max(20,intent.family*4),3.5)
    add('auto-dining','غرفة الطعام','dining',0,1,16 if intent.family<=6 else 20,3.)
    add('auto-kitchen','المطبخ','kitchen',0,1,16,3.)
    if intent.majlis:
        add('auto-majlis','مجلس الضيوف','majlis',0,1,24,3.5)
        add('auto-guest-wc','حمام الضيوف','bathroom',0,1,4,1.6)
    add('auto-family-bath','حمام الأسرة','bathroom',sleeping,max(1,math.ceil((1+math.ceil(remaining/2))/3)),5,1.6)
    if intent.accessible_bedroom and floors==2:add('auto-ground-bath','حمام الدور الأرضي','bathroom',0,1,5,1.6)
    if intent.office:add('auto-office','مكتب منزلي','office',0,1,12,3.)
    reasoning.extend([
        f'سعة النوم المقترحة {intent.family} أشخاص: غرفة رئيسية وغرف إضافية حسب عدد أفراد الأسرة، دون طلب عدد غرف منك.',
        'الضيافة والمدخل والموزع وحمام الضيوف منفصلة عن مسار الأسرة.' if intent.majlis else 'تُخصص المساحة للمعيشة العائلية دون مجلس مستقل بناءً على اختيارك.',
        'اقتُرح دوران لفصل النوم عن الاستقبال.' if floors==2 else 'اقتُرح دور واحد مع تجميع غرف النوم بعيدًا عن الاستقبال.',
        'المساحات والأبعاد توصيات تصميمية قابلة للتعديل، وليست حدودًا قانونية إلا حيث يحدد مرجع القاعدة ذلك.',
    ])
    if intent.accessible_bedroom:reasoning.append('غرفة رئيسية وحمام في الأرضي لتقليل استخدام الدرج؛ لا يعني ذلك اعتماد إتاحة الوصول.')
    warnings=(['اختيار المنطقة والمدينة لا يستبدل اشتراطات قطعة الأرض؛ تُستخدم مراجع السعودية المتاحة جزئيًا وتبقى المطابقة المحلية معلقة.'] if intent.country=='SA' else ['اليمن: لا تتوفر اشتراطات تنظيمية محلية موثقة في هذا الإصدار؛ الارتدادات 4م أمامي و2م جانبي/خلفي افتراضات تصميمية غير قانونية، ويجب اعتمادها من الجهة المختصة قبل أي إصدار تنفيذي.'])
    if unknown:warnings.append('عروض بعض الشوارع غير معروفة: جميع الارتدادات أمام الشوارع غير المتحقق منها افتراضية، ويجب مراجعتها محليًا.')
    if rotation:warnings.append('رُتبت الأبعاد والجهات لعرض المسقط والشمال إلى الأعلى؛ بيانات الأرض الأصلية محفوظة دون تغيير.')
    if intent.notes.strip():warnings.append('الرغبات النصية محفوظة كاملة؛ لا يُعد النص غير المحوّل إلى فراغ أو قيد منفذًا تلقائيًا.')
    if intent.site_evidence:
        warnings.append('أبعاد الأرض مستخلصة من زوايا مُدخلة أو صورة مُعايرة؛ ليست إثباتًا مساحيًا أو سند ملكية ولا تحدد الشوارع تلقائيًا.')
    municipality=''
    if intent.country=='SA':
        directory=json.loads((Path(__file__).resolve().parents[2]/'constitution/saudi/municipalities.json').read_text())
        for amanat in directory['amanats']:
            if intent.city==amanat['name'] or any(intent.city==r['Name'] for r in amanat['municipalities']):municipality=amanat['name'];break
    b=VillaBrief(project_name='تصور مسكن الأسرة',plot_width=width,plot_depth=depth,floors=floors,setbacks=setbacks,
        country=intent.country,apply_saudi_rules=intent.country=='SA',region=intent.region,
        entrance_face=entry,rooms=rows,city=intent.city or intent.region,municipality=municipality,boundary_widths=known,
        dining_seats=next((n for n in (4,6,8,10,12) if n>=intent.family),12),separate_guest_entry=intent.majlis,
        notes=intent.notes,massing_strategy='coherent',site_placement='auto_rear_corner')
    reasoning.append('مستوى المخرجات: '+{'economy':'اقتصادي','standard':'متوسط','luxury':'فاخر'}[intent.output_level]+'؛ أولوية التصميم: '+{'efficiency':'ترشيد المساحة','usability':'سهولة الاستخدام','prestige':'الرحابة والفخامة'}[intent.design_priority]+'.')
    planning={'version':'architect-program-2','method':'household program synthesis + constrained geometric search; no language model connected',
        'original_intent':intent.model_dump(),'site_evidence':intent.site_evidence.model_dump() if intent.site_evidence else None,'orientation':{'north_up':True,'edge_mapping':mapping},
        'recommended_floors':floors,'sleeping_capacity':sum(r.count*r.capacity for r in rows),
        'program':[r.model_dump() for r in rows],'reasoning':reasoning,'warnings':warnings,
        'setbacks':{'values':setbacks,'source':registry()['rules']['setbacks'] if intent.country=='SA' else {'jurisdiction':'YE','status':'UNVERIFIED_DESIGN_ASSUMPTION'},'unknown_street_faces':unknown,'local_parcel_verified':False}}
    return b,planning

def generate_automatic(intent:ClientIntent,output_dir=None):
    """Select three distinct *validated* geometries using the user's objectives.

    The search library may grow; no externally fixed L/U/stepped alternative.
    Unsupported multi-unit buildings deliberately fail instead of fabricating
    apartments from the detached-family program.
    """
    from .general_engine import generate_general
    b,planning=propose(intent)
    search_families=('spine','L','U','stepped')
    result=generate_general(b,output_dir,candidate_families=search_families)

    def indicators(model):
        metrics=model.get('metrics',{})
        built=float(metrics.get('floor_built_m2') or 1)
        floors=model.get('massing_quality',{}).get('floors',{})
        quality=list(floors.values())
        perimeter=sum(float(m.get('normalized_perimeter') or 0) for m in quality)/len(quality) if quality else 2
        fill=sum(float(m.get('envelope_fill') or 0) for m in quality)/len(quality) if quality else .5
        circulation=float(metrics.get('circulation_m2') or 0)/max(built*b.floors,1)
        public=sum(float(r['width']*r['depth']) for floor in model['floors']
                   for r in floor['rooms'] if r.get('request_id') and r['kind'] in ('majlis','living','dining'))
        return {'built_area_m2':round(built,2),'circulation_ratio':round(circulation,4),
                'normalized_perimeter':round(perimeter,4),'envelope_fill':round(fill,4),
                'social_area_m2':round(public,2)}

    def score(m):
        x=indicators(m)
        # Scores are design HEURISTICS (not construction estimates, usability
        # certification, or proof of luxury). Lower values are preferred.
        economy=x['built_area_m2']*(1+x['circulation_ratio']*.65)+x['normalized_perimeter']*9
        accessible=x['circulation_ratio']*180+x['normalized_perimeter']*9+(1-x['envelope_fill'])*12
        prestige=-x['social_area_m2']+x['normalized_perimeter']*9+(1-x['envelope_fill'])*14
        weights={'efficiency':(.75,.20,.05),'usability':(.3,.6,.1),'prestige':(.15,.25,.6)}[intent.design_priority]
        # Compare within each indicator separately, not currency or measured costs.
        all_scores=(economy/100,accessible/30,prestige/100)
        return round(sum(w*v for w,v in zip(weights,all_scores)),6)

    for m in result['candidates']:
        m['design_evaluation']={'metrics':indicators(m),'objective':intent.design_priority,
                                'output_level':intent.output_level,'heuristic_score':score(m),
                                'method':'measured_area+circulation+mass_compactness+social_area; unverified heuristic'}
    valid=sorted((m for m in result['candidates'] if m['release']['drawing_export_allowed']),
                 key=lambda m:(m['design_evaluation']['heuristic_score'],m['candidate_id']))
    rejected=sorted((m for m in result['candidates'] if not m['release']['drawing_export_allowed']),
                    key=lambda m:(len([c for c in m['checks'] if c['status']=='FAIL']),m['candidate_id']))
    # Never call a failed drawing a candidate that passed. Prefer three
    # buildable review drafts; preserve failed diagnostics when too few exist.
    chosen=(valid+rejected)[:3]
    titles=['المقترح الأنسب لاحتياجاتك','مقترح بديل للمقارنة','مقترح ثالث للمقارنة']
    for i,m in enumerate(chosen):
        m['design_option']={'order':i+1,'title':titles[i],
            'profile':intent.output_level,'priority':intent.design_priority,
            'validated':bool(m['release']['drawing_export_allowed']),
            'method':'adaptive ranking over an expandable geometric search library'}
        m['search']['family_label_ar']=titles[i]
    result['candidates']=chosen
    planning['massing_strategy']='coherent-1'
    planning['design_selection']={'strategy':'objective_ranked_geometry_v1',
        'user_level':intent.output_level,'user_priority':intent.design_priority,
        'families_examined':len(search_families),'alternatives_returned':len(chosen),
        'validated_count':sum(bool(m['release']['drawing_export_allowed']) for m in chosen),
        'library_limited':True,'executive_approval':False}
    planning['reasoning'].append('تمت مقارنة مكتبة هندسية متوسعة وفق المساحة المبنية والحركة وانتظام الكتلة ورحابة المعيشة؛ لا يُفرض شكل L أو U أو المتدرج كاسم للبديل.')
    planning['reasoning'].append('النتائج محدودة بالحلول التي اختبرها المحرك؛ المعايير النوعية والتكلفة الفعلية والإنشاء والخصوصية الكاملة تتطلب مراجعة المهندس.')
    planning['placement_strategy']='auto-rear-corner-1'
    result['planning']=planning
    out=Path(output_dir) if output_dir else Path(__file__).resolve().parents[2]/'outputs'
    for model in chosen:
        model['planning']=planning
        (out/(model['model_revision_id']+'.json')).write_text(json.dumps(model,ensure_ascii=False,indent=2),encoding='utf-8')
    return result
