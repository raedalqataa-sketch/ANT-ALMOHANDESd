import os
from pathlib import Path
import pytest
from backend.design.ai_lab.credentials import discover, save_secret, PKCEFlow


def test_discovery_returns_presence_only(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY','do-not-print')
    info=discover()
    assert info['GEMINI_API_KEY'] is True
    assert 'do-not-print' not in str(info)


def test_secret_storage_refuses_repo_and_symlinks(tmp_path):
    repo=tmp_path/'repo';repo.mkdir()
    with pytest.raises(ValueError):save_secret(repo/'key.env','GEMINI_API_KEY','secret',repo)
    target=tmp_path/'target';target.write_text('unchanged')
    link=tmp_path/'link';link.symlink_to(target)
    with pytest.raises(ValueError):save_secret(link,'GEMINI_API_KEY','secret',repo)
    assert target.read_text()=='unchanged'
    dest=tmp_path/'private'/'providers.env'
    save_secret(dest,'GEMINI_API_KEY','secret',repo)
    assert dest.stat().st_mode & 0o777 == 0o600
    assert dest.parent.stat().st_mode & 0o777 == 0o700
    with pytest.raises(ValueError):save_secret(dest,'OPENROUTER_API_KEY','x\nINJECTED=bad',repo)


def test_pkce_has_fresh_state_and_rejects_wrong_callback():
    a=PKCEFlow('http://127.0.0.1:8766/callback');b=PKCEFlow('http://127.0.0.1:8766/callback')
    assert a.state!=b.state and a.verifier!=b.verifier
    assert 'code_challenge_method=S256' in a.url
    with pytest.raises(ValueError):a.exchange('code','wrong')
    with pytest.raises(ValueError):PKCEFlow('https://attacker.example/callback')


def test_official_google_provisioning_is_authenticated_and_api_restricted(monkeypatch):
    import json
    import httpx
    from types import SimpleNamespace
    from backend.design.ai_lab.credentials import provision_gemini
    monkeypatch.delenv('GEMINI_API_KEY',raising=False)
    monkeypatch.setattr('backend.design.ai_lab.credentials.shutil.which',lambda x:'/official/gcloud')
    monkeypatch.setattr('backend.design.ai_lab.credentials.subprocess.run',lambda *a,**k:SimpleNamespace(returncode=0,stdout='mock-google-oauth'))
    resource='projects/123456/locations/global/keys/key-1';seen=[]
    def handler(req):
        assert req.headers['Authorization']=='Bearer mock-google-oauth'
        seen.append(req)
        if req.method=='POST':
            assert json.loads(req.content)['restrictions']=={'apiTargets':[{'service':'generativelanguage.googleapis.com'}]}
            return httpx.Response(200,json={'done':True,'response':{'name':resource}})
        if req.url.path.endswith('/keyString'):return httpx.Response(200,json={'keyString':'mock-result'})
        return httpx.Response(200,json={'keys':[]})
    key=provision_gemini('123456',client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert key=='mock-result' and len(seen)==3


def test_openrouter_provisioning_has_zero_spend_and_expiry(monkeypatch):
    import json
    import httpx
    from backend.design.ai_lab.credentials import provision_openrouter
    monkeypatch.delenv('OPENROUTER_API_KEY',raising=False)
    monkeypatch.setenv('OPENROUTER_MANAGEMENT_KEY','mock-management')
    def handler(req):
        if req.method=='GET':return httpx.Response(200,json={'data':[]})
        body=json.loads(req.content)
        assert body['limit']==0 and body['include_byok_in_limit'] is True and body['expires_at'].endswith('Z')
        return httpx.Response(200,json={'key':'mock-new-child-key'})
    assert provision_openrouter(client=httpx.Client(transport=httpx.MockTransport(handler)))=='mock-new-child-key'


def test_pkce_exchange_is_single_use_and_never_sends_password():
    import httpx,json
    flow=PKCEFlow('http://127.0.0.1:8766/callback')
    def handler(req):
        body=json.loads(req.content)
        assert body['code_verifier']==flow.verifier and body['code_challenge_method']=='S256'
        assert 'password' not in body
        return httpx.Response(200,json={'key':'mock-oauth-key'})
    assert flow.exchange('mock-code',flow.state,client=httpx.Client(transport=httpx.MockTransport(handler)))=='mock-oauth-key'
    with pytest.raises(ValueError):flow.exchange('mock-code',flow.state)


def test_secret_file_cannot_inject_shell_commands(tmp_path):
    repo=tmp_path/'repo';repo.mkdir()
    with pytest.raises(ValueError):save_secret(tmp_path/'private'/'providers.env','GEMINI_API_KEY','$(echo unsafe)',repo)


def test_provisioning_preflights_storage_before_remote_key_creation(monkeypatch,tmp_path):
    from backend.design.ai_lab import credentials
    minted=[]
    monkeypatch.setattr('sys.argv',['credentials','openrouter','--destination',str(Path(credentials.__file__).resolve().parents[3]/'unsafe-secret.env')])
    monkeypatch.setattr(credentials,'provision_openrouter',lambda:minted.append(True) or 'mock-child-key')
    with pytest.raises(SystemExit):credentials.main()
    assert minted==[]


def test_google_reuses_key_from_later_page(monkeypatch):
    import httpx
    from types import SimpleNamespace
    from backend.design.ai_lab.credentials import provision_gemini
    monkeypatch.delenv('GEMINI_API_KEY',raising=False)
    monkeypatch.setattr('backend.design.ai_lab.credentials.shutil.which',lambda x:'/official/gcloud')
    monkeypatch.setattr('backend.design.ai_lab.credentials.subprocess.run',lambda *a,**k:SimpleNamespace(returncode=0,stdout='mock-token'))
    calls=[]
    def handler(req):
        calls.append(req)
        assert req.method=='GET','must reuse, not create duplicate'
        if req.url.path.endswith('/keyString'):return httpx.Response(200,json={'keyString':'mock-existing'})
        if req.url.params.get('pageToken')=='next':
            return httpx.Response(200,json={'keys':[{'displayName':'ANT-AI-AUTO-KEYS-002',
                'name':'projects/123456/locations/global/keys/existing','restrictions':{'apiTargets':[{'service':'generativelanguage.googleapis.com'}]}}]})
        return httpx.Response(200,json={'keys':[],'nextPageToken':'next'})
    assert provision_gemini('123456',client=httpx.Client(transport=httpx.MockTransport(handler)))=='mock-existing'
    assert len(calls)==3
