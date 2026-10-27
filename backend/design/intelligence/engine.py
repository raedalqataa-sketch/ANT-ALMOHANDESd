"""Bounded topology/area-target search. Legacy production path stays untouched."""
import copy
import json
import os
import time
from itertools import combinations
from pathlib import Path
from .topology import program_graph, proposals
from .metrics import inspect

GAP_TOLERANCE_M2=1e-6  # numeric GEOS precision tolerance, not a building-code rule


def failure_record(model, option, source):
    failed=[c['check_id'] for c in model.get('checks',[]) if c['status']=='FAIL']
    links={'V4-program':['FAIL-005','FAIL-006'],'V4-functional-paths':['FAIL-007','FAIL-008'],
           'V4-furniture-clearance':['FAIL-019'],'guest-distributor-geometry':['FAIL-001','FAIL-007','FAIL-008'],
           'V4-geos-independent':['FAIL-016']}
    return dict(candidate_id=model.get('candidate_id'),geometry_sha256=model.get('geometry_sha256'),
        revision_id=model.get('model_revision_id'),source=source,option=copy.deepcopy(option),failed_checks=failed,
        known_failure_ids=sorted({known for check in failed for known in links.get(check,[])}),
        known_failure_source='constitution/source_bundles_004/05_FAILURE_MEMORY_SYSTEM_INSTRUCTION_AND_MASTER_SCHEMA.json#/sources/07_KNOWN_FAILURES_AND_FIXES.json',
        mapping_scope='potential failure categories; not a confirmed root cause',
        root_cause='UNCONFIRMED; inspect geometric check evidence' if failed else None,
        resolution_status='OPEN' if failed else None,verification_result='FAILED' if failed else 'PASSED',
        prevention_rule='preserve program/guest-family/door/stair invariants before new placement; revalidate geometry',
        unassigned_area_m2=model.get('architecture_intelligence',{}).get('unassigned_area_m2'),
        action='retain evidence; bounded alternative search; never relax validation',never_a_permanent_ban=True)


def _score(model):
    m=model['architecture_intelligence']
    # Disclosed comparison heuristics, not new room/legal limits. Shape and
    # routes counteract a misleading isolated reduction in vestibule area.
    shape=sum(max(0,r['aspect_ratio']-2)**2 for r in m['room_aspect_ratios'])
    reference=model.get('architecture_reference_penalty',0)
    return m.get('movement_with_measured_internal_paths_m2_total',m['circulation_union_m2_total'])+.02*m['gross_floor_area_m2']+10*shape+.1*(m['longest_required_travel_path_m'] or 0)+5*reference


def eligible(model):
    m=model['architecture_intelligence']
    from ..design_selection import MAX_SLEEPING_ASPECT_RATIO
    sleeping=model.get('design_evaluation',{}).get('metrics',{}).get('max_sleeping_aspect_ratio',1)
    return (sleeping<=MAX_SLEEPING_ASPECT_RATIO and model['release']['drawing_export_allowed'] and not any(c['status']=='FAIL' for c in model['checks'])
            and m['unassigned_area_m2']<=GAP_TOLERANCE_M2 and m['program_completeness']['status']=='PASS'
            and m['unreachable_required_routes']==[])


def rank_portfolio(models,limit=3):
    result=[];seen=set()
    for model in sorted((m for m in models if eligible(m)),key=lambda m:(_score(m),m['candidate_id'])):
        key=model['architecture_intelligence']['structural_signature']['hash']
        if key in seen:continue
        result.append(model);seen.add(key)
        if len(result)==limit:break
    return result


