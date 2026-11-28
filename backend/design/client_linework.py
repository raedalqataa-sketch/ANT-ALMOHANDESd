"""Experimental client linework; metres, not construction drawings."""
import ezdxf
from .client_geometry import generate_geometry

def export_client(program,envelopes,path):
    if program.floor_count!=1:
        return {'status':'needs_data','reason':'Coordinated vertical core not implemented'}
    result=generate_geometry(program,envelopes)
    if result['status']!='geometry_candidate':return result
    doc=ezdxf.new('R2010')
    doc.units=6
    for layer in ('WALL','DOOR','WINDOW','TEXT','DIMENSION'):
        doc.layers.new(layer)
    m=doc.modelspace()
    def line(a,b,layer):
        m.add_line((a[0],-a[1]),(b[0],-b[1]),dxfattribs={'layer':layer})
    def label(x,y,s):
        m.add_text(s,dxfattribs={'height':.18,'insert':(x,-y),'layer':'TEXT'})
    floor=result['layouts'][0]
    hall=floor['corridor']
    edges=set()
    def wall(a,b):
        key=tuple(sorted((tuple(round(v,7) for v in a),tuple(round(v,7) for v in b))))
        if key not in edges:
            edges.add(key);line(a,b,'WALL')
    for room in floor['rooms']:
        x,y,w,d=(room[k] for k in ('x','y','width','depth'))
        top=abs(y+d-hall['y'])<1e-7
        inner=y+d if top else y
        outer=y if top else y+d
        wall((x,y),(x,y+d));wall((x+w,y),(x+w,y+d))
        door=x+w/2-.45
        wall((x,inner),(door,inner));wall((door+.9,inner),(x+w,inner))
        sign=-1 if top else 1
        line((door,inner),(door,inner+sign*.9),'DOOR')
        m.add_arc((door,-inner),.9,0 if top else 270,90 if top else 360,dxfattribs={'layer':'DOOR'})
        if room['kind'] not in ('bathroom','storage','stairs'):
            win=min(1.5,w-.4);a=x+(w-win)/2;b=a+win
            wall((x,outer),(a,outer));wall((b,outer),(x+w,outer))
            for off in (-.05,.05):line((a,outer+off),(b,outer+off),'WINDOW')
        else:wall((x,outer),(x+w,outer))
        label(x+.15,y+d/2,room['program_id'])
        label(x+.15,y+d/2+.3,f'{w:.2f} x {d:.2f} m')
    x,y,w,d=(hall[k] for k in ('x','y','width','depth'))
    wall((x+w,y),(x+w,y+d))
    wall((x,y),(x,y+(d-1)/2));wall((x,y+(d+1)/2),(x,y+d))
    label(x+.1,y+d/2,'ENTRY / HALL')
    doc.saveas(path)
    audit=ezdxf.readfile(path).audit()
    if audit.errors:raise ValueError('DXF audit failed')
    return dict(result,exported=True,accepted=False,pending=result['pending']+['wall thickness and corridor boundary closure','opening legality','privacy and exterior access verification'])
