"""Translate household needs into a proposed architectural program, then geometric search.

Design recommendations are distinct from source-bound national rules and parcel approval.
"""
import json,math
from pathlib import Path
from typing import Literal
from pydantic import Field,model_validator
from .general_models import Strict,VillaBrief,SpaceRequest
from .saudi_rules import required_setbacks,registry

class ClientIntent(Strict):
    width: float = Field(ge=8,le=60)
    depth: float = Field(ge=8,le=80)
    city: str = Field(min_length=1,max_length=100)
    north_edge: Literal['top','right','bottom','left']='top'
    street_edges: list[Literal['top','right','bottom','left']]=Field(min_length=1,max_length=4)
    main_street: Literal['top','right','bottom','left']='bottom'
    street_widths: dict[str,float]=Field(default_factory=dict)
    family: int = Field(ge=1,le=12)
    building: Literal['villa','house']='villa'
    floors: Literal['auto','one','two']='auto'
    comfort: Literal['compact','balanced','generous']='balanced'
    majlis: bool=True
    office: bool=False
    accessible_bedroom: bool=False
    notes: str=Field(default='',max_length=1500)

    @model_validator(mode='after')
    def consistent(self):
        if len(set(self.street_edges))!=len(self.street_edges) or self.main_street not in self.street_edges:
            raise ValueError('حدد الشارع الرئيسي ضمن جهات الشوارع دون تكرار')
        if any(k not in self.street_edges or not 1<=v<=100 for k,v in self.street_widths.items()):
            raise ValueError('عرض الشارع المعروف بين 1 و100 م ولجهة شارع محددة فقط')
        return self

def propose(intent:ClientIntent):
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
    calculated=required_setbacks(SimpleNamespace(boundary_widths=known,entrance_face=entry))
    unknown=[mapping[e] for e in intent.street_edges if e not in intent.street_widths]
    setbacks={face:calculated.get(face,6.0 if face==entry else 3.0) for face in directions}
    rows=[];reasoning=[]
    scale={'compact':.92,'balanced':1.,'generous':1.15}[intent.comfort]
    def add(id,name,kind,floor,count,area,side,capacity=0):
        minimum=registry()['rules']['rooms']['minimums'].get(kind,[0,0])
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
    warnings=['اختيار المدينة لا يستبدل اشتراطات المخطط وقطعة الأرض؛ التطبيق يستخدم المرجع الوطني المتاح وتبقى المراجعة المحلية معلقة.']
    if unknown:warnings.append('عروض بعض الشوارع غير معروفة: اقتُرحت ارتدادات أولية 6 م للواجهة الرئيسية و3 م لبقية الشوارع؛ مطابقتها النظامية غير محسومة.')
    if rotation:warnings.append('رُتبت الأبعاد والجهات لعرض المسقط والشمال إلى الأعلى؛ بيانات الأرض الأصلية محفوظة دون تغيير.')
    if intent.notes.strip():warnings.append('الرغبات النصية محفوظة كاملة؛ لا يُعد النص غير المحوّل إلى فراغ أو قيد منفذًا تلقائيًا.')
    municipality=''
    directory=json.loads((Path(__file__).resolve().parents[2]/'constitution/saudi/municipalities.json').read_text())
    for amanat in directory['amanats']:
        if intent.city==amanat['name'] or any(intent.city==r['Name'] for r in amanat['municipalities']):municipality=amanat['name'];break
    b=VillaBrief(project_name='تصور مسكن الأسرة',plot_width=width,plot_depth=depth,floors=floors,setbacks=setbacks,
        entrance_face=entry,rooms=rows,city=intent.city,municipality=municipality,boundary_widths=known,
        dining_seats=next((n for n in (4,6,8,10,12) if n>=intent.family),12),separate_guest_entry=intent.majlis,
        notes=intent.notes,massing_strategy='coherent',site_placement='auto_rear_corner')
    planning={'version':'architect-program-1','method':'household program synthesis + constrained geometric search; no language model connected',
        'original_intent':intent.model_dump(),'orientation':{'north_up':True,'edge_mapping':mapping},
        'recommended_floors':floors,'sleeping_capacity':sum(r.count*r.capacity for r in rows),
        'program':[r.model_dump() for r in rows],'reasoning':reasoning,'warnings':warnings,
        'setbacks':{'values':setbacks,'source':registry()['rules']['setbacks'],'unknown_street_faces':unknown,'local_parcel_verified':False}}
    return b,planning

def generate_automatic(intent:ClientIntent,output_dir=None):
    from .general_engine import generate_general
    b,planning=propose(intent)
    result=generate_general(b,output_dir)
    def rank(model):
        if not model['release']['drawing_export_allowed']:return (1,float('inf'))
        metrics=list(model.get('massing_quality',{}).get('floors',{}).values())
        cost=sum(m['normalized_perimeter']+(1-m['envelope_fill'])+m['circulation_ratio'] for m in metrics)/len(metrics) if metrics else float('inf')
        return (0,cost)
    result['candidates'].sort(key=rank)
    planning['massing_strategy']='coherent-1'
    planning['recommended_pattern']=next((m['candidate_id'] for m in result['candidates'] if m['release']['drawing_export_allowed']),None)
    planning['reasoning'].append('أُعطيت الأولوية لكتلة متصلة ومنتظمة نسبيًا، مع تقليل النتوءات والممرات غير الخادمة؛ يُعرض البديل الأفضل في هذا القياس أولًا.')
    planning['placement_strategy']='auto-rear-corner-1'
    planning['reasoning'].append('عندما تسمح المساحة، يُجمع المبنى في أحد الركنين الخلفيين بعيدًا عن المدخل، بمحاذاة حدين متعامدين من نطاق البناء، لتبقى فسحة أمامية متصلة. تبقى الارتدادات النظامية محفوظة.')
    result['planning']=planning
    out=Path(output_dir) if output_dir else Path(__file__).resolve().parents[2]/'outputs'
    for model in result['candidates']:
        model['planning']=planning
        (out/(model['model_revision_id']+'.json')).write_text(json.dumps(model,ensure_ascii=False,indent=2),encoding='utf-8')
    return result
