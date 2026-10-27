"""Build a self-contained browser/WebView engine feasibility bundle.

Downloads run only at build time. Runtime has no remote URLs or API computation.
python -m mobile_probe.build_bundle --output /workspace/android-feasibility/offline-web
"""
import argparse
import concurrent.futures
import hashlib
import json
import shutil
import urllib.request
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PYODIDE_VERSION='0.29.3'
BASE=f'https://cdn.jsdelivr.net/pyodide/v{PYODIDE_VERSION}/full/'
PACKAGES=['pydantic','numpy','pillow','fonttools','pyparsing','charset-normalizer','six','shapely']
PURE={'reportlab':'4.4.3','python-bidi':'0.4.2','ezdxf':'1.4.5','openpyxl':'3.1.5','et-xmlfile':'2.0.0','arabic-reshaper':'3.0.0','networkx':'3.4.2'}


def fetch(url,path,expected=None):
    if not path.is_file() or (expected and hashlib.sha256(path.read_bytes()).hexdigest()!=expected):
        data=urllib.request.urlopen(url,timeout=90).read()
        if expected and hashlib.sha256(data).hexdigest()!=expected:raise ValueError('Hash mismatch: '+path.name)
        path.write_bytes(data)
    return dict(file=str(path.name),bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def pack_engine(out):
    with zipfile.ZipFile(Path(out)/'engine.zip','w',zipfile.ZIP_DEFLATED) as z:
        for folder in ('backend/design','requirements','constitution','frontend'):
            for p in sorted((ROOT/folder).rglob('*')):
                if not p.is_file() or '__pycache__' in p.parts:continue
                if folder=='frontend' and p.name not in ('PlanFont.ttf','Arabic.ttf','Latin.ttf','FONT-LICENSE.txt','LATIN-FONT-LICENSE.txt'):continue
                z.write(p,str(p.relative_to(ROOT)))
        z.writestr('backend/__init__.py','')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'mobile_probe/build')
    args=parser.parse_args();out=args.output;runtime=out/'runtime';wheels=out/'wheels'
    runtime.mkdir(parents=True,exist_ok=True);wheels.mkdir(exist_ok=True)
    fetch(BASE+'pyodide-lock.json',runtime/'pyodide-lock.json')
    lock=json.loads((runtime/'pyodide-lock.json').read_text());packages=lock['packages'];resolved=set()
    def resolve(name):
        name=name.replace('_','-')
        if name in resolved:return
        resolved.add(name)
        for dep in packages[name]['depends']:resolve(dep)
    for name in PACKAGES:resolve(name)
    tasks=[(BASE+n,runtime/n,None) for n in ['pyodide.js','pyodide.asm.js','pyodide.asm.wasm','python_stdlib.zip']]
    tasks.extend([('https://raw.githubusercontent.com/pyodide/pyodide/0.29.3/LICENSE',out/'PYODIDE-LICENSE',None),('https://raw.githubusercontent.com/python/cpython/v3.13.2/LICENSE',out/'CPYTHON-LICENSE',None)])
    for name in sorted(resolved):
        p=packages[name];tasks.append((BASE+p['file_name'],runtime/p['file_name'],p['sha256']))
    pure_versions={}
    for package,version in PURE.items():
        meta=json.load(urllib.request.urlopen(f'https://pypi.org/pypi/{package}/{version}/json',timeout=45))
        f=next(f for f in meta['urls'] if f['filename'].endswith('none-any.whl'))
        tasks.append((f['url'],wheels/f['filename'],f['digests']['sha256']));pure_versions[package]=version
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:files=list(pool.map(lambda t:fetch(*t),tasks))
    pack_engine(out)
    for name in ('index.html','worker.js'):shutil.copyfile(ROOT/'mobile_probe'/name,out/name)
    manifest=dict(pyodide_version=PYODIDE_VERSION,python_version=lock['info']['python'],
                  runtime_packages={n:packages[n]['version'] for n in sorted(resolved)},pure_packages=pure_versions,
                  pure_wheels=sorted(p.name for p in wheels.glob('*.whl')),engineering_wasm_packages=['shapely'],runtime_network_required=False,
                  target='Chromium/WebView feasibility; Android APK/device not yet verified',files=files)
    manifest['bundle_bytes']=sum(p.stat().st_size for p in out.rglob('*') if p.is_file())
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('Offline bundle:',out,'bytes',manifest['bundle_bytes'],flush=True)


if __name__=='__main__':main()
