import { useEffect, useRef, useState } from 'react';
import type { ClientDraft } from '@/lib/client-requirements';
import { Button } from '@/components/ui/button';

const channel = 'ANT_VILLA_V1';
const enginePath = '/villa-engine/generate/?embedded=1';

/** Same-origin bridge to the unchanged Python geometric engine in a Web Worker.
 * No project/database save, credentials, cloud compute, or engineering approval.
 */
export function VillaGenerator({ draft }: { draft: ClientDraft }) {
  const frame = useRef<HTMLIFrameElement>(null);
  const imported = useRef(false);
  const [session, setSession] = useState(() => crypto.randomUUID());
  const [height, setHeight] = useState(1000);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('جارٍ فتح إعدادات محرك Python…');

  useEffect(() => {
    imported.current = false;
    setError('');
    setStatus('جارٍ فتح إعدادات محرك Python…');
    const hello = () => frame.current?.contentWindow?.postMessage({ channel, nonce: session, type: 'HELLO' }, location.origin);
    const retry = window.setInterval(() => { if (!imported.current) hello(); }, 1000);
    const timeout = window.setTimeout(() => {
      if (!imported.current) { setError('تعذر الاتصال بواجهة المحرك. لم يحدث توليد أو إرسال ناجح. أعد المحاولة.'); window.clearInterval(retry); }
    }, 30000);
    const receive = (event: MessageEvent) => {
      if (event.source !== frame.current?.contentWindow || event.origin !== location.origin) return;
      const message = event.data;
      if (!message || message.channel !== channel || message.nonce !== session) return;
      if (message.type === 'READY' && !imported.current) {
        if (message.engineVersion !== '0.6.2-general') { setError('إصدار المحرك لا يطابق نسخة الواجهة. لم تُنقل المتطلبات.'); return; }
        frame.current?.contentWindow?.postMessage({ channel, nonce: session, type: 'DRAFT', draft }, location.origin);
      } else if (message.type === 'IMPORTED') {
        if (!Number.isInteger(message.roomCount) || message.roomCount < 0 || message.roomCount > 36) return;
        imported.current = true;
        window.clearInterval(retry); window.clearTimeout(timeout);
        setStatus(`نُقلت متطلبات ${message.roomCount} فراغًا إلى المحرك. أكمل البيانات الفارغة أدناه ثم اضغط «توليد المقترحات الثلاثة». لم يُنشأ مسقط بعد.`);
      } else if (message.type === 'RESULT' && imported.current) {
        if (!Array.isArray(message.candidates) || message.candidates.length > 3) return;
        const available = message.candidates.filter((candidate: { reviewable?: unknown }) => candidate.reviewable === true).length;
        setStatus(available ? `اكتمل البحث: ${available} مقترحات قابلة للمراجعة. عاين الفحوص ثم نزّل الملفات من المحرك أدناه؛ لا اعتماد تنفيذي.` : 'اكتمل البحث دون مقترح مجتاز للفحوص. راجع أسباب التعذر أدناه؛ ملفات الرسم محجوبة.');
      } else if (message.type === 'ERROR') {
        window.clearInterval(retry); window.clearTimeout(timeout);
        setError(typeof message.error === 'string' ? message.error : 'تعذر نقل المتطلبات إلى المحرك.');
      } else if (message.type === 'RESIZE' && imported.current && Number.isFinite(message.height)) {
        setHeight(Math.max(900, Math.min(16000, message.height)));
      }
    };
    window.addEventListener('message', receive); hello();
    return () => { window.clearInterval(retry); window.clearTimeout(timeout); window.removeEventListener('message', receive); };
  }, [draft, session]);

  const downloadSource = () => {
    const url = URL.createObjectURL(new Blob([JSON.stringify({ version: 1, client_requirements: draft }, null, 2)], { type: 'application/json' }));
    const link = document.createElement('a'); link.href = url; link.download = 'ant-client-requirements.json'; link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  return <section aria-label="محرك توليد مساقط الفلل" className="mt-8 min-w-0 space-y-4 border-t pt-6">
    <h3 className="font-display text-xl">من متطلباتك إلى المقترحات</h3>
    <p className="text-sm leading-7 text-muted-foreground">يعمل محرك Python في متصفحك. لا تُحفظ هذه العملية كمشروع في الخادم، ولا تمنح المخطط اعتمادًا. الرجوع لتعديل المتطلبات يغلق المحرك ويلغي العملية الجارية؛ أعد نقل المتطلبات بعد التعديل.</p>
    <p role="status" className="border-r-2 border-accent pr-3 text-sm leading-7">{status}</p>
    {error && <p role="alert" className="border-r-2 border-destructive pr-3 text-sm text-destructive">{error}</p>}
    <div className="flex flex-wrap gap-3">
      <Button type="button" variant="outline" onClick={downloadSource}>تنزيل متطلبات العميل كاملة</Button>
      <Button type="button" variant="outline" onClick={() => { setHeight(1000); setSession(crypto.randomUUID()); }}>إعادة فتح المحرك</Button>
    </div>
    <iframe key={session} ref={frame} title="إعداد وتوليد المقترحات بواسطة محرك Python" src={enginePath} sandbox="allow-scripts allow-same-origin allow-downloads" className="block w-full min-w-0 rounded-md border bg-white" style={{ height, maxWidth: '100%' }} onLoad={() => frame.current?.contentWindow?.postMessage({ channel, nonce: session, type: 'HELLO' }, location.origin)} />
  </section>;
}
