from html.parser import HTMLParser
import json,urllib.request,urllib.parse,concurrent.futures
from pathlib import Path
class Options(HTMLParser):
 def __init__(self):super().__init__();self.on=False;self.value=None;self.items=[]
 def handle_starttag(self,t,a):
  a=dict(a)
  if t=='select':self.on=a.get('id')=='selectAmanaId'
  if t=='option' and self.on:self.value=a.get('value')
 def handle_data(self,s):
  if self.on and self.value:self.items.append({'id':self.value,'name':s.strip()});self.value=None
 def handle_endtag(self,t):
  if t=='select':self.on=False
p=Options();p.feed(Path('/workspace/general-fix-review/saudi-sources/survey.html').read_text())
base='https://apps.balady.gov.sa/Eservices/Inquiries/InquerySurveyReport/GetSubMunicipalities?parentId='
def get(a):
 try:
  with urllib.request.urlopen(base+urllib.parse.quote(a['id']),timeout=20) as r:data=json.loads(r.read(1500000))
  return {**a,'municipalities':data,'downloaded':True}
 except Exception as e:return {**a,'municipalities':[],'downloaded':False,'error':type(e).__name__}
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:rows=list(pool.map(get,p.items))
result={'source':'https://apps.balady.gov.sa/Eservices/Inquiries/InquerySurveyReport','endpoint':base,'retrieved_at':'2026-10-18','scope':'Official public municipality directory; not a database of local building rules','amanats':rows,'all_local_rules_downloaded':False}
out=Path('/workspace/github-ant-almohandes/constitution/saudi/municipalities.json');out.write_text(json.dumps(result,ensure_ascii=False,indent=2))
for a in rows:print(a['name'],a['downloaded'],str(a['municipalities'])[:160])
