"""Measured, translation-invariant comparison of actual materialized residential plans.

Scores and diversity thresholds are disclosed design heuristics, not code provisions.
"""
import math
from itertools import combinations

WEIGHTS={
 'efficiency':{'area':.50,'circulation':.25,'compactness':.15,'routes':.10,'social':0},
 'usability':{'area':.10,'circulation':.25,'compactness':.10,'routes':.50,'social':.05},
 'prestige':{'area':.10,'circulation':.15,'compactness':.30,'routes':.15,'social':.30},
}
MAX_SLEEPING_ASPECT_RATIO = 2.0  # Design quality threshold, not a building-code rule.

def measure(model):
    rows={};route_lengths=[];social=0;ratios=[];sleeping_ratios=[];functional=[]
    for f in model['floors']:
        cells=f['cells'];x=min(r['x'] for r in cells);y=min(r['y'] for r in cells)
        w=max(r['x']+r['width'] for r in cells)-x;d=max(r['y']+r['depth'] for r in cells)-y
        rooms=[r for r in f['rooms'] if r.get('request_id')]
        for r in rooms:
            key=f['id']+':'+r['id'].removeprefix(f['id']+'-')
            rows[key]=((r['x']+r['width']/2-x)/w,(r['y']+r['depth']/2-y)/d,r['width']/w,r['depth']/d)
            ratios.append(max(r['width'],r['depth'])/min(r['width'],r['depth']))
            if r['kind'] in ('master','bedroom'):
                sleeping_ratios.append(ratios[-1])
            if r['kind'] in ('majlis','living','dining'):social+=r['width']*r['depth']
        # Door-graph distances use physical corridor cells and opening locations.
        by_id={r['id']:r for r in f['rooms']};graph={rid:{} for rid in by_id}
        for o in f['openings']:
            if o['kind']!='door':continue
            a,b=(o['connects']+[None,None])[:2]
            if a not in by_id or b not in by_id:continue
            ca,cb=by_id[a],by_id[b]
            weight=math.dist((ca['x']+ca['width']/2,ca['y']+ca['depth']/2),o['center'])+math.dist(o['center'],(cb['x']+cb['width']/2,cb['y']+cb['depth']/2))
            graph[a][b]=graph[b][a]=weight
        halls=[r for r in cells if r['kind']=='corridor' and not r.get('guest_distributor')]
        for a,b in combinations(halls,2):
            dx=min(a['x']+a['width'],b['x']+b['width'])-max(a['x'],b['x'])
            dy=min(a['y']+a['depth'],b['y']+b['depth'])-max(a['y'],b['y'])
            if (abs(dx)<1e-6 and dy>.60) or (abs(dy)<1e-6 and dx>.60):
                weight=math.dist((a['x']+a['width']/2,a['y']+a['depth']/2),(b['x']+b['width']/2,b['y']+b['depth']/2))
                graph[a['id']][b['id']]=graph[b['id']][a['id']]=weight
        def distance(start,target):
            distances={start:0};todo=[(0,start)]
            while todo:
                todo.sort(reverse=True);cost,node=todo.pop()
                if node==target:return cost
                for nxt,weight in graph.get(node,{}).items():
                    new=cost+weight
                    if new<distances.get(nxt,math.inf):distances[nxt]=new;todo.append((new,nxt))
            return None
        for ka,kb in [('kitchen','dining'),('living','dining'),('master','bathroom'),('bedroom','bathroom')]:
            for a in (r for r in rooms if r['kind']==ka):
                distances=[distance(a['id'],b['id']) for b in rooms if b['kind']==kb and b.get('zone')!='guest']
                distances=[v for v in distances if v is not None]
                if distances:
                    value=min(distances);route_lengths.append(value)
                    functional.append({'floor':f['id'],'from':a['id'],'to_kind':kb,'door_graph_route_m':round(value,3)})
    qs=list(model.get('massing_quality',{}).get('floors',{}).values())
    area=sum(model['metrics']['floor_built_by_id'].values())
    public_built=area or 1
    required=sum(r['min_area']*r['count'] for r in model['brief']['rooms'])
    proposed=sum(r['width']*r['depth'] for f in model['floors'] for r in f['rooms'] if r.get('request_id'))
    return {'program_excess_ratio':round(max(0,proposed/max(required,1)-1),5),'total_built_m2':round(area,3),'circulation_ratio':round(model['metrics']['circulation_m2']/public_built,5),
      'normalized_perimeter':round(sum(q['normalized_perimeter'] for q in qs)/len(qs),5) if qs else 2,
      'envelope_fill':round(sum(q['envelope_fill'] for q in qs)/len(qs),5) if qs else .5,
      'mean_functional_route_m':round(sum(route_lengths)/len(route_lengths),3) if route_lengths else 0,
      'social_area_m2':round(social,3),'social_ratio':round(social/public_built,5),
      'max_room_aspect_ratio':round(max(ratios,default=1),4),
      'max_sleeping_aspect_ratio':round(max(sleeping_ratios,default=1),4),
      'functional_routes':functional,'normalized_rooms':rows}

def objective_score(metrics,priority):
    components={'area':metrics['total_built_m2']/250,'circulation':metrics['circulation_ratio']/.20,
        'compactness':metrics['normalized_perimeter']+(1-metrics['envelope_fill']),
        'routes':metrics['mean_functional_route_m']/12,'social':1-min(metrics['social_ratio'],.65)/.65}
    weights=WEIGHTS[priority]
    components['program_excess']=metrics['program_excess_ratio']
    weights={**weights,'program_excess':.15}
    return round(sum(weights[k]*v for k,v in components.items()),6),components,weights

