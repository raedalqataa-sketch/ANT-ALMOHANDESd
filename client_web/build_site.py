"""Build the public client intake alongside the existing approved Site engine."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,sys,tempfile
ROOT=Path(__file__).resolve().parents[1]

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--site',type=Path,required=True);a=parser.parse_args()
 site=a.site.resolve();hosting=json.loads((site/'.openai/hosting.json').read_text());dist=site/hosting['static']['directory'];runtime=dist/'studio'
 target=dist/'client'
 if target.exists() and not (target/'client-source.json').exists():raise SystemExit('Refusing to replace an unmanaged client directory')
 with tempfile.TemporaryDirectory(prefix='ant-client-bundle-') as temporary:
  subprocess.run([sys.executable,'-m','lovable_integration.build','--output',temporary,'--runtime-source',str(runtime)],cwd=ROOT,check=True)
  public=ROOT/'client_web/public/villa-engine/generate';public.parent.mkdir(parents=True,exist_ok=True)
  if public.exists():shutil.rmtree(public)
  shutil.copytree(Path(temporary)/'public/villa-engine/generate',public)
  shutil.copyfile(Path(temporary)/'public/villa-engine/studio/engine.zip',public.parent/'engine.zip')
  for path in public.iterdir():
   if path.suffix in ('.js','.css'):
    path.write_text(path.read_text().replace('../studio/','/studio/').replace('/studio/engine.zip?v=062','../engine.zip?v=architect1'))
  subprocess.run(['npm','run','build'],cwd=ROOT/'client_web',check=True)
  built=ROOT/'client_web/dist'
  source_files=sorted(p for p in (ROOT/'client_web').rglob('*') if p.is_file() and not any(v in p.relative_to(ROOT/'client_web').parts for v in ('node_modules','dist','public','__pycache__')))
  digest=hashlib.sha256()
  for p in source_files:digest.update(str(p.relative_to(ROOT)).encode());digest.update(p.read_bytes())
  bundle_digest=hashlib.sha256()
  for p in sorted(public.rglob('*')):
   if p.is_file():bundle_digest.update(str(p.relative_to(public)).encode());bundle_digest.update(p.read_bytes())
  provenance={'embedded_bundle_sha256':bundle_digest.hexdigest(),'application':'ant-client-intake','path':'/client/','source_sha256':digest.hexdigest(),'source_reference':'Lovable 0534539568b6818e52ebe072ca780dc6afe9b5e1; adapted public intake only','site_placement_revision':'rear-corner-1','massing_revision':'coherent-massing-1','planner_version':'architect-program-4','reference_patterns_revision':'reference-principles-2','reference_projects':6,'reference_unique_images':19,'generation_revision':'architectural-engine-4','selection_revision':'objective_ranked_geometry_v4_functional','supported_countries':['SA','YE'],'engine_version':'0.6.2-general','engine_sha256':hashlib.sha256((public.parent/'engine.zip').read_bytes()).hexdigest(),'runtime_shared_at':'/studio/','client_persistence':'temporary tab-scoped sessionStorage; engine files memory only','lovable_sync_verified':False,'executive_approval':False}
  (built/'client-source.json').write_text(json.dumps(provenance,indent=2)+'\n')
  if target.exists():shutil.rmtree(target)
  shutil.copytree(built,target)
 home=dist/'index.html';html=home.read_text()
 if 'href="client/"' not in html:
  html=html.replace('<main>','<main><section class="panel" style="border:2px solid #244838;margin-bottom:20px"><h2>متطلبات فيلتك في خمس خطوات</h2><p>أدخل بيانات الأرض والأسرة والضيافة والفراغات، ثم راجع المقترحات وحمّل ملفات المخطط.</p><a class="secondary" href="client/" style="display:inline-block;background:#244838;color:white;padding:12px 20px;border-radius:8px">ابدأ متطلبات فيلتك ←</a></section>',1)
  home.write_text(html)
 home.write_text(home.read_text().replace('متطلبات فيلتك في خمس خطوات','صمّم مسكنك من احتياجات أسرتك').replace('أدخل بيانات الأرض والأسرة والضيافة والفراغات، ثم راجع المقترحات وحمّل ملفات المخطط.','عرّف أرضك وأسرتك ودع النظام يقترح الغرف والأبعاد وثلاثة تصورات مختلفة.'))
 print(json.dumps(provenance))

if __name__=='__main__':main()
