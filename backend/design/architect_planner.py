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
    district: str = Field(default='',max_length=100)
    neighborhood: str = Field(default='',max_length=100)
    investment_units: int = Field(default=4,ge=2,le=40)
    investment_unit_area: float = Field(default=100,ge=30,le=400)
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
    if intent.building=='house':scale*=.95
    corridor={'economy':1.3,'standard':1.5,'luxury':1.65}[intent.output_level]
    if intent.building=='house':corridor=max(1.2,corridor-.1)
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
        country=intent.country,apply_saudi_rules=intent.country=='SA',region=intent.region,district=intent.district,neighborhood=intent.neighborhood,building_type=intent.building,
        corridor_width=corridor,
        entrance_face=entry,rooms=rows,city=intent.city or intent.region,municipality=municipality,boundary_widths=known,
        dining_seats=next((n for n in (4,6,8,10,12) if n>=intent.family),12),separate_guest_entry=intent.majlis,
        notes=intent.notes,reference_strategy='design-principles-v1',adaptive_search=True,massing_strategy='coherent',site_placement='auto_rear_corner')
    reasoning.append('سكن خاص: برنامج عائلي مدمج وخدمات متقاربة وممرات أقل اتساعًا مع بقاء فصل الضيوف.' if intent.building=='house' else 'فيلا: فصل الاستقبال عن الأسرة مع رحابة حركة مناسبة للمستوى المختار.')
    reasoning.append('مستوى المخرجات: '+{'economy':'اقتصادي','standard':'متوسط','luxury':'فاخر'}[intent.output_level]+'؛ أولوية التصميم: '+{'efficiency':'ترشيد المساحة','usability':'سهولة الاستخدام','prestige':'الرحابة والفخامة'}[intent.design_priority]+'.')
    planning={'version':'architect-program-4','method':'household program synthesis + constrained geometric search; no language model connected',
        'original_intent':intent.model_dump(),'site_evidence':intent.site_evidence.model_dump() if intent.site_evidence else None,'orientation':{'north_up':True,'edge_mapping':mapping},
        'recommended_floors':floors,'sleeping_capacity':sum(r.count*r.capacity for r in rows),
        'program':[r.model_dump() for r in rows],'reasoning':reasoning,'warnings':warnings,
        'setbacks':{'values':setbacks,'source':registry()['rules']['setbacks'] if intent.country=='SA' else {'jurisdiction':'YE','status':'UNVERIFIED_DESIGN_ASSUMPTION'},'unknown_street_faces':unknown,'local_parcel_verified':False}}
    return b,planning

