"""Official, user-authenticated provisioning helpers. Never scrape sessions or print keys."""
import argparse
import base64
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs, quote
from http.server import BaseHTTPRequestHandler, HTTPServer

import httpx

NAMES=('GEMINI_API_KEY','OPENROUTER_API_KEY')

def discover():
    return {**{k:bool(os.environ.get(k)) for k in NAMES},
            'OPENROUTER_MANAGEMENT_KEY':bool(os.environ.get('OPENROUTER_MANAGEMENT_KEY')),
            'gcloud_available':bool(shutil.which('gcloud')),
            'google_identity_configured':bool(os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'))}


class CredentialError(ValueError):
    """Safe local status code, never transport response text."""


def preflight_destination(destination, repository, name=None):
    destination=Path(destination).absolute();repository=Path(repository).resolve()
    if destination.is_symlink() or destination.resolve().is_relative_to(repository):
        raise CredentialError('UNSAFE_SECRET_DESTINATION')
    if any(parent.is_symlink() for parent in destination.parents):
        raise CredentialError('SYMLINK_SECRET_DESTINATION')
    destination.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    if destination.parent.stat().st_mode & 0o077:
        raise CredentialError('SECRET_DIRECTORY_NOT_PRIVATE')
    if destination.exists():
        if not destination.is_file() or destination.stat().st_mode & 0o077:
            raise CredentialError('SECRET_FILE_NOT_PRIVATE')
        if name and re.search(r'^'+re.escape(name)+r'=',destination.read_text(),re.M):
            raise CredentialError('EXISTING_SECRET_REUSE_REQUIRED')
    # Reserve/check a private temporary file before any external key creation.
    fd,probe=tempfile.mkstemp(dir=destination.parent,prefix='.credential-preflight-')
    os.close(fd);os.unlink(probe)
    return destination


def save_secret(destination, name, value, repository):
    """Explicit server-side destination outside the repo; atomic 0600 file, no overwrites."""
    destination=preflight_destination(destination,repository,name)
    if name not in NAMES or not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,1024}',value):
        raise CredentialError('invalid secret input')
    if destination.is_symlink() or destination.resolve().is_relative_to(repository):
        raise CredentialError('secret destination must be outside repository and not a symlink')
    for parent in destination.parents:
        if parent.is_symlink():
            raise CredentialError('symlink parent forbidden')
    destination.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    # Refuse existing shared dirs rather than chmod an unrelated user's directory.
    if destination.parent.stat().st_mode & 0o077:
        raise CredentialError('destination directory must be private mode 0700')
    previous=destination.read_text() if destination.exists() else ''
    if re.search(r'^'+name+r'=',previous,re.M):
        raise CredentialError('credential already saved; reuse it rather than overwrite')
    fd,temp=tempfile.mkstemp(dir=destination.parent,prefix='.credentials-')
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,'w') as stream:
            stream.write(previous.rstrip()+'\n'+name+'='+value+'\n')
            stream.flush();os.fsync(stream.fileno())
        os.replace(temp,destination)
    finally:
        if os.path.exists(temp):os.unlink(temp)
    os.environ[name]=value


def _request(client,method,url,**kwargs):
    try:
        response=client.request(method,url,timeout=30,follow_redirects=False,**kwargs)
        if response.status_code>=300:
            raise CredentialError('OFFICIAL_API_HTTP_'+str(response.status_code))
        if len(response.content)>1_000_000:
            raise CredentialError('OFFICIAL_RESPONSE_TOO_LARGE')
        return response.json()
    except (httpx.HTTPError,json.JSONDecodeError):
        raise CredentialError('OFFICIAL_API_UNAVAILABLE') from None


