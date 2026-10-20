"""Build a same-origin, self-contained Lovable integration from verified engine assets.

No credentials or hosted compute API. Python is the unchanged geometric engine.
"""
from pathlib import Path
import argparse,hashlib,json,shutil,zipfile,subprocess
ROOT=Path(__file__).resolve().parents[1]

def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--runtime-source',type=Path,required=True);a=p.parse_args()
 target=a.output/'public/villa-engine';studio=target/'studio';generate=target/'generate';studio.mkdir(parents=True,exist_ok=True)
 for folder in ('runtime','wheels'):shutil.copytree(a.runtime_source/folder,studio/folder,dirs_exist_ok=True)
 (studio/'assets').mkdir(exist_ok=True)
 for name in ('Arabic.ttf','Latin.ttf','PlanFont.ttf','FONT-LICENSE.txt','LATIN-FONT-LICENSE.txt'):
  source=ROOT/'frontend'/name
  if source.exists():shutil.copyfile(source,studio/'assets'/name)
 for name in ('CPYTHON-LICENSE','PYODIDE-LICENSE','engine.zip','manifest.json'):shutil.copyfile(a.runtime_source/name,studio/name)
 with zipfile.ZipFile(studio/'engine.zip') as archive:
  assert archive.read('backend/design/general_engine.py')==(ROOT/'backend/design/general_engine.py').read_bytes(),'Runtime source must match the checked-out geometric engine'
 subprocess.run(['python','-m','web_generator.build','--output',str(generate)],cwd=ROOT,check=True)
 html=(generate/'index.html').read_text()
 html=html.replace('<head>','<head><script>window.AntEmbedded=new URLSearchParams(location.search).get("embedded")==="1";if(window.AntEmbedded)document.documentElement.dataset.clientAwaiting="1";</script><style>html[data-client-awaiting] body{visibility:hidden}#client-transfer-notice{padding:20px;line-height:1.9}#client-transfer-notice p{margin:10px 0}html[data-embedded] header,html[data-embedded] .hero{display:none}</style>')
 html=html.replace('<script defer src="./app.js?v=062">','<script defer src="./client-bridge.js?v=1"></script><script defer src="./app.js?v=062">')
 html=html.replace('</head>','<script defer src="./embedded-runtime.js?v=1"></script></head>')
 html=html.replace('الأرقام الحالية مثال قابل للتعديل، وليست اشتراطات رسمية.','أكمل الحقول الفارغة؛ قياسات الجدران والحركة الظاهرة مقترحات قابلة للتعديل، وليست اشتراطات رسمية.')
 (generate/'index.html').write_text(html)
 for file in ('client-bridge.js','embedded-runtime.js'):shutil.copyfile(ROOT/'lovable_integration'/file,generate/file)
 app=(generate/'app.js').read_text()
 app=app.replace("function persist(){try", "function persist(){if(window.AntEmbedded)return;try")
 app=app.replace("let chosen;try{chosen=JSON.parse", "let chosen=window.AntEmbedded?{revision:state.chosenRevision}:null;try{if(!window.AntEmbedded)chosen=JSON.parse")
 app=app.replace("اخترت هذا المقترح. الاختيار محفوظ في هذا المتصفح، ولا يمثل اعتمادًا تنفيذيًا.","اخترت هذا المقترح مؤقتًا في هذه الجلسة؛ لا يمثل حفظ مشروع في الخادم أو اعتمادًا تنفيذيًا.")
 app=app.replace("try{localStorage.setItem('ant-general-last-050'", "try{if(!window.AntEmbedded)localStorage.setItem('ant-general-last-050'")
 app=app.replace("try{localStorage.setItem('ant-general-choice-050'", "try{state.chosenRevision=state.selected.model_revision_id;if(!window.AntEmbedded)localStorage.setItem('ant-general-choice-050'")
 app=app.replace("renderResult();$('engine-state').textContent='اكتمل", "renderResult();window.AntEmbeddedNotify?.(result);$('engine-state').textContent='اكتمل")
 app=app.replace("$('municipality').addEventListener('change',()=>{$('city').value=''", "$('municipality').addEventListener('change',()=>{if(!window.AntEmbedded)$('city').value=''")
 app=app.replace("async function init(){let saved;", "async function init(){if(window.AntEmbedded){document.documentElement.dataset.embedded='1';state.rooms=[];renderRooms();await loadJurisdictions();aiStatus();return;}let saved;")
 app=app.replace(" }init();", " }window.AntEmbeddedReady=init();\n window.AntLoadClientBrief=b=>{restore(b);changed();};")
 assert 'window.AntLoadClientBrief=b=>' in app
 (generate/'app.js').write_text(app)
 client=(generate/'static-client.js').read_text().replace("const worker=new Worker", "let worker=new Worker")
 client=client.replace("if('caches' in window)","if(!window.AntEmbedded&&'caches' in window)").replace("if('caches'in window)","if(!window.AntEmbedded&&'caches'in window)")
 client=client.replace("pending.set(id,{resolve,reject});", "const timer=setTimeout(()=>window.AntStopEngine('تجاوزت العملية مدة الانتظار؛ أعد المحاولة.'),600000);pending.set(id,{resolve,reject,timer});")
 client=client.replace("pending.delete(data.id);", "pending.delete(data.id);clearTimeout(request.timer);")
 start=client.index('  worker.onmessage=');end=client.index('  window.AntFiles=',start)
 handlers=client[start:end].replace("for(const p of pending.values())p.reject(", "for(const p of pending.values()){clearTimeout(p.timer);p.reject(").replace("'));pending.clear()", "'));}pending.clear()")
 client=client[:start]+"  function attachWorker(){\n"+handlers+"  }\n  attachWorker();\n  window.AntStopEngine=(reason='أُوقفت العملية؛ يمكنك تعديل الإعدادات وإعادة التوليد.')=>{worker.terminate();for(const p of pending.values()){clearTimeout(p.timer);p.reject(Error(reason));}pending.clear();worker=new Worker('./worker.js?v=062');attachWorker();};\n"+client[end:]
 (generate/'static-client.js').write_text(client)
 for file in ('app.js','static-client.js','embedded-runtime.js','client-bridge.js'):subprocess.run(['node','--check',str(generate/file)],check=True)
 source=ROOT/'lovable_integration/lovable-src'
 if source.exists():shutil.copytree(source,a.output/'src',dirs_exist_ok=True)
 manifest={'engine_version':'0.6.2-general','engine_sha256':hashlib.sha256((studio/'engine.zip').read_bytes()).hexdigest(),'same_origin_assets':True,'runtime_paid_services':False,'client_data_persistence':'memory; parent draft expires in sessionStorage','executive_approval':False}
 (target/'integration.json').write_text(json.dumps(manifest,indent=2)+'\n')
 print(json.dumps(manifest))

if __name__=='__main__':main()
