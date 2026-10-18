"""Optional offline browser check; requires Playwright and a built local bundle."""
import json,argparse
from pathlib import Path
from playwright.sync_api import sync_playwright
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,default=Path('mobile_probe/build/browser-check'))
args=parser.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=True)
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
    context=browser.new_context(viewport={'width':1280,'height':900},accept_downloads=True)
    page=context.new_page();logs=[];remote=[];requests=[]
    page.on('console',lambda message:logs.append(message.type+': '+message.text))
    page.on('pageerror',lambda e:logs.append('PAGEERROR '+str(e)))
    def route(r):
        url=r.request.url
        if url.startswith('http://127.0.0.1:8010/') or url.startswith(('blob:','data:')):r.continue_()
        else:remote.append(url);r.abort()
    context.route('**/*',route)
    page.on('request',lambda r:requests.append(r.url))
    page.goto('http://127.0.0.1:8010/')
    page.locator('#initialize').click()
    page.wait_for_function('window.probe.ready || window.probe.error',timeout=180000)
    initial=page.evaluate('window.probe')
    (out/'browser-startup.json').write_text(json.dumps({'probe':initial,'logs':logs,'remote_requests':remote},ensure_ascii=False,indent=2))
    assert initial['ready'],initial
    # Disallow even localhost requests after initialization. Generation must be local.
    context.set_offline(True)
    tick_start=page.evaluate('window.probe.ui_ticks');request_start=len(requests)
    page.locator('#run').click()
    page.wait_for_function('window.probe.result || window.probe.error',timeout=240000)
    result=page.evaluate('window.probe');print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
    (out/'browser-result.json').write_text(json.dumps({'probe':result,'logs':logs,'remote_requests':remote,'requests_during_generation':requests[request_start:],'user_agent':page.evaluate('navigator.userAgent')},ensure_ascii=False,indent=2))
    assert not result['error'],result
    assert result['ui_ticks']>tick_start+2
    assert len(result['result']['candidates'])==3
    assert all(c['failed']==0 and c['dxf_audit']['dxf_version']=='AC1024' for c in result['result']['candidates'])
    assert not remote
    assert not requests[request_start:],requests[request_start:]
    page.wait_for_function("document.querySelector('#preview').complete && document.querySelector('#preview').naturalWidth>0",timeout=15000)
    for ext in ('pdf','dxf','json'):
        filename='social_hub.'+ext
        with page.expect_download() as download:page.get_by_role('button',name=filename,exact=True).click()
        download.value.save_as(out/('wasm-social_hub.'+ext))
    # Test only JS-to-native encoding; this does not exercise Android's file picker.
    page.evaluate("window.AndroidFiles={save:(name,data)=>window.bridgeProbe={name,prefix:data.slice(0,8),length:data.length}}")
    page.get_by_role('button',name='social_hub.pdf',exact=True).click()
    page.wait_for_function('window.bridgeProbe')
    bridge=page.evaluate('window.bridgeProbe')
    assert bridge['prefix']=='JVBERi0x' and bridge['length']>1000,bridge
    (out/'bridge-encoding.json').write_text(json.dumps(dict(result='PASS',scope='JS_BASE64_ENCODING_ONLY_NOT_ANDROID_FILE_PICKER',details=bridge),indent=2)+'\n')
    page.screenshot(path=str(out/'offline-engine.png'),full_page=True)
    context.close();browser.close()
print('Offline WASM generation, validation, exports, UI responsiveness and downloads PASS',flush=True)
