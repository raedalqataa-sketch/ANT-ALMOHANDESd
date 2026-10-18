'use strict';
/* Same design service as the Python API; computations and files stay in this browser. */
(()=>{
  const nativeFetch=window.fetch.bind(window);const worker=new Worker('./worker.js?v=041');
  const pending=new Map(),urls=new Map(),sessionFiles=new Map();let seq=0;
  const CACHE='ant-villa-studio-files-041';
  const mime=path=>path.endsWith('.svg')?'image/svg+xml':path.endsWith('.pdf')?'application/pdf':path.endsWith('.json')?'application/json':'application/dxf';
  const key=path=>new URL('./local-files/'+path.split('/').pop(),location.href).href;
  const valid=path=>/^\/api\/files\/[a-f0-9]{32}(?:-(?:GF|FF|SITE))?\.(?:pdf|dxf|json|svg)$/.test(path);
  function call(operation,extra={}){
    return new Promise((resolve,reject)=>{
      const id=++seq;pending.set(id,{resolve,reject});
      worker.postMessage({id,operation,...extra},extra.bytes?[extra.bytes]:[]);
    });
  }
  async function read(path){
    if(!valid(path))throw Error('رابط مراجعة غير صالح');
    if(sessionFiles.has(path))return sessionFiles.get(path);
    if('caches' in window){const cache=await caches.open(CACHE);const response=await cache.match(key(path));if(response){const blob=await response.blob();sessionFiles.set(path,blob);return blob}}
    throw Error('ملف المراجعة غير محفوظ في هذا المتصفح؛ أعد التوليد أو افتح النسخة التي نزّلتها.');
  }
  function register(path,blob){
    if(!urls.has(path))urls.set(path,URL.createObjectURL(blob));
    sessionFiles.set(path,blob);
  }
  async function hydrate(model){
    for(const path of [...Object.values(model.previews||{}),...Object.values(model.downloads||{})]){
      register(path,await read(path))
    }
  }
  async function store(files){
    let cache;try{if('caches'in window)cache=await caches.open(CACHE)}catch{}
    for(const f of files||[]){
      if(!valid(f.path))continue;
      const blob=new Blob([f.bytes],{type:mime(f.path)});register(f.path,blob);
      if(cache)try{await cache.put(key(f.path),new Response(blob,{headers:{'Content-Type':blob.type}}))}catch{console.warn('Browser persistence unavailable; current downloads remain available')}
    }
    if(cache){const keys=await cache.keys();for(const old of keys.slice(0,Math.max(0,keys.length-144)))await cache.delete(old)}
  }
  worker.onmessage=async({data})=>{
    const request=pending.get(data.id);if(!request)return;pending.delete(data.id);
    try{if(data.error)throw Error(data.error);await store(data.files);request.resolve(data.result)}catch(e){request.reject(e)}
  };
  worker.onerror=()=>{for(const p of pending.values())p.reject(Error('تعذر تشغيل المحرك في هذا المتصفح. أعد تحميل الصفحة أو جرّب متصفحًا حديثًا.'));pending.clear()};
  window.AntFiles={url:path=>urls.get(path)||'',read};
  window.fetch=async(input,options={})=>{
    const path=typeof input==='string'?input:input.url;
    try{
      if(path==='/api/v2/project')return Response.json(await call('project'));
      if(path==='/api/v2/design')return Response.json(await call('design',{options:JSON.parse(options.body)}));
      if(path==='/api/v2/import-excel'){
        const file=options.body.get('file');
        if(!file||!file.name.toLowerCase().endsWith('.xlsx'))throw Error('ارفع ملف XLSX');
        if(file.size>5000000)throw Error('حجم الملف أكبر من 5 ميغابايت');
        return Response.json(await call('import',{bytes:await file.arrayBuffer()}));
      }
      if(valid(path)){
        const blob=await read(path);const model=JSON.parse(await blob.text());await hydrate(model);
        return Response.json(model);
      }
    }catch(error){return Response.json({detail:error.message},{status:422})}
    return nativeFetch(input,options);
  };
})();
