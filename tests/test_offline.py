import json
from backend.design.offline import run_local


def test_direct_engine_writes_local_exports_without_network(tmp_path,monkeypatch):
    import socket
    def deny_network(*args,**kwargs):raise AssertionError('Offline engine attempted network access')
    monkeypatch.setattr(socket,'create_connection',deny_network)
    result=run_local({'layout_family':'social_hub'},tmp_path)
    assert result['scope']=='ENGINE_FEASIBILITY_ONLY'
    assert not result['http_server_used_for_computation']
    candidate=result['candidates'][0]
    assert candidate['failed']==0 and candidate['dxf_audit']['dxf_version']=='AC1024'
    assert len(candidate['files'])==5
    assert (tmp_path/'social_hub.pdf').read_bytes().startswith(b'%PDF-')
    assert '<svg' in (tmp_path/'social_hub-GF.svg').read_text()
    assert all((tmp_path/name).is_file() for name in candidate['files'])


def test_offline_entry_does_not_bypass_failed_checks(tmp_path):
    result=run_local({'layout_family':'social_hub','bedroom_count':2},tmp_path)
    candidate=result['candidates'][0]
    assert candidate['failed']>0
    assert candidate['files']==['social_hub.json']
    model=json.loads((tmp_path/'social_hub.json').read_text())
    assert not model['release']['drawing_export_allowed']
    assert len(list(tmp_path.iterdir()))==1
