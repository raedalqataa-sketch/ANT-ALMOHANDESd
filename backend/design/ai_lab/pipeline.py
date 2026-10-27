"""Provider-assisted constrained search with authoritative existing engineering gates."""
import copy
import json
import time
from itertools import combinations
from pathlib import Path

from .schemas import LabRequest
from ..architect_planner import propose
from ..auto_repair import ArchitectureAutoRepairEngine, fingerprint
from ..constitution_v2 import assess_candidate
from ..design_selection import evaluate, select, difference
from ..functional_program import validate
from ..general_engine import generate_general, export_general_model
from quality_review.space_efficiency import measure_candidate
from quality_review.unallocated_geometry import measure_model

# A disclosed fixed comparison budget, not a replacement for production auto-design.
BASELINE_OPTIONS = [
    dict(family='adaptive',policy='social_front',core_position='front',guest_strategy='compact_side'),
    dict(family='adaptive',policy='social_front',core_position='front',guest_strategy='side_spine'),
    dict(family='adaptive',policy='relationship_aware',core_position='rear',guest_strategy='linear'),
    dict(family='freeform',policy='relationship_aware',core_position='rear',guest_strategy='linear'),
    dict(family='spine',policy='service_aligned',core_position='front',guest_strategy='linear'),
    dict(family='cross',policy='family_front',core_position='front',guest_strategy='linear'),
]


def make_provider(name, model):
    from .providers import Provider, ProviderConfig
    return Provider(ProviderConfig.from_env(name, model))


def validate_candidate(candidate, brief, intent):
    """Fresh full checks plus independent *lab-only* gap exclusion; no legacy rule edits."""
    model = copy.deepcopy(candidate)
    model['checks'] = validate(model, brief)
    audit = assess_candidate(model, intent)
    model['constitution_v2'] = audit
    spaces = measure_candidate(model)
    gaps = measure_model(model)
    gap_area = sum(f['unallocated_gross_area_m2'] for f in gaps['floors'])
    failed = any(c['status'] == 'FAIL' for c in model['checks']) or bool(audit['hard_failures'])
    # Tolerance is floating point precision, not a newly asserted statutory limit.
    blocked = failed or gap_area > 1e-6
    model['release'].update(status='BLOCKED' if blocked else 'DRAFT_REVIEW',
                            drawing_export_allowed=not blocked, executive_issue_allowed=False)
    model['ai_lab'] = {'unallocated_m2':round(gap_area, 5),
                       'gross_circulation_union_m2':round(sum(f['gross_circulation_union_area_m2'] for f in spaces['floors']),5),
                       'space_efficiency':spaces, 'void_diagnostic':gaps,
                       'gap_scope':'existing local 0.5m morphological diagnostic; wider exterior recesses not certified',
                       'gap_gate':'experimental laboratory only; production acceptance unchanged',
                       'review_required':True}
    model['generation_mode'] = 'V3_ADAPTIVE'
    model['design_evaluation'] = evaluate(model, intent)
    model['geometry_sha256'] = fingerprint(model)
    return model


def _context(brief, planning):
    # Never transmit owner/contact data, arbitrary notes or the entire project JSON.
    return {'site':{'width_m':brief.plot_width, 'depth_m':brief.plot_depth,
                    'country':brief.country,'entrance_face':brief.entrance_face,
                    'setbacks':brief.setbacks.model_dump(),'floors':brief.floors},
            'program':[r.model_dump() for r in brief.rooms],
            'design_priority':planning['original_intent']['design_priority'],
            'output_level':planning['original_intent']['output_level'],
            'mandatory':['preserve program and minimums','guest entrance -> distributor -> majlis and WC separately',
                         'separate guest/family movement','preserve stair connections',
                         'natural light / furniture / doors checked by deterministic engine'],
            'limitations':['Yemen local rules PENDING','Saudi rules only documented repository subset',
                          'all alternatives drafts requiring architectural review']}


def _summary(model):
    return {'candidate_id':model['candidate_id'], 'revision_id':model['model_revision_id'],
            'accepted':model['release']['drawing_export_allowed'],
            'failed_checks':[c['check_id'] for c in model['checks'] if c['status']=='FAIL'],
            'constitution_failures':model['constitution_v2']['hard_failures'],
            'gross_circulation_union_m2':model['ai_lab']['gross_circulation_union_m2'],
            'unallocated_m2':model['ai_lab']['unallocated_m2'],
            'metrics':model['design_evaluation']['metrics'],
            'repair_attempts':len(model.get('auto_repair_v4',{}).get('attempts',[]))}


