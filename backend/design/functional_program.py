"""V4 semantic program and furniture-aware paths. No statutory conclusions.

The 0.60m body and 0.20m raster are disclosed design approximations. Recorded
polylines traverse modeled portals and avoid furniture; they are not egress or
accessible-route certification. Unsupported policy ontology remains REVIEW.
"""
from dataclasses import dataclass, asdict
import math
from .functional_intelligence import RELATIONSHIPS
from .walkability import floor_access
from .furnishing import valid_group

@dataclass(frozen=True)
class FunctionalSpace:
    id: str
    function: str
    floor: int
    count: int
    min_area_m2: float
    min_side_m: float
    capacity: int
    privacy: str
    required_furniture: tuple
    natural_light: str='exterior_opening_required_but_adequacy_unverified'
    services: str='not_coordinated'
    preferred_dimensions: None=None
    design_max_area: None=None
    basis: str='customer_or_proposed_program; not a statutory rule'

@dataclass(frozen=True)
class SpatialRelationship:
    id: str
    source_kind: str
    target_kind: str
    type: str
    strength: str
    weight: float
    source_rule: str | None

FURNITURE={'bedroom':('bed','wardrobe'),'master':('bed',),'living':('sofa',),
           'majlis':('sofa',),'dining':('dining_table','dining_chair'),
           'kitchen':('kitchen_counter',),'bathroom':('toilet','basin'),
           'office':('desk',),'laundry':('washing_machine',),'storage':('storage',)}

class RoomProgramValidator:
    def __init__(self, brief):self.brief=brief
    def spaces(self):
        return [asdict(FunctionalSpace(r.id,r.kind,r.floor,r.count,r.min_area,r.min_side,r.capacity,
                   'private' if r.kind in ('master','bedroom') else 'program_dependent',
                   FURNITURE.get(r.kind,()),services='wet_service_uncoordinated' if r.kind in ('bathroom','kitchen','laundry') else 'not_coordinated'))
                for r in self.brief.rooms]
    def validate(self,model):
        errors=[]
        for index in range(self.brief.floors):
            actual=[r for f in model['floors'] if f['id']==('GF','FF')[index] for r in f['rooms'] if r.get('request_id')]
            for req in (r for r in self.brief.rooms if r.floor==index):
                matches=[r for r in actual if r['request_id']==req.id]
                if len(matches)!=req.count:errors.append({'request':req.id,'problem':'count','expected':req.count,'actual':len(matches)})
                for r in matches:
                    if r['kind']!=req.kind or r.get('capacity',0)<req.capacity or r['width']*r['depth']+1e-6<req.min_area or min(r['width'],r['depth'])+1e-6<req.min_side:
                        errors.append({'request':req.id,'room':r['id'],'problem':'function_capacity_or_dimensions'})
            unexpected=[r['id'] for r in actual if r['request_id'] not in {q.id for q in self.brief.rooms if q.floor==index}]
            if unexpected:errors.append({'floor':index,'problem':'unrequested_spaces','rooms':unexpected})
        return {'status':'FAIL' if errors else 'PASS','errors':errors,'spaces':self.spaces()}

