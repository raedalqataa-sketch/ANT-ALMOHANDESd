"""Compare actual exports of the same household program before/after massing changes."""
import json,argparse
from pathlib import Path
import fitz
from backend.design.massing_quality import measures

def main():
 p=argparse.ArgumentParser();p.add_argument('before',type=Path);p.add_argument('after',type=Path);p.add_argument('output',type=Path);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
 before=json.loads((a.before/'all-candidates.json').read_text());after=json.loads((a.after/'all-candidates.json').read_text());baseline={m['candidate_id']:m for m in before['candidates']};rows=[];pdf=fitz.open()
 for m in after['candidates']:
  if not m['release']['drawing_export_allowed']:continue
  old=baseline[m['candidate_id']]
  assert old['brief']['setbacks']==m['brief']['setbacks'] and old['brief']['rooms']==m['brief']['rooms']
  q0=measures(old['floors'][0]['cells']);q1=measures(m['floors'][0]['cells'])
  row={'pattern':m['candidate_id'],'before':q0,'after':q1,'setbacks_unchanged':True,'program_unchanged':True,'massing_fallback':m['profile'].get('massing_fallback',False)};rows.append(row)
  page=pdf.new_page(width=1190,height=842);page.insert_text((30,26),m['candidate_id']+' | Same plot, program and setbacks | BEFORE / AFTER',fontsize=13)
  for idx,folder in enumerate((a.before,a.after)):
   with fitz.open(folder/'candidates'/m['candidate_id']/'pdf.pdf') as source:
    page.show_pdf_page(fitz.Rect(10+idx*590,40,590+idx*590,820),source,0)
 pdf.save(a.output/'before-after.pdf');(a.output/'comparison.json').write_text(json.dumps({'candidates':rows},indent=2)+'\n');print(json.dumps(rows,indent=2))
if __name__=='__main__':main()
