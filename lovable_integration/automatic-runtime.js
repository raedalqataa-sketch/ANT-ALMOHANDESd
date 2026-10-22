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
 const response=await fetch('/api/v3/auto-design',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(draft.intent)});
 const result=await response.json();if(!response.ok)throw Error(typeof result.detail==='string'?result.detail:'راجع بيانات الأرض والأسرة؛ تعذر تكوين برنامج ضمن حدود المحرك.');
 window.AntApplyAutomaticResult(result);
 title.textContent='البرنامج الذي اقترحناه لأسرتك';text.textContent='أنت قدمت بيانات الأرض والأسرة؛ هذه قرارات مقترحة من النظام وليست مدخلات طلبنا منك حسابها.';
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
  const title=document.createElement('h3');title.textContent='محرك V3 — العلاقات الوظيفية وتشكيل الأجنحة';report.append(title);
  const summary=document.createElement('p');
  summary.textContent='بحث المحرك تكوينات بأجنحة متغيرة، وقاس مسارات الأبواب وعلاقات المعيشة والطعام والخدمة. القبول ما زال خاضعًا للفحوص الهندسية؛ النتائج مسودات للمراجعة.';
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
  }
  program.append(report);
 }
 const reasoning=document.createElement('ul');for(const reason of result.planning.reasoning){const item=document.createElement('li');item.textContent=reason;reasoning.append(item);}program.append(reasoning);
 const assumptions=document.createElement('details'),summary=document.createElement('summary');summary.textContent='كيف حُسبت الارتدادات؟ وما الافتراضات التي تحتاج مراجعة؟';assumptions.append(summary);
 for(const warning of result.planning.warnings){const p=document.createElement('p');p.textContent=warning;assumptions.append(p);}
 const numbers=document.createElement('p');numbers.textContent='الارتدادات المقترحة بالمتر: '+Object.entries(result.planning.setbacks.values).map(([k,v])=>({north:'شمال',south:'جنوب',east:'شرق',west:'غرب'}[k])+': '+v).join('، ');assumptions.append(numbers);
 if(draft.intent.country==='SA'){const source=document.createElement('a');source.href='https://momah.gov.sa/ar/node/15715';source.target='_blank';source.rel='noopener';source.textContent='المرجع السعودي المتاح للارتدادات · يلزم اعتماد البلدية';assumptions.append(source);}else{const caution=document.createElement('p');caution.textContent='اليمن: الارتدادات قيم تصميمية افتراضية؛ لم تُتحقق اشتراطات المحافظة والسلطة المختصة.';assumptions.append(caution);}program.append(assumptions);box.append(program);
 window.AntEmbeddedNotify(result);
};
