"""Build the general customer interface alongside the existing shared runtime."""
import argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=True)
    for name in ('index.html','style.css','app.js','ENGINE_LICENSE'):
        text=(ROOT/'web_generator'/name).read_text()
        text=text.replace('/generator-assets/','./').replace("url('/assets/Arabic.ttf')","url('../studio/assets/Arabic.ttf')")
        if name=='index.html':text=text.replace('<script defer src="./app.js">','<script defer src="./static-client.js?v=061"></script><script defer src="./app.js?v=061">')
        (out/name).write_text(text)
    worker=(ROOT/'web_studio/worker.js').read_text()
    for old,new in [('./runtime/','../studio/runtime/'),('./manifest.json','../studio/manifest.json?v=061'),('./wheels/','../studio/wheels/'),('./engine.zip','../studio/engine.zip?v=061')]:worker=worker.replace(old,new)
    worker=worker.replace('from backend.design.models import DesignOptions','from backend.design.models import DesignOptions\nfrom backend.design.general_models import VillaBrief\nfrom backend.design.general_engine import generate_general')
    worker=worker.replace("data.operation==='design'","data.operation==='general'").replace('design(DesignOptions(**json.loads(options_json)))','generate_general(VillaBrief(**json.loads(options_json)))')
    (out/'worker.js').write_text(worker)
    client=(ROOT/'web_studio/offline-client.js').read_text().replace('./worker.js?v=041','./worker.js?v=061')
    client=client.replace("if(path==='/api/v2/project')", "if(path==='/api/v3/ai-status')return Response.json({configured:false,connected:false});\n      if(path==='/api/v3/design')return Response.json(await call('general',{options:JSON.parse(options.body)}));\n      if(path==='/api/v2/project')")
    client=client.replace("if(path==='/api/v3/ai-status')","if(path==='/api/v3/jurisdictions')return nativeFetch('./municipalities.json?v=061');\n      if(path==='/api/v3/ai-status')")
    (out/'static-client.js').write_text(client)
    (out/'municipalities.json').write_text((ROOT/'constitution/saudi/municipalities.json').read_text())
    print('General customer generator built:',out)


if __name__=='__main__':main()
