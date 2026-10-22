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
 # Add the proposed-program layer without changing any approved geometry module.
 existing=studio/'engine.zip'
 with zipfile.ZipFile(existing) as archive:entries={name:archive.read(name) for name in archive.namelist()}
 entries['backend/design/architect_planner.py']=(ROOT/'backend/design/architect_planner.py').read_bytes()
 with zipfile.ZipFile(existing,'w',zipfile.ZIP_DEFLATED) as archive:
  for name,data in sorted(entries.items()):archive.writestr(zipfile.ZipInfo(name),data,compress_type=zipfile.ZIP_DEFLATED)
 subprocess.run(['python','-m','web_generator.build','--output',str(generate)],cwd=ROOT,check=True)
 html=(generate/'index.html').read_text()
 html=html.replace('<head>','<head><script>window.AntEmbedded=new URLSearchParams(location.search).get("embedded")==="1";if(window.AntEmbedded)document.documentElement.dataset.clientAwaiting="1";</script><style>html[data-client-awaiting] body{visibility:hidden}#client-transfer-notice{padding:20px;line-height:1.9}#client-transfer-notice p{margin:10px 0}html[data-embedded] header,html[data-embedded] .hero{display:none}</style>')
 html=html.replace('<script defer src="./app.js?v=062">','<script defer src="./client-bridge.js?v=1"></script><script defer src="./app.js?v=062">')
 html=html.replace('<script defer src="./static-client.js', '<script defer src="./worker-session.js?v=1"></script><script defer src="./static-client.js')
 html=html.replace('</head>','<script defer src="./automatic-runtime.js?v=1"></script><script defer src="./embedded-runtime.js?v=1"></script></head>')
 html=html.replace('الأرقام الحالية مثال قابل للتعديل، وليست اشتراطات رسمية.','أكمل الحقول الفارغة؛ قياسات الجدران والحركة الظاهرة مقترحات قابلة للتعديل، وليست اشتراطات رسمية.')
 (generate/'index.html').write_text(html)
 for file in ('client-bridge.js','embedded-runtime.js','worker-session.js','automatic-runtime.js'):shutil.copyfile(ROOT/'lovable_integration'/file,generate/file)
 app=(generate/'app.js').read_text()
 app=app.replace("function persist(){try", "function persist(){if(window.AntEmbedded)return;try")
 app=app.replace("let chosen;try{chosen=JSON.parse", "let chosen=window.AntEmbedded?{revision:state.chosenRevision}:null;try{if(!window.AntEmbedded)chosen=JSON.parse")
 app=app.replace("اخترت هذا المقترح. الاختيار محفوظ في هذا المتصفح، ولا يمثل اعتمادًا تنفيذيًا.","اخترت هذا المقترح مؤقتًا في هذه الجلسة؛ لا يمثل حفظ مشروع في الخادم أو اعتمادًا تنفيذيًا.")
 app=app.replace("try{localStorage.setItem('ant-general-last-050'", "try{if(!window.AntEmbedded)localStorage.setItem('ant-general-last-050'")
 app=app.replace("try{localStorage.setItem('ant-general-choice-050'", "try{state.chosenRevision=state.selected.model_revision_id;if(!window.AntEmbedded)localStorage.setItem('ant-general-choice-050'")
 app=app.replace("renderResult();$('engine-state').textContent='اكتمل", "renderResult();window.AntEmbeddedNotify?.(result);$('engine-state').textContent='اكتمل")
 app=app.replace("$('municipality').addEventListener('change',()=>{$('city').value=''", "$('municipality').addEventListener('change',()=>{if(!window.AntEmbedded)$('city').value=''")
 app=app.replace("async function init(){let saved;", "async function init(){if(window.AntEmbedded){document.documentElement.dataset.embedded='1';state.rooms=[];renderRooms();await loadJurisdictions();aiStatus();return;}let saved;")
 app=app.replace(" }init();", " }window.AntEmbeddedReady=init();\n window.AntLoadClientBrief=b=>{restore(b);changed();};window.AntApplyAutomaticResult=result=>{if(result.candidates[0])restore(result.candidates[0].brief);state.result=result;state.stale=false;renderResult();};")
 assert 'window.AntLoadClientBrief=b=>' in app
 (generate/'app.js').write_text(app)
 client=(generate/'static-client.js').read_text()
 client=client.replace("if('caches' in window)","if(!window.AntEmbedded&&'caches' in window)").replace("if('caches'in window)","if(!window.AntEmbedded&&'caches'in window)")
 old="const nativeFetch=window.fetch.bind(window);const worker=new Worker('./worker.js?v=062');"
 assert old in client
 client=client.replace(old,"const nativeFetch=window.fetch.bind(window);const engine=window.AntWorkerSession.create({url:'./worker.js?v=062',store});window.AntStopEngine=reason=>engine.stop(reason);")
 client=client.replace("if(path==='/api/v3/design')","if(path==='/api/v3/auto-design')return Response.json(await call('automatic',{options:JSON.parse(options.body)}));if(path==='/api/v3/design')")
 client=client.replace("const pending=new Map(),urls=new Map(),sessionFiles=new Map();let seq=0;", "const urls=new Map(),sessionFiles=new Map();")
 start=client.index('  function call(');end=client.index('  async function read(',start)
 client=client[:start]+"  const call=(operation,extra={})=>engine.call(operation,extra);\n"+client[end:]
 start=client.index('  worker.onmessage=');end=client.index('  window.AntFiles=',start)
 client=client[:start]+client[end:]
 worker=(generate/'worker.js').read_text()
 marker="    await ready;"
 assert marker in worker
 worker=worker.replace(marker,marker+"\n    if(data.operation==='initialize'){postMessage({id:data.id,ready:true});return;}")
 worker=worker.replace('from backend.design.general_engine import generate_general','from backend.design.general_engine import generate_general\nfrom backend.design.architect_planner import ClientIntent,generate_automatic')
 worker=worker.replace("data.operation==='general'", "(data.operation==='general'||data.operation==='automatic')")
 worker=worker.replace("python.runPython('json.dumps(generate_general(VillaBrief(**json.loads(options_json))),ensure_ascii=False)')", "python.runPython(data.operation==='automatic'?'json.dumps(generate_automatic(ClientIntent(**json.loads(options_json))),ensure_ascii=False)':'json.dumps(generate_general(VillaBrief(**json.loads(options_json))),ensure_ascii=False)')")
 (generate/'worker.js').write_text(worker)
 (generate/'static-client.js').write_text(client)
 for file in ('app.js','static-client.js','embedded-runtime.js','client-bridge.js','worker-session.js','worker.js','automatic-runtime.js'):subprocess.run(['node','--check',str(generate/file)],check=True)
 source=ROOT/'lovable_integration/lovable-src'
 if source.exists():shutil.copytree(source,a.output/'src',dirs_exist_ok=True)
 manifest={'engine_version':'0.6.2-general','engine_sha256':hashlib.sha256((studio/'engine.zip').read_bytes()).hexdigest(),'same_origin_assets':True,'runtime_paid_services':False,'client_data_persistence':'memory; parent draft expires in sessionStorage','executive_approval':False}
 (target/'integration.json').write_text(json.dumps(manifest,indent=2)+'\n')
 print(json.dumps(manifest))

if __name__=='__main__':main()
