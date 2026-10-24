import hashlib
import json

import pytest

from lovable_integration.browser_dependencies import prepare_browser_dependencies


def test_client_adds_verified_wasm_and_pure_wheels_without_changing_studio_manifest(tmp_path):
    runtime=tmp_path/'runtime';wheels=tmp_path/'wheels'
    runtime.mkdir();wheels.mkdir()
    original={'pyodide_version':'0.29.3','pure_wheels':['old.whl'],'runtime_network_required':False}
    source=tmp_path/'manifest.json';source.write_text(json.dumps(original))
    payloads={'shapely-demo.whl':b'wasm-wheel','networkx-demo.whl':b'graph-wheel'}
    lock={'packages':{name:{'file_name':filename,'sha256':hashlib.sha256(payloads[filename]).hexdigest()}
                      for name,filename in [('shapely','shapely-demo.whl'),('networkx','networkx-demo.whl')]}}
    (runtime/'pyodide-lock.json').write_text(json.dumps(lock))
    output=tmp_path/'client-manifest.json'

    manifest=prepare_browser_dependencies(runtime,wheels,source,output,
                                          fetch=lambda url: payloads[url.rsplit('/',1)[-1]])

    assert manifest['engineering_wasm_packages']==['shapely']
    assert manifest['pure_wheels']==['old.whl','networkx-demo.whl']
    assert (runtime/'shapely-demo.whl').read_bytes()==b'wasm-wheel'
    assert (wheels/'networkx-demo.whl').read_bytes()==b'graph-wheel'
    assert json.loads(source.read_text())==original
    assert json.loads(output.read_text())==manifest


def test_client_rejects_wheel_that_differs_from_pyodide_lock(tmp_path):
    runtime=tmp_path/'runtime';wheels=tmp_path/'wheels'
    runtime.mkdir();wheels.mkdir()
    source=tmp_path/'manifest.json';source.write_text('{"pyodide_version":"0.29.3","pure_wheels":[]}')
    (runtime/'pyodide-lock.json').write_text(json.dumps({'packages':{
        'shapely':{'file_name':'shapely.whl','sha256':'0'*64},
        'networkx':{'file_name':'networkx.whl','sha256':'1'*64},
    }}))
    with pytest.raises(ValueError,match='SHA-256'):
        prepare_browser_dependencies(runtime,wheels,source,tmp_path/'client.json',fetch=lambda _:b'wrong')
