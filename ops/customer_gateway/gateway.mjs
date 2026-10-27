/** Server-only Gemini adviser. Never accepts a key, model, URL, code or rules from a client. */
const families=['adaptive','freeform','spine','cross','cluster','meander'];
const policies=['social_front','family_front','service_aligned','relationship_aware'];
const cores=['front','rear'],guests=['linear','side_spine','compact_side'];
const exact=(o,keys)=>o&&typeof o==='object'&&!Array.isArray(o)&&Object.keys(o).every(k=>keys.includes(k))&&keys.every(k=>Object.hasOwn(o,k));
export function validPlan(p){return exact(p,['options'])&&Array.isArray(p.options)&&p.options.length>=3&&p.options.length<=6&&p.options.every(o=>exact(o,['family','policy','core_position','guest_strategy'])&&families.includes(o.family)&&policies.includes(o.policy)&&cores.includes(o.core_position)&&guests.includes(o.guest_strategy))&&new Set(p.options.map(o=>JSON.stringify([o.family,o.policy,o.core_position,o.guest_strategy]))).size===p.options.length}
const schema={type:'OBJECT',properties:{options:{type:'ARRAY',minItems:3,maxItems:6,items:{type:'OBJECT',properties:{family:{type:'STRING',enum:families},policy:{type:'STRING',enum:policies},core_position:{type:'STRING',enum:cores},guest_strategy:{type:'STRING',enum:guests}},required:['family','policy','core_position','guest_strategy']}}},required:['options']};
const json=(data,status=200)=>Response.json(data,{status,headers:{'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}});
function config(env){return {configured:Boolean(env.GEMINI_API_KEY),freeTierConfirmed:env.GEMINI_FREE_TIER_CONFIRMED==='true',model:env.GEMINI_MODEL||'',connected:false,billingVerification:'OWNER_CONFIRMATION_ONLY',hosted:true}}
function validContext(c){
 if(!exact(c,['site','program','design_priority','output_level','mandatory','limitations'])&&!exact(c,['site','program']))return false;
 const s=c.site;
 if(!exact(s,['width_m','depth_m','country','floors','setbacks','entrance_face'])||!['SA','YE'].includes(s.country)||![1,2].includes(s.floors)||!Number.isFinite(s.width_m)||s.width_m<8||s.width_m>60||!Number.isFinite(s.depth_m)||s.depth_m<8||s.depth_m>80||!['north','south','east','west'].includes(s.entrance_face))return false;
 if(!exact(s.setbacks,['north','south','east','west'])||Object.values(s.setbacks).some(v=>!Number.isFinite(v)||v<0||v>30))return false;
 return Array.isArray(c.program)&&c.program.length>0&&c.program.length<=30&&c.program.every(r=>exact(r,['id','kind','floor','count','min_area','min_side','capacity','name'])&&typeof r.id==='string'&&r.id.length<=70&&typeof r.name==='string'&&r.name.length<=65&&['master','bedroom','majlis','living','dining','kitchen','bathroom','office','storage','laundry'].includes(r.kind)&&[0,1].includes(r.floor)&&Number.isInteger(r.count)&&r.count>=1&&r.count<=12&&Number.isFinite(r.min_area)&&r.min_area>0&&Number.isFinite(r.min_side)&&r.min_side>0&&Number.isInteger(r.capacity)&&r.capacity>=0&&r.capacity<=12);
}
export function createGateway(fetcher=fetch){
 const recent=new Map(); // local defensive throttle, not a billing/quota guarantee
 return {async fetch(req,env={}){
  const url=new URL(req.url),path=url.pathname;
  if(path==='/api/client/gemini/status'&&req.method==='GET')return json(config(env));
  if(!['/api/client/gemini/propose','/api/client/gemini/connection'].includes(path))return json({detail:'Unknown endpoint'},404);
  if(!req.headers.get('oai-authenticated-user-id'))return json({detail:'سجّل الدخول بحساب ChatGPT لاستخدام Gemini.',code:'SIGN_IN_REQUIRED'},401);
  if(req.headers.get('Origin')&&req.headers.get('Origin')!==url.origin)return json({detail:'Origin not allowed'},403);
  const conf=config(env);
  if(!conf.configured)return json({detail:'لم يُضف GEMINI_API_KEY إلى أسرار استضافة الموقع. مفتاح GitHub Actions منفصل.',code:'MISSING_HOSTED_SECRET'},503);
  if(path.endsWith('/connection')&&req.method==='GET'){
   try{const r=await fetcher('https://generativelanguage.googleapis.com/v1beta/models?pageSize=100',{headers:{'x-goog-api-key':env.GEMINI_API_KEY},signal:AbortSignal.timeout(15000)});if(!r.ok)return json({detail:`Gemini HTTP ${r.status}`,connected:false,http_status:r.status},r.status===429?429:502);
    const d=await r.json();const available=(d.models||[]).filter(m=>m.supportedGenerationMethods?.includes('generateContent')).map(m=>m.name.replace(/^models\//,''));return json({...conf,connected:true,configuredModelAvailable:available.includes(conf.model),models:available,http_status:200,inference_executed:false});
   }catch{return json({detail:'تعذر الاتصال بـGemini خلال المهلة.',connected:false},502)}
  }
  if(req.method!=='POST')return json({detail:'Method not allowed'},405);
  if(!conf.freeTierConfirmed||!/^gemini-[\w.-]*flash[\w.-]*$/.test(conf.model))return json({detail:'يلزم نموذج Flash محدد وتأكيد صاحب المشروع توفر فئته المجانية لهذا الحساب؛ لا طلب توليد.',code:'FREE_TIER_UNCONFIRMED'},412);
  if(!req.headers.get('Content-Type')?.includes('application/json'))return json({detail:'JSON required'},415);
  if(Number(req.headers.get('Content-Length')||0)>30000)return json({detail:'Request too large'},413);
  let body;try{const raw=await req.text();if(raw.length>30000)return json({detail:'Request too large'},413);body=JSON.parse(raw)}catch{return json({detail:'Malformed JSON'},422)}
  if(!exact(body,['consent','context'])||body.consent!==true||!validContext(body.context))return json({detail:'طلب غير صالح؛ يلزم برنامج من المحرك وموافقة إرسال بياناته فقط.'},422);
  const user=req.headers.get('oai-authenticated-user-id'),now=Date.now();if(now-(recent.get(user)||0)<15000)return json({detail:'انتظر قليلًا قبل إعادة الطلب.',code:'RATE_LIMIT'},429);
  if(recent.size>2000)for(const [k,t]of recent)if(now-t>60000)recent.delete(k);recent.set(user,now);
  const started=Date.now();
  try{
   // Only quantified site/program data is sent; no arbitrary notes or provider code.
   const prompt='Return 3 to 6 genuinely different supported spatial search configurations. Geometry and all legal rules are enforced by the existing engine, not you. Preserve program, compact guest access separate from family, furniture practicality, daylight and short useful movement. Do not invent regulatory numbers. Search options are advice, not accepted floor plans.\n'+JSON.stringify({site:body.context.site,program:body.context.program});
   const r=await fetcher('https://generativelanguage.googleapis.com/v1beta/models/'+conf.model+':generateContent',{method:'POST',headers:{'Content-Type':'application/json','x-goog-api-key':env.GEMINI_API_KEY},signal:AbortSignal.timeout(30000),body:JSON.stringify({contents:[{role:'user',parts:[{text:prompt}]}],generationConfig:{responseMimeType:'application/json',responseSchema:schema,maxOutputTokens:1600,temperature:.5}})});
   if(!r.ok)return json({detail:`تعذر طلب Gemini: HTTP ${r.status}. لا استبدال بنتيجة محلية.`,http_status:r.status,request_count:1,code:'PROVIDER_ERROR'},r.status===429?429:502);
   const data=await r.json(),text=data.candidates?.[0]?.content?.parts?.map(p=>p.text||'').join('');let plan;try{plan=JSON.parse(text)}catch{return json({detail:'Gemini أعاد JSON غير صالح؛ لم تُنشأ هندسة.',code:'INVALID_PROVIDER_JSON'},502)}
   if(!validPlan(plan))return json({detail:'خيارات Gemini غير صالحة أو مكررة؛ لم تُنشأ هندسة.',code:'INVALID_PROVIDER_PLAN'},502);
   return json({plan,origin:'LIVE_GEMINI',model:conf.model,request_count:1,elapsed_ms:Date.now()-started,usage:data.usageMetadata||null,actual_cost_usd:null,cost_status:'not reported by Gemini API; owner-confirmed free tier',engineering_accepted:false});
  }catch{return json({detail:'انتهت مهلة Gemini أو تعذر الاتصال؛ لا إعادة تلقائية أو توليد بديل صامت.',code:'PROVIDER_TIMEOUT'},502)}
 }};
}
