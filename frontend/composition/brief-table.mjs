/* Table adapter only. Geometry, program support and acceptance stay in Python. */
const clone=value=>JSON.parse(JSON.stringify(value));
export const KINDS={majlis:'مجلس',dining:'صالة طعام',living:'صالة عائلية',bedroom:'غرفة نوم',master:'غرفة نوم رئيسية',kitchen:'مطبخ',bathroom:'حمام ومغاسل',storage:'مستودع',office:'مكتب',laundry:'غسيل'};
const faces={south:'جنوب',east:'شرق',north:'شمال',west:'غرب'};
export const FIELDS=[
 ['project_name','اسم المشروع','text',null,null,'فيلا جديدة'],
 ['plot_width','عرض الأرض (م)','number',8,60,''],['plot_depth','عمق الأرض (م)','number',8,80,''],
 ['entrance_face','جهة الشارع الرئيسي',faces,null,null,'south'],
 ...Object.entries(faces).map(([key,label])=>['setbacks.'+key,'ارتداد '+label+' (م)','number',0,20,'']),
 ['floors','عدد الأدوار',{'1':'أرضي فقط','2':'أرضي وأول — خارج نطاق التكوين الحالي'},null,null,2],
 ['main_entry_width','عرض الباب الرئيسي الصافي (م)','number',.9,2.4,1],
 ['entry_plinth_height_m','ارتفاع جلسة المبنى (م)','number',0,1.2,0],
 ['wall_thickness','سماكة الجدار (م)','number',.15,.4,.2],
 ['corridor_width','عرض الحركة الأدنى (م)','number',1.2,2.4,1.5],
 ['floor_height','ارتفاع الدور (م)','number',2.8,3.8,3.2],
 ['dining_seats','مقاعد كل صالة طعام',{'4':'4','6':'6','8':'8','10':'10','12':'12'},null,null,6],
 ['compact_core','نوع الدرج',{'false':'درج منحني','true':'درج U'},null,null,false],
 ['country','الدولة',{SA:'السعودية',YE:'اليمن'},null,null,'SA']
];
function at(object,path){return path.split('.').reduce((v,k)=>v?.[k],object);}
function put(object,path,value){const keys=path.split('.');let p=object;for(const k of keys.slice(0,-1))p=p[k]??={};p[keys.at(-1)]=value;}
function number(value,label,min,max,integer=false){
 const text=String(value??'').trim().replace(/[٠-٩]/g,c=>String(c.charCodeAt(0)-1632)).replace(/[۰-۹]/g,c=>String(c.charCodeAt(0)-1776)).replace(/[٫,]/g,'.');
 if(!text||!/^[-+]?(?:\d+(?:\.\d*)?|\.\d+)$/.test(text))throw Error('أدخل قيمة صحيحة: '+label);
 const result=Number(text);
 if(!Number.isFinite(result)||result<min||result>max||(integer&&!Number.isInteger(result)))throw Error(`${label}: القيمة المطلوبة بين ${min} و${max}${integer?' وبعدد صحيح':''}.`);
 return result;
}
export function toTableState(brief){
 if(!brief||typeof brief!=='object'||!Array.isArray(brief.rooms)||!Array.isArray(brief.guest_groups??[]))throw Error('ملف برنامج العميل يجب أن يحتوي قائمة غرف صحيحة.');
 const known=new Set(brief.rooms.map(r=>r.id));
 if((brief.guest_groups||[]).some(g=>!Array.isArray(g.rooms)||g.rooms.some(id=>!known.has(id))))throw Error('مجموعة الضيافة في الملف تشير إلى غرفة غير موجودة.');
 return {fields:Object.fromEntries(FIELDS.map(([key,,,,,fallback])=>[key,at(brief,key)??fallback])),rooms:brief.rooms.map(r=>({...clone(r),group_ids:(brief.guest_groups||[]).filter(g=>g.rooms.includes(r.id)).map(g=>g.id)})),groups:clone(brief.guest_groups||[])};
}
const siteField=key=>key==="plot_width"||key==="plot_depth"||key.startsWith("setbacks.");
export function tableToBrief(base,state,{withoutSite=false}={}){
 const b=clone(base);
 if(withoutSite){delete b.plot_width;delete b.plot_depth;delete b.setbacks;}
 for(const[key,label,type,min,max]of FIELDS){
  if(withoutSite&&siteField(key))continue;
  let v=state.fields[key];
  if(type==='number')v=number(v,label,min,max);
  else if(type==='text'){v=String(v??'').trim();if(!v||v.length>100)throw Error('أدخل اسم مشروع من 1 إلى 100 حرف.');}
  else {if(!Object.hasOwn(type,String(v)))throw Error('اختر قيمة صحيحة: '+label);if(key==='compact_core')v=String(v)==='true';else if(['floors','dining_seats'].includes(key))v=Number(v);}
  put(b,key,v);
 }
 if(!withoutSite&&(b.setbacks.east+b.setbacks.west+b.wall_thickness>=b.plot_width||b.setbacks.north+b.setbacks.south+b.wall_thickness>=b.plot_depth))throw Error('الارتدادات لا تترك مساحة بناء داخل الأرض.');
 if(!state.rooms.length||state.rooms.length>30)throw Error('أدخل من 1 إلى 30 صفًا للغرف.');
 const ids=new Set(),groupIds=new Set(state.groups.map(g=>g.id));
 if(groupIds.size!==state.groups.length||state.groups.length>12)throw Error('مجموعات الضيافة مكررة أو أكثر من الحد المتاح.');
 b.rooms=state.rooms.map(row=>{
  const {group_ids,...room}=clone(row);const label=String(room.name??'').trim();
  if(!/^[a-zA-Z0-9_-]{1,45}$/.test(room.id)||ids.has(room.id))throw Error('معرّف غرفة مكرر أو غير صحيح.');ids.add(room.id);
  if(!label||label.length>65)throw Error('اكتب اسمًا لكل غرفة من 1 إلى 65 حرفًا.');room.name=label;
  if(!Object.hasOwn(KINDS,room.kind))throw Error('اختر نوع الغرفة: '+label);
  for(const[k,min,max,int]of [['floor',0,1,true],['count',1,12,true],['min_area',3,100,false],['min_side',1.4,10,false],['capacity',0,2,true]])room[k]=number(room[k]??(k==='capacity'?0:k==='count'?1:undefined),label+' — '+({floor:'الدور',count:'العدد',min_area:'المساحة',min_side:'أصغر ضلع',capacity:'عدد أفراد النوم'}[k]),min,max,int);
  if(room.floor>=b.floors)throw Error('دور الغرفة خارج عدد أدوار المبنى: '+label);
  if((group_ids||[]).some(id=>!groupIds.has(id)))throw Error('مجموعة ضيافة غير موجودة للغرفة: '+label);
  room.ensuite_for=room.ensuite_for||null;return room;
 });
 const by=Object.fromEntries(b.rooms.map(r=>[r.id,r]));
 for(const r of b.rooms)if(r.ensuite_for){const parent=by[r.ensuite_for];if(r.kind!=='bathroom'||!parent||!['bedroom','master'].includes(parent.kind)||parent.floor!==r.floor||parent.count!==1||r.count!==1)throw Error('حدد غرفة نوم واحدة في الدور نفسه للحمام الخاص: '+r.name);}
 b.guest_groups=state.groups.map(g=>{
  if(!/^[a-zA-Z0-9_-]{1,45}$/.test(g.id)||(g.entry&&!/^[a-zA-Z0-9_-]{1,45}$/.test(g.entry)))throw Error('معرّف مجموعة أو مدخل غير صحيح.');
  const rooms=state.rooms.filter(r=>r.group_ids?.includes(g.id)).map(r=>r.id);
  if(!rooms.length)throw Error('اختر غرفًا لمجموعة الضيافة أو احذف المجموعة الفارغة.');
  if(rooms.some(id=>!['majlis','dining','bathroom','storage'].includes(by[id].kind)))throw Error('مجموعة الضيافة تقبل المجلس والطعام والحمام والمستودع فقط.');
  const ordered=[...(g.rooms||[]).filter(id=>rooms.includes(id)),...rooms.filter(id=>!(g.rooms||[]).includes(id))];
  return {...clone(g),rooms:ordered};
 });
 for(const relation of b.spatial_requirements||[])if(!by[relation.source]||!by[relation.target])throw Error('إحدى العلاقات المحفوظة تشير إلى غرفة محذوفة. أعد الغرفة أو حدّث ملف العلاقات.');
 return b;
}
const groupName=(group,index)=>({men:'ضيافة الرجال',women:'ضيافة النساء'}[group.id]||`ضيافة ${index+1}`);
export function createBriefTable({container,document:doc=globalThis.document,onChange=()=>{}}){
 let base,state,fields={},roomRefs=[],groupRefs=[],controls=[],locked=false,withoutSite=false;
 const el=(tag,text)=>{const e=doc.createElement(tag);if(text!==undefined)e.textContent=text;return e;};
 function input(value,label,options=null){const e=el(options?'select':'input');e.setAttribute('aria-label',label);if(options){const list={...options};if(value!==undefined&&!Object.hasOwn(list,String(value)))list[value]=String(value)+' — محفوظ';for(const[v,text]of Object.entries(list)){const o=el('option',text);o.value=v;e.append(o);}}else{e.type='text';e.inputMode='decimal';}e.value=String(value??'');e.disabled=locked;e.oninput=()=>onChange();e.onchange=()=>onChange();controls.push(e);return e;}
 function button(text,run){const e=el('button',text);e.type='button';e.className='secondary';e.disabled=locked;e.onclick=run;controls.push(e);return e;}
 function table(headers){const wrapper=el('div');wrapper.className='brief-table-scroll';const t=el('table'),head=el('thead'),tr=el('tr');t.className='brief-table';for(const title of headers){const th=el('th',title);th.scope='col';tr.append(th);}head.append(tr);const body=el('tbody');t.append(head,body);wrapper.append(t);container.append(wrapper);return body;}
 const row=(body,cells)=>{const tr=el('tr');for(const value of cells){const td=el('td');td.append(value);tr.append(td);}body.append(tr);};
 function raw(){return {fields:Object.fromEntries(Object.entries(fields).map(([k,e])=>[k,e.value])),rooms:roomRefs.map(({source,refs,checks})=>({...source,...Object.fromEntries(Object.entries(refs).map(([k,e])=>[k,e.value])),group_ids:checks.filter(q=>q.input.checked).map(q=>q.id)})),groups:groupRefs.map(({source,entry})=>({...source,entry:entry.value||null}))};}
 function changeStructure(fn){state=raw();fn();render();onChange();}
 function render(){
  container.replaceChildren();controls=[];fields={};roomRefs=[];groupRefs=[];
  const assumed=FIELDS.filter(([key])=>['floors','main_entry_width','entry_plinth_height_m'].includes(key)&&at(base,key)==null);
  if(assumed.length){const values=assumed.map(([key,label,type,,,fallback])=>label+': '+(typeof type==='object'?type[String(fallback)]:fallback));const notice=el('p','الملف المستورد لا يحدد بعض القيم؛ استُخدمت القيم الأصلية التالية: '+values.join('، ')+'. راجعها في الجدول قبل التوليد.');notice.className='brief-scope';notice.setAttribute('role','status');container.append(notice);}
  container.append(el('h3','بيانات الأرض والمداخل'));const land=table(['البيان','القيمة']);
  for(const[key,label,type]of FIELDS){const e=input(state.fields[key],label,typeof type==='object'?type:null);if(type==='text')e.inputMode='text';e.setAttribute('data-field',key);fields[key]=e;row(land,[el('span',label),e]);if(siteField(key))e.closest('tr').hidden=withoutSite;}
  container.append(el('h3','مجموعات الضيافة ومداخلها'));
  const groups=table(['المجموعة','المدخل','تعديل']);
  state.groups.forEach((g,index)=>{const options={'':'مدخل مستقل لهذه المجموعة'};state.groups.forEach((other,j)=>{options[other.entry||other.id]='المدخل: '+groupName(other,j);});const e=input(g.entry??'',groupName(g,index)+' — المدخل',options);groupRefs.push({source:g,entry:e});row(groups,[el('span',groupName(g,index)),e,button('حذف المجموعة',()=>changeStructure(()=>{state.groups=state.groups.filter(q=>q.id!==g.id);state.rooms.forEach(r=>r.group_ids=r.group_ids.filter(id=>id!==g.id));}))]);});
  container.append(button('إضافة مجموعة ضيافة',()=>changeStructure(()=>{let n=1;while(state.groups.some(g=>g.id==='guest-'+n))n++;state.groups.push({id:'guest-'+n,entry:null,rooms:[]});})));
  container.append(el('h3','جدول الغرف المطلوبة'));const body=table(['اسم الفراغ','النوع','العدد','المساحة الدنيا م²','أصغر ضلع م','الدور','أفراد النوم','مجموعة الضيافة','الحمام خاص بـ','تعديل']);
  const beds={'':'ليس حمامًا خاصًا'};state.rooms.filter(r=>['bedroom','master'].includes(r.kind)).forEach(r=>beds[r.id]=r.name);
  state.rooms.forEach(r=>{
   const refs={name:input(r.name,'اسم الفراغ'),kind:input(r.kind,r.name+' — النوع',KINDS),count:input(r.count??1,r.name+' — العدد'),min_area:input(r.min_area,r.name+' — المساحة الدنيا'),min_side:input(r.min_side,r.name+' — أصغر ضلع'),floor:input(r.floor??0,r.name+' — الدور',{'0':'الأرضي','1':'الأول'}),capacity:input(r.capacity??0,r.name+' — أفراد النوم',{'0':'غير محدد','1':'1','2':'2'}),ensuite_for:input(r.ensuite_for??'',r.name+' — حمام خاص',beds)};
   refs.name.inputMode='text';refs.kind.onchange=()=>changeStructure(()=>{});
   const member=el('div');member.className='brief-memberships';const checks=[];
   state.groups.forEach((g,index)=>{const label=el('label'),check=el('input');check.type='checkbox';check.checked=(r.group_ids||[]).includes(g.id);check.disabled=locked;check.setAttribute('aria-label',r.name+' — '+groupName(g,index));check.onchange=()=>onChange();controls.push(check);checks.push({id:g.id,input:check});label.append(check,el('span',groupName(g,index)));member.append(label);});
   const remove=button('حذف',()=>{const snapshot=raw();if(snapshot.rooms.some(q=>q.ensuite_for===r.id)||(base.spatial_requirements||[]).some(q=>q.source===r.id||q.target===r.id)){onChange('لا يمكن حذف غرفة مرتبطة بحمام خاص أو علاقة محفوظة. حدّث الارتباط أولًا.');return;}changeStructure(()=>{state.rooms=state.rooms.filter(q=>q.id!==r.id);});});
   roomRefs.push({source:r,refs,checks});row(body,[...['name','kind','count','min_area','min_side','floor','capacity'].map(k=>refs[k]),member,refs.ensuite_for,remove]);
  });
  container.append(button('إضافة غرفة',()=>changeStructure(()=>{let n=1;while(state.rooms.some(r=>r.id==='room-'+n))n++;state.rooms.push({id:'room-'+n,name:'غرفة جديدة',kind:'bedroom',floor:0,count:1,min_area:16,min_side:3.5,capacity:1,ensuite_for:null,group_ids:[]});})));
  if(base.spatial_requirements?.length)container.append(el('p',`توجد ${base.spatial_requirements.length} علاقة مكانية مستوردة؛ ستُرسل كاملة مع البرنامج. إدارة العلاقات الإضافية من الملف المستورد.`));
 }
 return {load(brief){const next=toTableState(brief);base=clone(brief);state=next;render();onChange();},read(){if(!base)throw Error('انتظر تحميل برنامج العميل.');return tableToBrief(base,raw(),{withoutSite});},setWithoutSite(value){withoutSite=value;for(const[key,e]of Object.entries(fields))if(siteField(key))e.closest("tr").hidden=value;onChange();},setDisabled(value){locked=value;controls.forEach(e=>e.disabled=value);container.setAttribute('aria-busy',String(value));}};
}
