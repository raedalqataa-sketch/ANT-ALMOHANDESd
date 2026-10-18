"""Export contracts: exact CAD release and faithful rotated furniture envelopes."""
import copy
import ezdxf
from backend.design.generator import generate_candidates
from backend.design.models import DesignOptions
from backend.design.export import export_dxf,svg
from backend.design.scene import Scene
from backend.design.furniture_symbols import draw_furniture
from backend.design.vector_paths import flatten_path


def test_furniture_rotations_stay_within_validated_envelopes():
    fixtures=[q for m in generate_candidates(DesignOptions()) for f in m['floors'] for q in f['furniture']+f['outdoor_furniture']]
    supported=set()
    for q in fixtures:
        before=copy.deepcopy(q);scene=Scene((0,0,20,30))
        if not draw_furniture(scene,q):continue
        supported.add(q['kind'])
        assert q==before  # Styling cannot change placement, capacity or use zones.
        for item in scene.items:
            if item['type']=='path':points,_=flatten_path(item['commands'])
            elif item['type']=='line':points=[item['a'],item['b']]
            elif item['type']=='ellipse':points=[(item['x'],item['y']),(item['x']+item['width'],item['y']+item['depth'])]
            else:raise AssertionError(item['type'])
            for x,y in points:
                assert q['x']-1e-6<=x<=q['x']+q['width']+1e-6,(q['kind'],q.get('rotation'),item)
                assert q['y']-1e-6<=y<=q['y']+q['depth']+1e-6,(q['kind'],q.get('rotation'),item)
    assert {'sofa','double_bed','single_bed','dining_table','dining_chair','coffee_table','wardrobe'}<=supported


def test_dxf_is_r2010_and_preserves_furniture_curves(tmp_path):
    m=generate_candidates(DesignOptions(layout_family='social_hub'))[0]
    output=tmp_path/'r2010.dxf';audit=export_dxf(m,output)
    cad=ezdxf.readfile(output)
    assert cad.dxfversion=='AC1024' and cad.header['$ACADVER']=='AC1024'
    assert audit['dxf_version']=='AC1024' and audit['format']=='AutoCAD 2010 DXF'
    assert cad.header['$INSUNITS']==6 and not cad.audit().errors
    assert any(len(e)>16 for e in cad.modelspace().query('LWPOLYLINE[layer=="FURNITURE"]'))
    assert cad.modelspace().query('HATCH[layer=="FURNITURE_FILL"]')
    assert cad.modelspace().query('ARC[layer=="DOOR"]')
    assert not cad.modelspace().query('IMAGE')
    # The SVG uses editable cubic contours as well, with no raster substitutions.
    data=svg(m,m['floors'][0]);assert '<path' in data and '<image' not in data
