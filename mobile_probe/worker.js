/* All runtime files, wheels and project assets are packaged locally. */
importScripts('./runtime/pyodide.js');
let python;
function progress(text){postMessage({type:'progress',text})}
async function initialize(){
  const started=performance.now();
  progress('تحميل Python المحلي…');
  python=await loadPyodide({indexURL:new URL('./runtime/',self.location.href).href});
  const manifest=await (await fetch('./manifest.json')).json();
  await python.loadPackage(['pydantic','numpy','pillow','fonttools','pyparsing','charset-normalizer','six']);
  progress('تجهيز مكتبات التصدير والملفات المحلية…');
  python.FS.mkdirTree('/project');python.FS.mkdirTree('/wheels');
  for(const file of manifest.pure_wheels){
    python.FS.writeFile('/wheels/'+file,new Uint8Array(await (await fetch('./wheels/'+file)).arrayBuffer()));
  }
  python.FS.writeFile('/engine.zip',new Uint8Array(await (await fetch('./engine.zip')).arrayBuffer()));
  python.runPython(`
import sys,site,zipfile,pathlib,json,time
for wheel in pathlib.Path('/wheels').glob('*.whl'):
    with zipfile.ZipFile(wheel) as archive: archive.extractall(site.getsitepackages()[0])
with zipfile.ZipFile('/engine.zip') as archive: archive.extractall('/project')
sys.path.insert(0,'/project')
from backend.design.offline import run_local
`);
  postMessage({type:'ready',startup_ms:Math.round(performance.now()-started),python:python.runPython('sys.version'),runtime:python.version});
}
self.onmessage=async({data})=>{
 try{
  if(data.type==='initialize'){await initialize()}
  if(data.type==='run'){
    progress('توليد وفحص وتصدير داخل الجهاز…');
    python.globals.set('probe_options_json',JSON.stringify(data.options||{}));
    const started=performance.now();
    const result=JSON.parse(python.runPython(`json.dumps(run_local(json.loads(probe_options_json),'/outputs'),ensure_ascii=False)`));
    result.worker_elapsed_ms=Math.round(performance.now()-started);
    result.wasm_heap_bytes=python._module.HEAP8.byteLength;
    result.memory_scope='WASM_LINEAR_HEAP_ONLY_NOT_TOTAL_PROCESS_MEMORY';
    postMessage({type:'result',result});
  }
  if(data.type==='file'){
    if(!/^[a-z_]+(?:-(?:GF|FF))?\.(?:svg|pdf|dxf|json)$/.test(data.name))throw Error('اسم غير مسموح');
    const bytes=python.FS.readFile('/outputs/'+data.name);postMessage({type:'file',name:data.name,bytes},[bytes.buffer]);
  }
 }catch(error){postMessage({type:'error',message:String(error),stack:error.stack})}
};