def provision_gemini(project_number, *, client=None):
    if os.environ.get('GEMINI_API_KEY'):
        return os.environ['GEMINI_API_KEY']
    if not re.fullmatch(r'[0-9]{5,25}',project_number):
        raise CredentialError('explicit numeric Google project number required')
    if not shutil.which('gcloud'):
        raise CredentialError('GOOGLE_LOGIN_REQUIRED: use official AI Studio or install/login gcloud')
    token=subprocess.run(['gcloud','auth','print-access-token'],capture_output=True,text=True,timeout=30)
    if token.returncode or not token.stdout.strip():
        raise CredentialError('GOOGLE_LOGIN_REQUIRED')
    headers={'Authorization':'Bearer '+token.stdout.strip()};client=client or httpx.Client()
    base='https://apikeys.googleapis.com/v2/projects/'+project_number+'/locations/global/keys'
    matching=[];page_token=None;seen_tokens=set()
    for _ in range(100):
        keys=_request(client,'GET',base,headers=headers,params={'pageToken':page_token} if page_token else {})
        matching.extend(k for k in keys.get('keys',[]) if k.get('displayName')=='ANT-AI-AUTO-KEYS-002')
        page_token=keys.get('nextPageToken')
        if not page_token:break
        if not isinstance(page_token,str) or page_token in seen_tokens:
            raise CredentialError('INVALID_GOOGLE_PAGINATION')
        seen_tokens.add(page_token)
    else:
        raise CredentialError('GOOGLE_KEY_LIST_BUDGET_EXCEEDED')
    if len(matching)>1:
        raise CredentialError('AMBIGUOUS_EXISTING_GOOGLE_KEYS')
    if matching:
        key=matching[0]
        allowed=key.get('restrictions',{}).get('apiTargets',[])
        if allowed!=[{'service':'generativelanguage.googleapis.com'}]:
            raise CredentialError('EXISTING_KEY_RESTRICTIONS_REQUIRE_REVIEW')
    else:
        operation=_request(client,'POST',base,headers=headers,json={
            'displayName':'ANT-AI-AUTO-KEYS-002',
            'restrictions':{'apiTargets':[{'service':'generativelanguage.googleapis.com'}]}})
        for _ in range(20):
            if operation.get('done'):break
            name=operation.get('name','')
            if not re.fullmatch(r'operations/[A-Za-z0-9_-]+',name):
                raise CredentialError('INVALID_GOOGLE_OPERATION')
            time.sleep(.5)
            operation=_request(client,'GET','https://apikeys.googleapis.com/v2/'+name,headers=headers)
        if not operation.get('done') or operation.get('error'):
            raise CredentialError('GOOGLE_KEY_CREATION_PENDING_OR_DENIED; no billing/API activation attempted')
        key=operation.get('response',{})
    name=key.get('name','')
    if not name.startswith('projects/'+project_number+'/locations/global/keys/'):
        raise CredentialError('INVALID_GOOGLE_KEY_RESOURCE')
    return _request(client,'GET','https://apikeys.googleapis.com/v2/'+name+'/keyString',headers=headers)['keyString']


def provision_openrouter(*,client=None):
    if os.environ.get('OPENROUTER_API_KEY'):
        return os.environ['OPENROUTER_API_KEY']
    management=os.environ.get('OPENROUTER_MANAGEMENT_KEY')
    if not management:
        raise CredentialError('OPENROUTER_AUTH_REQUIRED: use official OAuth PKCE workflow')
    client=client or httpx.Client()
    # Management listings cannot reveal previous raw keys: never mint a duplicate named key.
    headers={'Authorization':'Bearer '+management}
    for page in range(100):
        listed=_request(client,'GET','https://openrouter.ai/api/v1/keys',headers=headers,params={'offset':page*100})
        rows=listed.get('data',[])
        if any(k.get('name')=='ANT-AI-AUTO-KEYS-002' for k in rows):
            raise CredentialError('EXISTING_KEY_NOT_RETRIEVABLE: restore existing secret or rotate explicitly')
        if len(rows)<100:break
    else:
        raise CredentialError('OPENROUTER_KEY_LIST_BUDGET_EXCEEDED')
    expires=(datetime.now(timezone.utc)+timedelta(days=7)).strftime('%Y-%m-%dT%H:%M:%SZ')
    response=_request(client,'POST','https://openrouter.ai/api/v1/keys',headers=headers,
        json={'name':'ANT-AI-AUTO-KEYS-002','limit':0,'include_byok_in_limit':True,'expires_at':expires})
    return response['key']


