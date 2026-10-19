from playwright.sync_api import sync_playwright
from pathlib import Path
import json
root=Path('/workspace/github-ant-almohandes');out=Path('/workspace/automatic-browser-qa');out.mkdir(exist_ok=True)
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
 ctx=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True)
 page=ctx.new_page();errors=[];external=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 page.on('request',lambda r:external.append(r.url) if not r.url.startswith(('http://127.0.0.1:8011','blob:','data:')) else None)
 page.goto('http://127.0.0.1:8011/generate/');page.wait_for_function("document.querySelector('#municipality').options.length===18")
 page.locator('#brief-file').set_input_files(root/'requirements/regressions/submitted-b4a690-brief.json')
 page.wait_for_function("AntGeneral.rooms[0]?.id==='r8f48d0f48e374e3da9fb8ab64777a'")
 page.locator('#municipality').select_option(label='أمانة منطقة الرياض');page.locator('#city').fill('الرياض')
 page.locator('#plot_width').fill('24');page.locator('#plot_depth').fill('32')
 page.get_by_text('عروض الشوارع وحدود الأرض',exact=True).click()
 for f,v in [('north','0'),('south','15'),('east','0'),('west','0')]:page.locator('#road-'+f).fill(v)
 for selector in ('#auto-lightwell','#auto-annex','#auto-balcony','#auto-services'):page.locator(selector).check()
 page.locator('#main-street-known').select_option('known');page.locator('#main-south').check()
 page.locator('#generate').click();page.wait_for_function('!AntGeneral.busy && AntGeneral.result!==null',timeout=180000)
 assert page.locator('#error').is_hidden(),page.locator('#error').inner_text()
 result=page.evaluate('AntGeneral.result');models=[m for m in result['candidates'] if m['release']['drawing_export_allowed']]
 assert len(models)>=2
 for m in models:
  assert m['schema_version']=='0.6.0-general'
  assert len(m['feature_generation'])==4 and all(x['status']=='GENERATED' for x in m['feature_generation'])
  assert not m['release']['executive_issue_allowed']
  assert m['brief']['automatic_features']['roof_annex']
 page.locator('[data-family="L"]').click();assert page.locator('#feature-results .generated').count()==4
 for fid in ('GF','FF','RF','SITE'):
  page.locator(f'[data-floor="{fid}"]').click();page.wait_for_function("document.querySelector('#plan').complete && document.querySelector('#plan').naturalWidth>0")
  page.locator('#plan').screenshot(path=str(out/f'plan-{fid}.png'))
 for label,ext in [('↓ DXF 2010','dxf'),('↓ PDF','pdf'),('↓ JSON','json')]:
  with page.expect_download() as dl:page.get_by_role('link',name=label,exact=True).click()
  dl.value.save_as(out/f'features.{ext}')
 page.locator('#choose').click();rev=page.evaluate('AntGeneral.selected.model_revision_id')
 page.screenshot(path=str(out/'desktop.png'),full_page=True)
 page.reload();page.wait_for_function('AntGeneral.selected!==null',timeout=30000)
 assert not page.evaluate('AntGeneral.stale')
 assert page.locator('#auto-annex').is_checked() and page.locator('#auto-lightwell').is_checked()
 page.locator('[data-family="L"]').click();assert page.evaluate('AntGeneral.selected.model_revision_id')==rev
 page.locator('#well-length').fill('2.2');assert page.locator('#stale').is_visible() and not page.locator('#downloads a').count()
 page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth');page.screenshot(path=str(out/'mobile.png'),full_page=True)
 # Import and transmit an expert's geometry without silently dropping or replacing it.
 manual=models[0]['brief'];manual['automatic_features']={};manual['regulatory_geometry']={'light_wells':[],'roof_annex_absent':True,'projections':[]}
 manualfile=out/'manual.json';manualfile.write_text(json.dumps(manual,ensure_ascii=False))
 page.locator('#brief-file').set_input_files(manualfile);page.wait_for_function("document.querySelector('#regulatory-json').value.includes('roof_annex_absent')")
 assert not page.locator('#auto-annex').is_checked()
 with page.expect_download() as dl:page.locator('#save-brief').click()
 dl.value.save_as(out/'manual-roundtrip.json')
 saved=json.loads((out/'manual-roundtrip.json').read_text());assert saved['regulatory_geometry']==manual['regulatory_geometry']
 # Generation must actually receive the geometry, not just display it in an editor.
 page.locator('#generate').click();page.wait_for_function('!AntGeneral.busy && AntGeneral.result.candidates[0]?.brief.regulatory_geometry?.roof_annex_absent===true',timeout=180000)
 assert page.locator('#error').is_hidden(),page.locator('#error').inner_text()
 assert page.evaluate("AntGeneral.result.candidates[0].brief.regulatory_geometry.light_wells.length===0")
 page.reload();page.wait_for_function('AntGeneral.selected!==null');assert not page.evaluate('AntGeneral.stale')
 assert not errors,errors
 assert not external,external
 evidence={'actual_features_generated':4,'reviewable_families':[m['candidate_id'] for m in models],'floor_tabs':['GF','FF','RF','SITE'],'manual_geometry_roundtrip':True,'manual_geometry_sent_to_engine':True,'feature_change_marks_stale':True,'cache_reload':True,'mobile_overflow':False,'downloads':['pdf','dxf','json'],'page_errors':errors,'external_runtime_requests':external,'full_code_approval':False}
 (out/'browser-qa.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2));print(json.dumps(evidence,ensure_ascii=False))
 browser.close()
