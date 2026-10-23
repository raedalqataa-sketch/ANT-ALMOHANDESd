const {test}=require('node:test');
const assert=require('node:assert/strict');
const {create}=require('../lovable_integration/telemetry.js');
const handler=require('../api/telemetry.js');
function browser(config={}) {
  const calls=[];const listeners={};
  const runtime={location:{origin:'https://example.test'},fetch:(...args)=>{calls.push(args);return Promise.resolve({ok:true});},addEventListener:(name,fn)=>{listeners[name]=fn;}};
  return {calls,listeners,client:create(config,runtime)};
}
test('monitoring is disabled by default and does not affect client generation',()=>{
  const {calls,client}=browser();assert.equal(client.isActive(),false);
  assert.equal(client.report('ENGINE_GENERATION_FAILED','generation'),false);assert.equal(calls.length,0);
});
test('only a same-origin TLS telemetry endpoint can be configured',()=>{
  const config={enabled:true,endpoint:'https://attacker.test/api/telemetry'};
  assert.equal(browser(config).client.isActive(),false);
  assert.equal(browser({enabled:true,endpoint:'/api/telemetry?token=x'}).client.isActive(),false);
  assert.equal(browser({enabled:true,endpoint:'/api/telemetry'}).client.isActive(),true);
});
test('safe schema, allowlist, deduplication and unhandled error protection',()=>{
  const {calls,client,listeners}=browser({enabled:true,endpoint:'/api/telemetry'});
  assert.equal(client.report('ENGINE_GENERATION_FAILED','generation'),true);
  assert.equal(client.report('ENGINE_GENERATION_FAILED','generation'),false);
  assert.equal(client.report('custom-message with private customer info','generation'),false);
  listeners.error({error:new Error('private data')});
  assert.equal(calls.length,2);
  assert.equal(calls[0][0],'https://example.test/api/telemetry');
  assert.deepEqual(JSON.parse(calls[0][1].body),{schema:1,app:'ant-almohandes',event:'client_engine_error',code:'ENGINE_GENERATION_FAILED',stage:'generation'});
  assert.equal(calls[0][1].credentials,'omit');
  assert.equal(calls[0][1].mode,'same-origin');
});
function mockRequest(overrides={}) {
  const result={code:200,headers:{},setHeader(k,v){this.headers[k]=v;return this;},status(k){this.code=k;return this;},end(){this.ended=true;return this;}};
  const req={method:'POST',headers:{origin:'https://example.test','content-type':'application/json'},body:{schema:1,app:'ant-almohandes',event:'client_engine_error',code:'ENGINE_WORKER_FAILED',stage:'worker'},...overrides};
  return {req,result};
}
test('endpoint fails closed on missing origin configuration and rejects unexpected data',()=>{
  const previous=process.env.ANT_MONITORING_ORIGIN;
  try {
    delete process.env.ANT_MONITORING_ORIGIN;
    let {req,result}=mockRequest();handler(req,result);assert.equal(result.code,403);
    process.env.ANT_MONITORING_ORIGIN='https://example.test';
    ({req,result}=mockRequest({body:{schema:1,app:'ant-almohandes',event:'client_engine_error',code:'ENGINE_WORKER_FAILED',stage:'worker',plot:'private'}}));
    handler(req,result);assert.equal(result.code,400);
    ({req,result}=mockRequest({headers:{origin:'https://other.test','content-type':'application/json'}}));
    handler(req,result);assert.equal(result.code,403);
  } finally {if(previous===undefined)delete process.env.ANT_MONITORING_ORIGIN;else process.env.ANT_MONITORING_ORIGIN=previous;}
});
test('endpoint logs only schema-approved codes',()=>{
  const prev=process.env.ANT_MONITORING_ORIGIN;process.env.ANT_MONITORING_ORIGIN='https://example.test';
  const log=console.error;let output='';console.error=msg=>output=msg;
  try {const {req,result}=mockRequest();handler(req,result);assert.equal(result.code,204);assert.deepEqual(JSON.parse(output),{level:'error',service:'ant-almohandes',event:'client_engine_error',code:'ENGINE_WORKER_FAILED',stage:'worker'});}finally{console.error=log;if(prev===undefined)delete process.env.ANT_MONITORING_ORIGIN;else process.env.ANT_MONITORING_ORIGIN=prev;}
});


test('timeout code is supported but arbitrary error text is never sent',()=>{
 const {client,calls}=browser({enabled:true,endpoint:'/api/telemetry'});
 assert.equal(client.report('ENGINE_TIMEOUT','timeout'),true);
 assert.equal(client.report('ENGINE_TIMEOUT: private example','timeout'),false);
 assert.equal(calls.length,1);
 const body=JSON.parse(calls[0][1].body);
 assert.equal(body.code,'ENGINE_TIMEOUT');
 assert.equal(JSON.stringify(body).includes('private example'),false);
});
