import json
import httpx
import pytest
from pydantic import ValidationError
from backend.design.ai_lab.schemas import SearchPlan
from backend.design.ai_lab.providers import Provider, ProviderConfig, ProviderError


def plan():
    return {'options':[
        {'family':'adaptive','policy':'social_front','core_position':'front','guest_strategy':'compact_side'},
        {'family':'adaptive','policy':'relationship_aware','core_position':'rear','guest_strategy':'linear'},
        {'family':'spine','policy':'service_aligned','core_position':'front','guest_strategy':'side_spine'}]}


def test_schema_rejects_code_geometry_unknown_and_duplicate_options():
    assert len(SearchPlan.model_validate(plan()).options)==3
    for extra in [{'code':'pass'},{'setbacks':{}},{'rooms':[]}]:
        with pytest.raises(ValidationError):SearchPlan.model_validate({**plan(),**extra})
    with pytest.raises(ValidationError):SearchPlan.model_validate({'options':[plan()['options'][0]]*3})


def provider(name='GEMINI',handler=None,**config):
    return Provider(ProviderConfig(provider=name,model='test-model',api_key='secret-test',gemini_free_tier_confirmed=True,**config),
                    client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_missing_key_no_network_and_config_repr_redacted(monkeypatch):
    monkeypatch.delenv('GEMINI_API_KEY',raising=False)
    p=Provider(ProviderConfig.from_env('GEMINI','test'))
    with pytest.raises(ProviderError,match='MISSING_CREDENTIAL'):p.propose({})
    assert 'secret-test' not in repr(ProviderConfig(provider='GEMINI',model='test',api_key='secret-test'))


def test_gemini_structured_json_and_metrics():
    def handler(req):
        assert req.headers['x-goog-api-key']=='secret-test'
        assert 'secret-test' not in str(req.url)
        assert json.loads(req.content)['generationConfig']['responseMimeType']=='application/json'
        return httpx.Response(200,json={'candidates':[{'content':{'parts':[{'text':json.dumps(plan())}]}}],
                                       'usageMetadata':{'promptTokenCount':11,'candidatesTokenCount':9}})
    p=provider(handler=handler)
    assert p.propose({'program':[]}).model_dump()==plan()
    assert p.metrics['request_count']==1
    assert p.metrics['input_tokens']==11


@pytest.mark.parametrize('status,code,attempts',[(401,'AUTHENTICATION',1),(429,'QUOTA_EXHAUSTED',1),(503,'UPSTREAM_UNAVAILABLE',2)])
def test_safe_error_no_secret_echo_and_bounded_retries(status,code,attempts):
    p=provider(handler=lambda req:httpx.Response(status,text='secret-test'))
    with pytest.raises(ProviderError,match=code) as caught:p.propose({})
    assert 'secret-test' not in str(caught.value)
    assert p.metrics['request_count']==attempts


def test_timeout_bounded_and_malformed_output():
    def timeout(req):raise httpx.ReadTimeout('secret-test',request=req)
    p=provider(handler=timeout)
    with pytest.raises(ProviderError,match='TIMEOUT'):p.propose({})
    assert p.metrics['request_count']==2
    p=provider(handler=lambda r:httpx.Response(200,json={'candidates':[]}))
    with pytest.raises(ProviderError,match='INVALID_OUTPUT'):p.propose({})


def test_free_tier_guard_prevents_paid_or_unverified_requests():
    p=Provider(ProviderConfig(provider='GEMINI',model='test',api_key='x'))
    with pytest.raises(ProviderError,match='FREE_TIER_UNCONFIRMED'):p.propose({})
    def paid(req):return httpx.Response(200,json={'data':[{'id':'test-model','pricing':{'prompt':'0.1','completion':'0.1'}}]})
    p=provider('OPENROUTER',handler=paid)
    with pytest.raises(ProviderError,match='PAID_MODEL_BLOCKED'):p.propose({})
    assert p.metrics['request_count']==1


def test_openrouter_price_checked_before_structured_request():
    def handler(req):
        if req.url.path.endswith('/models'):
            return httpx.Response(200,json={'data':[{'id':'test-model','pricing':{'prompt':'0','completion':'0'}}]})
        body=json.loads(req.content)
        assert body['provider']['max_price']=={'prompt':0,'completion':0}
        assert body['provider']['allow_fallbacks'] is False
        assert body['response_format']['type']=='json_schema'
        return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps(plan())}}],
                                       'usage':{'prompt_tokens':8,'completion_tokens':7,'cost':0}})
    p=provider('OPENROUTER',handler=handler)
    assert len(p.propose({}).options)==3
    assert p.metrics['request_count']==2
    assert p.metrics['estimated_cost_usd']==0


@pytest.mark.parametrize('pricing',[{'prompt':None,'completion':None},{'prompt':'0'}, {'prompt':'NaN','completion':'0'}])
def test_unknown_or_nonfinite_catalog_price_is_not_free(pricing):
    p=provider('OPENROUTER',handler=lambda req:httpx.Response(200,json={'data':[{'id':'test-model','pricing':pricing}]}))
    with pytest.raises(ProviderError):p.propose({})


def test_402_reports_credit_limit_without_retry():
    p=provider(handler=lambda req:httpx.Response(402,text='secret-test'))
    with pytest.raises(ProviderError,match='CREDIT_LIMIT'):p.propose({})
    assert p.metrics['request_count']==1


def test_oversize_response_rejected_and_model_url_cannot_inject():
    with pytest.raises(ValueError):ProviderConfig('GEMINI','../../secrets',api_key='secret')
    p=provider(handler=lambda req:httpx.Response(200,content=b'x'*2_000_001))
    with pytest.raises(ProviderError,match='RESPONSE_TOO_LARGE'):p.propose({})


@pytest.mark.parametrize('name,usage_key',[('GEMINI','usageMetadata'),('OPENROUTER','usage')])
@pytest.mark.parametrize('usage',[[],None,{'prompt_tokens':'secret-test'},{'promptTokenCount':float('inf')}])
def test_malformed_usage_is_safe_provider_error(name,usage_key,usage):
    def handler(req):
        if req.url.path.endswith('/models'):
            return httpx.Response(200,json={'data':[{'id':'test-model','pricing':{'prompt':'0','completion':'0'}}]})
        body={'candidates':[{'content':{'parts':[{'text':json.dumps(plan())}]}}]} if name=='GEMINI' else {'choices':[{'message':{'content':json.dumps(plan())}}]}
        body[usage_key]=usage
        # Encode deliberately malformed metadata, including non-finite JSON.
        return httpx.Response(200,content=json.dumps(body).encode())
    # Mixed provider-specific field names are also rejected rather than ignored.
    p=provider(name,handler=handler)
    with pytest.raises(ProviderError,match='INVALID_OUTPUT'):p.propose({})