def semantic_layout(model):
    """Ignore instance IDs of interchangeable rooms and a whole-building translation."""
    rows=[]
    for f in model.get('floors',[]):
        cells=f['cells'];x=min(r['x'] for r in cells);y=min(r['y'] for r in cells)
        w=max(r['x']+r['width'] for r in cells)-x;d=max(r['y']+r['depth'] for r in cells)-y
        for r in f['rooms']:
            rows.append((f['id'],r.get('request_id') or r['kind'],r['kind'],r.get('capacity',0),r.get('zone','family'),bool(r.get('guest_distributor')),
                round((r['x']-x)/w,5),round((r['y']-y)/d,5),round(r['width']/w,5),round(r['depth']/d,5)))
    return sorted(rows)


def difference(a,b):
    if a.get('floors') and b.get('floors') and semantic_layout(a)==semantic_layout(b):
        return {'distinct':False,'mean_displacement':0,'relative_order_changes':0,'quadrant_changes':0,'semantic_duplicate':True,'reason':'same physical functional layout; interchangeable instance IDs ignored'}
    ar=a['design_evaluation']['metrics']['normalized_rooms'];br=b['design_evaluation']['metrics']['normalized_rooms']
    keys=set(ar)&set(br)
    if not keys:return {'distinct':False,'mean_displacement':0,'relative_order_changes':0,'quadrant_changes':0}
    displacement=sum(math.dist(ar[k][:2],br[k][:2]) for k in keys)/len(keys)
    quadrants=sum((ar[k][0]>=.5,ar[k][1]>=.5)!=(br[k][0]>=.5,br[k][1]>=.5) for k in keys)
    changes=0
    for ka,kb in combinations(sorted(keys),2):
        if ka.split(':')[0]!=kb.split(':')[0]:continue
        changes+=any((ar[ka][axis]-ar[kb][axis])*(br[ka][axis]-br[kb][axis])<-.0025 for axis in (0,1))
    # Both a material geometric difference and a changed functional room position/order.
    return {'distinct':displacement>=.065 and bool(quadrants or changes),
        'mean_displacement':round(displacement,5),'relative_order_changes':changes,'quadrant_changes':quadrants,
        'threshold_status':'design heuristic; normalized mean displacement >= 0.065 and functional position/order change'}

def evaluate(model,intent):
    metrics=measure(model);score,components,weights=objective_score(metrics,intent.design_priority)
    failed=[c['check_id'] for c in model['checks'] if c['status']=='FAIL']
    reference=None
    if model['brief'].get('reference_strategy','none')!='none':
        from .reference_patterns import measure as reference_measure
        reference=reference_measure(model)
        weight={'efficiency':.15,'usability':.25,'prestige':.20}[intent.design_priority]
        components['reference_patterns']=reference['design_penalty'];weights={**weights,'reference_patterns':weight}
        score=round(score+weight*reference['design_penalty'],6)
    intelligent=None
    if model.get('generation_mode')=='V3_ADAPTIVE':
        from .functional_intelligence import inspect
        intelligent=inspect(model)
        importance={'efficiency':.16,'usability':.32,'prestige':.20}[intent.design_priority]
        components['measured_functional_relations']=intelligent['soft_penalty']
        weights={**weights,'measured_functional_relations':importance}
        score=round(score+importance*intelligent['soft_penalty'],6)
    if model.get('functional_program_v4'):
        value=model['functional_program_v4']['movement']['soft_penalty']
        importance={'efficiency':.16,'usability':.32,'prestige':.20}[intent.design_priority]
        components['furniture_aware_paths']=value;weights={**weights,'furniture_aware_paths':importance}
        score=round(score+importance*value,6)
    return {'functional_intelligence':intelligent,'reference_patterns':reference,'metrics':metrics,'heuristic_score':score,'objective':intent.design_priority,'output_level':intent.output_level,
        'score_components':components,'weights':weights,'failed_checks':failed,
        'pending_checks':[c['check_id'] for c in model['checks'] if c['status']=='PENDING'],
        'acceptance_reason':'اجتاز الفحوص الهندسية المتاحة؛ الاشتراطات المعلقة لا تمثل اعتمادًا' if not failed else 'حجب الرسم بسبب فشل فحوص هندسية',
        'method':'actual net rooms, gross mass and weighted hosted-door graph routes; disclosed design heuristics'}

def select(models,limit=3,*,optimization='greedy'):
    valid=sorted((m for m in models if m['release']['drawing_export_allowed']
                  and m['design_evaluation']['metrics'].get('max_sleeping_aspect_ratio',1)
                      <= MAX_SLEEPING_ASPECT_RATIO),
                 key=lambda m:(m['design_evaluation']['heuristic_score'],m['candidate_id']))
    if optimization not in ('greedy','cp_sat'):
        raise ValueError('Unknown architecture portfolio selection strategy')
    if optimization=='cp_sat':
        from .engineering_selection import choose_distinct_subset
        incompatible=[]
        for i,j in combinations(range(len(valid)),2):
            if not difference(valid[i],valid[j])['distinct']:
                incompatible.append((i,j))
        indices,solver_info=choose_distinct_subset(len(valid),incompatible,limit=limit)
        chosen=[valid[index] for index in indices]
        for model in chosen:
            model['design_evaluation']['selection_solver']=dict(solver_info)
    else:
        chosen=[]
        for model in valid:
            if all(difference(model,old)['distinct'] for old in chosen):
                chosen.append(model)
            if len(chosen)==limit:break
    for i,model in enumerate(chosen):
        model['design_evaluation']['diversity_against_selected']=[
            difference(model,old) for old in chosen[:i]
        ]
    return chosen
