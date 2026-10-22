import {useEffect,useRef,useState} from 'react';
import {FileImage,MapPinned,RotateCcw,Ruler,CheckCircle2} from 'lucide-react';
import {measureGeoCorners,measureImageCorners} from '@/lib/plot-intake';
import type {PlotMeasurement,Point,GeoCorner} from '@/lib/plot-intake';

type Mode='image'|'coords';
const labels=['A · أعلى يسار','B · أعلى يمين','C · أسفل يمين','D · أسفل يسار'];
interface Props {onApply:(measurement:PlotMeasurement)=>void}

export function PlotIntake({onApply}:Props){
 const [mode,setMode]=useState<Mode>('image');
 const imageRef=useRef<HTMLImageElement|null>(null);
 const [fileUrl,setFileUrl]=useState('');
 const [fileName,setFileName]=useState('');
 const [fileType,setFileType]=useState<'image'|'pdf'|''>('');
 const [points,setPoints]=useState<Point[]>([]);
 const [known,setKnown]=useState('');
 const [coordinates,setCoordinates]=useState<string[]>(['','','','']);
 const [result,setResult]=useState<PlotMeasurement|null>(null);
 const [error,setError]=useState('');
 useEffect(()=>()=>{if(fileUrl)URL.revokeObjectURL(fileUrl)},[fileUrl]);
 const resetResult=()=>{setResult(null);setError('')};
 const upload=(file?:File)=>{
  resetResult();setPoints([]);
  if(!file)return;
  const image=/^image\/(png|jpeg|webp)$/.test(file.type);
  const pdf=file.type==='application/pdf';
  if(!image&&!pdf){setError('يُقبل فقط JPG أو PNG أو WebP أو PDF.');return}
  if(file.size>10*1024*1024){setError('الحد الأقصى 10 ميجابايت.');return}
  const url=URL.createObjectURL(file);
  setFileUrl(url);setFileName(file.name);setFileType(pdf?'pdf':'image');
 };
 const mark=(event:React.MouseEvent<HTMLButtonElement>)=>{
  if(points.length>=4)return;
  const rect=event.currentTarget.getBoundingClientRect();
  const next=[...points,{x:(event.clientX-rect.left)/rect.width,y:(event.clientY-rect.top)/rect.height}];
  setPoints(next);resetResult();
 };
 const changeCoordinate=(index:number,value:string)=>{
  setCoordinates(previous=>previous.map((x,i)=>i===index?value:x));resetResult();
 };
 const calculate=()=>{
  try{
   const measurement=mode==='image'?(()=>{
    if(fileType!=='image')throw new Error('لمعايرة مخطط PDF، احفظ صفحته كصورة أولًا، أو أدخل الأبعاد يدويًا أدناه.');
    if(points.length!==4)throw new Error('حدد أركان الأرض الأربعة على الصورة بالترتيب A ثم B ثم C ثم D.');
    return measureImageCorners(points,Number(known),(imageRef.current?.naturalWidth||1)/(imageRef.current?.naturalHeight||1));
   })():(()=>{
    const parsed:GeoCorner[]=coordinates.map(value=>{
     const bits=value.trim().replace(/،/g,',').split(/[,\s]+/).filter(Boolean);
     if(bits.length!==2)throw new Error('اكتب كل ركن بصيغة: خط العرض، خط الطول.');
     return {lat:Number(bits[0]),lon:Number(bits[1])};
    });
    return measureGeoCorners(parsed);
   })();
   setResult(measurement);setError('');
  }catch(e){setResult(null);setError(e instanceof Error?e.message:'تعذر قراءة حدود الأرض.')}
 };
 return <div className="rounded-2xl border bg-muted/30 p-4 sm:p-5 space-y-4">
  <h3 className="font-display text-lg">مساعد قراءة الأرض <span className="text-xs font-normal text-muted-foreground">· تجريبي</span></h3>
  <p className="text-xs leading-6 text-muted-foreground">استخدم مخطط الأرض أو إحداثيات زواياها لحساب أبعاد مستطيلة مبدئية. لا نستنتج الشوارع أو الملكية أو الارتدادات من نقطة موقع فقط.</p>
  <div className="grid grid-cols-2 gap-2">
   <button type="button" onClick={()=>{setMode('image');resetResult()}} className={'flex items-center justify-center gap-2 rounded-lg border px-2 py-3 text-sm '+(mode==='image'?'border-primary bg-primary/10 font-semibold':'bg-card')}><FileImage size={16}/> صورة / PDF</button>
   <button type="button" onClick={()=>{setMode('coords');resetResult()}} className={'flex items-center justify-center gap-2 rounded-lg border px-2 py-3 text-sm '+(mode==='coords'?'border-primary bg-primary/10 font-semibold':'bg-card')}><MapPinned size={16}/> إحداثيات الأركان</button>
  </div>
  {mode==='image'?<div className="space-y-4">
   <label className="grid gap-2 text-sm">اختر صورة مسقط الأرض أو ملف PDF
    <input className="w-full rounded-lg border bg-card p-2 text-sm" type="file" accept=".jpg,.jpeg,.png,.webp,.pdf,image/jpeg,image/png,image/webp,application/pdf" onChange={e=>upload(e.currentTarget.files?.[0])}/>
   </label>
   {fileUrl&&<div className="space-y-2">
    <p className="break-all text-xs text-muted-foreground">{fileName} · لا يُرفع الملف إلى الخادم</p>
    {fileType==='image'?<div className="relative overflow-hidden rounded-lg border bg-white" dir="ltr">
     <img ref={imageRef} src={fileUrl} alt="المخطط المرفوع لتحديد زوايا الأرض" className="block h-auto w-full"/>
     <button type="button" className="absolute inset-0 cursor-crosshair" aria-label={'حدد '+(labels[points.length]||'اكتملت الزوايا')} onClick={mark} disabled={points.length>=4}/>
     {points.map((p,i)=><span key={i} className="pointer-events-none absolute flex size-7 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border-2 border-white bg-primary text-xs font-bold text-white shadow-lg" style={{left:(p.x*100)+'%',top:(p.y*100)+'%'}}>{'ABCD'[i]}</span>)}
    </div>:<p className="rounded-lg border bg-card p-3 text-xs leading-6">ملف PDF مقبول للمعاينة المرجعية فقط. لا نقرأ قياساته آليًا بعد؛ حوّل الصفحة التي تحتوي حدود الأرض إلى صورة PNG/JPG لتحديد الأركان، أو أدخل الأبعاد بنفسك.</p>}
   </div>}
   {fileType==='image'&&<div className="space-y-3">
    <p className="text-xs">اضغط زوايا حدود الأرض بالترتيب: <strong>A أعلى يسار ← B أعلى يمين ← C أسفل يمين ← D أسفل يسار</strong>.</p>
    <div className="flex items-center justify-between gap-2 text-xs"><span>تم تحديد {points.length} من 4</span><button type="button" className="inline-flex items-center gap-1 underline" onClick={()=>{setPoints([]);resetResult()}}><RotateCcw size={14}/> إعادة تحديد النقاط</button></div>
    <label className="grid gap-2 text-sm">الطول الحقيقي للضلع A–B بالمتر (من مستند أو قياس معروف)
     <input type="number" inputMode="decimal" min=".01" step=".01" className="w-full rounded-lg border bg-card p-3" value={known} onChange={e=>{setKnown(e.target.value);resetResult()}} placeholder="مثلاً 20"/>
    </label>
   </div>}
  </div>:<div className="space-y-3">
   <p className="text-xs leading-6">أدخل <strong>الإحداثيات الدقيقة للأركان الأربعة</strong> بحسب ترتيبها على المخطط (A–B–C–D). نقطة وسط الأرض وحدها لا تكشف حدودها. لا يوجد اتصال بخدمة خرائط أو سجل ملكيات.</p>
   <div className="grid gap-3 sm:grid-cols-2">{labels.map((label,i)=><label key={i} className="grid gap-1 text-xs">{label}<input dir="ltr" className="w-full rounded-lg border bg-card p-3 text-sm" value={coordinates[i]} onChange={e=>changeCoordinate(i,e.target.value)} placeholder="15.123456, 44.123456"/></label>)}</div>
   <p className="text-xs text-muted-foreground">لا نقبل قطعة مائلة أو غير مستطيلة على أنها مستطيل. لا تُحفظ الإحداثيات الخام داخل ملف المشروع.</p>
  </div>}
  <button type="button" className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-primary bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground" onClick={calculate}><Ruler size={17}/> احسب الأبعاد وتحقق منها</button>
  {error&&<p role="alert" className="rounded-lg bg-destructive/10 p-3 text-sm text-destructive">{error}</p>}
  {result&&<div className="space-y-3 rounded-xl border border-primary/30 bg-card p-4">
   <p className="flex items-center gap-2 text-sm font-semibold"><CheckCircle2 className="size-4 text-primary"/> نتيجة أولية تحتاج تأكيدك</p>
   <div className="grid grid-cols-3 gap-2 text-center text-sm"><div><strong>{result.width}م</strong><p className="text-xs text-muted-foreground">العرض</p></div><div><strong>{result.depth}م</strong><p className="text-xs text-muted-foreground">العمق</p></div><div><strong>{result.area}م²</strong><p className="text-xs text-muted-foreground">المساحة</p></div></div>
   <p className="text-xs leading-6 text-muted-foreground">نتيجة هندسية تقريبية، وليست رفعًا مساحيًا معتمدًا. الشوارع وحدود الجوار تحددها بنفسك قبل التصميم. {result.north_edge?'استُنتج اتجاه الشمال التقريبي من الإحداثيات.':'اختر اتجاه الشمال من الرسم يدويًا.'}</p>
   <button type="button" className="w-full rounded-lg border border-primary px-3 py-3 text-sm font-semibold text-primary" onClick={()=>onApply(result)}>اعتمد هذه الأبعاد المبدئية في النموذج</button>
  </div>}
 </div>;
}
