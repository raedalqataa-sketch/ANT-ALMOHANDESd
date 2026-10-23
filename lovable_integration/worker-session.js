/* Queue design requests until Python is ready; cancel requests without aborting importScripts. */
(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  else root.AntWorkerSession=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(){
  'use strict';
  function report(code,stage){try{globalThis.AntTelemetry?.report(code,stage);}catch{}}
  function create({url,store=async()=>{},WorkerClass=globalThis.Worker,timeoutMs=600000}){
    let worker=null,ready=false,sequence=0;
    const pending=new Map();
    const cancelled='أُوقف الطلب؛ قد يكتمل تحميل ملفات التشغيل في الخلفية. يمكنك إعادة التوليد.';
    function rejectAll(reason){
      for(const request of pending.values()){clearTimeout(request.timer);request.reject(Error(reason));}
      pending.clear();
    }
    function dispose(){if(worker){worker.onmessage=null;worker.onerror=null;worker.terminate();}worker=null;ready=false;}
    function dispatch(id,request){
      if(request.sent)return;
      request.sent=true;
      try{worker.postMessage({id,operation:request.operation,...request.extra},request.extra.bytes?[request.extra.bytes]:[]);}
      catch(error){pending.delete(id);clearTimeout(request.timer);request.reject(error);}
    }
    function start(){
      if(worker)return;
      const current=worker=new WorkerClass(url);
      current.onmessage=async({data})=>{
        if(worker!==current)return;
        if(data.id===0){
          if(data.error){report('ENGINE_INITIALIZATION_FAILED','initialization');rejectAll(data.error);dispose();return;}
          if(data.ready!==true)return;
          ready=true;
          for(const [id,request] of pending)dispatch(id,request);
          return;
        }
        const request=pending.get(data.id);if(!request||!request.sent)return;
        try{
          if(data.error){report('ENGINE_GENERATION_FAILED','generation');throw Error(data.error);}
          await store(data.files);
          if(worker!==current||pending.get(data.id)!==request)return;
          pending.delete(data.id);clearTimeout(request.timer);request.resolve(data.result);
        }catch(error){
          if(pending.get(data.id)===request){report('ENGINE_RESULT_FAILED','result');pending.delete(data.id);clearTimeout(request.timer);request.reject(error);}
        }
      };
      current.onerror=()=>{if(worker!==current)return;report('ENGINE_WORKER_FAILED','worker');rejectAll('تعذر تشغيل المحرك في هذا المتصفح. أعد المحاولة أو جرّب متصفحًا حديثًا.');dispose();};
      current.postMessage({id:0,operation:'initialize'});
    }
    function stop(reason=cancelled){
      rejectAll(reason);
      // Terminating a cold worker interrupts synchronous importScripts with a browser NetworkError.
      // Its queue is now empty, so finishing initialization cannot run a cancelled design.
      if(ready)dispose();
    }
    function call(operation,extra={}){
      return new Promise((resolve,reject)=>{
        const id=++sequence;
        const timer=setTimeout(()=>stop('تجاوزت العملية مدة الانتظار؛ أعد المحاولة.'),timeoutMs);
        const request={resolve,reject,timer,operation,extra,sent:false};pending.set(id,request);
        try{start();if(ready)dispatch(id,request);}
        catch(error){rejectAll(error.message);dispose();}
      });
    }
    return {call,stop};
  }
  return {create};
});