class FunctionalGraph:
    def __init__(self,model):self.model=model
    def relationships(self):
        return [asdict(SpatialRelationship(code,a,b,'SHORT_ROUTE','SOFT_PREFERENCE',weight,rule))
                for a,b,weight,code,rule in RELATIONSHIPS]
    def inspect(self):
        rows=[]
        for floor in self.model['floors']:
            requested=[r for r in floor['rooms'] if (r.get('request_id') or r['kind']=='stair') and r.get('zone')!='guest']
            for source,target,weight,code,rule in RELATIONSHIPS:
                targets=[r for r in requested if r['kind']==target]
                for a in (r for r in requested if r['kind']==source):
                    if not targets:continue
                    choices=[]
                    for b in targets:
                        if a['id']==b['id']:continue
                        allowed={r['id'] for r in floor['rooms'] if r['id'] in (a['id'],b['id']) or
                                 (r['kind'] not in ('bedroom','master','bathroom') and r.get('zone')!='guest')}
                        evidence=floor_access(self.model,floor,step=.20,body_width=.60,
                                              start_room_id=a['id'],allowed_room_ids=allowed)
                        points=evidence['routes'].get(b['id'])
                        if points:
                            length=sum(math.dist(p,q) for p,q in zip(points,points[1:]))
                            choices.append((length,b,points))
                    base={'id':code,'floor':floor['id'],'from_id':a['id'],'target_kind':target,'weight':weight,'source_rule':rule}
                    if not choices:
                        rows.append({**base,'status':'UNREACHABLE','route_m':None,'points':[],'detour_ratio':None});continue
                    length,b,points=min(choices,key=lambda q:(q[0],q[1]['id']))
                    straight=math.dist(points[0],points[-1])
                    rows.append({**base,'to_id':b['id'],'status':'MEASURED','route_m':round(length,4),'points':points,
                                 'detour_ratio':round(length/max(straight,.1),4),'turns':max(0,len(points)-2)})
        weights=sum(r['weight'] for r in rows) or 1
        penalty=sum(r['weight']*(1 if r['status']=='UNREACHABLE' else min(1,max(0,r['detour_ratio']-1)/2)) for r in rows)/weights
        return {'revision':'functional-geometry-4','relationships':self.relationships(),'routes':rows,
                'unreachable':[r for r in rows if r['status']=='UNREACHABLE'],'soft_penalty':round(penalty,6),
                'method':'0.20m axis-aligned raster, 0.60m proposed body, physical doors open, furniture inflated; private/guest transit forbidden',
                'legal_approval':False,'visual_and_acoustic_privacy':'REVIEW','unsupported_ontology':'REVIEW, not silently mapped to generic rooms'}

def furniture_issues(model):
    bad=[]
    for f in model['floors']:
        for r in f['rooms']:
            items=[q for q in f['furniture'] if q['room_id']==r['id']]
            if items and not valid_group(f,r,items,existing=[]):bad.append({'floor':f['id'],'room':r['id'],'problem':'overlap_use_zone_or_port_clearance'})
    return bad

def assess(model,brief):
    program=RoomProgramValidator(brief).validate(model);paths=FunctionalGraph(model).inspect();furniture=furniture_issues(model)
    from .visual_privacy import inspect as inspect_privacy
    from .independent_audit import inspect as inspect_independent
    from .execution_coordination import assess as assess_coordination
    return {'visual_privacy':inspect_privacy(model),'independent_geometry':inspect_independent(model),
            'execution_coordination':assess_coordination(model,brief),
            'revision':'functional-program-4','program':program,'movement':paths,'furniture_issues':furniture}

def checks(report):
    from .execution_coordination import checks as coordination_checks
    basic=[dict(check_id='V4-program',status=report['program']['status'],label='سلامة الوظيفة والسعة والبرنامج',evidence={'errors':report['program']['errors']}),
            dict(check_id='V4-functional-paths',status='FAIL' if report['movement']['unreachable'] else 'PASS',label='مسارات وظيفية حول الأثاث عبر الأبواب دون اختراق الخصوصية',evidence=report['movement']),
            dict(check_id='V4-furniture-clearance',status='FAIL' if report['furniture_issues'] else 'PASS',label='عدم تداخل الأثاث وخلوصات الاستعمال والفتح',evidence={'invalid':report['furniture_issues']}),
            dict(check_id='V4-geos-independent',status=report['independent_geometry']['status'],
                 label='تدقيق مستقل لتداخل الغرف وخروجها عن حيز الكتلة',evidence=report['independent_geometry']),
            dict(check_id='V4-networkx-topology',
                 status='PENDING' if report['independent_geometry']['requires_circulation_review'] else 'PASS',
                 label='رسم بياني مستقل لاتصال الفراغات؛ لا يحل محل فحص مسارات الحركة',
                 evidence={'requires_review':report['independent_geometry']['requires_circulation_review'],
                           'floors':report['independent_geometry']['floors']})]
    return basic+coordination_checks(report['execution_coordination'])


def validate(model,brief):
    from .general_engine import validate_general
    rows=validate_general(model,brief)
    model['functional_program_v4']=assess(model,brief)
    return rows+checks(model['functional_program_v4'])
