'use strict';
if(window.AntEmbedded){
 let nonce='';let accepted=false;let importing=false;
 const send=(type,data={})=>{if(nonce)parent.postMessage({channel:'ANT_VILLA_V1',nonce,type,...data},location.origin);};
 window.AntEmbeddedNotify=result=>send('RESULT',{candidates:result.candidates.map(m=>({family:m.candidate_id,revision:m.model_revision_id,reviewable:m.release.drawing_export_allowed,executive:false})),unavailable:result.unavailable});
 addEventListener('message',async event=>{
  if(event.source!==parent||event.origin!==location.origin)return;
  const message=event.data;
  if(!message||message.channel!=='ANT_VILLA_V1'||typeof message.nonce!=='string'||!/^[a-zA-Z0-9-]{8,80}$/.test(message.nonce))return;
  if(message.type==='HELLO'){
   nonce=message.nonce;
   try{await window.AntEmbeddedReady;send('READY',{engineVersion:'0.6.2-general'});}catch{send('ERROR',{error:'تعذر تجهيز واجهة المحرك. أعد المحاولة.'});}
   return;
  }
  if(message.nonce!==nonce||message.type!=='DRAFT'||accepted||importing)return;
  importing=true;
  try{
   if(message.draft?.mode==='automatic'){
    await window.AntEmbeddedReady;accepted=true;
    await window.AntStartAutomatic(message.draft,send);return;
   }
   const converted=AntClientBridge.convert(message.draft);
   await window.AntEmbeddedReady;
   window.AntLoadClientBrief(converted.brief);
   window.AntOriginalClientDraft=structuredClone(message.draft);
   const box=document.createElement('aside');box.id='client-transfer-notice';box.className='note';box.setAttribute('role','status');
   const title=document.createElement('h2');title.textContent='متطلبات العميل وصلت إلى المحرك';box.append(title);
   for(const warning of converted.warnings){const p=document.createElement('p');p.textContent=warning;box.append(p);}
   const reset=document.createElement('button');reset.type='button';reset.textContent='إيقاف / إعادة تشغيل المحرك';reset.onclick=()=>window.AntStopEngine?.();box.append(reset);
   document.querySelector('main').prepend(box);
   accepted=true;delete document.documentElement.dataset.clientAwaiting;
   send('IMPORTED',{roomRows:converted.brief.rooms.length,roomCount:converted.brief.rooms.reduce((n,r)=>n+r.count,0),warnings:converted.warnings});
   new ResizeObserver(()=>send('RESIZE',{height:Math.min(16000,Math.max(900,document.documentElement.scrollHeight))})).observe(document.body);
  }catch(error){window.AntTelemetry?.report('EMBEDDED_BRIDGE_FAILED','bridge');send('ERROR',{error:error.message||'تعذر نقل المتطلبات.'});}
  finally{importing=false;}
 });
}
