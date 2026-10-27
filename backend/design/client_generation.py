"""Browser-safe client orchestration; remote advice never substitutes engineering checks."""
import copy
import json
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from .architect_planner import ClientIntent, generate_automatic
from .ai_lab.schemas import SearchPlan

class ProviderEvidence(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    origin: Literal['LIVE_GEMINI']
    model: str = Field(max_length=100, pattern=r'^gemini-[A-Za-z0-9.-]+$')
    request_count: Literal[1]
    elapsed_ms: int = Field(ge=0)
    prompt_tokens: int | None = Field(default=None,ge=0)
    output_tokens: int | None = Field(default=None,ge=0)

class ClientGenerationRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    mode: Literal['legacy','intelligence','gemini'] = 'legacy'
    intent: ClientIntent
    advice: SearchPlan | None = None
    provider_evidence: ProviderEvidence | None = None

    @model_validator(mode='after')
    def advice_scope(self):
        if (self.mode == 'gemini') != (self.advice is not None):
            raise ValueError('Gemini requires validated structured advice; local modes reject remote advice')
        if self.mode != 'gemini' and self.provider_evidence is not None:
            raise ValueError('Local generation rejects Gemini evidence')
        return self


def generate_client(request, output_dir=None):
    req = ClientGenerationRequest.model_validate(request)
    out = Path(output_dir) if output_dir else Path(__file__).resolve().parents[2]/'outputs'
    if req.mode == 'legacy':
        return generate_automatic(req.intent,out,constitution_v2=True,generation_v3=True,generation_v4=True)
    # Importing the diagnostic/search path must not load a network client in Pyodide.
    from .intelligence.engine import run
    base = generate_automatic(req.intent,out,constitution_v2=True,generation_v3=True,generation_v4=True) if req.mode != 'gemini' else None
    if req.mode == 'gemini':
        from .architect_planner import propose
        from .general_engine import generate_general
        from .ai_lab.pipeline import validate_candidate
        from .auto_repair import ArchitectureAutoRepairEngine
        from .functional_program import validate
        brief,planning=propose(req.intent)
        brief=brief.model_copy(update={'compact_core':True,'proposed_room_area_factor':1.2})
        options=[o.model_dump() for o in req.advice.options]
        batch=generate_general(brief,out,search_options=options,candidate_families=tuple(dict.fromkeys(o['family'] for o in options)),emit_drawings=False,
            candidate_validator=lambda m:ArchitectureAutoRepairEngine(lambda q:validate(q,brief),max_attempts=8).repair(m),repair_layout=True)
        base=dict(candidates=[validate_candidate(m,brief,req.intent) for m in batch['candidates']],origin='GEMINI_JSON_ADVICE',requested_provider='GEMINI',fallback_used=False,unavailable=batch['unavailable'])
        # Only Gemini-advised options are searched, no silent deterministic fallback.
        result=run(req.intent,out,options=options,budget=len(options),baseline_result=base,emit_drawings=False)
        result['planning']=planning
    else:
        result=run(req.intent,out,budget=6,baseline_result=base,emit_drawings=False)
        from .architect_planner import propose
        _,result['planning']=propose(req.intent)
    result['planning']['method']='Gemini structured search advice + deterministic validated geometry' if req.mode=='gemini' else 'Reference-conditioned bounded topology search + deterministic validated geometry'
    result['planning']['client_generation']={'mode':req.mode,'origin':'GEMINI_JSON_ADVICE' if req.mode=='gemini' else 'LOCAL_REFERENCE_SEARCH',
        'fallback_used':False,'selected_count':len(result['candidates']), 'attempted_options':result['attempted_search_options'],
        'limitations':result['limitations']}
    result['provider_evidence']=req.provider_evidence.model_dump() if req.provider_evidence else None
    result['advice']=req.advice.model_dump() if req.advice else None
    result['unavailable']=copy.deepcopy(base.get('unavailable',[]))
    for record in result['failure_memory']:
        if record.get('stage')=='unavailable':
            result['unavailable'].append({'label':'تكوين إضافي غير متاح','reason':json.dumps(record['evidence'],ensure_ascii=False)})
        elif record.get('failed_checks'):
            result['unavailable'].append({'label':record.get('candidate_id','مرشح مرفوض'),'reason':'الفحوص غير المجتازة: '+', '.join(record['failed_checks'])})
    if not result['candidates'] and not result['unavailable']:
        result['unavailable'].append({'label':'لم يُقبل أي بديل','reason':'لم يستوفِ أي مرشح بوابات الهندسة والتنوع والفراغات؛ تفاصيل البحث محفوظة في failure_memory.'})
    # Attach final provenance before any client-visible JSON export.
    from .general_engine import export_general_model
    from .general_models import VillaBrief
    for model in result['candidates']:
        model['planning']=copy.deepcopy(result['planning'])
        model['client_generation']=copy.deepcopy(result['planning']['client_generation'])
        model['provider_evidence']=copy.deepcopy(result['provider_evidence'])
        model['provider_evidence_scope']='client-reported server response metadata; inspect gateway/API evidence for independent proof'
        model['structured_advice']=copy.deepcopy(result['advice'])
        export_general_model(model,VillaBrief.model_validate(model['brief']),out)
        (out/(model['model_revision_id']+'.json')).write_text(json.dumps(model,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    (out/'report.json').write_text(json.dumps(result,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    # The existing result renderer also needs the original program and warnings.
    return result
