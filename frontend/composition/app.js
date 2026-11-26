import {createBriefTable} from './brief-table.mjs?v=4';
import {createLiveWorkspace} from './live-workspace.mjs?v=1';
import {createProgressView} from './progress-view.mjs?v=3';
const $=id=>document.getElementById(id),mode=new URLSearchParams(location.search).get('strategy');
const modes={clustered:['التكوين السابق','كتل متداخلة · صالة مركزية وضيافة مستقلة'],relational:['تكوين تجريبي موقوف','أوقف هذا المسار للمراجعة المعمارية']};
const retired=mode==='relational';
let result,busy=false,fitRequest=null,inputMode="table",unresolvedText=false;
const clientTable=createBriefTable({container:$('client-form'),document,onChange:syncTablePreview});
function syncTablePreview(message){try{if(message)throw Error(message);$('brief').value=JSON.stringify(clientTable.read(),null,2);$('brief-errors').hidden=true;}catch(e){$('brief-errors').textContent=e.message;$('brief-errors').hidden=false;}}
function readBrief(){const brief=clientTable.read();$('brief').value=JSON.stringify(brief,null,2);return brief;}
function lockBrief(value){
 clientTable.setDisabled(value);$('brief-file').disabled=value;$('reset').disabled=value;
 for(const id of ['first-floor','without-site','table-mode','text-mode','program-description','adapt-program','vertical-program'])$(id).disabled=value;
 $('upper-program').disabled=value||!$('first-floor').checked;
}
function syncUpperProgram(){
 const enabled=$('first-floor').checked;
 $('upper-program').hidden=!enabled;
 $('upper-program').disabled=!enabled||busy;
}
$('first-floor').addEventListener('change',syncUpperProgram);
syncUpperProgram();
function readUpperProgram(){
 if(!$('first-floor').checked)return undefined;
 for(const id of ['upper-area','upper-side']){
  if(!$(id).reportValidity())throw Error('راجع أبعاد غرف الأبناء في الدور الأول.');
 }
 return {
  children:Number($('upper-children').value),
  child_area_m2:$('upper-area').valueAsNumber,
  child_min_side_m:$('upper-side').valueAsNumber
 };
}
function setInputMode(next){
 inputMode=next;
 $('text-program').hidden=next!=='text';
 $('table-mode').setAttribute('aria-pressed',String(next==='table'));
 $('text-mode').setAttribute('aria-pressed',String(next==='text'));
 $('generate').textContent=next==='text'?'تحويل الوصف ومراجعته':'توليد المقترحات';
}
$('table-mode').onclick=()=>setInputMode('table');
$('text-mode').onclick=()=>setInputMode('text');
$('without-site').onchange=()=>clientTable.setWithoutSite($('without-site').checked);
function loadBrief(brief){
 $('without-site').checked=!Object.hasOwn(brief,'plot_width');
 clientTable.setWithoutSite($('without-site').checked);
 clientTable.load(brief);
 unresolvedText=false;
 $('program-review').hidden=true;
}
async function reviewDescription(){
 let brief;
 try{brief=readBrief();}catch(error){status(error.message);return;}
 const text=$('program-description').value.trim();
 if(text.length<3){status('اكتب وصف البرنامج أولًا.');return;}
 busy=true;lockBrief(true);$('generate').disabled=true;
 try{
  const draft=await AntComposition.editor('/api/v3/concepts/program-draft',{brief,text});
  loadBrief(draft.brief);setInputMode('table');
  $('first-floor').checked=Boolean(draft.upper_program);
  if(draft.upper_program){
   $('upper-children').value=draft.upper_program.children;
   $('upper-area').value=draft.upper_program.child_area_m2;
   $('upper-side').value=draft.upper_program.child_min_side_m;
  }
  syncUpperProgram();
  const notice=$('program-review');
  notice.hidden=false;
  notice.textContent='راجع المساحات والأبعاد المقترحة ومجموعات الضيافة قبل التوليد.';
  unresolvedText=draft.unresolved.length>0;
  if(unresolvedText){
   const items=document.createElement('p');
   items.textContent='عبارات تحتاج مراجعة: '+draft.unresolved.join('، ');
   const label=document.createElement('label'),check=document.createElement('input');
   check.type='checkbox';check.onchange=()=>{unresolvedText=!check.checked;};
   label.append(check,' راجعت العبارات وأكملت الجدول حسب المطلوب');
   notice.append(items,label);
  }
  status('أصبحت مسودة الوصف جاهزة للمراجعة في الجدول.');
 }catch(error){status('تعذّر تحويل الوصف: '+error.message);}
 finally{busy=false;lockBrief(false);$('generate').disabled=false;}
}
function showFit(data, context){
 if(data.fit){
  fitRequest=context;
  const fit=data.fit;
  $('fit-message').textContent=(fit.classification==='PROVEN_ENVELOPE_SHORTFALL'
   ?'الأرض لا تستوعب البرنامج الحالي في الدور المطلوب.'
   :'التكوين الحالي لم يتسع داخل مساحة البناء المتاحة.')+
   ' أبعاد الحيّز بعد الارتدادات '+fit.available_envelope_width_m+' × '+fit.available_envelope_depth_m+' م.';
  $('fit-options').hidden=false;
 }else if(data.proposals?.length){
  $('fit-options').hidden=true;fitRequest=null;
 }
}
$('adapt-program').onclick=()=>generateDesign('adapt');
$('vertical-program').onclick=()=>generateDesign('vertical');
const progress=createProgressView({container:$('generation-progress'),ring:$('generation-ring'),value:$('generation-percent'),detail:$('generation-detail'),elapsed:$('generation-elapsed')});
const live=createLiveWorkspace({container:$('live-workspace'),canvas:$('live-canvas'),stage:$('live-stage'),steps:$('live-steps'),count:$('live-count'),accepted:$('live-accepted'),summary:$('live-summary'),toggle:$('live-toggle')},drawing);
function status(s){$('status').textContent=s;}
function hasCentralProgram(brief){const guests=new Set((brief.guest_groups||[]).flatMap(g=>g.rooms||[]));return (brief.rooms||[]).some(r=>r.kind==='dining'&&guests.has(r.id));}
function offerRelational(){
 $('switch-relational').hidden=true;
 status('هذا البرنامج يتجاوز نطاق التكوين الحالي. أُوقف التكوين التجريبي للمراجعة؛ احتفظ بالمدخلات كاملة، ولن تُحذف العلاقات أو الغرف لتجاوز هذا القيد.');
}
function showRetired(){
 $('retired-notice').hidden=false;$('generate').disabled=true;$('sample').disabled=true;
 status('أُوقف هذا التكوين بعد المراجعة المعمارية. المدخلات محفوظة في الجدول، ويمكن نقلها إلى الكتل المتداخلة؛ دعم البرامج الأوسع ما زال قيد التطوير.');
}
$('use-clustered').onclick=()=>{try{const brief=readBrief();sessionStorage.setItem('ant-composition-pending-brief',JSON.stringify(brief));location.href='/composition/?strategy=clustered';}catch{status('تعذر نقل المدخلات؛ راجع قيم الجدول واحتفظ بنسخة منها.');}};
$('switch-relational').hidden=true;
function download(value,name){const blob=new Blob([JSON.stringify(value,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),30000);}
function node(tag,attrs={},text){const e=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [k,v]of Object.entries(attrs))e.setAttribute(k,v);if(text)e.textContent=text;return e;}
function drawing(p,viewport){const objects=[...p.rooms_by_floor[0],...p.halls_by_floor[0]],points=objects.flatMap(r=>r.polygon).concat((p.entrance_platforms||[]).flatMap(e=>[...e.landing_polygon,...e.treads.flatMap(q=>q.polygon)])),xs=points.map(q=>q[0]),ys=points.map(q=>q[1]),minx=Math.min(...xs)-1,miny=Math.min(...ys)-1,w=Math.max(...xs)-minx+1,h=Math.max(...ys)-miny+1;const svg=node('svg',{viewBox:`${minx} ${miny} ${w} ${h}`,role:'img','aria-label':'تكوين المسقط المولّد'}),g=node('g',{transform:`translate(0 ${2*miny+h}) scale(1 -1)`});svg.append(g);if(viewport){svg.setAttribute('viewBox',viewport.join(' '));g.setAttribute('transform',`translate(0 ${2*viewport[1]+viewport[3]}) scale(1 -1)`);g.append(node('rect',{x:0,y:0,width:viewport[2]-2,height:viewport[3]-2,fill:'none',stroke:'#90a28c','stroke-width':.06,'stroke-dasharray':'.3 .2'}));}const colors={majlis:'#e8ddc9',living:'#dae7dc',kitchen:'#dbe6e4',bathroom:'#dfebec',dining:'#eee6d5',corridor:'#f1ede2',stair:'#ddd9cf'};for(const platform of p.entrance_platforms||[]){for(const polygon of [platform.landing_polygon,...platform.treads.map(q=>q.polygon)])g.append(node('polygon',{points:polygon.map(q=>q.join(',')).join(' '),fill:'#e9dfca',stroke:'#7c806c','stroke-width':.035}));for(const step of platform.riser_lines){const[a,b]=step.points;g.append(node('line',{x1:a[0],y1:a[1],x2:b[0],y2:b[1],stroke:'#646b5a','stroke-width':.035}));}}for(const r of objects){g.append(node('polygon',{points:r.polygon.map(q=>q.join(',')).join(' '),fill:colors[r.kind]||'#eee','stroke':'#2b3e34','stroke-width':.12}));const t=node('text',{x:r.x+r.width/2,y:(viewport?2*viewport[1]+viewport[3]:2*miny+h)-(r.y+r.depth/2),'text-anchor':'middle','font-size':.46,fill:'#263b31'},r.name||r.id);svg.append(t);}{for(const f of p.furniture_by_floor?.[0]||[]){if(f.physical===false)continue;g.append(node('rect',{x:f.x,y:f.y,width:f.width,height:f.depth,fill:'#b1bba8','fill-opacity':.55,stroke:'#637761','stroke-width':.035}));}for(const [kind,items]of Object.entries(p.opening_model_009?.[0]||{})){if(!['doors','windows'].includes(kind))continue;for(const o of items){const [x,y]=o.center,half=o.width/2;g.append(node('line',{x1:o.axis==='x'?x-half:x,y1:o.axis==='y'?y-half:y,x2:o.axis==='x'?x+half:x,y2:o.axis==='y'?y+half:y,stroke:kind==='doors'?'#bf793c':'#428a9a','stroke-width':.17}));if(kind==='doors'){const r=objects.find(q=>q.id===o.receiving_room);if(r){const a=o.axis==='x'?0:1,n=1-a,mid=n?r.y+r.depth/2:r.x+r.width/2,sign=mid>o.center[n]?1:-1,t=p.brief_snapshot?.wall_thickness||.2;for(const[index,width]of(o.leaf_widths||[o.width]).entries()){const h=[...o.center];h[n]+=sign*(t/2+.001);h[a]+=index?o.width/2:-o.width/2;const pts=[];for(let i=0;i<=18;i++){const q=[...h],theta=Math.PI/2*i/18;q[a]+=(index?-1:1)*width*Math.cos(theta);q[n]+=sign*width*Math.sin(theta);pts.push(q);}g.append(node('polyline',{points:pts.map(q=>q.join(',')).join(' '),fill:'none',stroke:'#637761','stroke-width':.025}));g.append(node('line',{x1:h[0],y1:h[1],x2:pts[18][0],y2:pts[18][1],stroke:'#263b31','stroke-width':.035}));}}}}}}for(const polygon of p.slab_openings_by_floor?.[0]||[])g.append(node('polygon',{points:polygon.map(q=>q.join(',')).join(' '),fill:'none',stroke:'#804b2d','stroke-width':.08,'stroke-dasharray':'.25 .17'}));return svg;}
function render(data,source,{pending=false}={}){if(!pending)result=data;$('results').replaceChildren();for(const [i,p]of (data.proposals||[]).entries()){const card=document.createElement('article');card.className='proposal';const h=document.createElement('h3');h.textContent=`المقترح ${i+1}`;card.append(h);
const hasUpper=p.rooms_by_floor.length>1||Boolean(p.first_floor);
if(hasUpper){
 const ground=document.createElement('h4');ground.textContent='الدور الأرضي';card.append(ground);
}
card.append(drawing(p));
if(hasUpper){
 const upper=document.createElement('h4');upper.textContent='الدور الأول';
 const openings=p.opening_model_009[1]||{doors:p.first_floor.doors,windows:p.first_floor.windows};
 card.append(upper,drawing({
  rooms_by_floor:[p.rooms_by_floor[1]||p.first_floor.rooms],
  halls_by_floor:[p.halls_by_floor[1]||[]], opening_model_009:[openings],
  slab_openings_by_floor:[p.slab_openings_by_floor?.[1]||[]], brief_snapshot:p.brief_snapshot,
 }));
 const layout=p.upper_wing_group?.join('');
 const descriptions={
  '111':'غرف الأبناء موزعة على ثلاثة جوانب من الصالة العائلية.',
  '210':'غرفتان للأبناء في جناح واحد والثالثة في الجناح المقابل.',
  '110':'غرفتا الأبناء في جناحين متقابلين على جانبي الصالة.',
  '011':'غرفتا الأبناء في جناحين متجاورين حول الصالة.'
 };
 if(descriptions[layout]){
  const note=document.createElement('p');
  note.textContent=descriptions[layout];
  card.append(note);
 }
}
if (p.functional_differences?.length) {
  const directions={south:'جنوب',north:'شمال',east:'شرق',west:'غرب'};
  const differences=document.createElement('p');
  differences.textContent=p.functional_differences.map(({space_id,direction})=>{
    const room=p.rooms_by_floor[0].find(item=>item.id===space_id);
    return (room?.name||space_id)+' '+directions[direction]+' الصالة العائلية';
  }).join(' · ');
  card.append(differences);
}
const info=document.createElement('p');
info.textContent=source+' · '+(p.brief_snapshot.setbacks?'مسقط مرتبط بالأرض':'دراسة من دون حدود أرض');
card.append(info);
const actions=document.createElement('div');
actions.className='actions';
const choose=document.createElement('button');
choose.textContent='اختيار هذا المسقط';
choose.disabled=pending;
choose.setAttribute('aria-expanded','false');
const next=document.createElement('div');
next.className='proposal-next';
next.hidden=true;
choose.onclick=()=>{next.hidden=!next.hidden;choose.setAttribute('aria-expanded',String(!next.hidden));};
function remember(){
 sessionStorage.setItem('ant-composition-pending-brief',$('brief').value);
 const upperState=Object.fromEntries(['upper-children','upper-area','upper-side'].map(id=>[id,$(id).value]));
 sessionStorage.setItem('ant-composition-return-results',JSON.stringify({
  data,source,upperState,firstFloor:$('first-floor').checked
 }));
}
const facade=document.createElement('button');
facade.textContent='توليد الواجهات الأربع';
facade.onclick=()=>{
 try{
  remember();
  const handoff=crypto.randomUUID();
  sessionStorage.setItem('ant-facade-plan:'+handoff,JSON.stringify(p));
  location.href='/facades/?plan='+handoff;
 }catch(error){status(error.message);}
};
const edit=document.createElement('button');
edit.textContent='تعديل المسقط المقترح';
edit.onclick=async()=>{
 edit.disabled=true;
 status('جارٍ فتح المسقط في المحرّر…');
 try{
  remember();
  const saved=await AntComposition.editor('/api/editor/sessions',{proposal:p});
  location.href='/editor/?session='+saved.session_id;
 }catch(error){status('تعذّر فتح المحرّر: '+error.message);edit.disabled=false;}
};
const json=document.createElement('button');
json.className='secondary';
json.textContent='تنزيل المسقط JSON';
json.onclick=()=>download(p,`ANT-${mode}-${i+1}.json`);
actions.append(choose,json);
next.append(facade,edit);
card.append(actions,next);
$('results').append(card);
}
if(data.recovery){
 const review=document.createElement('section');
 const p=document.createElement('p');
 if(data.recovery.action==='adapt'){
  p.textContent='هذا برنامج مقترح للمراجعة. بقي جدولك الأصلي محفوظًا.';
  const list=document.createElement('ul');
  for(const change of data.recovery.changes){
   const item=document.createElement('li');
   item.textContent=`${change.name}: ${change.old_area} ← ${change.new_area} م²، وأقصر ضلع ${change.old_side} ← ${change.new_side} م`;
   list.append(item);
  }
  review.append(p,list);
 }else{
  p.textContent='نُقل إلى الدور الأول: '+data.recovery.moved.join('، ')+'، بالأبعاد المطلوبة. أضاف التكوين العائلي مساحات الدور الأول المبيّنة على المسقط.';
  review.append(p);
 }
 $('results').prepend(review);
}
const count=data.proposals?.length||0, requested=data.requested_results||1;
status(pending?`ظهر ${count} مقترح مقبول.`:`${source}: ${count} مقترح اجتاز الفحص من أصل ${requested} مطلوب.${count<requested?'\n'+JSON.stringify(data.failures||data.rejected?.[0]||data.status):''}`);
}
async function reset(){const r=await fetch('/composition/reference-brief.json');loadBrief(await r.json());}
if(modes[mode]){$('generator').hidden=false;$('mode-label').textContent=modes[mode][0];$('mode-title').textContent=modes[mode][1];document.querySelector(`a[href="?strategy=${mode}"]`)?.classList.add('active');await reset();}
$('sample').onclick=async()=>{if(busy)return;live.hide();try{const r=await fetch(`/composition/${mode}-sample.json`);render(await r.json(),'نتائج المرجع المحفوظة — دون إعادة توليد');}catch(e){status(e.message);}};
$('reset').onclick=()=>{if(!busy)return reset();};$('save-brief').onclick=()=>{try{download(readBrief(),'ANT-client-brief.json');}catch(e){status(e.message);}};
$('brief-file').onchange=async e=>{if(busy||!e.target.files[0])return;try{loadBrief(JSON.parse(await e.target.files[0].text()));status('فُتح برنامجك في الجدول؛ راجع القيم قبل التوليد.');}catch(error){status('تعذر قراءة البرنامج: '+error.message);}};
async function generateDesign(fitAction){
 if(busy)return;
 if(retired){showRetired();return;}
 if(!fitAction&&inputMode==='text'){await reviewDescription();return;}
 if(!fitAction&&unresolvedText){status('راجع العبارات غير المفهومة وأكّد استكمال الجدول.');return;}
 let context;
 try{
  context=fitAction?fitRequest:{brief:readBrief(),upperProgram:readUpperProgram(),firstFloor:$('first-floor').checked};
  if(!context)return;
 }catch(error){status(error.message);return;}
 const {brief,upperProgram,firstFloor}=context;
 if(!fitAction){
  $('fit-options').hidden=true;fitRequest=null;
  if(brief.spatial_requirements?.length&&!hasCentralProgram(brief)){offerRelational();return;}
 }
 busy=true;lockBrief(true);progress.start();live.start(brief);
 $('generate').disabled=true;$('sample').disabled=true;$('cancel').hidden=false;
 $('results').replaceChildren();
 status('جارٍ البحث عن مسقط يجتاز الفحوص…');
 try{
  const data=await AntComposition.generate(mode,brief,progress.update,{firstFloor,upperProgram,fitAction});
  render(data,fitAction?'نتيجة إعادة البحث':'توليد من المدخلات الحالية');
  showFit(data,context);
  if(data.proposals?.length)progress.complete();else progress.fail();
  live.finish(data.proposals?.length||0);
 }catch(error){
  progress.fail();live.finish(0,true);status('تعذّر إكمال التوليد: '+error.message);
 }finally{
  busy=false;lockBrief(false);$('generate').disabled=false;$('sample').disabled=false;$('cancel').hidden=true;
 }
}
$('generate').onclick=()=>generateDesign();
$('cancel').onclick=()=>{if(confirm('إيقاف البحث؟ المدخلات ستبقى محفوظة هنا.')){sessionStorage.setItem('ant-composition-pending-brief',JSON.stringify(readBrief()));location.reload();}};
const pending=sessionStorage.getItem('ant-composition-pending-brief');if(pending&&modes[mode]){try{loadBrief(JSON.parse(pending));sessionStorage.removeItem('ant-composition-pending-brief');}catch(e){status('تعذر استعادة البرنامج المحفوظ: '+e.message);}}

const previousResults=sessionStorage.getItem('ant-composition-return-results');
if(previousResults&&mode==='clustered'){
 sessionStorage.removeItem('ant-composition-return-results');
 try{
  const {data,source,upperState,firstFloor}=JSON.parse(previousResults);
  if(upperState){
   $('first-floor').checked=firstFloor;
   for(const id of ['upper-children','upper-area','upper-side'])$(id).value=upperState[id];
   syncUpperProgram();
  }
  render(data,source);
 }catch{/* The generator remains available. */}
}

if(retired)showRetired();
if(modes[mode]&&!retired){const prepare=()=>AntComposition.prepare().then(()=>{if(!busy&&!result&&$('switch-relational').hidden)status('المحرك جاهز. عدّل البرنامج ثم اضغط التوليد.');}).catch(()=>{});if(window.requestIdleCallback)window.requestIdleCallback(prepare,{timeout:1500});else setTimeout(prepare,0);}
