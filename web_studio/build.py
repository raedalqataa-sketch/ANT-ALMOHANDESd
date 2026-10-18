"""Package the current studio and full local engine for static Sites hosting."""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'web_studio/build')
    args=parser.parse_args();out=args.output.resolve()
    subprocess.run([sys.executable,'-m','mobile_probe.build_bundle','--output',str(out)],cwd=ROOT,check=True)
    assets=out/'assets';assets.mkdir(exist_ok=True)
    for name in ('style.css','studio.css','studio.js','Arabic.ttf','FONT-LICENSE.txt'):
        shutil.copyfile(ROOT/'frontend'/name,assets/name)
    for name in ('worker.js','offline-client.js'):
        shutil.copyfile(ROOT/'web_studio'/name,(assets if name=='offline-client.js' else out)/name)
    css=assets/'style.css';css.write_text(css.read_text().replace("url('/assets/Arabic.ttf')","url('./Arabic.ttf')"))
    html=(ROOT/'frontend/studio.html').read_text().replace('/assets/','./assets/')
    html=html.replace('<script src="./assets/studio.js" defer>', '<script src="./assets/offline-client.js?v=041" defer></script><script src="./assets/studio.js?v=041" defer>')
    html=html.replace('href="/rectangles"','href="/#generation-panel"').replace('تجربة مستطيلات حرة','المتطلبات والسجلات السابقة')
    html=html.replace('مساحة عمل محلية · دون نشر','المحرك والأثاث المحدّثان · 0.4.1')
    html=html.replace('الملفات على خادم العمل المحلي.','الملفات محفوظة في هذا المتصفح عند توفر التخزين المحلي؛ نزّل نسخة للاحتفاظ بها.')
    html=html.replace('بنود معلقة','بنود معلقة')
    html=html.replace('استوديو المساقط المعمارية','المحرك والأثاث المحدّثان · 0.4.1')
    html=html.replace('قارن الأرضي والأول، وافحص ما تحقق وما بقي معلقًا.','قارن الأرضي والأول، ونزّل لوحات PDF وDXF 2010. المصدر المعتمد: Excel المحفد، أرض 20 × 30 م. تعديلات الجدول السابق لا تنتقل إلى هذا الاستوديو تلقائيًا.')
    (out/'index.html').write_text(html,encoding='utf-8')
    js=assets/'studio.js';s=js.read_text()
    s=s.replace("byId('plan-image').src=url", "byId('plan-image').src=window.AntFiles.url(url)")
    s=s.replace("a.href=path;a.download=''", "a.href=window.AntFiles.url(path);a.download=path.split('/').pop()")
    s=s.replace("a.href=selected.downloads.json;a.download=''", "a.href=window.AntFiles.url(selected.downloads.json);a.download=selected.downloads.json.split('/').pop()")
    s=s.replace("h.slice(0,30)","h.slice(0,18)")
    s=s.replace('قد تكون ملفات خادم العمل قد حُذفت','قد تكون ملفات هذا المتصفح قد حُذفت')
    js.write_text(s)
    print('Hosted studio built:',out)


if __name__=='__main__':main()
