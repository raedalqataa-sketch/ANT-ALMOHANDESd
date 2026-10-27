"""Real intake-to-export QA. Missing Gemini secret/auth is explicit, never mocked as live.
Run against a local Sites/Worker preview.
"""
import json,os
from pathlib import Path
from playwright.sync_api import sync_playwright
out=Path(os.environ.get('ANT_ENGINE_QA_OUTPUT','/tmp/ant-engine-selector-qa'));out.mkdir(parents=True,exist_ok=True)
base=os.environ.get('ANT_ENGINE_QA_BASE','http://127.0.0.1:8048')
with sync_playwright() as p:
 b=p.chromium.launch(headless=True);page=b.new_page(viewport={'width':1440,'height':1000});errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.on('console',lambda m:print(m.type,m.text[:160],flush=True) if m.type=='error' else None)
 page.goto(base+'/client/')
 page.get_by_role('region',name='اختيار محرك التصميم').wait_for()
 assert page.get_by_role('radio',name='الذكاء المعماري المحدّث',exact=False).is_checked()
 page.screenshot(path=str(out/'updated-client.png'),full_page=True)
 page.get_by_role('radio',name='Gemini + المحرك الهندسي',exact=False).check()
 assert page.get_by_role('checkbox',name='أوافق على إرسال',exact=False).is_visible()
 page.get_by_role('button',name='اختبار اتصال Gemini',exact=True).click()
 page.get_by_text('سجّل الدخول بحساب ChatGPT لاستخدام Gemini.',exact=True).wait_for()
 page.get_by_role('radio',name='الذكاء المعماري المحدّث',exact=False).check()
 # Use real form and same-origin iframe bridge, not a detached mocked worker.
 page.get_by_label('المنطقة / المحافظة',exact=True).fill('الرياض')
 page.get_by_label('عرض الأرض (م)',exact=True).fill('20')
 page.get_by_label('عمق الأرض (م)',exact=True).fill('30')
 page.get_by_role('button',name='التالي',exact=True).click()
 page.get_by_label('عدد أفراد الأسرة',exact=True).fill('6')
 page.get_by_role('button',name='التالي',exact=True).click()
 page.get_by_role('button',name='صمّم مقترحاتي الثلاثة',exact=True).click()
 page.wait_for_selector('iframe[title="إعداد وتوليد المقترحات بواسطة محرك التوليد"]')
 frame=page.frames[-1]
 frame.wait_for_function("window.AntGeneral?.result != null || parent.document.querySelector('[role=alert]')",timeout=360000)
 assert not page.get_by_role('alert').count(), page.get_by_role('alert').all_text_contents()
 result=frame.evaluate('AntGeneral.result')
 assert result['planning']['client_generation']['mode']=='intelligence'
 assert len(result['candidates'])==3
 assert not any(c['status']=='FAIL' for m in result['candidates'] for c in m['checks'])
 assert all(m['architecture_intelligence']['unassigned_area_m2']<=1e-6 for m in result['candidates'])
 downloads=[]
 for label,ext in [('↓ PDF','pdf'),('↓ DXF 2010','dxf')]:
  with page.expect_download() as d:frame.get_by_role('link',name=label,exact=True).click()
  d.value.save_as(out/('selected.'+ext));downloads.append(ext)
 frame.locator('#viewer').screenshot(path=str(out/'real-intelligence-plan.png'))
 page.set_viewport_size({'width':390,'height':844});page.screenshot(path=str(out/'mobile-client.png'),full_page=True)
 assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
 assert not errors,errors
 proof={'candidates':len(result['candidates']),'modes':result['planning']['client_generation'],'files':downloads,'page_errors':errors,'metrics':[m['architecture_intelligence'] for m in result['candidates']]}
 (out/'proof.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2));print('Real intake -> intelligence -> 3 validated alternatives -> PDF/DXF downloads: PASS')
 b.close()
