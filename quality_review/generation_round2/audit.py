"""Audit actual browser downloads for every exportable candidate, not synthetic exports."""
import argparse,json
from pathlib import Path
import ezdxf,fitz
from backend.design.general_models import VillaBrief
from backend.design.general_engine import validate_general

def main():
 parser=argparse.ArgumentParser();parser.add_argument('directory',type=Path);args=parser.parse_args();root=args.directory
 result=json.loads((root/'all-candidates.json').read_text());rows=[]
 for model in result['candidates']:
  if not model['release']['drawing_export_allowed']:continue
  folder=root/'candidates'/model['candidate_id'];doc=ezdxf.readfile(folder/'dxf.dxf');errors=doc.audit().errors
  assert doc.dxfversion=='AC1024' and not errors
  assert doc.header['$INSUNITS']==6
  assert not list(doc.modelspace().query('HATCH SOLID TRACE 3DFACE'))
  assert not any(e.dxf.const_width for e in doc.modelspace().query('LWPOLYLINE'))
  pdf=fitz.open(folder/'pdf.pdf');assert len(pdf)>=len(model['floors'])
  for page in pdf:
   assert page.get_text().strip()
  exported=json.loads((folder/'json.json').read_text());assert exported['geometry_sha256']==model['geometry_sha256']
  checks=validate_general(exported,VillaBrief(**exported['brief']))
  failed=[c['check_id'] for c in checks if c['status']=='FAIL'];assert not failed,failed
  requested=sum(r['count'] for r in exported['brief']['rooms'])
  actual=sum(bool(r.get('request_id')) for f in exported['floors'] for r in f['rooms']);assert actual==requested
  assert exported['release']['executive_issue_allowed'] is False
  rows.append({'pattern':model['candidate_id'],'dxf':'AC1024','units':'metres','dxf_audit_errors':len(errors),'fills':False,'pdf_pages':len(pdf),'actual_requested_spaces':actual,'native_independent_recheck_failures':failed,'pending_checks':sum(c['status']=='PENDING' for c in checks),'executive_approved':False})
 assert {r['pattern'] for r in rows}=={'L','U','stepped'}
 report={'all_actual_exports_audited':True,'candidates':rows};(root/'export-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':main()
