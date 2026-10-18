from playwright.sync_api import sync_playwright
from pathlib import Path
import json
out=Path('/workspace/general-fix-review')
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
 ctx=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True)
 page=ctx.new_page();errors=[];external=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 page.on('request',lambda r:external.append(r.url) if not r.url.startswith(('http://127.0.0.1:8011','blob:','data:')) else None)
 page.goto('http://127.0.0.1:8011/generate/')
 page.wait_for_function("document.querySelector('#municipality').options.length===18",timeout=20000)
 assert '378' in page.locator('#jurisdiction-state').inner_text()
 # Import exactly the report uploaded by the user, before selecting any city.
 page.locator('#brief-file').set_input_files(out/'submitted.json')
 page.wait_for_function("AntGeneral.rooms[0]?.id==='r8f48d0f48e374e3da9fb8ab64777a'")
 assert page.locator('#error').is_hidden(),page.locator('#error').inner_text()
 page.locator('#municipality').select_option(label='أمانة منطقة الرياض')
 page.locator('#city').fill('الرياض')
 page.locator('#generate').click()
 page.wait_for_function('!AntGeneral.busy && AntGeneral.result!==null',timeout=120000)
 assert page.locator('#error').is_hidden(),page.locator('#error').inner_text()
 models=page.evaluate('AntGeneral.result.candidates')
 assert len(models)==3 and all(m['release']['drawing_export_allowed'] for m in models)
 assert all(m['schema_version']=='0.5.1-general' for m in models)
 assert all(m['metrics']['proposed_flexible_m2']==0 for m in models)
 for m in models:
  assert len(m['stairs'])==2 and len(m['parking'])==2
  assert not m['regulatory_profile']['local_rules_verified'] and not m['release']['executive_issue_allowed']
  for key in ('guest-route','free-text','stair-geometry','GF-walkability','FF-walkability','GF-door-sweeps','FF-door-sweeps','SA-GF-daylight','SA-FF-daylight'):
   assert next(c for c in m['checks'] if c['check_id']==key)['status']=='PASS'
 assert 'غير معتمدة' in page.locator('#compliance-summary').inner_text()
 assert page.locator('#checks .rule-source').count()>8
 page.locator('[data-family="stepped"]').click()
 for fid in ('GF','FF','SITE'):
  page.locator(f'[data-floor="{fid}"]').click();page.wait_for_function("document.querySelector('#plan').complete && document.querySelector('#plan').naturalWidth>0")
 page.locator('[data-floor="GF"]').click()
 for label,ext in [('↓ DXF 2010','dxf'),('↓ PDF','pdf'),('↓ JSON','json')]:
  with page.expect_download() as dl:page.get_by_role('link',name=label,exact=True).click()
  dl.value.save_as(out/f'fixed-browser.{ext}')
 page.locator('#choose').click();revision=page.evaluate('AntGeneral.selected.model_revision_id')
 page.screenshot(path=str(out/'fixed-desktop.png'),full_page=True)
 page.reload();page.wait_for_function('AntGeneral.selected!==null',timeout=30000)
 assert not page.evaluate('AntGeneral.stale')
 page.locator('[data-family="stepped"]').click();assert page.evaluate('AntGeneral.selected.model_revision_id')==revision
 assert 'اخترت' in page.locator('#chosen').inner_text()
 # Another city has the same national baseline, never fictitious verified local rules.
 page.locator('#municipality').select_option(label='أمانة محافظة جدة');assert page.locator('#city').input_value()==''
 page.locator('#city').fill('جدة');assert page.locator('#stale').is_visible() and page.locator('#downloads a').count()==0
 page.get_by_text('عروض الشوارع وحدود الأرض',exact=True).click()
 # Apply the explicit wide-street and adjacent-street baseline.
 for face,value in [('north','0'),('south','40'),('east','10'),('west','0')]:page.locator('#road-'+face).fill(value)
 page.locator('#apply-setbacks').click()
 assert page.locator('#south').input_value()=='6' and page.locator('#east').input_value()=='2'
 # Mobile layout is usable, with only the table scrolling internally.
 page.set_viewport_size({'width':390,'height':844})
 assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
 page.screenshot(path=str(out/'fixed-mobile.png'),full_page=True)
 assert not errors,errors
 assert not external,external
 evidence={'submitted_report_import':True,'city_directory':{'amanats':17,'municipality_records':378},'three_reviewable_alternatives':True,'guest_separation':True,'modeled_staircases':True,'movement_and_door_sweeps':True,'daylight_numeric_checks':True,'no_unrequested_reserve_rooms':True,'two_parking_stalls':True,'floor_and_site_previews':True,'pdf_dxf_json_downloads':True,'cache_reload_and_selection':True,'city_change_marks_stale':True,'wide_street_baseline':True,'full_code_or_local_approval_claimed':False,'mobile_outer_overflow':False,'page_errors':errors,'external_runtime_requests':external}
 (out/'browser-qa.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2))
 browser.close()
print('Saudi submitted-case browser QA: PASS')
