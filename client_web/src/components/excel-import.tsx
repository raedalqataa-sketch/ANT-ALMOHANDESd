import { useRef, useState } from 'react';
import { FileSpreadsheet, Upload } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { readExcelWorkbook, importSummary, type ExcelImport } from '@/lib/excel-import';

export function ExcelImporter({ onImport }: { onImport: (result: ExcelImport) => void }) {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [filename, setFilename] = useState('');
  return <div className="mb-6 space-y-3 border-b pb-5">
    <input ref={input} type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/octet-stream" aria-label="ملف Excel" className="sr-only" disabled={busy} onChange={async e => {
      const file = e.target.files?.[0];
      e.target.value = '';
      if (!file) return;
      setError(''); setBusy(true);
      try {
        if (!/\.xlsx$/i.test(file.name)) throw new Error('اختر ملفًا بامتداد .xlsx؛ ملفات .xls غير مدعومة.');
        if (file.size > 10 * 1024 * 1024) throw new Error('الملف أكبر من 10 ميغابايت؛ قلل حجمه قبل الاستيراد.');
        onImport(await readExcelWorkbook(await file.arrayBuffer()));
        setFilename(file.name);
      } catch (failure) { setError(failure instanceof Error ? failure.message : 'تعذر قراءة الملف. تحقق من سلامته وأسماء الأعمدة.'); }
      finally { setBusy(false); }
    }} />
    <Button type="button" variant="outline" disabled={busy} onClick={() => input.current?.click()}><Upload />{busy ? 'جارٍ قراءة الملف…' : 'استيراد Excel'}</Button>
    {filename && <p role="status" className="break-all text-sm text-muted-foreground">آخر ملف مستورد: <bdi>{filename}</bdi></p>}
    {error && <p role="alert" className="text-sm leading-7 text-destructive">{error}</p>}
  </div>;
}

export function ImportedFields({ result, onApply }: { result: ExcelImport; onApply: () => void }) {
  const summary = importSummary(result.fields);
  return <section className="mb-8 border-y py-5" aria-label="حقول Excel المستوردة">
    <div className="mb-4 flex flex-wrap items-center justify-between gap-3"><h2 className="flex items-center gap-2 font-display text-xl"><FileSpreadsheet className="text-teal" />الحقول المستوردة ({result.fields.length})</h2><Button type="button" variant="outline" onClick={onApply}>تعبئة الحقول الفارغة المطابقة</Button></div>
    <p className="mb-4 text-sm text-muted-foreground">مسودة غير محفوظة؛ تبقى الحقول غير المطابقة ظاهرة دون افتراض بيانات أو تغيير القيم الحالية.</p>
    <dl aria-label="ملخص البيانات المستوردة" className="mb-5 grid grid-cols-2 gap-4 border-y py-4 md:grid-cols-4">{[['إجمالي الحقول', summary.total], ['قيم مزودة', summary.filled], ['قيم غير مزودة', summary.empty], ['الأوراق', summary.sheets]].map(([label, value]) => <div key={label}><dt className="text-sm text-muted-foreground">{label}</dt><dd className="mt-1 font-display text-xl">{value}</dd></div>)}</dl>
    {summary.empty > 0 && <p className="mb-4 text-sm text-muted-foreground">هناك {summary.empty} حقول بلا قيمة؛ احتُفظ بها دون استكمال افتراضي.</p>}
    {summary.requirements.length > 0 && <div className="mb-5"><h3 className="mb-3 font-display text-lg">متطلبات الفيلا الواردة في الملف</h3><dl className="grid gap-3 md:grid-cols-2">{summary.requirements.map((field, i) => <div key={i} className="border-r-2 border-accent pr-3"><dt className="break-words text-sm font-medium">{field.field}</dt><dd className="whitespace-pre-wrap break-words text-sm text-muted-foreground">{field.value || 'غير مزود'}</dd></div>)}</dl></div>}
    {result.warnings.length > 0 && <ul role="status" className="mb-4 space-y-2 text-sm text-muted-foreground">{result.warnings.map((warning, i) => <li key={i}>{warning}</li>)}</ul>}
    <div className="overflow-x-auto"><table className="w-full min-w-96 text-right text-sm"><thead><tr className="border-b"><th className="p-3">الورقة / الرقم</th><th className="p-3">الحقل</th><th className="p-3">القيمة</th><th className="p-3">إرشادات</th></tr></thead><tbody>{result.fields.map((field, i) => <tr key={i} className="border-b align-top"><td className="p-3">{field.sheet} / {field.number || field.row}</td><th scope="row" className="whitespace-pre-wrap break-words p-3 font-medium">{field.field}</th><td className="whitespace-pre-wrap break-words p-3">{field.value || 'غير مزود'}</td><td className="whitespace-pre-wrap break-words p-3 text-muted-foreground">{field.guidance || '—'}</td></tr>)}</tbody></table></div>
  </section>;
}
