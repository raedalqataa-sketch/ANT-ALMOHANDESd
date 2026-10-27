"""Standalone loopback-only experiment service. Not mounted in the production app."""
import os
import re
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import Field

from .schemas import LabRequest, Strict
from .providers import Provider, ProviderConfig
from .pipeline import run

class VerifyRequest(Strict):
    model: str = Field(min_length=1,max_length=180,pattern=r'^[A-Za-z0-9_./:@-]+$')


def create_app(output_root=None):
    app=FastAPI(title='ANT AI Laboratory',docs_url=None,redoc_url=None,openapi_url=None)
    app.add_middleware(TrustedHostMiddleware,allowed_hosts=['localhost','127.0.0.1','[::1]','testserver'])
    root=Path(output_root) if output_root else Path(tempfile.gettempdir())/'ant-ai-lab'
    executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='ant-ai-lab')
    jobs={};lock=threading.Lock()

    @app.middleware('http')
    async def local_guard(request:Request,call_next):
        if os.environ.get('ANT_AI_LAB_ENABLED')!='true':
            return JSONResponse({'detail':'experimental laboratory disabled'},status_code=404)
        if request.client and request.client.host not in ('127.0.0.1','::1','testclient'):
            return JSONResponse({'detail':'loopback access only'},status_code=403)
        if request.method=='POST':
            origin=request.headers.get('origin')
            if request.headers.get('X-ANT-Lab')!='1' or (origin and origin!=str(request.base_url).rstrip('/')):
                return JSONResponse({'detail':'same-origin explicit laboratory action required'},status_code=403)
            if int(request.headers.get('content-length','0'))>32000:
                return JSONResponse({'detail':'request too large'},status_code=413)
        response=await call_next(request)
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='no-referrer'
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'"
        return response

    @app.get('/')
    def dashboard():
        return FileResponse(Path(__file__).with_name('dashboard.html'))

    @app.get('/api/providers')
    def status():
        return {name:{'credential_present':bool(os.environ.get(name+'_API_KEY')),
                      'status':'CONFIGURED_UNVERIFIED' if os.environ.get(name+'_API_KEY') else 'MISSING_CREDENTIAL',
                      'model':os.environ.get(name+'_MODEL',''), 'quota':'UNKNOWN',
                      'free_tier':'operator confirmation required' if name=='GEMINI' else 'zero-price catalog guard before inference'}
                for name in ('GEMINI','OPENROUTER')}

    @app.post('/api/providers/{name}/verify')
    def verify(name:str,body:VerifyRequest):
        if name not in ('GEMINI','OPENROUTER'):
            raise HTTPException(404,'unknown provider')
        try:
            provider=Provider(ProviderConfig.from_env(name,body.model))
        except ValueError:
            raise HTTPException(422,'invalid model identifier') from None
        try:
            return provider.status(verify=True)
        finally:
            provider.close()

    def execute(job_id,body):
        try:
            result=run(body,root/job_id)
            with lock:jobs[job_id].update(state='DONE',result=result)
        except Exception:
            # Never reflect provider errors/tracebacks or untrusted data into browser/logs.
            with lock:jobs[job_id].update(state='FAILED',error='LAB_EXECUTION_FAILED; no unvalidated drawings released')

    @app.post('/api/jobs',status_code=202)
    def generate(body:LabRequest):
        with lock:
            if any(job['state']=='RUNNING' for job in jobs.values()):
                raise HTTPException(409,'one controlled benchmark at a time')
            if len(jobs)>=10:
                raise HTTPException(429,'local run budget reached; restart laboratory to continue')
            job_id=uuid4().hex;jobs[job_id]={'state':'RUNNING'}
        executor.submit(execute,job_id,body)
        return {'job_id':job_id,'state':'RUNNING'}

    def get_job(job_id):
        with lock:
            if job_id not in jobs:
                raise HTTPException(404,'unknown job')
            return dict(jobs[job_id])

    @app.get('/api/jobs/{job_id}')
    def job(job_id:str):
        return get_job(job_id)

    @app.get('/api/jobs/{job_id}/files/{filename}')
    def artifact(job_id:str,filename:str):
        job=get_job(job_id)
        if job['state']!='DONE':raise HTTPException(409,'job not complete')
        allowed={'report.json'}
        for model in job['result']['candidates']:
            rev=model['model_revision_id']
            allowed.update(rev+'.'+ext for ext in ('pdf','dxf','json'))
            allowed.update(rev+'-'+f['id']+'.svg' for f in model['floors'])
            allowed.add(rev+'-SITE.svg')
        if filename not in allowed:raise HTTPException(404,'artifact not released')
        path=root/job_id/filename
        if not path.is_file() or path.is_symlink():raise HTTPException(404,'artifact unavailable')
        return FileResponse(path,filename=filename)

    return app

app=create_app()

if __name__=='__main__':
    import uvicorn
    uvicorn.run('backend.design.ai_lab.app:app',host='127.0.0.1',port=8002,access_log=False)
