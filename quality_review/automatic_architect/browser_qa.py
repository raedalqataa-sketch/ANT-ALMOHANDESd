"""Client supplies land and household only; Python proposes program and produces all drawings."""
from pathlib import Path
import os,json
from playwright.sync_api import sync_playwright
OUT=Path(os.environ.get('ANT_ARCHITECT_QA_OUTPUT','/workspace/architect-browser-qa'));OUT.mkdir(parents=True,exist_ok=True)
BASE=os.environ.get('ANT_ARCHITECT_QA_BASE','http://127.0.0.1:8041')
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,args=['--no-sandbox']);context=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True)
 page=context.new_page();errors=[]
 page.on('pageerror',lambda e:errors.append(str(e)));page.on('console',lambda m:errors.append(m.text) if m.type=='error' else None)
 page.goto(BASE+'/client/');page.get_by_role('button',name='التالي',exact=True).wait_for()
 page.get_by_role('button',name='التالي',exact=True).click();assert page.get_by_role('alert').is_visible()
 page.get_by_label('المدينة',exact=True).fill('الرياض')
 page.get_by_label('عرض الأرض (م)',exact=True).fill('24');page.get_by_label('عمق الأرض (م)',exact=True).fill('32')
 # Street width is deliberately unknown: no setback, room, floor or dimension entry.
 page.screenshot(path=str(OUT/'desktop-land.png'),full_page=True)
 page.get_by_role('button',name='التالي',exact=True).click();page.get_by_label('عدد أفراد الأسرة',exact=True).fill('6')
 page.wait_for_timeout(500);page.reload();page.get_by_role('button',name='التالي',exact=True).wait_for()
 assert page.get_by_label('عرض الأرض (م)',exact=True).input_value()=='24'
 page.get_by_role('button',name='التالي',exact=True).click();assert page.get_by_label('عدد أفراد الأسرة',exact=True).input_value()=='6'
 page.get_by_role('button',name='التالي',exact=True).click()
 page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth');page.screenshot(path=str(OUT/'mobile-review.png'),full_page=True)
 page.set_viewport_size({'width':1440,'height':1000});page.get_by_role('button',name='صمّم مقترحاتي الثلاثة',exact=True).click()
 page.locator('iframe').wait_for();frame=page.frames[1];frame.locator('#auto-progress').wait_for(timeout=45000)
 assert frame.locator('.workspace').is_hidden()
 frame.wait_for_function('AntGeneral.result!==null',timeout=240000)
 assert frame.locator('#auto-program').is_visible();result=frame.evaluate('AntGeneral.result')
 assert frame.evaluate('AntGeneral.floor')=='SITE'
 assert result['planning']['sleeping_capacity']==6
 assert result['planning']['setbacks']['unknown_street_faces']==['south']
 assert result['planning']['original_intent']['street_widths']=={}
 models=[m for m in result['candidates'] if m['release']['drawing_export_allowed']];assert {m['candidate_id'] for m in models}=={'L','U','stepped'}
 for m in models:
  assert sum(r['count']*r['capacity'] for r in m['brief']['rooms'])==6
  assert any(r.get('guest_distributor') for r in m['floors'][0]['rooms'])
  assert m['site_placement']['active'] and m['site_placement']['rear_face']=='north'
  assert 'south' not in m['site_placement']['anchor_faces']
  assert all(value+1e-5>=m['brief']['setbacks'][face] for face,value in m['site_placement']['actual_clearances_m'].items())
  assert not m['release']['executive_issue_allowed']
  folder=OUT/'candidates'/m['candidate_id'];folder.mkdir(parents=True,exist_ok=True)
  for key,path in {**m['downloads'],**m['previews']}.items():
   data=frame.evaluate('async path=>Array.from(new Uint8Array(await (await AntFiles.read(path)).arrayBuffer()))',path)
   (folder/(key+'.'+path.rsplit('.',1)[-1])).write_bytes(bytes(data))
 for label,ext in [('↓ PDF','pdf'),('↓ DXF 2010','dxf'),('↓ JSON','json')]:
  with page.expect_download() as download:frame.get_by_role('link',name=label,exact=True).click()
  download.value.save_as(OUT/('automatic.'+ext))
 page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth') and frame.evaluate('document.documentElement.scrollWidth<=innerWidth')
 frame.locator('#auto-progress').screenshot(path=str(OUT/'proposed-program.png'));frame.locator('#viewer').screenshot(path=str(OUT/'mobile-result.png'))
 assert not errors,errors
 assert page.evaluate('localStorage.length')==0
 (OUT/'all-candidates.json').write_text(json.dumps(result,ensure_ascii=False))
 proof={'basic_inputs_only':True,'required_room_counts':False,'required_room_dimensions':False,'required_manual_setbacks':False,'automatic_generation':True,'family':6,'sleeping_capacity':6,'patterns':[m['candidate_id'] for m in models],'draft_recovered':True,'real_downloads':['pdf','dxf','json'],'unknown_street_width_disclosed':True,'page_errors':errors,'mobile_overflow':False,'executive_approved':False}
 (OUT/'browser-qa.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2));print(json.dumps(proof,ensure_ascii=False));browser.close()
