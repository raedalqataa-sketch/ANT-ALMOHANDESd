"""Full public five-step intake -> real Python -> actual CAD/PDF downloads."""
from pathlib import Path
import json,os
from urllib.parse import urlsplit,parse_qs
from playwright.sync_api import sync_playwright
OUT=Path(os.environ.get('ANT_CLIENT_QA_OUTPUT','/workspace/ant-client-web-qa'));OUT.mkdir(exist_ok=True)
BASE=os.environ.get('ANT_CLIENT_QA_BASE','http://127.0.0.1:8041')
CANCEL_TEST=os.environ.get('ANT_CLIENT_QA_CANCEL','1')!='0'
FIXTURE=OUT/'client-test.xlsx'
from openpyxl import Workbook
wb=Workbook();sheet=wb.active;sheet.title='متطلبات';sheet.append(['الحقل','القيمة','إرشادات'])
for row in [('اسم المشروع','فيلا اختبار العميل','اختبار فقط'),('عرض الأرض (م)',24,''),('عمق الأرض (م)',32,''),('عدد الأدوار',2,''),('الموقع','الرياض',''),('اتجاه الشمال','شمال',''),('غرف النوم',3,'يُراجع العدد في الخطوة الرابعة'),('الحمامات',1,''),('خصوصية','مدخل ضيوف مستقل',''),('مطلب خاص','مراجعة مسبح مستقبلي','غير محول إلى قيد'),('قيمة نصية','A & B < محفوظ',''),('حقل فارغ',None,'يبقى فارغًا')]:sheet.append(row)
wb.save(FIXTURE)
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
 context=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True)
 page=context.new_page();errors=[];requests=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 page.on('console',lambda m:errors.append(m.text) if m.type=='error' else None)
 page.on('request',lambda r:requests.append(r.url))
 page.goto(BASE+'/client/?mode=advanced');page.get_by_role('button',name='التالي',exact=True).wait_for(state='visible')
 page.get_by_role('button',name='التالي',exact=True).click()
 assert page.get_by_role('alert').count()>0
 page.get_by_label('عرض الأرض (م)',exact=True).fill('23')
 page.get_by_label('لا أعرف عرض الأرض (م)',exact=True).check()
 assert page.get_by_label('عرض الأرض (م)',exact=True).input_value()==''
 page.get_by_label('لا أعرف عرض الأرض (م)',exact=True).uncheck()
 assert page.get_by_label('عرض الأرض (م)',exact=True).input_value()=='23'
 page.get_by_text('لديك ملف Excel؟',exact=True).click()
 file=page.get_by_label('ملف Excel',exact=True)
 file.set_input_files({'name':'broken.xlsx','mimeType':'application/octet-stream','buffer':b'not a zip file'})
 page.locator('details').first.get_by_role('alert').wait_for(state='visible')
 file.set_input_files(FIXTURE)
 page.get_by_role('region',name='حقول Excel المستوردة').wait_for(state='visible')
 page.get_by_role('button',name='تعبئة الحقول الفارغة المطابقة',exact=True).click()
 assert page.get_by_label('عرض الأرض (م)',exact=True).input_value()=='23'
 assert page.get_by_label('عمق الأرض (م)',exact=True).input_value()=='32'
 assert page.get_by_text('A & B < محفوظ',exact=True).count()>0
 page.get_by_label('عرض الأرض (م)',exact=True).fill('24')
 page.get_by_label('واجهة الأرض',exact=True).fill('جنوب')
 page.locator('details').first.locator('summary').click()
 page.get_by_role('button',name='التالي',exact=True).click()
 assert page.get_by_label('اسم المشروع',exact=True).input_value()=='فيلا اختبار العميل'
 assert page.get_by_label('عدد الأدوار',exact=True).input_value()=='2'
 page.get_by_label('عدد أفراد الأسرة',exact=True).fill('6')
 page.get_by_label('نوع المسكن',exact=True).select_option(label='فيلا')
 page.wait_for_timeout(500);page.reload()
 page.get_by_label('عدد أفراد الأسرة',exact=True).wait_for(state='visible')
 assert page.get_by_label('عدد أفراد الأسرة',exact=True).input_value()=='6'
 assert page.get_by_label('اسم المشروع',exact=True).input_value()=='فيلا اختبار العميل'
 page.get_by_role('button',name='التالي',exact=True).click()
 for label in ('مجلس رجال','مدخل رجال مستقل','موزع ضيوف يصل مباشرة إلى المجلس وحمام الضيوف'):page.get_by_label(label,exact=True).check()
 page.get_by_role('button',name='التالي',exact=True).click()
 for label,value in [('عدد غرف نوم','3'),('عدد حمامات','1'),('عدد مطبخ','1'),('عدد طعام','1'),('عدد معيشة','1')]:page.get_by_label(label,exact=True).fill(value)
 page.get_by_role('button',name='التالي',exact=True).click()
 page.screenshot(path=str(OUT/'desktop-review.png'),full_page=True)
 page.set_viewport_size({'width':390,'height':844})
 assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
 page.screenshot(path=str(OUT/'mobile-review.png'),full_page=True)
 page.set_viewport_size({'width':1440,'height':1000})
 page.get_by_role('button',name='إعداد المقترحات',exact=True).click()
 iframe=page.locator('iframe');iframe.wait_for(state='visible')
 frame=page.frames[1]
 frame.locator('#client-transfer-notice').wait_for(state='visible',timeout=45000)
 # Static Sites canonicalizes index.html to its directory; Vite needs the explicit source URL.
 assert urlsplit(frame.url).netloc==urlsplit(BASE).netloc
 assert urlsplit(frame.url).path in ('/client/villa-engine/generate/index.html','/client/villa-engine/generate/')
 assert parse_qs(urlsplit(frame.url).query).get('embedded')==['1']
 assert frame.evaluate('AntGeneral.rooms.reduce((n,r)=>n+r.count,0)')==9
 assert frame.locator('#project_name').input_value()=='فيلا اختبار العميل'
 assert frame.locator('#plot_width').input_value()=='24'
 assert frame.locator('#north').input_value()==''
 assert all(r['floor']=='' for r in frame.evaluate('AntGeneral.rooms'))
 assert 'لم يُنشأ مسقط بعد' in page.get_by_role('region',name='محرك توليد مساقط الفلل').get_by_role('status').inner_text()
 frame.locator('#generate').click();assert frame.evaluate('AntGeneral.result') is None
 frame.locator('#municipality').select_option(label='أمانة منطقة الرياض')
 for side,value in [('north','2'),('south','3'),('east','2'),('west','2')]:frame.locator('#'+side).fill(value)
 specs={'client-bedroom':(1,20,3.5,2),'client-bathroom':(1,5,1.6,0),'client-kitchen':(0,16,3,0),'client-dining':(0,16,3,0),'client-living':(0,24,3.5,0),'client-majlis':(0,24,3.5,0),'client-guest-wc':(0,4,1.6,0)}
 for i,r in enumerate(frame.evaluate('AntGeneral.rooms')):
  floor,area,side,capacity=specs[r['id']];tr=frame.locator('#rooms tr').nth(i)
  tr.locator('select').nth(1).select_option(str(floor))
  for label,value in [('المساحة',area),('أقل ضلع',side),('سعة النوم',capacity)]:tr.get_by_label(r['name']+' — '+label,exact=True).fill(str(value))
 frame.locator('#generate').click()
 if not frame.evaluate('AntGeneral.busy'):
  print('PRE_GENERATION_DIAGNOSTIC',frame.locator('#error').inner_text(),frame.locator('#brief-form :invalid').evaluate_all('(nodes)=>nodes.map(n=>({id:n.id,value:n.value,message:n.validationMessage}))'),frame.evaluate('AntGeneral.rooms'),flush=True)
 if CANCEL_TEST:
  frame.wait_for_function('AntGeneral.busy')
  frame.get_by_role('button',name='إيقاف / إعادة تشغيل المحرك',exact=True).click()
  frame.wait_for_function('!AntGeneral.busy');assert frame.evaluate('AntGeneral.result') is None
  frame.locator('#generate').click()
 frame.wait_for_function('!AntGeneral.busy && AntGeneral.result!==null',timeout=240000)
 assert frame.locator('#error').is_hidden(),frame.locator('#error').inner_text()
 result=frame.evaluate('AntGeneral.result')
 (OUT/'all-candidates.json').write_text(json.dumps(result,ensure_ascii=False))
 models=[m for m in result['candidates'] if m['release']['drawing_export_allowed']];assert len(models)>=2
 for model in models:
  folder=OUT/'candidates'/model['candidate_id'];folder.mkdir(parents=True,exist_ok=True)
  for kind,path in {**model['downloads'],**model['previews']}.items():
   data=frame.evaluate('async path=>Array.from(new Uint8Array(await (await AntFiles.read(path)).arrayBuffer()))',path)
   extension=path.rsplit('.',1)[-1];(folder/(kind+'.'+extension)).write_bytes(bytes(data))
 assert page.get_by_role('region',name='محرك توليد مساقط الفلل').get_by_role('status').inner_text().startswith('اكتمل البحث')
 for m in models:
  assert m['brief']['plot_width']==24 and m['brief']['plot_depth']==32 and sum(r['count'] for r in m['brief']['rooms'])==9
  assert any(r.get('guest_distributor') for r in m['floors'][0]['rooms'])
  assert not m['release']['executive_issue_allowed']
 for label,ext in [('↓ PDF','pdf'),('↓ DXF 2010','dxf'),('↓ JSON','json')]:
  with page.expect_download() as download:frame.get_by_role('link',name=label,exact=True).click()
  download.value.save_as(OUT/('client.'+ext))
 with page.expect_download() as download:page.get_by_role('button',name='تنزيل متطلبات العميل كاملة',exact=True).click()
 download.value.save_as(OUT/'source-requirements.json')
 original=json.loads((OUT/'source-requirements.json').read_text())['client_requirements']
 assert len(original['imported']['fields'])==12
 assert any(r['value']=='A & B < محفوظ' for r in original['imported']['fields'])
 frame.locator('#choose').click()
 assert page.evaluate('localStorage.length')==0
 assert 'ant-villa-studio-files-041' not in page.evaluate('caches.keys()')
 page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth') and frame.evaluate('document.documentElement.scrollWidth<=innerWidth')
 frame.locator('#viewer').screenshot(path=str(OUT/'mobile-results.png'))
 frame.locator('#notes').fill('تغيير اختبار لإبطال النسخة السابقة')
 assert frame.locator('#stale').is_visible() and frame.locator('#downloads a').count()==0
 page.get_by_role('button',name='تعديل الأسرة',exact=True).click()
 assert page.locator('iframe').count()==0
 assert page.get_by_label('عدد أفراد الأسرة',exact=True).input_value()=='6'
 assert not errors,errors
 external=[u for u in requests if not u.startswith((BASE+'/','blob:','data:'))];assert not external,external
 evidence={'five_step_rtl_intake':True,'xlsx_fields_preserved':12,'invalid_xlsx_error':True,'import_does_not_overwrite_existing_values':True,'draft_survives_reload':True,'unknown_toggle_preserves_value':True,'real_requested_spaces':9,'real_python_patterns':[m['candidate_id'] for m in models],'real_downloads':['pdf','dxf','json','original-client-requirements'],'real_worker_cancel_retry':CANCEL_TEST,'stale_exports_blocked':True,'edit_unmounts_engine':True,'engine_has_no_persistent_customer_files':True,'mobile_overflow':False,'external_requests':external,'page_errors':errors,'lovable_project_sync_verified':False,'executive_approval':False}
 (OUT/'browser-qa.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2));print(json.dumps(evidence,ensure_ascii=False))
 browser.close()
