"""Render actual PDF vectors and overlay diagnostic geometry, never invented plans.
Run using a Python with PyMuPDF and Pillow after export_evidence.py.
"""
import argparse,json,math
from pathlib import Path
import fitz
from PIL import Image,ImageDraw


def main():
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);a=p.parse_args();rows=json.loads((a.root/'export-vector-evidence.json').read_text());pictures={};audits=[]
    for row in rows:
        doc=fitz.open(row['path']);m=row['model'];page_results=[]
        for frame in row['pdf_frames']:
            index=frame['page'];page=doc[index];actual=[]
            for path in page.get_drawings():
                for item in path['items']:
                    if item[0]=='l':actual.append((tuple(item[1]),tuple(item[2])))
            def close(a,b):return abs(a[0]-b[0])<.025 and abs(a[1]-b[1])<.025
            absent=[(u,v) for u,v in frame['lines'] if not any((close(u,x) and close(v,y)) or (close(u,y) and close(v,x)) for x,y in actual)]
            assert not absent,('PDF metric line mismatch',row['revision'],index,len(absent))
            page_results.append(dict(page=index+1,expected_line_segments=len(frame['lines']),missing=0))
            if index>=len(m['floors']):continue
            pix=page.get_pixmap(matrix=fitz.Matrix(.65,.65));image=Image.frombytes('RGB',(pix.width,pix.height),pix.samples);overlay=Image.new('RGBA',image.size);draw=ImageDraw.Draw(overlay)
            f=m['architecture_intelligence']['floors'][index] if m.get('architecture_intelligence') else None
            if not f:
                # Read existing baseline diagnostics from results, already measured.
                case=next(r for r in json.loads((a.root/'results.json').read_text()) if r['case']==row['case'])
                f=next(c for c in case['before'] if c['revision']==row['revision'])['metrics']['floors'][index]
            vx,vy,*_=frame['viewbox'];scale=frame['scale'];ox,oy=frame['ox'],frame['oy']
            def pt(p):return ((ox+(p[0]-vx)*scale)*.65,(oy+(p[1]-vy)*scale)*.65)
            for field,colour in [('circulation_polygons',(40,120,240,65)),('internal_required_path_polygons',(255,170,0,85))]:
                for poly in f[field]:
                    draw.polygon([pt(q) for q in poly['coordinates'][0]],fill=colour)
                    for hole in poly['coordinates'][1:]:draw.polygon([pt(q) for q in hole],fill=(0,0,0,0))
            image=Image.alpha_composite(image.convert('RGBA'),overlay).convert('RGB');draw=ImageDraw.Draw(image)
            draw.text((15,15),row['case']+' '+row['stage']+' '+m['floors'][index]['id'],fill='black')
            draw.text((15,30),'Blue: corridor union | Orange: sampled internal movement',fill='black')
            name=f"{row['case']}-{row['stage']}-{row['revision']}-{m['floors'][index]['id']}.png";image.save(a.root/name)
            pictures[(row['case'],row['stage'],row['revision'],index)]=image
        audits.append(dict(case=row['case'],stage=row['stage'],revision=row['revision'],pages_checked=page_results,dxf_coordinate_match=row['dxf_coordinate_match'],matched_room_polygons=row['matched_room_polygons']))
    results=json.loads((a.root/'results.json').read_text())
    for case in results:
        for rank,(b,c) in enumerate(zip(case['before'],case['after']),1):
            for floor in range(2):
                im1=pictures[(case['case'],'before',b['revision'],floor)];im2=pictures[(case['case'],'after',c['revision'],floor)]
                panel=Image.new('RGB',(im1.width+im2.width,max(im1.height,im2.height)), 'white');panel.paste(im1,(0,0));panel.paste(im2,(im1.width,0));panel.save(a.root/f"{case['case']}-rank-{rank}-{'GF' if floor==0 else 'FF'}-comparison.png")
    (a.root/'pdf-dxf-vector-verification.json').write_text(json.dumps(audits,indent=2));print('PDF vectors and DXF geometry verified',len(audits),'plans')


if __name__=='__main__':main()