def generate_automatic(intent:ClientIntent,output_dir=None,*,constitution_v2=False,generation_v3=False,generation_v4=False):
    """Search physical allocations and core positions, validate, diversify, then export.

    No failed drawings or near-duplicate plans fill a missing third alternative.
    """
    generation_v3=generation_v3 or generation_v4
    constitution_v2=constitution_v2 or generation_v4
    from .general_engine import generate_general,export_general_model
    from .design_selection import evaluate,select,MAX_SLEEPING_ASPECT_RATIO
    out=Path(output_dir) if output_dir else Path(__file__).resolve().parents[2]/'outputs'
    out.mkdir(parents=True,exist_ok=True)
    b,planning=propose(intent)
    if generation_v4:b=b.model_copy(update={'compact_core':True})
    if generation_v3:
        primary=[{'family':f,'policy':p,'core_position':c} for f,p,c in (
            ('freeform','relationship_aware','rear'),
            ('adaptive','relationship_aware','rear'),
            ('spine','relationship_aware','rear'),
            ('cross','relationship_aware','rear'),
            ('freeform','social_front','front'),
            ('adaptive','social_front','front'),
            ('spine','service_aligned','rear'),
        )]
    else:
        primary=[{'family':f,'policy':'legacy','core_position':'rear'} for f in ('spine','L','U','stepped','cross')]
        primary.extend({'family':f,'policy':'social_front','core_position':'front'} for f in ('spine','L'))
        primary.append({'family':'spine','policy':'service_aligned','core_position':'rear'})
    if generation_v4:
        primary.insert(0,{'family':'cluster','policy':'relationship_aware','core_position':'rear'})
        primary.insert(1,{'family':'meander','policy':'relationship_aware','core_position':'rear'})
    pool=[];unavailable=[];examined=[];repair_history=[]
    def preflight_v4(candidate):
        # Evaluate actual room/furniture paths and attempt safe local repairs
        # *before* accepting a geometric candidate. A V3-valid first layout
        # may fail V4 even when the following layout is fit for use.
        from .auto_repair import ArchitectureAutoRepairEngine
        from .functional_program import validate as validate_v4
        return ArchitectureAutoRepairEngine(lambda proposed:validate_v4(proposed,b),max_attempts=8).repair(candidate)
    def explore(options):
        batch=generate_general(b,out,candidate_families=tuple(dict.fromkeys(o['family'] for o in options)),search_options=options,emit_drawings=False,
            candidate_validator=preflight_v4 if generation_v4 else None,repair_layout=generation_v4)
        unavailable.extend(batch['unavailable']);examined.extend(options)
        for m in batch['candidates']:
            if generation_v4:
                # Preflight may have inspected several room arrangements already.
                # Never skip validation of a legacy-rejected fallback model.
                if 'auto_repair_v4' not in m:
                    m=preflight_v4(m)
                failed=any(row['status']=='FAIL' for row in m['checks'])
                m['release'].update(status='BLOCKED' if failed else 'DRAFT_REVIEW',drawing_export_allowed=not failed)
            m['candidate_id']='-'.join((m['search']['family'],m['search']['allocation_policy'],m['search']['core_position']))
            if generation_v3:
                from .functional_intelligence import repair_reasons
                m['generation_mode']='V3_ADAPTIVE'
                m['repair_diagnosis']=repair_reasons(m)
                m['search']['relation_aware_allocation']=m['search']['allocation_policy']=='relationship_aware'
            if constitution_v2:
                from .constitution_v2 import assess_candidate
                audit=assess_candidate(m,intent)
                m['constitution_v2']=audit
                if audit['hard_failures']:
                    m['release']['status']='BLOCKED'
                    m['release']['drawing_export_allowed']=False
            m['design_evaluation']=evaluate(m,intent);pool.append(m)
    explore(primary)
    chosen=select(pool,optimization='cp_sat' if generation_v4 else 'greedy')
    expanded=False
    poor_quality=(generation_v3 and any(
        (m['design_evaluation']['functional_intelligence'] or {}).get('soft_penalty',0)>.28
        for m in chosen))
    if len(chosen)<3 or poor_quality:
        expanded=True
        if generation_v3:
            from collections import Counter
            reasons=Counter(r for model in pool for r in model.get('repair_diagnosis',[]))
            preferred=[('freeform','relationship_aware','front'),
                       ('adaptive','relationship_aware','front'),
                       ('spine','relationship_aware','front'),
                       ('cross','relationship_aware','front')]
            if reasons.get('guest_circulation'):
                preferred.insert(0,('cross','social_front','rear'))
            if reasons.get('food_service_detour'):
                preferred.insert(0,('adaptive','service_aligned','front'))
                preferred.insert(0,('spine','service_aligned','front'))
            if reasons.get('family_movement'):
                preferred.insert(0,('adaptive','relationship_aware','front'))
            if reasons.get('vertical_core') or reasons.get('furnishing'):
                preferred.insert(0,('spine','family_front','rear'))
            preferred.extend([('freeform','service_aligned','rear'),
                              ('adaptive','service_aligned','rear'),
                              ('cross','family_front','front'),
                              ('spine','social_front','front')])
            if generation_v4:
                preferred.insert(0,('cluster','relationship_aware','front'))
                preferred.insert(0,('meander','relationship_aware','rear'))
            tried={(o['family'],o['policy'],o['core_position']) for o in examined}
            repairs=[{'family':f,'policy':p,'core_position':c} for f,p,c in preferred
                     if (f,p,c) not in tried][:5]
            repair_history.append({'round':1,'previous_valid_distinct':len(chosen),
                'reason_counts':dict(reasons),'method':'re-search alternative physical layout, never weaken checks',
                'chosen_search_options':repairs})
            if repairs:explore(repairs)
        else:
            explore([{'family':f,'policy':p,'core_position':c} for f,p,c in (
                ('spine','family_front','rear'),('cross','social_front','rear'),('stepped','social_front','front'),
                ('U','social_front','front'),('L','family_front','front'))])
        chosen=select(pool,optimization='cp_sat' if generation_v4 else 'greedy')
        if repair_history:repair_history[-1]['result_valid_distinct']=len(chosen)
        if generation_v4:
            from .layout_rebuild import replacement_evidence
            blocked=[m for m in pool if not m['release']['drawing_export_allowed']]
            for selected in chosen:
                if not blocked:break
                source=next((candidate for candidate in blocked if candidate['candidate_id']!=selected['candidate_id']),None)
                if source is not None:
                    selected['layout_rebuild_v4']=replacement_evidence(source,selected)
    if generation_v4:
        from .rule_traceability import matrix
        for m in pool:m['rule_traceability_v4']=matrix(m)
    titles=['المقترح الأنسب لاحتياجاتك','بديل وظيفي للمقارنة','بديل ثالث للمقارنة']
    for i,m in enumerate(chosen):
        metrics=m['design_evaluation']['metrics']
        m['design_option']={'order':i+1,'title':titles[i],'profile':intent.output_level,'priority':intent.design_priority,
            'validated':True,'method':'diversified physical allocations and vertical cores after geometric validation',
            'advantages':[f"نسبة الممرات {metrics['circulation_ratio']*100:.1f}٪ من المسطح الكلي",
                f"متوسط مسارات العلاقات الوظيفية المقاسة {metrics['mean_functional_route_m']:.1f} م",
                f"مسطح إجمالي للأدوار {metrics['total_built_m2']:.1f} م²"],
            'selection_reason':'اجتياز الفحوص ثم ترتيب الهدف المختار، مع اختلاف مواقع/ترتيب الفراغات هندسيًا ووظيفيًا عن البدائل السابقة.'}
        reference=m['design_evaluation'].get('reference_patterns')
        if reference and reference['wet_alignment']['ratio'] is not None:
            m['design_option']['advantages'].append(f"تراكب الخدمات رأسيًا {100*reference['wet_alignment']['ratio']:.0f}٪ · مؤشر تنسيق مبدئي")
        if generation_v3:
            from .executive_readiness import assess as executive_assess
            m['executive_readiness']=executive_assess(m)
            m['release']['executive_issue_allowed']=False
            fi=m['design_evaluation']['functional_intelligence']
            m['design_option']['functional_evidence']={
                'evaluated_routes':fi['evaluated_relations'],
                'unreachable_routes':len(fi['unreachable']),
                'guest_exposure':fi['guest_family_exposure'],
                'weighted_preference_penalty':fi['soft_penalty']}
            m['design_option']['method']='V3 parametric wings, measured functional door routes and iterative search repair'
        if generation_v4:m['design_option']['method']='V4 bounded clustered/wing allocation, furniture-aware raster routes, transactional local repair and measured ranking'
        m['search']['family_label_ar']=titles[i]
    diagnostics=[{'candidate_id':m['candidate_id'],'revision_id':m['model_revision_id'],
        'accepted':m in chosen,'geometry_valid':m['release']['drawing_export_allowed'],
        'score':m['design_evaluation']['heuristic_score'],'failed_checks':m['design_evaluation']['failed_checks'],
        'reason':('اختير بعد تقييم الأولوية والتنوع' if m in chosen else 'فشل هندسي؛ الرسم محجوب' if not m['release']['drawing_export_allowed']
                  else f'استبعد بسبب استطالة غرفة نوم تتجاوز نسبة {MAX_SLEEPING_ASPECT_RATIO:.1f} إلى 1؛ حد جودة تصميمي وليس اشتراطًا نظاميًا'
                  if m['design_evaluation']['metrics']['max_sleeping_aspect_ratio']>MAX_SLEEPING_ASPECT_RATIO
                  else 'لم يفضل في الترتيب أو لم يحقق اختلافًا كافيًا')}
        for m in pool]
    from .reference_patterns import REVISION,PROJECTS,UNIQUE_IMAGES
    planning['reference_design']={'revision':REVISION,'project_count':len(PROJECTS),'unique_images':UNIQUE_IMAGES,'legal_rules_extracted':0,'status':'visual design preferences; not surveyed or code-certified','unsupported_reference_features':['basements','general double-height slabs','arbitrary four-level programs','chamfered plots']}
    planning['reasoning'].append('تُقارن خدمة المطبخ للطعام دون عبور الغرف الخاصة، وتراكب الخدمات بين الأدوار، وفسحة نوافذ المعيشة داخل الأرض؛ مؤشرات تصميمية مستخلصة من المراجع وليست قوانين.')
    planning.update(massing_strategy='coherent-1',placement_strategy='auto-rear-corner-1')
    if generation_v3:
        planning['generation_v3']={
            'revision':'adaptive-functional-search-2','status':'EXPERIMENTAL_DESIGN_DRAFT',
            'geometric_method':'bounded three-band variable setbacks plus adaptive orthogonal wings; actual occupied union',
            'functional_method':'scored allocation + measured door-graph relations and privacy evidence',
            'automatic_repair':repair_history,
            'unverified':['unrestricted floorplate solver','structural model','full visual privacy','mechanical services','code approval'],
            'legacy_shapes_in_default_v3_search':False}
    if constitution_v2:
        planning['architecture_constitution_v2']={'version':'2.0.0-draft',
            'mode':'EXPERIMENTAL_OPT_IN_PARTIAL','audited_count':len(pool),
            'blocked_by_v2_count':sum(bool(m['constitution_v2']['hard_failures']) for m in pool),
            'scope':'16 evidence-based audit gates; no complete 143-rule enforcement or code certification'}
    if generation_v4:
        planning['generation_v4']={'revision':'architectural-engine-4','status':'PARTIALLY_COMPLETED',
            'reproducibility':{'stochastic':False,'search_seed':0,'algorithm':'deterministic bounded beam and parameter enumeration','settings':examined},
            'functional_routes':'furniture-aware 0.20m raster with 0.60m design body; recorded polylines',
            'portfolio_selection':'deterministic OR-Tools CP-SAT cardinality-first selection of validated distinct designs',
            'bounded_relayout':'alternate meander/cluster topology; constrained moves and size changes before regenerating all hosted geometry',
            'reflow_evidence_count':sum(bool(m.get('layout_rebuild_v4')) for m in chosen),
            'local_repair_attempts':sum(len(m['auto_repair_v4']['attempts']) for m in pool),
            'local_repairs_accepted':sum(m['auto_repair_v4']['accepted_steps'] for m in pool),
            'reference_projects':['P01','P03','P04','P06','P07','P08'],
            'excluded_reference_projects':['P02','P05'],
            'unimplemented':['unrestricted_polygon_solver','arbitrary_room_edit_within_locked_model','generalized_corridor_polygon_solver','stair_relocation_repair','complete_visual_acoustic_privacy','investment_unit_engine','structural_MEP_approval']}
    planning['design_selection']={'strategy':'objective_ranked_geometry_v3_functional' if generation_v3 else 'objective_ranked_geometry_v2','user_level':intent.output_level,'user_priority':intent.design_priority,
        'families_examined':len(set(o['family'] for o in examined)),'search_variants_examined':len(examined),
        'search_expanded':expanded,'alternatives_returned':len(chosen),'validated_count':len(chosen),
        'max_sleeping_aspect_ratio_design_limit':MAX_SLEEPING_ASPECT_RATIO,
        'library_limited':True,'diversity_rule':'normalized room displacement >= 0.065 plus changed functional order/quadrant',
        'executive_approval':False,'diagnostics':diagnostics}
    planning['reasoning'].append('البحث يغير عنقود الغرف وترتيب الاستقبال والأسرة وموضع الدرج، ويقارن مسارات الأبواب والمسطحات والكتلة. لا يفرض ثلاثة أشكال خارجية.')
    planning['reasoning'].append('الدرجات وعتبات التنوع مؤشرات تصميمية معلنة، وليست تكلفة محسوبة أو اعتمادًا قانونيًا أو ضمانًا للحل الأمثل.')
    if len(chosen)<3:
        unavailable.append({'family':'adaptive','label':'بدائل لم تتحقق','reason':f'بعد توسيع البحث في {len(examined)} توزيعات، تحقق {len(chosen)} حلول مختلفة مجتازة فقط؛ لم تُحذف غرف أو تُخفف فحوص لملء البدائل.'})
    # Only selected valid plans get drawing files. Diagnostics retain JSON only.
    for m in pool:
        m['planning']=planning
        if m in chosen:export_general_model(m,b,out)
        (out/(m['model_revision_id']+'.json')).write_text(json.dumps(m,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    return {'status':'DRAFT_REVIEW' if chosen else 'BLOCKED','candidates':chosen,'unavailable':unavailable,
        'planning':planning,'scope':('V3: كتل متغيرة التراجع وتوزيع علاقات ومسارات وأثاث وبحث إصلاحي محدود؛ أراض مستطيلة 1–2 دور؛ مسودات غير تنفيذية'
            if generation_v3 else 'بحث هندسي محدود قابل للتوسعة؛ أراض مستطيلة ودور أو دوران؛ لا اعتماد تنفيذي'),
        'ai':{'mode':'geometric_search','language_model_connected':False}}
