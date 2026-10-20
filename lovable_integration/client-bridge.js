'use strict';
/* Pure conversion: unknown client values stay blank until reviewed in the engine UI. */
((root,factory)=>{const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.AntClientBridge=api;})(globalThis,()=>{
 const kinds=new Set(['master','bedroom','majlis','living','dining','kitchen','bathroom','office','storage','laundry']);
 const faces={north:'north',south:'south',east:'east',west:'west','شمال':'north','شمالية':'north','جنوب':'south','جنوبية':'south','شرق':'east','شرقية':'east','غرب':'west','غربية':'west'};
 function convert(draft){
  if(!draft||typeof draft!=='object'||!draft.data||!draft.counts||!draft.hospitality||!Array.isArray(draft.rooms))throw Error('صيغة متطلبات العميل غير صالحة.');
  if(JSON.stringify(draft).length>200000)throw Error('حجم المتطلبات أكبر من الحد المتاح.');
  const supplied=key=>draft.unknown?.[key]?'':String(draft.data[key]??'').trim();
  const number=key=>{const value=supplied(key);if(!value)return '';const n=Number(value);if(!Number.isFinite(n)||n<=0)throw Error('قيمة غير صالحة في '+key);return n;};
  const floors=number('floors');if(floors!==''&&(!Number.isInteger(floors)||floors>2))throw Error('محرك الفلل يدعم أرضيًا أو أرضيًا وأول فقط، مع ملحق اختياري.');
  if(supplied('housing')&&!['فيلا','بيت مستقل'].includes(supplied('housing')))throw Error('هذا المحرك لفيلا أو بيت مستقل؛ الشقق والدوبلكس والوحدات المتعددة تحتاج محركًا مختلفًا، ولم نغير طلبك.');
  const warnings=['أكمل أدوار الغرف وحدود مساحاتها وأضلاعها وسعة النوم، والارتدادات والجهات، قبل التوليد. لم نفترض قيمًا للبيانات الناقصة.','المخططات مسودات؛ الاشتراطات الخاصة بالقطعة والمطابقة الشاملة للكود والاعتماد التنفيذي تحتاج مراجعة.'];
  const rooms=[];
  function add(id,name,kind,count,width,length){
   if(!Number.isInteger(count)||count<1||count>12)throw Error('عدد غير مدعوم لـ«'+name+'»: من 1 إلى 12 لكل صف.');
   if(!String(name).trim()||String(name).length>65)throw Error('راجع اسم الفراغ.');
   const dimensions=[width,length].map(v=>v==null||v===''?'':Number(v));
   if(dimensions.some(v=>v!==''&&(!Number.isFinite(v)||v<=0)))throw Error('أبعاد غير صالحة لـ«'+name+'».');
   const complete=dimensions.every(v=>v!=='');
   rooms.push({id,name,kind:kinds.has(kind)?kind:'',floor:'',count,
    min_area:complete?dimensions[0]*dimensions[1]:'',min_side:complete?Math.min(...dimensions):'',
    capacity:['bedroom','master'].includes(kind)?'':0});
   if(complete)warnings.push('«'+name+'»: حُولت الأبعاد المدخلة إلى حد أدنى للمساحة وأقصر ضلع؛ راجع الجدول. لا يضمن البحث الأبعاد نفسها حرفيًا.');
   if(!kinds.has(kind))warnings.push('اختر التصنيف الهندسي صراحةً لـ«'+name+'»؛ لم نفترض نوع الخدمة.');
  }
  for(const [key,name,kind]of [['bedroom','غرف نوم','bedroom'],['bathroom','حمامات الأسرة','bathroom'],['kitchen','مطبخ','kitchen'],['dining','طعام','dining'],['living','معيشة','living'],['services','خدمات','']]){
   const count=draft.counts[key]??0;if(count===0)continue;add('client-'+key,name,kind,count);
  }
  if(draft.hospitality.majlis)add('client-majlis','مجلس رجال','majlis',1);
  if(draft.hospitality.guestLobby){if(!draft.hospitality.majlis)throw Error('موزع الضيوف يحتاج مجلس رجال.');add('client-guest-wc','حمام ضيوف','bathroom',1);}
  draft.rooms.forEach((r,i)=>add('client-custom-'+i,r.name,r.room_type,r.quantity,r.width_m,r.length_m));
  if(rooms.length>30||rooms.reduce((n,r)=>n+r.count,0)>36)throw Error('هذا الإصدار يدعم 30 صفًا و36 فراغًا كحد أقصى.');
  const notes=['مصدر المتطلبات: معالج العميل في Lovable.'];
  for(const [key,label]of [['north','اتجاه الشمال المقدم'],['streets','الشوارع كما وردت'],['boundaries','الحدود كما وردت'],['setbacks','الارتدادات النصية الموردة'],['source','مصدر الارتدادات'],['family','أفراد الأسرة'],['housing','نوع المسكن'],['type','نوع المشروع']])if(supplied(key))notes.push(label+': '+supplied(key));
  if(supplied('type')&&supplied('type')!=='سكني')throw Error('المحرك الحالي لتوليد الفلل السكنية؛ لا يصمم المشروع التجاري أو متعدد الاستخدامات.');
  if(supplied('setbacks'))warnings.push('الارتدادات النصية محفوظة؛ أدخل مقادير الجهات الأربع يدويًا، مع مصدرها. لم نفسر النص كاشتراط معتمد.');
  if(draft.imported?.fields?.length){warnings.push('حُفظت جميع حقول Excel في واجهة العميل وتنزيل المتطلبات. البنود غير المحولة إلى جدول الغرف أو إعدادات التوليد تحتاج مراجعة؛ لا يُعد التوليد إثباتًا لاستيفائها.');notes.push('متطلبات Excel غير المحولة إلى قيود هندسية: '+draft.imported.fields.length+' حقلًا؛ راجع ملف متطلبات العميل الأصلي.');}
  let text=notes.join('\n');if(text.length>4000){text='المتطلبات النصية طويلة؛ تفاصيلها محفوظة بواجهة العميل وتنزيل المتطلبات. البنود غير المحولة إلى قيود هندسية تحتاج مراجعة.\n'+text.slice(0,3500);warnings.push('نُقل ملخص النص الطويل للمحرك، وتبقى النسخة الكاملة في متطلبات العميل القابلة للتنزيل.');}
  return {brief:{project_name:supplied('title'),plot_width:number('width'),plot_depth:number('depth'),floors,
   city:supplied('location'),municipality:'',entrance_face:faces[supplied('frontage')]||'',
   setbacks:{north:'',south:'',east:'',west:''},boundary_widths:{},rooms,notes:text,
   separate_guest_entry:!!(draft.hospitality.menEntrance||draft.hospitality.guestLobby),
   automatic_features:{},regulatory_geometry:null},warnings};
 }
 return {convert};
});