def run(request: LabRequest, output_dir, *, provider_factory=make_provider):
    from .providers import ProviderError
    if request.architectural_intelligence:
        from ..intelligence.engine import run_lab
        return run_lab(request,output_dir,provider_factory=provider_factory)
    start = time.monotonic()
    out = Path(output_dir);out.mkdir(parents=True,exist_ok=True)
    brief, planning = propose(request.intent)
    brief = brief.model_copy(update={'compact_core':True,'proposed_room_area_factor':1.2})
    context = _context(brief,planning)
    pool=[];history=[];providers=[];fallback=False;origin='EXISTING_ENGINE';tried=set()
    options=copy.deepcopy(BASELINE_OPTIONS)

    def explore(options):
        fresh=[]
        for option in options:
            key=tuple(sorted(option.items()))
            if key not in tried:
                fresh.append(option);tried.add(key)
        if not fresh:
            history.append({'stage':'search','status':'NO_NEW_OPTIONS'})
            return
        batch=generate_general(brief,out,candidate_families=tuple(dict.fromkeys(o['family'] for o in fresh)),
              search_options=fresh,emit_drawings=False,
              candidate_validator=lambda m:ArchitectureAutoRepairEngine(lambda q:validate(q,brief),max_attempts=8).repair(m),
              repair_layout=True)
        for model in batch['candidates']:
            model['candidate_id']='-'.join(str(model['search'].get(k,'')) for k in ('family','allocation_policy','core_position','guest_strategy'))
            model=validate_candidate(model,brief,request.intent)
            pool.append(model)
        history.append({'stage':'geometry','options':fresh,'unavailable':batch['unavailable'],
                        'results':[_summary(m) for m in pool]})

    try:
        if request.provider != 'EXISTING_ENGINE':
            origin='NO_API_RESULT'
            name=request.primary_provider if request.provider=='HYBRID' else request.provider
            primary=provider_factory(name,request.model);providers.append(primary)
            try:
                proposed=primary.propose(context)
                options=[o.model_dump() for o in proposed.options]
                origin=primary.metrics.get('result_origin','LIVE_API')
                history.append({'stage':'proposal','provider':name,'options':options,'origin':origin})

            except ProviderError as exc:
                history.append({'stage':'proposal','error':str(exc),'provider':name})
                if request.allow_engine_fallback:
                    fallback=True;origin='EXISTING_ENGINE_FALLBACK'
                else:
                    options=[]
        if options:
            explore(options)
        chosen=select(pool,optimization='cp_sat')
        if request.provider=='HYBRID' and request.critic_provider and options and not fallback:
            critic=provider_factory(request.critic_provider,request.critic_model);providers.append(critic)
            try:
                reviewed=critic.propose({**context,'critique_search_plan':{'options':options},
                    'candidate_metrics':[_summary(m) for m in pool],
                    'selected_count':len(chosen)})
                critique_options=[o.model_dump() for o in reviewed.options]
                history.append({'stage':'critique','provider':request.critic_provider,'options':critique_options,
                    'basis':'actual materialized and validated candidate metrics',
                    'origin':critic.metrics.get('result_origin','LIVE_API')})
                explore(critique_options);chosen=select(pool,optimization='cp_sat')
            except ProviderError as exc:
                history.append({'stage':'critique','error':str(exc),'action':'primary validated candidates retained'})
        if request.provider!='EXISTING_ENGINE' and not fallback and options:
            for iteration in range(request.max_corrections):
                if len(chosen)==3:
                    break
                try:
                    proposal=providers[0].propose({**context,'correction_round':iteration+1,
                       'feedback':[_summary(m) for m in pool],
                       'selected_count':len(chosen),'previous_options':[dict(k) for k in sorted(tried)]})
                    options=[o.model_dump() for o in proposal.options]
                    history.append({'stage':'correction','round':iteration+1,'options':options})
                    explore(options);chosen=select(pool,optimization='cp_sat')
                except ProviderError as exc:
                    history.append({'stage':'correction','round':iteration+1,'error':str(exc)})
                    break
            if len(chosen)<3 and request.allow_engine_fallback:
                fallback=True;origin=origin+'+EXISTING_ENGINE_FALLBACK'
                explore(copy.deepcopy(BASELINE_OPTIONS));chosen=select(pool,optimization='cp_sat')
        # Only selected, freshly validated models are exported; no artifacts for rejected geometry.
        for model in chosen:
            model['planning']=planning
            model['design_option']={'validated':True,'method':'provider-assisted constrained engine search',
                'title':'مختبر المقترحات المعمارية','profile':request.intent.output_level,
                'priority':request.intent.design_priority,'advantages':[],
                'selection_reason':'الفحوص الحالية والتنوع المقاس؛ مسودة للمراجعة','review_required':True}
            export_general_model(model,brief,out)
            model['downloads']['json']=f'/api/files/{model["model_revision_id"]}.json'
            (out/(model['model_revision_id']+'.json')).write_text(json.dumps(model,ensure_ascii=False,allow_nan=False),encoding='utf-8')
        telemetry={'request_count':sum(p.metrics.get('request_count',0) for p in providers),
                   'elapsed_seconds':round(time.monotonic()-start,3),
                   'estimated_cost_usd':sum(p.metrics.get('estimated_cost_usd') or 0 for p in providers) if providers else 0,
                   'providers':[copy.deepcopy(p.metrics) for p in providers],
                   'quota':'provider-specific; UNKNOWN when not reported',
                   'cost_warning':'free-only safeguards; not an independent billing audit'}
        result={'status':'DRAFT_REVIEW' if chosen else 'BLOCKED','origin':origin,
                'requested_provider':request.provider,'fallback_used':fallback,'candidates':chosen,
                'alternatives_missing':3-len(chosen),'attempted_search_options':len(tried),
                'history':history,'telemetry':telemetry,
                'comparison':[_summary(m) for m in chosen],
                'pairwise_diversity':[difference(a,b) for a,b in combinations(chosen,2)],
                'limitations':['bounded existing geometric library; not free-form neural geometry',
                   'service feasibility and full visual privacy require professional review',
                   'PENDING legal requirements are not compliance approval',
                   'fewer than three validated distinct alternatives are reported honestly']}
        (out/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
        return result
    finally:
        for provider in providers:
            provider.close()
