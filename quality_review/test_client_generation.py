from backend.design.client_generation import ClientGenerationRequest
import pytest

def test_rejects_advice_for_local_mode():
    with pytest.raises(ValueError):
        ClientGenerationRequest.model_validate(dict(mode='intelligence', intent={}, advice={'options':[]}))

def test_provider_mode_requires_real_advice():
    with pytest.raises(ValueError):
        ClientGenerationRequest.model_validate(dict(mode='gemini', intent={}))

def test_browser_entry_has_no_http_transport_import():
    import subprocess,sys
    code="import sys; from backend.design.client_generation import ClientGenerationRequest; assert 'httpx' not in sys.modules; assert 'backend.design.ai_lab.providers' not in sys.modules"
    assert subprocess.run([sys.executable,'-c',code]).returncode == 0

def _intent():
    import json
    from pathlib import Path
    return json.loads((Path(__file__).parent/'gemini_sa600_case.json').read_text())['intent']

def test_advice_mode_validation_uses_valid_intent():
    intent=_intent()
    with pytest.raises(ValueError,match='Gemini requires'):
        ClientGenerationRequest.model_validate(dict(mode='gemini',intent=intent))
    from backend.design.ai_lab.pipeline import BASELINE_OPTIONS
    with pytest.raises(ValueError,match='Gemini requires'):
        ClientGenerationRequest.model_validate(dict(mode='intelligence',intent=intent,advice={'options':BASELINE_OPTIONS[:3]}))
    assert ClientGenerationRequest.model_validate(dict(mode='gemini',intent=intent,advice={'options':BASELINE_OPTIONS[:3]})).mode=='gemini'

def test_new_client_path_preserves_gates_and_has_real_exports(tmp_path):
    from backend.design.client_generation import generate_client
    r=generate_client(dict(mode='intelligence',intent=_intent()),tmp_path)
    assert r['planning']['client_generation']['mode']=='intelligence'
    assert len(r['candidates'])==3
    signatures=set()
    for m in r['candidates']:
        assert m['release']['drawing_export_allowed']
        assert not any(c['status']=='FAIL' for c in m['checks'])
        assert m['architecture_intelligence']['unassigned_area_m2']<=1e-6
        signatures.add(m['architecture_intelligence']['structural_signature']['hash'])
        for path in m['downloads'].values(): assert (tmp_path/path.split('/')[-1]).is_file()
        import json
        saved=json.loads((tmp_path/(m['model_revision_id']+'.json')).read_text())
        assert saved['client_generation']['mode']=='intelligence'
        assert saved['planning']['client_generation']==r['planning']['client_generation']
    assert len(signatures)==3
