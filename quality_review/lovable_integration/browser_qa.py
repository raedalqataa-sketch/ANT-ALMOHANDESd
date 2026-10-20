from pathlib import Path
import json
from playwright.sync_api import sync_playwright
out=Path('/workspace/lovable-bridge-qa');out.mkdir(exist_ok=True)
draft={'data':{'title':'فيلا اختبار الربط','type':'سكني','housing':'فيلا','width':'24','depth':'32','floors':'2','location':'الرياض','frontage':'جنوب'},'unknown':{},'counts':{'bedroom':2,'bathroom':1,'kitchen':1,'dining':1,'living':1},'hospitality':{'majlis':True,'menEntrance':True,'guestLobby':True,'familyEntrance':True},'rooms':[{'name':'نوم رئيسية','room_type':'bedroom','quantity':1,'privacy':'private','width_m':4,'length_m':5}], 'step':4,'imported':{'fields':[{'sheet':'متطلبات','row':2,'number':'1','field':'طلب خاص','value':'مراجعة المسبح','guidance':'لم يحول تلقائيا'}],'warnings':[]}}
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
 ctx=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True)
 page=ctx.new_page();errors=[];requests=[]
 page.on('pageerror',lambda error:errors.append(str(error)))
 page.on('request',lambda request:requests.append(request.url))
 page.goto('http://127.0.0.1:8031/harness.html')
 frame=page.frames[1];frame.wait_for_function('window.AntGeneral && AntGeneral.rooms.length===0')
 assert frame.locator('body').evaluate('(node)=>getComputedStyle(node).visibility')=='hidden'
 # Child-to-child and wrong-channel traffic cannot import a draft.
 frame.evaluate('(draft)=>window.postMessage({channel:"ANT_VILLA_V1",nonce:"fake-session-123",type:"DRAFT",draft},location.origin)',draft)
 assert frame.evaluate('AntGeneral.rooms.length')==0
 page.evaluate('(draft)=>connect(draft)',draft)
 page.wait_for_function("events.some(event=>event.type==='IMPORTED')")
 assert frame.evaluate('AntGeneral.rooms.reduce((n,r)=>n+r.count,0)')==9
 assert frame.locator('#project_name').input_value()==draft['data']['title']
 assert frame.locator('#plot_width').input_value()=='24'
 assert frame.locator('#north').input_value()==''
 assert frame.locator('#city').input_value()=='الرياض'
 assert frame.evaluate("AntGeneral.rooms.filter(r=>r.floor===''&&r.min_area==='').length")>0
 assert page.evaluate('localStorage.length')==0
 frame.locator('#generate').click();assert frame.evaluate('AntGeneral.result') is None
 assert frame.locator('#error').is_visible() or frame.locator('#brief-form :invalid').count()>0
 frame.locator('#municipality').select_option(label='أمانة منطقة الرياض')
 assert frame.locator('#city').input_value()=='الرياض'
 for f,v in [('north','2'),('south','3'),('east','2'),('west','2')]:frame.locator('#'+f).fill(v)
 settings={'client-bedroom':(1,16,3.2,2,'bedroom'),'client-bathroom':(1,5,1.6,0,'bathroom'),'client-kitchen':(0,16,3,0,'kitchen'),'client-dining':(0,16,3,0,'dining'),'client-living':(0,24,3.5,0,'living'),'client-majlis':(0,24,3.5,0,'majlis'),'client-guest-wc':(0,4,1.6,0,'bathroom'),'client-custom-0':(1,20,3.5,2,'master')}
 for i,r in enumerate(frame.evaluate('AntGeneral.rooms')):
  floor,area,side,capacity,kind=settings[r['id']];cells=frame.locator('#rooms tr').nth(i).locator('td')
  cells.nth(1).locator('select').select_option(kind)
  cells=frame.locator('#rooms tr').nth(i).locator('td')
  cells.nth(2).locator('select').select_option(str(floor))
  for col,value in [(4,area),(5,side),(6,capacity)]:cells.nth(col).locator('input').fill(str(value))
 # Cancellation must release the actual Worker, then permit a new generation.
 frame.locator('#generate').click();frame.wait_for_function('AntGeneral.busy')
 frame.evaluate('AntStopEngine()');frame.wait_for_function('!AntGeneral.busy')
 assert frame.evaluate('AntGeneral.result') is None
 frame.locator('#generate').click();frame.wait_for_function('!AntGeneral.busy && AntGeneral.result!==null',timeout=240000)
 assert frame.locator('#error').is_hidden(),frame.locator('#error').inner_text()
 page.wait_for_function("events.some(event=>event.type==='RESULT')")
 result=frame.evaluate('AntGeneral.result');models=[m for m in result['candidates'] if m['release']['drawing_export_allowed']]
 assert models
 for m in models:
  assert m['brief']['project_name']==draft['data']['title'] and m['brief']['plot_width']==24
  assert sum(r['count'] for r in m['brief']['rooms'])==9
  assert any(r.get('guest_distributor') for r in m['floors'][0]['rooms'])
  assert not m['release']['executive_issue_allowed']
 for label,ext in [('↓ PDF','pdf'),('↓ DXF 2010','dxf'),('↓ JSON','json')]:
  with page.expect_download() as download:frame.get_by_role('link',name=label,exact=True).click()
  download.value.save_as(out/('integrated.'+ext))
 frame.locator('#choose').click();assert page.evaluate('localStorage.length')==0
 assert 'ant-villa-studio-files-041' not in page.evaluate('caches.keys()')
 frame.locator('#rooms tr').first.locator('td').nth(4).locator('input').fill('17')
 assert frame.locator('#stale').is_visible() and frame.locator('#downloads a').count()==0
 page.set_viewport_size({'width':390,'height':844})
 assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
 assert frame.evaluate('document.documentElement.scrollWidth<=innerWidth')
 page.screenshot(path=str(out/'mobile.png'),full_page=True)
 assert not errors,errors
 external=[u for u in requests if not u.startswith(('http://127.0.0.1:8031/','blob:','data:'))]
 assert not external,external
 evidence={'same_origin_parent_handshake':True,'real_client_room_count':9,'missing_values_remain_missing':True,'missing_values_block_generation':True,'actual_worker_cancel_and_retry':True,'python_candidates':[m['candidate_id'] for m in models],'real_downloads':['pdf','dxf','json'],'no_persistent_client_files':True,'changed_inputs_block_old_downloads':True,'mobile_overflow':False,'external_requests':external,'page_errors':errors,'executive_approval':False}
 (out/'browser-qa.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2));print(json.dumps(evidence,ensure_ascii=False))
 browser.close()
