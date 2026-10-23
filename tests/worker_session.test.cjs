const {test}=require('node:test');
const assert=require('node:assert/strict');
const {create}=require('../lovable_integration/worker-session.js');
class Worker {
 static instances=[];
 constructor(){this.messages=[];this.terminated=false;Worker.instances.push(this);}
 postMessage(data){this.messages.push(data);}
 terminate(){this.terminated=true;}
 async emit(data){await this.onmessage?.({data});}
}
function setup(extra={}){Worker.instances=[];return create({url:'engine-worker',WorkerClass:Worker,...extra});}
test('cold cancellation never executes the cancelled design and reuses the loading runtime',async()=>{
 const engine=setup();const cancelled=engine.call('general',{options:{name:'old'}});const rejected=assert.rejects(cancelled,/أُوقف/);
 const worker=Worker.instances[0];assert.deepEqual(worker.messages,[{id:0,operation:'initialize'}]);
 engine.stop();await rejected;assert.equal(worker.terminated,false);
 const retry=engine.call('general',{options:{name:'new'}});assert.equal(Worker.instances.length,1);
 await worker.emit({id:0,ready:true});assert.equal(worker.messages.length,2);assert.equal(worker.messages[1].options.name,'new');
 await worker.emit({id:worker.messages[1].id,result:'actual result'});assert.equal(await retry,'actual result');
});
test('warm cancellation terminates execution and a late response cannot resolve a new request',async()=>{
 const engine=setup();const first=engine.call('general');const worker=Worker.instances[0];await worker.emit({id:0,ready:true});
 const staleHandler=worker.onmessage;const oldId=worker.messages[1].id;const rejected=assert.rejects(first,/أُوقف/);engine.stop();await rejected;assert.equal(worker.terminated,true);
 const next=engine.call('general');const replacement=Worker.instances[1];await staleHandler({data:{id:oldId,result:'stale'}});
 await replacement.emit({id:0,ready:true});await replacement.emit({id:replacement.messages[1].id,result:'new'});assert.equal(await next,'new');
});
test('initialization errors are explicit and retry uses a fresh runtime',async()=>{
 const engine=setup();const first=engine.call('general');const rejected=assert.rejects(first,/runtime missing/);await Worker.instances[0].emit({id:0,error:'runtime missing'});await rejected;assert.equal(Worker.instances[0].terminated,true);
 const next=engine.call('general');const worker=Worker.instances[1];await worker.emit({id:0,ready:true});await worker.emit({id:worker.messages[1].id,result:42});assert.equal(await next,42);
});
test('cancellation during file registration cannot report a successful stale result',async()=>{
 let release;const engine=setup({store:()=>new Promise(r=>release=r)});const first=engine.call('general');const worker=Worker.instances[0];await worker.emit({id:0,ready:true});
 const handling=worker.emit({id:worker.messages[1].id,result:'stale',files:[]});const rejected=assert.rejects(first,/أُوقف/);engine.stop();await rejected;release();await handling;
});
test('a cold timeout rejects the request and never queues its design after readiness',async()=>{
 const engine=setup({timeoutMs:10});const pending=engine.call('general');await assert.rejects(pending,/مدة الانتظار/);const worker=Worker.instances[0];await worker.emit({id:0,ready:true});assert.equal(worker.messages.length,1);engine.stop();
});


test('a timeout emits only a safe timeout code; a user cancellation stays silent',async()=>{
 const captured=[];
 globalThis.AntTelemetry={report:(code,stage)=>captured.push([code,stage])};
 try{
  const timed=setup({timeoutMs:8});const expired=timed.call('general');
  await assert.rejects(expired,/مدة الانتظار/);
  assert.deepEqual(captured,[['ENGINE_TIMEOUT','timeout']]);
  timed.stop();
  const manual=setup();const interrupted=manual.call('general');manual.stop();
  await assert.rejects(interrupted,/أُوقف/);
  assert.equal(captured.length,1);
 }finally{delete globalThis.AntTelemetry;}
});
test('failure creating a Worker reports safe transport code without exposing exception text',async()=>{
 const captured=[];
 globalThis.AntTelemetry={report:(code,stage)=>captured.push([code,stage])};
 class BrokenWorker {constructor(){throw Error('customer-private-input');}}
 try{
  const engine=setup({WorkerClass:BrokenWorker});
  await assert.rejects(engine.call('general'),/customer-private-input/);
  assert.deepEqual(captured,[['ENGINE_WORKER_FAILED','worker']]);
 }finally{delete globalThis.AntTelemetry;}
});
