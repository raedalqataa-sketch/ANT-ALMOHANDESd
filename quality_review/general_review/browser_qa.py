from pathlib import Path
from playwright.sync_api import sync_playwright
import json
out=Path('/workspace/general-review')
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
 context=browser.new_context(viewport={'width':1440,'height':1050},accept_downloads=True)
 page=context.new_page();errors=[];external=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 page.on('request',lambda r:external.append(r.url) if not r.url.startswith(('http://127.0.0.1:8011','blob:','data:')) else None)
 page.goto('http://127.0.0.1:8011/generate/');page.locator('#generate').click()
 page.wait_for_function('!AntGeneral.busy && AntGeneral.result!==null',timeout=120000)
 assert page.locator('#error').is_hidden(),page.locator('#error').inner_text()
 models=page.evaluate('AntGeneral.result.candidates')
 assert len(models)==3 and all(m['release']['drawing_export_allowed'] for m in models)
 assert page.locator('.alternative').count()==3
 assert 'غير متصل' in page.locator('#ai-state').inner_text()
 page.locator('[data-family="U"]').click();page.locator('[data-floor="FF"]').click()
 page.wait_for_function("document.querySelector('#plan').complete && document.querySelector('#plan').naturalWidth>0")
 page.screenshot(path=str(out/'general-desktop.png'),full_page=True)
 page.locator('#plan').screenshot(path=str(out/'general-plan.png'))
 page.locator('#choose').click();assert 'اخترت' in page.locator('#chosen').inner_text()
 revision=page.evaluate('AntGeneral.selected.model_revision_id')
 for label,ext in [('↓ DXF 2010','dxf'),('↓ PDF','pdf'),('↓ JSON','json')]:
  with page.expect_download() as dl:page.get_by_role('link',name=label,exact=True).click()
  dl.value.save_as(out/f'browser.{ext}')
 page.reload();page.wait_for_function('AntGeneral.selected!==null',timeout=30000)
 assert not page.evaluate('AntGeneral.stale')
 page.locator('[data-family="U"]').click();assert page.evaluate('AntGeneral.selected.model_revision_id')==revision
 assert 'اخترت' in page.locator('#chosen').inner_text()
 page.locator('#plot_width').fill('24');assert page.locator('#stale').is_visible()
 assert page.locator('#downloads a').count()==0
 # Change the actual requested bedroom count, not a cosmetic drawing property.
 page.locator('#rooms tr').nth(6).locator('td').nth(3).locator('input').fill('3')
 page.locator('#generate').click();page.wait_for_function('!AntGeneral.busy && AntGeneral.selected.brief.plot_width===24',timeout=120000)
 assert len(page.evaluate("AntGeneral.selected.floors.flatMap(f=>f.rooms).filter(r=>r.request_id===AntGeneral.rooms[6].id)"))==3
 # Truly infeasible: preserve requested spaces and explain each missing family.
 page.locator('#plot_width').fill('12');page.locator('#plot_depth').fill('14')
 page.locator('#generate').click();page.wait_for_function('!AntGeneral.busy && AntGeneral.result.candidates.length===0',timeout=120000)
 assert page.locator('#unavailable p').count()==3
 assert page.locator('#viewer').is_hidden()
 # Responsive, no outer horizontal scrolling (the program table scrolls internally).
 page.set_viewport_size({'width':390,'height':844})
 assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
 page.screenshot(path=str(out/'general-mobile.png'),full_page=True)
 assert not errors,errors
 assert not external,external
 (out/'browser-qa.json').write_text(json.dumps({'three_distinct_schemes':True,'real_program_count_change':True,'blocked_infeasible':True,'selection_persisted':True,'cache_after_reload':True,'stale_downloads_disabled':True,'real_downloads':['pdf','dxf','json'],'mobile_outer_overflow':False,'page_errors':errors,'external_runtime_requests':external,'ollama_live_connected':False},indent=2))
 browser.close()
print('General hosted browser QA: PASS')