class PKCEFlow:
    def __init__(self,callback_url):
        url=urlparse(callback_url)
        if url.scheme!='http' or url.hostname not in ('127.0.0.1','localhost') or not url.port or url.query or url.fragment:
            raise CredentialError('only explicit loopback callback supported')
        self.callback_url=callback_url
        self.state=secrets.token_urlsafe(32);self.verifier=secrets.token_urlsafe(64)
        self.created=time.monotonic();self.used=False
        challenge=base64.urlsafe_b64encode(hashlib.sha256(self.verifier.encode()).digest()).rstrip(b'=').decode()
        self.url='https://openrouter.ai/auth?'+urlencode({'callback_url':callback_url,'code_challenge':challenge,
                                                       'code_challenge_method':'S256','state':self.state})

    def exchange(self,code,state,*,client=None):
        if self.used or time.monotonic()-self.created>600 or not secrets.compare_digest(state,self.state) or not code:
            raise CredentialError('invalid/expired OAuth callback')
        self.used=True
        result=_request(client or httpx.Client(),'POST','https://openrouter.ai/api/v1/auth/keys',
                        json={'code':code,'code_verifier':self.verifier,'code_challenge_method':'S256'})
        return result['key']


def oauth_local(destination,repository):
    """Run on the user's machine; login happens at OpenRouter, not in this app."""
    preflight_destination(destination,repository,'OPENROUTER_API_KEY')
    flow=PKCEFlow('http://127.0.0.1:8766/callback');result={}
    class Callback(BaseHTTPRequestHandler):
        def log_message(self,*args):pass  # callback query contains sensitive authorization code
        def do_GET(self):
            url=urlparse(self.path);query=parse_qs(url.query)
            try:
                if url.path!='/callback':raise CredentialError('wrong callback')
                preflight_destination(destination,repository,'OPENROUTER_API_KEY')
                key=flow.exchange(query.get('code',[''])[0],query.get('state',[''])[0])
                save_secret(destination,'OPENROUTER_API_KEY',key,repository)
                result['ok']=True;message=b'Credential saved server-side. You may close this tab.';status=200
            except (ValueError,KeyError,OSError):
                result['ok']=False;message=b'Authorization not completed. No credential was exposed.';status=400
            self.send_response(status);self.send_header('Content-Type','text/plain');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(message)
    with HTTPServer(('127.0.0.1',8766),Callback) as server:
        server.timeout=30
        print('Open this official authorization link on this machine:\n'+flow.url,flush=True)
        while time.monotonic()-flow.created<600 and not result:
            server.handle_request()
    if not result.get('ok'):
        raise CredentialError('OAuth not completed')
    print('OPENROUTER_API_KEY saved privately; configure its zero spending limit in OpenRouter settings before testing.')


def main():
    parser=argparse.ArgumentParser(description='Official credential discovery/provisioning; never print secrets')
    parser.add_argument('action',choices=['discover','gemini','openrouter','openrouter-oauth'])
    parser.add_argument('--project-number');parser.add_argument('--destination',type=Path)
    args=parser.parse_args()
    if args.action=='discover':print(json.dumps(discover()));return
    if not args.destination:parser.error('explicit private server-side destination required')
    repo=Path(__file__).resolve().parents[3]
    try:
        preflight_destination(args.destination,repo,'GEMINI_API_KEY' if args.action=='gemini' else 'OPENROUTER_API_KEY')
        if args.action=='openrouter-oauth':oauth_local(args.destination,repo);return
        key=provision_gemini(args.project_number or '') if args.action=='gemini' else provision_openrouter()
        save_secret(args.destination,'GEMINI_API_KEY' if args.action=='gemini' else 'OPENROUTER_API_KEY',key,repo)
        print(json.dumps({'saved':True,'verification':'not yet performed; use provider status then minimal authorized test'}))
    except (ValueError,KeyError,OSError,subprocess.SubprocessError) as exc:
        # CLI traceback must never echo an exception carrying transport/auth content.
        print(json.dumps({'saved':False,'status':str(exc) if isinstance(exc,CredentialError) else 'AUTHENTICATION_OR_CONFIGURATION_REQUIRED','guide':'docs/AI_PROVIDER_LAB_AR.md'}))
        raise SystemExit(2)

if __name__=='__main__':main()
