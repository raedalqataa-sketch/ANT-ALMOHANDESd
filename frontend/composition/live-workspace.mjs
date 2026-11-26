/** Only the latest real search frame is retained; no replay or synthetic motion. */
export function createLiveWorkspace(ui,draw){
 let latest,active=false,paused=false,timer,lastPaint=0,bounds,total=0;
 const names={composition:'توزيع الكتل',openings:'الأبواب والنوافذ',furnishing:'تجربة التأثيث',checking:'التحقق المعماري'};
 function paint(){
  clearTimeout(timer);timer=null;if(!latest||paused)return;
  ui.canvas.replaceChildren(draw(latest,bounds));lastPaint=Date.now();
  ui.stage.textContent=latest.label||names[latest.phase]||'تكوين المسقط';ui.steps.setAttribute('data-phase',latest.phase);
  const count=latest.rooms_by_floor[0].filter(r=>r.request_id).length;
  ui.count.textContent=`${count} / ${total} فراغات في التكوين المعروض`;
 }
 function accepted(n){ui.accepted.textContent=`${n} مقترحات مقبولة في النتائج أدناه`;}
 ui.toggle.onclick=()=>{paused=!paused;ui.toggle.textContent=paused?'استئناف العرض الحي':'إيقاف العرض الحي';ui.toggle.setAttribute('aria-pressed',String(paused));if(paused){clearTimeout(timer);timer=null;}else paint();};
 return {
  start(brief){clearTimeout(timer);timer=null;latest=null;paused=false;active=true;lastPaint=0;
   const t=brief.wall_thickness??.2,s=brief.setbacks||{};bounds=brief.setbacks?[-1,-1,brief.plot_width-s.west-s.east-t+2,brief.plot_depth-s.north-s.south-t+2]:undefined;
   total=Array.isArray(brief.rooms)?brief.rooms.reduce((n,r)=>n+(r.count??1),0):0;ui.container.hidden=false;ui.canvas.replaceChildren();ui.canvas.textContent='تجهيز المحرك… سيظهر التكوين هنا عند بدء البحث.';
   ui.stage.textContent='تجهيز بيئة التوليد';ui.steps.setAttribute('data-phase','loading');ui.summary.textContent='يعرض أحد التكوينات الجاري بحثها؛ قد تتحرك الكتل أو تُستبدل أثناء البحث. هذه المعاينة لا تعني قبول التصميم.';ui.count.textContent=`0 / ${total} فراغات في التكوين المعروض`;accepted(0);ui.toggle.textContent='إيقاف العرض الحي';ui.toggle.setAttribute('aria-pressed','false');
  },
  update(frame){if(!active||frame?.schema!=='assl-preview-1'||frame.verified!==false)return;latest=frame;if(paused)return;
   const delay=250-(Date.now()-lastPaint);if(delay<=0)paint();else if(!timer)timer=setTimeout(paint,delay);
  },
  accepted,
  finish(n,failed=false){active=false;clearTimeout(timer);timer=null;paint();accepted(n);
   ui.summary.textContent=failed?'توقفت المحاولة. التكوين المعروض مسودة؛ المقترحات المقبولة فقط متاحة في النتائج أدناه.':n?'اكتمل البحث. التكوين المعروض مسودة من مراحل العمل؛ اختر مقترحًا مقبولًا من النتائج أدناه.':'لم ينتج البحث مقترحًا مقبولًا. التكوين المعروض آخر مسودة فقط، ولا يصلح للتصدير.';
  },
  hide(){active=false;clearTimeout(timer);timer=null;latest=null;ui.container.hidden=true;}
 };
}
