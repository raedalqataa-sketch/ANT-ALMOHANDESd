"""Retained static assets + documented ESM fetch Worker, with no build-time secrets."""
import argparse,json,shutil
from pathlib import Path

def build(source,output,gateway):
    source,output=Path(source),Path(output)
    if source.resolve()==output.resolve():raise ValueError('source and output must differ')
    if output.exists():shutil.rmtree(output)
    shutil.copytree(source,output/'client')
    server=output/'server';server.mkdir()
    code=Path(gateway).read_text()
    code+='\nconst gateway=createGateway();\nexport default {async fetch(request,env,ctx){if(new URL(request.url).pathname.startsWith("/api/client/gemini/"))return gateway.fetch(request,env);return env.ASSETS.fetch(request)}};\n'
    (server/'index.js').write_text(code)
    (server/'wrangler.json').write_text(json.dumps({'name':'ant-customer-design','main':'index.js','compatibility_date':'2026-05-15','compatibility_flags':['nodejs_compat'],'assets':{'directory':'../client','binding':'ASSETS','run_worker_first':['/api/client/gemini/*']}},indent=2)+'\n')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    build(a.source,a.output,Path(__file__).with_name('gateway.mjs'))
