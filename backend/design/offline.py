"""Direct engine entry point for offline runtime feasibility; no HTTP server.

This is a probe, not the complete studio API or Android integration.
"""
import json
import time
from pathlib import Path
from .models import DesignOptions
from .generator import generate_candidates
from .validators import validate_model,release_decision
from .export import svg,export_pdf,export_dxf


def run_local(options=None,output_dir='offline-outputs'):
    start=time.perf_counter();options=DesignOptions(**(options or {}))
    output=Path(output_dir);output.mkdir(parents=True,exist_ok=True)
    models=generate_candidates(options);generated=time.perf_counter();results=[]
    for model in models:
        checks=validate_model(model);decision=release_decision(checks)
        model['checks']=checks;model['release']=decision
        family=model['search']['family'];files=[]
        if decision['drawing_export_allowed']:
            for floor in model['floors']:
                filename=f'{family}-{floor["id"]}.svg'
                (output/filename).write_text(svg(model,floor),encoding='utf-8');files.append(filename)
            for ext,exporter in [('pdf',export_pdf),('dxf',export_dxf)]:
                filename=f'{family}.{ext}';audit=exporter(model,output/filename);files.append(filename)
                if ext=='dxf':model['export_audit']=audit
        filename=f'{family}.json'
        (output/filename).write_text(json.dumps(model,ensure_ascii=False,indent=2),encoding='utf-8');files.append(filename)
        results.append(dict(family=family,revision=model['model_revision_id'],
                            passed=sum(c['status']=='PASS' for c in checks),pending=sum(c['status']=='PENDING' for c in checks),
                            failed=sum(c['status']=='FAIL' for c in checks),
                            dxf_audit=model.get('export_audit'),files=files))
    return dict(scope='ENGINE_FEASIBILITY_ONLY',http_server_used_for_computation=False,android_device_verified=False,
                generation_seconds=round(generated-start,3),total_seconds=round(time.perf_counter()-start,3),candidates=results)
