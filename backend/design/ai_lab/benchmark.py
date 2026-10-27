"""Controlled identical-input experiments. Mocked advice is always labeled MOCK_NOT_LIVE."""
import argparse
import json
from pathlib import Path

import httpx
from .providers import Provider, ProviderConfig
from .schemas import LabRequest
from .pipeline import run
from ..architect_planner import ClientIntent

MOCK_PLAN={'options':[
    dict(family='adaptive',policy='social_front',core_position='front',guest_strategy='compact_side'),
    dict(family='adaptive',policy='relationship_aware',core_position='rear',guest_strategy='linear'),
    dict(family='spine',policy='service_aligned',core_position='front',guest_strategy='side_spine'),
    dict(family='freeform',policy='relationship_aware',core_position='rear',guest_strategy='linear'),
    dict(family='cross',policy='family_front',core_position='front',guest_strategy='linear'),
    dict(family='adaptive',policy='social_front',core_position='front',guest_strategy='side_spine'),
]}


def mock_provider(name,model):
    """Exercise actual adapters via a local transport; absolutely no network or real key."""
    def reply(request):
        if request.url.path.endswith('/models'):
            return httpx.Response(200,json={'data':[{'id':model,'pricing':{'prompt':'0','completion':'0'}}]})
        if name=='GEMINI':
            return httpx.Response(200,json={'candidates':[{'content':{'parts':[{'text':json.dumps(MOCK_PLAN)}]}}],
                'usageMetadata':{'promptTokenCount':0,'candidatesTokenCount':0}})
        return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps(MOCK_PLAN)}}],
                                      'usage':{'prompt_tokens':0,'completion_tokens':0,'cost':0}})
    provider=Provider(ProviderConfig(name,model,api_key='mock-not-a-credential',gemini_free_tier_confirmed=True),
                      client=httpx.Client(transport=httpx.MockTransport(reply)))
    provider.metrics['result_origin']='MOCK_NOT_LIVE'
    return provider


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--mock',action='store_true',help='explicitly simulated advice, no provider network calls')
    parser.add_argument('--case',choices=['ye-medium','sa-large','sa-small','sa-corner','all'],default='all')
    parser.add_argument('--gemini-model',default='')
    parser.add_argument('--openrouter-model',default='')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    reference=json.loads((Path(__file__).resolve().parents[3]/'quality_review/space_efficiency_baseline.json').read_text())
    cases={r['case']:r['input'] for r in reference['cases']}
    names=list(cases) if args.case=='all' else [args.case]
    rows=[]
    for name in names:
        intent=ClientIntent.model_validate(cases[name])
        for provider in ('EXISTING_ENGINE','GEMINI','OPENROUTER','HYBRID'):
            model=('mock-fixture' if args.mock else (args.openrouter_model if provider=='OPENROUTER' else args.gemini_model))
            if provider!='EXISTING_ENGINE' and not args.mock and (not model or (provider=='HYBRID' and not args.openrouter_model)):
                rows.append({'case':name,'provider':provider,'status':'BLOCKED','origin':'NO_API_RESULT','reason':'credential/model not configured'})
                continue
            request=LabRequest(intent=intent,provider=provider,model=model,
                allow_remote_program=not args.mock or provider!='EXISTING_ENGINE',
                critic_provider='OPENROUTER' if provider=='HYBRID' else None,
                critic_model=('mock-fixture' if args.mock else args.openrouter_model) if provider=='HYBRID' else '',
                max_corrections=0)
            kwargs={'provider_factory':mock_provider} if args.mock else {}
            result=run(request,args.output/name/provider,**kwargs)
            row={'case':name,'provider':provider,'status':result['status'],'origin':result['origin'],
                 'alternatives':len(result['candidates']),'search_options':result['attempted_search_options'],
                 'telemetry':result['telemetry'],'comparison':result['comparison'],
                 'pairwise_diversity':result['pairwise_diversity']}
            rows.append(row)
            print(json.dumps({k:row[k] for k in ('case','provider','status','origin','alternatives')},ensure_ascii=False),flush=True)
            (args.output/'benchmark.json').write_text(json.dumps({'rows':rows,'mock':args.mock,
                'method':'identical inputs, V4 checks and export, bounded search up to six initial options each; no correction rounds in this comparison',
                'warning':'mock results test the integration; do not measure Gemini/OpenRouter intelligence or quality gains'},ensure_ascii=False,indent=2))
    (args.output/'benchmark.json').write_text(json.dumps({'rows':rows,'mock':args.mock,
        'method':'identical inputs and engineering gates; baseline is fixed-budget lab engine, not full production search',
        'warning':'mock advice does not establish API connectivity or intelligence/quality improvement'},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
