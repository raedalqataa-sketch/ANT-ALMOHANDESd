"""Independent DXF room/line coordinate checks and PDF expected metric scenes.

Uses original exporters unchanged. PDF vector verification/rendering runs with
render_evidence.py and PyMuPDF, not a screenshot of invented geometry.
"""
import argparse,json,math
from pathlib import Path
from collections import Counter
import ezdxf
from backend.design.general_drawing import drawing


def point_key(p):return tuple(round(v,5) for v in tuple(p)[:2])
def segment(a,b):return tuple(sorted((point_key(a),point_key(b))))


def audit(model,path):
    rev=model['model_revision_id'];doc=ezdxf.readfile(path/(rev+'.dxf'));assert not doc.audit().errors
    scenes=[drawing(model,f) for f in model['floors']]+[drawing(model,model['floors'][0],site_view=True)]
    expected_lines=Counter();expected_rooms=Counter();frames=[]
    for index,scene in enumerate(scenes):
        offset=index*(model['site']['width']+8)
        def pt(p):return (offset+p[0],model['site']['depth']-p[1])
        for p in scene.items:
            if p['type']=='line' and p['layer']!='WALL':expected_lines[(p['layer'],segment(pt(p['a']),pt(p['b'])))]+=1
        if index<len(model['floors']):
            for r in model['floors'][index]['rooms']:
                x,y,w,h=r['x'],r['y'],r['width'],r['depth'];expected_rooms[tuple(sorted(point_key(pt(p)) for p in [(x,y),(x+w,y),(x+w,y+h),(x,y+h)]))]+=1
        vx,vy,vw,vh=scene.viewbox;pw,ph=1190.55,1683.78;scale=min((pw-75)/vw,(ph-80)/vh);ox=(pw-vw*scale)/2;oy=(ph-vh*scale)/2
        frames.append(dict(page=index,viewbox=scene.viewbox,scale=scale,ox=ox,oy=oy,
            lines=[[[ox+(p['a'][0]-vx)*scale,oy+(p['a'][1]-vy)*scale],[ox+(p['b'][0]-vx)*scale,oy+(p['b'][1]-vy)*scale]] for p in scene.items if p['type']=='line']))
    actual_lines=Counter((e.dxf.layer,segment(e.dxf.start,e.dxf.end)) for e in doc.modelspace().query('LINE'))
    actual_rooms=Counter(tuple(sorted(point_key(p) for p in e.get_points('xy'))) for e in doc.modelspace().query('LWPOLYLINE[layer=="ROOM"]'))
    assert not expected_lines-actual_lines,'DXF scene line mismatch'
    assert expected_rooms==actual_rooms,'DXF net room geometry mismatch'
    return dict(revision=rev,expected_dxf_line_count=sum(expected_lines.values()),matched_room_polygons=sum(expected_rooms.values()),dxf_coordinate_match=True,
                pdf_frames=frames,scope='DXF all scene LINE primitives and exact net-room polygons; PDF separate vector comparison; not every arc/text primitive verified')


def main():
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);args=p.parse_args();rows=[]
    for path in sorted(args.root.glob('*/report.json')):
        result=json.loads(path.read_text())
        for stage,key,where in [('after','candidates',path.parent),('before','baseline_candidates',path.parent/'baseline')]:
            for m in result[key]:
                r=audit(m,where);r.update(case=path.parent.name,stage=stage,path=str(where/(m['model_revision_id']+'.pdf')),model=m);rows.append(r)
    (args.root/'export-vector-evidence.json').write_text(json.dumps(rows,ensure_ascii=False))
    print('DXF geometry matched',len(rows),'accepted alternatives')


if __name__=='__main__':main()
