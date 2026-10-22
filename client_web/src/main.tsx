import { createRoot } from 'react-dom/client';
import {AutomaticClient} from './pages/automatic-client';
import { ClientRequirements } from './pages/client-requirements';
import './styles.css';
function App(){return <>
  <header className="border-b bg-card"><div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-5 py-5 sm:px-8"><a href="/" className="font-display text-xl font-semibold text-primary">أنت المهندس <span className="mr-2 text-xs font-normal text-muted-foreground">مساحتك تبدأ بفكرة</span></a><nav aria-label="التنقل الرئيسي" className="flex gap-5 text-sm"><a href="/client/" aria-current="page" className="font-semibold text-primary">متطلبات فيلتك</a><a href="/generate/" className="text-muted-foreground">المولد المتقدم</a></nav></div></header>
  <main className="mx-auto max-w-6xl px-4 py-8 sm:px-8 sm:py-12">{new URLSearchParams(location.search).get('mode')==='advanced'?<ClientRequirements />:<AutomaticClient />}</main>
  <footer className="mx-auto max-w-4xl border-t px-5 py-7 text-sm leading-7 text-muted-foreground">المقترحات مسودات للمراجعة الهندسية. إدخال المتطلبات والتوليد في هذا المتصفح لا يمثل حفظ مشروع في الخادم أو اعتمادًا تنفيذيًا.</footer>
</>}
createRoot(document.getElementById('root')!).render(<App/>);
