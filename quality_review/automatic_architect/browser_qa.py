"""Client supplies land and household only; Python proposes program and produces all drawings."""
from pathlib import Path
import os,json
from playwright.sync_api import sync_playwright
OUT=Path(os.environ.get('ANT_ARCHITECT_QA_OUTPUT','/workspace/architect-browser-qa'));OUT.mkdir(parents=True,exist_ok=True)
COUNTRY=os.environ.get('ANT_ARCHITECT_QA_COUNTRY','SA')
LEVEL=os.environ.get('ANT_ARCHITECT_QA_LEVEL','standard')
PRIORITY=os.environ.get('ANT_ARCHITECT_QA_PRIORITY','usability')
BASE=os.environ.get('ANT_ARCHITECT_QA_BASE','http://127.0.0.1:8041')
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,args=['--no-sandbox']);context=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True)
 page=context.new_page();errors=[]
 page.on('pageerror',lambda e:errors.append(str(e)));page.on('console',lambda m:errors.append(m.text) if m.type=='error' else None)
 page.goto(BASE+'/client/');page.get_by_role('button',name='التالي',exact=True).wait_for()
 page.get_by_role('button',name='التالي',exact=True).click();assert page.get_by_role('alert').is_visible()
 page.get_by_text('المدينة والحي · اختياري',exact=True).click()
 page.get_by_label('المدينة · اختياري',exact=True).fill('الرياض')
 page.get_by_label('المنطقة / المحافظة',exact=True).fill('الرياض')
 assert page.locator('#architect-regions option').count()==13
 page.get_by_label('الدولة',exact=True).select_option('YE')
 assert page.locator('#architect-regions option').count()==22
 assert page.locator('#architect-regions option[value="المنطقة الشرقية"]').count()==0
 page.get_by_label('المحافظة / أمانة العاصمة',exact=True).fill('محافظة يدوية')
 page.get_by_label('المدينة · اختياري',exact=True).fill('مدينة يدوية')
 page.get_by_label('المديرية · اختياري',exact=True).fill('مديرية اختبار')
 page.get_by_label('الحي · اختياري',exact=True).fill('حي اختبار')
 page.get_by_label('الدولة',exact=True).select_option('SA')
 assert page.get_by_label('المدينة · اختياري',exact=True).input_value()=='الرياض'
 if COUNTRY=='YE':
  page.get_by_label('الدولة',exact=True).select_option('YE')
  assert page.get_by_label('المدينة · اختياري',exact=True).input_value()=='مدينة يدوية'
  assert page.get_by_label('المديرية · اختياري',exact=True).input_value()=='مديرية اختبار'

 page.get_by_label('عرض الأرض (م)',exact=True).fill('24');page.get_by_label('عمق الأرض (م)',exact=True).fill('32')
 # Street width is deliberately unknown: no setback, room, floor or dimension entry.
 page.screenshot(path=str(OUT/'desktop-land.png'),full_page=True)
 page.get_by_role('button',name='التالي',exact=True).click();page.get_by_label('عدد أفراد الأسرة',exact=True).fill('6')
 page.get_by_label('نوع المبنى',exact=True).select_option('investment')
 page.get_by_label('عدد الوحدات المقترح',exact=True).fill('5')
 with page.expect_download() as d:page.get_by_role('button',name='تنزيل متطلبات المشروع بصيغة JSON',exact=True).click()
 d.value.save_as(OUT/'investment-requirements.json')
 investment=json.loads((OUT/'investment-requirements.json').read_text());assert investment['intent']['investment_units']==5
 page.get_by_role('button',name='التالي',exact=True).click();assert page.get_by_role('alert').is_visible()
 assert page.locator('iframe').count()==0
 page.get_by_label('نوع المبنى',exact=True).select_option('villa')
 page.wait_for_timeout(500);page.reload();page.get_by_role('button',name='التالي',exact=True).wait_for()
 assert page.get_by_label('عرض الأرض (م)',exact=True).input_value()=='24'
 page.get_by_role('button',name='التالي',exact=True).click();assert page.get_by_label('عدد أفراد الأسرة',exact=True).input_value()=='6'
 page.get_by_role('button',name='التالي',exact=True).click()
 page.get_by_label('مستوى المخرجات',exact=True).select_option(LEVEL)
 page.get_by_label('أولوية التصميم',exact=True).select_option(PRIORITY)
 page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth');page.screenshot(path=str(OUT/'mobile-review.png'),full_page=True)
 page.set_viewport_size({'width':1440,'height':1000});page.get_by_role('button',name='ولّد البدائل',exact=True).click()
 page.locator('iframe').wait_for();frame=page.frames[1];frame.locator('#auto-progress').wait_for(timeout=45000)
 assert frame.locator('.workspace').is_hidden()
 frame.wait_for_function('AntGeneral.result!==null',timeout=600000)
 assert frame.locator('#auto-program').count()==1;result=frame.evaluate('AntGeneral.result')
 assert frame.evaluate('AntGeneral.floor') in ('SITE','GF')
 (OUT/'all-candidates.json').write_text(json.dumps(result,ensure_ascii=False))
 assert result['planning']['reference_design']['project_count']==6
 assert result['planning']['reference_design']['legal_rules_extracted']==0
 assert result['planning']['reference_design']['unique_images']==19
 assert result['planning']['generation_v4']['revision']=='architectural-engine-4'
 assert result['planning']['sleeping_capacity']==6
 assert result['planning']['setbacks']['unknown_street_faces']==['south']
 assert result['planning']['original_intent']['street_widths']=={}
 models=[m for m in result['candidates'] if m['release']['drawing_export_allowed']];assert len(models)==3
 assert result['planning']['original_intent']['country']==COUNTRY
 assert result['planning']['original_intent']['output_level']==LEVEL
 assert result['planning']['original_intent']['design_priority']==PRIORITY
 assert result['planning']['design_selection']['search_variants_examined']>=7
 for m in models:
  assert sum(r['count']*r['capacity'] for r in m['brief']['rooms'])==6
  assert any(r.get('guest_distributor') for r in m['floors'][0]['rooms'])
  place=m['site_placement']
  if place['active']:
   assert place['rear_face']=='north' and 'south' not in place['anchor_faces']
   assert all(value+1e-5>=m['brief']['setbacks'][face] for face,value in place['actual_clearances_m'].items())
  else:
   assert place['reason']=='insufficient_front_or_side_surplus'
   assert not (place['front_extra_m']>=3-1e-5 and place['side_extra_m']>=2-1e-5 and place['envelope_ratio']<=.8+1e-5)
  points=[p for polys in m['footprint']['polygons_by_floor'].values() for poly in polys for p in poly]
  clear={'west':min(p[0] for p in points),'east':m['site']['width']-max(p[0] for p in points),'north':min(p[1] for p in points),'south':m['site']['depth']-max(p[1] for p in points)}
  assert all(clear[face]+1e-5>=value for face,value in m['brief']['setbacks'].items())
  assert not m['release']['executive_issue_allowed']
  assert next(c for c in m['checks'] if c['check_id']=='REF-functional-route')['status']=='PASS'
  assert m['design_evaluation']['reference_patterns']['revision']=='reference-principles-2'
  assert m['design_evaluation']['reference_patterns']['legal_rule'] is False
  assert m['rule_traceability_v4']['rule_count']==199
  assert m['functional_program_v4']['movement']['routes']
  assert not m['functional_program_v4']['movement']['unreachable']
  assert not [c for c in m['checks'] if c['status']=='FAIL']
  if COUNTRY=='YE':assert not any(c['check_id'].startswith('SA-') for c in m['checks'])
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
 proof={'country':COUNTRY,'output_level':LEVEL,'priority':PRIORITY,'country_location_recovered':True,'investment_drawing_blocked':True,'investment_requirements_exported':True,'basic_inputs_only':True,'required_room_counts':False,'required_room_dimensions':False,'required_manual_setbacks':False,'automatic_generation':True,'family':6,'sleeping_capacity':6,'patterns':[m['candidate_id'] for m in models],'draft_recovered':True,'real_downloads':['pdf','dxf','json'],'unknown_street_width_disclosed':True,'page_errors':errors,'mobile_overflow':False,'executive_approved':False}
 (OUT/'browser-qa.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2));print(json.dumps(proof,ensure_ascii=False));browser.close()
