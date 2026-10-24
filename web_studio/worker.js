'use strict';
importScripts('./runtime/pyodide.js');
let python;
let ready;
async function initialize(){
  python=await loadPyodide({indexURL:new URL('./runtime/',self.location.href).href});
  const manifest=await (await fetch('./manifest.json')).json();
  await python.loadPackage(['pydantic','numpy','pillow','fonttools','pyparsing','charset-normalizer','six']);
  if(manifest.engineering_wasm_packages?.length)await python.loadPackage(manifest.engineering_wasm_packages);
  python.FS.mkdirTree('/project');python.FS.mkdirTree('/wheels');
  for(const file of manifest.pure_wheels)python.FS.writeFile('/wheels/'+file,new Uint8Array(await (await fetch('./wheels/'+file)).arrayBuffer()));
  python.FS.writeFile('/engine.zip',new Uint8Array(await (await fetch('./engine.zip')).arrayBuffer()));
  python.runPython(`
import sys,site,zipfile,pathlib,json
for wheel in pathlib.Path('/wheels').glob('*.whl'):
    with zipfile.ZipFile(wheel) as archive: archive.extractall(site.getsitepackages()[0])
with zipfile.ZipFile('/engine.zip') as archive: archive.extractall('/project')
sys.path.insert(0,'/project')
from backend.design.service import get_project,design
from backend.design.models import DesignOptions
from backend.design.requirements import import_brief
`);
}
self.onmessage=async({data})=>{
  try{
    if(!ready)ready=initialize();
    await ready;
    if(data.operation==='project'){
      const result=JSON.parse(python.runPython('json.dumps(get_project(),ensure_ascii=False)'));
      postMessage({id:data.id,result});return;
    }
    if(data.operation==='import'){
      if(data.bytes.byteLength>5000000)throw Error('حجم الملف أكبر من 5 ميغابايت');
      const binary=python.toPy(new Uint8Array(data.bytes));python.globals.set('brief_bytes',binary);
      try{const result=JSON.parse(python.runPython('json.dumps(import_brief(bytes(brief_bytes)),ensure_ascii=False)'));postMessage({id:data.id,result})}
      finally{python.globals.delete('brief_bytes');binary.destroy()}
      return;
    }
    if(data.operation==='design'){
      python.globals.set('options_json',JSON.stringify(data.options));
      const result=JSON.parse(python.runPython('json.dumps(design(DesignOptions(**json.loads(options_json))),ensure_ascii=False)'));
      const files=[];
      for(const model of result.candidates){
        for(const path of [...Object.values(model.previews),...Object.values(model.downloads)]){
          const name=path.split('/').pop();const bytes=python.FS.readFile('/project/outputs/'+name);
          files.push({path,bytes});python.FS.unlink('/project/outputs/'+name);
        }
      }
      postMessage({id:data.id,result,files},files.map(f=>f.bytes.buffer));return;
    }
    throw Error('عملية غير مدعومة');
  }catch(error){
    console.error('Local engine operation failed',error);
    const lines=String(error).trim().split('\n');
    postMessage({id:data.id,error:lines.slice(-4).join('\n')});
  }
};
