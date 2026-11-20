'use strict';
window.AntStartAutomatic=async(draft,send)=>{
 const main=document.querySelector('main');
 document.querySelector('.workspace').hidden=true;
 const box=document.createElement('section');box.id='auto-progress';box.className='note';box.setAttribute('role','status');
 const title=document.createElement('h2');title.textContent='نحوّل احتياجات أسرتك إلى برنامج معماري…';box.append(title);
 const text=document.createElement('p');text.textContent='نقترح الغرف والأبعاد والارتدادات، ثم نبحث ونفحص البدائل. قد يستغرق تحميل أدوات الرسم أول مرة قليلًا.';box.append(text);
 main.prepend(box);delete document.documentElement.dataset.clientAwaiting;
 window.AntOriginalClientDraft=structuredClone(draft);
 send('IMPORTED',{roomCount:0,roomRows:0,automatic:true});
 new ResizeObserver(()=>send('RESIZE',{height:Math.min(20000,Math.max(900,document.documentElement.scrollHeight))})).observe(document.body);
 const response=await fetch('/api/v3/auto-design?constitution_v2=true&generation_v3=true&generation_v4=true',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(draft.intent)});
 const result=await response.json();
 if(!response.ok){
  const detail=typeof result.detail==='string'?result.detail:'';
  title.textContent='تعذّر إكمال التوليد';
  text.textContent='راجع تفاصيل الخطأ في صفحة المتطلبات ثم أعد المحاولة.';
  if(detail.includes('المساحة المتاحة بعد الارتدادات أصغر من نطاق البحث الحالي')){
   throw Error('المساحة المتاحة بعد الارتدادات أصغر من نطاق البحث. راجع أبعاد الأرض والاحتياجات ثم جرّب من جديد.');
  }
  throw Error('تعذر إكمال التوليد. تحقق من بيانات الأرض والأسرة أو أعد فتح المحرك.');
 }
 window.AntApplyAutomaticResult(result);
 const explanation=document.createElement('details');explanation.className='result-details results-explanation';
 const overview=document.createElement('summary');overview.textContent='البرنامج المقترح والافتراضات والفحوص التفصيلية';explanation.append(overview);
 document.querySelector('#results').after(explanation);box.remove();
 const program=document.createElement('div');program.id='auto-program';
 const dl=document.createElement('dl');dl.style.cssText='display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:16px;margin:20px 0';
 for(const row of result.planning.program){const cell=document.createElement('div'),name=document.createElement('dt'),value=document.createElement('dd');name.textContent=row.name+' × '+row.count;value.textContent=(row.floor?'الدور الأول':'الدور الأرضي')+' · مساحة مقترحة من '+row.min_area+' م²';cell.append(name,value);dl.append(cell);}program.append(dl);
 const selection=result.planning.design_selection;if(selection){const decision=document.createElement('p');decision.textContent=`قارنّا ${selection.search_variants_examined} توزيعات أولية، واخترنا ${selection.validated_count} بدائل مختلفة اجتازت الفحوص المتاحة. تجد سبب اختيار كل بديل ومزاياه مع معاينته.`;program.append(decision);}
 // Real V2 audit from selected geometries, not an invented architectural rating.
 const auditHost=document.createElement('section');auditHost.setAttribute('aria-label','تدقيق الدستور المعماري V2');
 const h3=document.createElement('h3');h3.textContent='تدقيق الدستور المعماري V2 · نتائج هندسية أولية';auditHost.append(h3);
 const overall=result.planning.architecture_constitution_v2;
 if(overall){
  const summary=document.createElement('p');
  summary.textContent=`فُحصت ${overall.audited_count} توزيعات مرشحة عبر 16 بوابة. المخرجات تظل مسودات؛ المطابقة البلدية والإنشاء والإنارة والصيانة تحتاج مراجعات مستقلة.`;
  auditHost.append(summary);
  result.candidates.forEach((candidate,index)=>{
   const audit=candidate.constitution_v2;if(!audit)return;
   const counts=audit.gates.reduce((acc,g)=>(acc[g.status]=(acc[g.status]||0)+1,acc),{});
   const details=document.createElement('details'),heading=document.createElement('summary');
   heading.textContent=`البديل ${index+1}: ${counts.PASS||0} اجتاز فحوصًا جزئية · ${counts.REVIEW||0} يحتاج مراجعة · ${counts.FAIL||0} إخفاقات · ${counts.NOT_APPLICABLE||0} غير منطبق`;
   details.append(heading);
   const list=document.createElement('ul');
   for(const gate of audit.gates){
    const item=document.createElement('li');
    const name={PASS:'اجتاز فحصًا جزئيًا',FAIL:'فشل',REVIEW:'يحتاج مراجعة',NOT_APPLICABLE:'غير منطبق'}[gate.status]||gate.status;
    item.textContent=`${gate.label_ar} — ${name}. ${gate.reason_ar}`;
    list.append(item);
   }
   details.append(list);auditHost.append(details);
  });
  const caution=document.createElement('p');caution.textContent='هذا التدقيق لا يثبت أن القواعد الـ143 نُفذت آليًا بالكامل، ولا يُعد اعتمادًا تنفيذيًا.';auditHost.append(caution);
 }else{const note=document.createElement('p');note.textContent='لم يتوفر تقرير V2 لهذه النسخة؛ الفحوص السابقة فقط فعالة.';auditHost.append(note);}
 program.append(auditHost);
 const v3=result.planning?.generation_v3;
 if(v3){
  const report=document.createElement('section');report.setAttribute('aria-label','بحث المساقط الوظيفي V3');
  const title=document.createElement('h3');title.textContent='محرك V3 — العلاقات الوظيفية وتشكيل الكتلة المتغيّر';report.append(title);
  const summary=document.createElement('p');
  summary.textContent='بحث المحرك تشكيلات متعددة التراجع وأجنحة متغيرة، وقاس مسارات الأبواب وعلاقات المعيشة والطعام والخدمة. هذه حلول هندسية أولية، وليست نماذج إنشائية أو اعتمادًا قانونيًا.';
  report.append(summary);
  const rounds=v3.automatic_repair||[];
  const repair=document.createElement('p');
  repair.textContent=rounds.length?
   `أجرى المحرك ${rounds.length} جولة إعادة بحث إصلاحية. لم يحذف الغرف المطلوبة ولم يخفض معايير الفحص.`:
   'لم تستدعِ نتيجة البحث جولة إصلاح إضافية.';
  report.append(repair);
  for(const [i,m] of result.candidates.entries()){
   const info=m.design_option?.functional_evidence;
   if(!info)continue;
   const p=document.createElement('p');
   p.textContent=`البديل ${i+1}: قِيسَت ${info.evaluated_routes} علاقة حركة، ومسارات غير متصلة: ${info.unreachable_routes}. تفاصيل الفحص أسفل التقرير.`;
   report.append(p);
   const readiness=m.executive_readiness;
   if(readiness){
    const approval=document.createElement('details'),caption=document.createElement('summary');
    caption.textContent=`البديل ${i+1} — اعتماد تنفيذي: غير ممنوح، ${readiness.required_signoffs.length} مراجعات لازمة`;
    approval.append(caption);
    const list=document.createElement('ul');
    for(const requirement of readiness.required_signoffs){
     const row=document.createElement('li');row.textContent=requirement.label_ar+' — لم يُتحقق بعد';list.append(row);
    }
    approval.append(list);report.append(approval);
   }
  }
  program.append(report);
 }
 const v4=result.planning?.generation_v4;
 if(v4){
  const section=document.createElement('section');section.setAttribute('aria-label','فحص المسارات والإصلاح V4');
  const heading=document.createElement('h3');heading.textContent='مسارات حول الأثاث وإصلاح هندسي محلي';section.append(heading);
  const note=document.createElement('p');note.textContent=`فُحصت المسارات مع الأبواب والأثاث. قُبل ${v4.local_repairs_accepted} إصلاح من ${v4.local_repair_attempts} محاولة محلية؛ المحاولات التي لم تحسّن الفحص أُلغيت. لا تزال بعض وظائف V4 قيد التطوير.`;section.append(note);
  for(const [i,m] of result.candidates.entries()){
   const info=m.functional_program_v4;if(!info)continue;
   const row=document.createElement('p');row.textContent=`البديل ${i+1}: ${info.movement.routes.length} مسار مقاس؛ ${info.movement.unreachable.length} غير متصل. فحص شبكي تقريبي وليس اعتماد إتاحة وصول.`;section.append(row);
  }
  const source=document.createElement('p');source.textContent='المراجع الفعالة: 6 مشروعات و19 صورة؛ استُبعد المقترحان الثاني والخامس. مصفوفة القواعد وأدلة الإصلاح محفوظة في JSON؛ القواعد غير المتحققة تبقى للمراجعة.';section.append(source);program.append(section);
 }
 const reasoning=document.createElement('ul');for(const reason of result.planning.reasoning){const item=document.createElement('li');item.textContent=reason;reasoning.append(item);}program.append(reasoning);
 const assumptions=document.createElement('details'),summary=document.createElement('summary');summary.textContent='كيف حُسبت الارتدادات؟ وما الافتراضات التي تحتاج مراجعة؟';assumptions.append(summary);
 for(const warning of result.planning.warnings){const p=document.createElement('p');p.textContent=warning;assumptions.append(p);}
 const numbers=document.createElement('p');numbers.textContent='الارتدادات المقترحة بالمتر: '+Object.entries(result.planning.setbacks.values).map(([k,v])=>({north:'شمال',south:'جنوب',east:'شرق',west:'غرب'}[k])+': '+v).join('، ');assumptions.append(numbers);
 if(draft.intent.country==='SA'){const source=document.createElement('a');source.href='https://momah.gov.sa/ar/node/15715';source.target='_blank';source.rel='noopener';source.textContent='المرجع السعودي المتاح للارتدادات · يلزم اعتماد البلدية';assumptions.append(source);}else{const caution=document.createElement('p');caution.textContent='اليمن: الارتدادات قيم تصميمية افتراضية؛ لم تُتحقق اشتراطات المحافظة والسلطة المختصة.';assumptions.append(caution);}program.append(assumptions);explanation.append(program);
 window.AntEmbeddedNotify(result);
};