def run(intent,output_dir,*,use_references=True,options=None,budget=12,emit_drawings=True,baseline_result=None):
    """Materialize bounded alternatives with unchanged program/minima/checks.

    `baseline_result` contains existing validated choices (or AI-advised choices).
    None runs the unmodified deterministic lab first. No live inference here.
    """
    if type(budget) is not int or not 1<=budget<=18:raise ValueError('budget must be integer 1..18')
    from ..architect_planner import propose
    from ..ai_lab.schemas import LabRequest
    from ..ai_lab.pipeline import run as run_legacy, validate_candidate
    from ..general_engine import generate_general,export_general_model
    from ..functional_program import validate
    from ..auto_repair import ArchitectureAutoRepairEngine
    start=time.monotonic();out=Path(output_dir);out.mkdir(parents=True,exist_ok=True)
    brief,planning=propose(intent)
    base=copy.deepcopy(baseline_result) if baseline_result is not None else run_legacy(LabRequest(intent=intent),out/'baseline')
    pool=[];history=[]
    def register(model,source,option):
        model=copy.deepcopy(model)
        model['architecture_intelligence']=inspect(model)
        if use_references:
            from ..reference_patterns import measure
            model['architecture_reference_penalty']=measure(model)['design_penalty']
        else:model['architecture_reference_penalty']=0
        model['architecture_source']=dict(stage=source,option=option)
        pool.append(model)
        history.append({**failure_record(model,option,source),'eligible':eligible(model)})
    for model in base['candidates']:register(model,'baseline',model['search'])
    plans=options if options is not None else proposals(brief,use_references=use_references)
    for index,plan in enumerate(plans[:budget]):
        # Whitelist strict geometry options even when a caller supplies advice.
        from .topology import TopologyOption
        option=TopologyOption.model_validate({k:plan[k] for k in ('family','policy','core_position','guest_strategy')}).model_dump()
        factor=plan.get('proposed_area_factor',1.0)
        if type(factor) not in (int,float) or factor not in (1.0,1.1,1.2):raise ValueError('unsupported proposed area factor')
        configured=brief.model_copy(update={'compact_core':True,'proposed_room_area_factor':factor})
        batch=generate_general(configured,out/'search',candidate_families=(option['family'],),search_options=[option],emit_drawings=False,
            candidate_validator=lambda m:ArchitectureAutoRepairEngine(lambda q:validate(q,configured),max_attempts=8).repair(m),repair_layout=True)
        for model in batch['candidates']:
            model['candidate_id']='intelligence-'+str(index)+'-'+str(factor)+'-'+model['candidate_id']
            model=validate_candidate(model,configured,intent)
            register(model,'topology_search',{**option,'proposed_area_factor':factor,'reference_projects':plan.get('reference_projects',[])})
        if batch['unavailable']:history.append(dict(stage='unavailable',option=option,evidence=batch['unavailable'],never_a_permanent_ban=True))
    chosen=rank_portfolio(pool)
    for model in chosen:
        # A final fresh validation precedes each exported copy. No failed result
        # may be approved by a score or by LLM advice.
        from ..general_models import VillaBrief
        b=VillaBrief.model_validate(model['brief']);verified=validate_candidate(model,b,intent)
        if not verified['release']['drawing_export_allowed']:raise ValueError('final validation failed; no revised exports')
        model.update(checks=verified['checks'],functional_program_v4=verified['functional_program_v4'],constitution_v2=verified['constitution_v2'],release=verified['release'])
        model['planning']=planning
        model['design_option']=dict(title='تكوين وظيفي تجريبي',profile=intent.output_level,priority=intent.design_priority,
            validated=True,review_required=True,method='bounded topology/area search; existing authoritative validators',advantages=[],selection_reason='measured movement/room/routes trade-off, not legal approval')
    # Verify entire selected batch before beginning exports.
    if emit_drawings:
        for model in chosen:
            b=VillaBrief.model_validate(model['brief']);export_general_model(model,b,out)
            (out/(model['model_revision_id']+'.json')).write_text(json.dumps(model,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    result=dict(status='DRAFT_REVIEW' if chosen else 'BLOCKED',origin='LOCAL_DETERMINISTIC_OPTIMIZATION',advice_origin=base.get('origin','EXISTING_ENGINE'),
        requested_provider=base.get('requested_provider','EXISTING_ENGINE'),fallback_used=base.get('fallback_used',False),
        experimental=True,candidates=chosen,alternatives_missing=3-len(chosen),functional_graph=program_graph(brief),
        baseline_candidates=base['candidates'],baseline_telemetry=base.get('telemetry'),attempted_search_options=min(budget,len(plans)),
        failure_memory=history,telemetry=dict(elapsed_seconds=round(time.monotonic()-start,3),additional_api_requests=0),
        selection_basis=dict(legal_rule=False,weights=dict(corridor_plus_measured_internal_movement_union=1,gross_area=.02,aspect_over_two_squared=10,longest_required_path=.1,reference_penalty=5),
                             structural_diversity='functional adjacency/access graph with dissolved hall cells',gap_tolerance_m2=GAP_TOLERANCE_M2),
        reference_conditioning=dict(enabled=use_references,method='catalogue-derived pattern conditioning; no training/fine tuning',
                                    quantitative_reference_geometry='UNAVAILABLE; not fabricated'),
        limitations=['bounded existing geometric allocator; not unrestricted architecture',
                     'room internal movement measured only for recorded required paths',
                     'legal PENDING, full visual/acoustic privacy and service feasibility require review'])
    (out/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    return result


def run_lab(request,output_dir,*,provider_factory):
    """Reuse original JSON advice/repair loop; never invent AI-origin geometry."""
    from ..ai_lab.pipeline import run as run_legacy
    if request.provider!='EXISTING_ENGINE' and os.environ.get('INTELLIGENCE_LIVE_BUDGET_CONFIRMED')!='true':
        raise ValueError('live intelligence quota/billing budget not confirmed; use deterministic engine')
    from ..architect_planner import propose
    brief,_=propose(request.intent)
    graph=program_graph(brief)
    class ConditionedAdviser:
        def __init__(self,provider):self.provider=provider;self.metrics=provider.metrics
        def propose(self,context):
            return self.provider.propose({**context,'functional_topology':graph,
                'advisory_scope':'choose supported JSON topology options; do not override mandatory relations or program',
                'reference_conditioning':request.reference_conditioning})
        def close(self):self.provider.close()
    def conditioned_factory(name,model):return ConditionedAdviser(provider_factory(name,model))
    base=run_legacy(request.model_copy(update={'architectural_intelligence':False}),Path(output_dir)/'advice',provider_factory=conditioned_factory)
    if request.provider!='EXISTING_ENGINE' and base.get('origin')=='NO_API_RESULT' and not request.allow_engine_fallback:
        return {**base,'experimental':True,'local_optimization_skipped':'no validated provider advice; fallback not authorized'}
    result=run(request.intent,output_dir,budget=request.intelligence_search_budget,use_references=request.reference_conditioning,baseline_result=base)
    result['origin']=base['origin']+'_ADVISED_LOCAL_OPTIMIZATION'
    result['provider_evidence']={k:base[k] for k in ('origin','history','telemetry','fallback_used')}
    result['telemetry']['provider_requests']=base['telemetry']['request_count']
    (Path(output_dir)/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    return result
