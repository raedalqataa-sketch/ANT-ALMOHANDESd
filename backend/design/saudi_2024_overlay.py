"""Geometric evidence checks for 2024 municipal *draft* outlines.

Coordinates use the generator's metric site frame: (0,0) is upper-left,
x increases east, y increases south. These polygons are operator-supplied
overlays, NEVER fabricated by the room allocator. An overlay PASS means
only that supplied geometry matches specified plan geometry.
"""
from math import isfinite

EPS = 1e-5


def signed_area(p):
    return sum(x*v-y*u for (x,y),(u,v) in zip(p,p[1:]+p[:1])) / 2


def bounds(p):
    return min(q[0] for q in p),min(q[1] for q in p),max(q[0] for q in p),max(q[1] for q in p)


def _range_overlap(a,b,c,d):
    return min(max(a,b),max(c,d)) >= max(min(a,b),min(c,d)) - EPS


def valid_polygon(p):
    """Simple, orthogonal (no diagonal), nonzero-area polygons only."""
    if not isinstance(p,list) or len(p)<4 or len(p)>64:
        return False
    if any(len(q)!=2 or any(not isinstance(x,(int,float)) or not isfinite(x) for x in q) for q in p):
        return False
    if len({tuple(q) for q in p}) != len(p) or abs(signed_area(p)) < EPS:
        return False
    edges=list(zip(p,p[1:]+p[:1]))
    for a,b in edges:
        if (abs(a[0]-b[0]) < EPS)==(abs(a[1]-b[1]) < EPS):
            return False
    # No crossing or touching between nonadjacent edges.
    for i,(a,b) in enumerate(edges):
        for j,(c,d) in enumerate(edges):
            if j<=i+1 or (i==0 and j==len(edges)-1):
                continue
            hor=abs(a[1]-b[1])<EPS
            h2=abs(c[1]-d[1])<EPS
            if hor and h2 and abs(a[1]-c[1])<EPS and _range_overlap(a[0],b[0],c[0],d[0]):
                return False
            if not hor and not h2 and abs(a[0]-c[0])<EPS and _range_overlap(a[1],b[1],c[1],d[1]):
                return False
            if hor != h2:
                h=(a,b) if hor else (c,d)
                v=(c,d) if hor else (a,b)
                if min(h[0][0],h[1][0])-EPS<=v[0][0]<=max(h[0][0],h[1][0])+EPS and min(v[0][1],v[1][1])-EPS<=h[0][1]<=max(v[0][1],v[1][1])+EPS:
                    return False
    return True


def point_in_polygon(x,y,p):
    # boundary inclusive for containment; all inputs axis aligned
    inside=False
    for (a,b),(c,d) in zip(p,p[1:]+p[:1]):
        if min(a,c)-EPS<=x<=max(a,c)+EPS and min(b,d)-EPS<=y<=max(b,d)+EPS and (abs(a-c)<EPS or abs(b-d)<EPS):
            return True
        if (b>y)!=(d>y):
            xx=a+(c-a)*(y-b)/(d-b)
            if x<xx:inside=not inside
    return inside


def polygon_intersection(p,q):
    """Exact positive-area overlap for orthogonal polygons using grid cells."""
    if not valid_polygon(p) or not valid_polygon(q):return None
    xs=sorted(set([x for x,y in p]+[x for x,y in q]))
    ys=sorted(set([y for x,y in p]+[y for x,y in q]))
    for x0,x1 in zip(xs,xs[1:]):
        for y0,y1 in zip(ys,ys[1:]):
            x=(x0+x1)/2;y=(y0+y1)/2
            if point_in_polygon(x,y,p) and point_in_polygon(x,y,q):
                return True
    return False


def covered_by(p,others):
    if not valid_polygon(p) or not others or not all(valid_polygon(q) for q in others):
        return False
    xs=sorted(set([x for x,y in p]+[x for q in others for x,y in q]))
    ys=sorted(set([y for x,y in p]+[y for q in others for x,y in q]))
    for x0,x1 in zip(xs,xs[1:]):
        for y0,y1 in zip(ys,ys[1:]):
            x=(x0+x1)/2;y=(y0+y1)/2
            if point_in_polygon(x,y,p) and not any(point_in_polygon(x,y,q) for q in others):
                return False
    return True


def rect_poly(r):
    x,y,w,d=(r[k] for k in ('x','y','width','depth'))
    return [[x,y],[x+w,y],[x+w,y+d],[x,y+d]]


def on_edge(pt,p):
    x,y=pt
    return any(min(a[0],b[0])-EPS<=x<=max(a[0],b[0])+EPS and min(a[1],b[1])-EPS<=y<=max(a[1],b[1])+EPS and
               (abs(a[0]-b[0])<EPS and abs(x-a[0])<EPS or abs(a[1]-b[1])<EPS and abs(y-a[1])<EPS)
               for a,b in zip(p,p[1:]+p[:1]))


def exterior_face(w, floor):
    if not w.get('exterior') or len(w.get('room_ids',[]))!=1:return None
    room=next((r for r in floor.get('rooms',[]) if r['id']==w['room_ids'][0]),None)
    if room is None:return None
    x,y=w['start']
    if w['axis']=='horizontal':
        return 'north' if room['y']+room['depth']/2>y else 'south'
    return 'west' if room['x']+room['width']/2>x else 'east'


def segment_near_rect(w,r):
    a,b=w['start'],w['end']
    if w['axis']=='horizontal':
        return r['y']-EPS<=a[1]<=r['y']+r['depth']+EPS and _range_overlap(a[0],b[0],r['x'],r['x']+r['width'])
    return r['x']-EPS<=a[0]<=r['x']+r['width']+EPS and _range_overlap(a[1],b[1],r['y'],r['y']+r['depth'])


def evaluate(model, brief):
    features=model.get('regulatory_geometry') or {}
    floors={f['id']:f for f in model.get('floors',[])}
    overlays=[]
    def emit(key,status,detail,source_page,**evidence):
        overlays.append(dict(check_id='SA-2024-'+key,status=status,label=detail,
                             evidence={**evidence,'scope':'مطابقة هندسية أولية للمسقط المقترح، لا اعتماد تنفيذي'},
                             source={'id':'MOMAH-RES-2024','pdf_page':source_page,'document_year':2024,'sbc_full_text_verified':False}))
    site=model.get('site',{})
    sw,sd=site.get('width'),site.get('depth')
    site_ready=isinstance(sw,(int,float)) and isinstance(sd,(int,float))
    def inside_plot(poly):
        if not site_ready:return None
        x0,y0,x1,y1=bounds(poly)
        return x0>=-EPS and y0>=-EPS and x1<=sw+EPS and y1<=sd+EPS

    wells=features.get('light_wells')
    if wells:
        bad=[];unknown=[];ok=[]
        for well in wells:
            p=well.get('polygon')
            if p is None:
                unknown.append({'id':well['id'],'reason':'منور بلا مضلع مقاس'});continue
            if not valid_polygon(p):
                bad.append({'id':well['id'],'reason':'مضلع غير صالح أو غير متعامد'});continue
            if inside_plot(p) is False:
                bad.append({'id':well['id'],'reason':'المنور خارج حدود الملكية'});continue
            x0,y0,x1,y1=bounds(p)
            if abs(x1-x0-well['width_m'])>EPS or abs(y1-y0-well['length_m'])>EPS:
                bad.append({'id':well['id'],'reason':'الأبعاد المعلنة لا تطابق المضلع'});continue
            # A genuine light well is an unoccupied void across its served levels.
            levels=list(floors.values())[:well['storeys_served']]
            if len(levels)<well['storeys_served']:
                unknown.append({'id':well['id'],'reason':'بعض الأدوار المطلوبة للمنور غير مرسومة'});continue
            covered=False
            for f in levels:
                if any(polygon_intersection(p,rect_poly(c)) for c in f.get('cells',[])):
                    covered=True;break
            if covered:
                bad.append({'id':well['id'],'reason':'المنور متداخل مع غرف أو ممرات مرسومة'});continue
            ids=well.get('window_ids')
            if not ids:
                unknown.append({'id':well['id'],'reason':'نوافذ المنور لم تربط بمعرفات الفتحات'});continue
            refs={o['id']:(o,f) for f in levels for o in f.get('openings',[])}
            invalid=[]
            for ident in ids:
                found=refs.get(ident)
                if found is None:
                    invalid.append({'window':ident,'reason':'نافذة غير موجودة بالدور'});continue
                o,f=found
                host=next((w for w in f.get('walls',[]) if w['id']==o.get('wall_id')),None)
                if o.get('kind')!='window' or not host or not host.get('exterior') or not on_edge(o['center'],p):
                    invalid.append({'window':ident,'reason':'الفتحة ليست نافذة على حد المنور الفعلي'})
            if invalid:bad.append({'id':well['id'],'windows':invalid})
            else:ok.append({'id':well['id'],'linked_windows':ids})
        emit('lightwell-opening-overlay','FAIL' if bad else 'PENDING' if unknown else 'PASS',
             'مطابقة مضلع المنور مع غرف الأدوار والنوافذ على حدوده',29,
             invalid=bad,pending=unknown,verified=ok)
    elif wells == []:
        emit('lightwell-opening-overlay','NOT_APPLICABLE','لا توجد مناور مصرح بها في مدخلات الهندسة',29)
    else:
        emit('lightwell-opening-overlay','PENDING','يلزم إدخال مضلعات المناور وارتباط النوافذ',29)

    annex=features.get('roof_annex')
    if annex:
        polygon=annex.get('polygon')
        areas=model.get('footprint',{}).get('polygons_by_floor',{})
        parent='FF' if 'FF' in areas else 'GF'
        under=areas.get(parent)
        if polygon is None or under is None:
            emit('annex-footprint-overlay','PENDING','يلزم مضلع الملحق ومسقط الدور الذي تحته',20)
        elif not valid_polygon(polygon):
            emit('annex-footprint-overlay','FAIL','مضلع الملحق العلوي غير صالح',20)
        else:
            geometric_area=abs(signed_area(polygon))
            declared=annex['area_m2']
            parent_area=sum(abs(signed_area(p)) for p in under)
            valid_site=inside_plot(polygon)
            subset=covered_by(polygon,under)
            mismatched=abs(geometric_area-declared)>.025
            ratio=geometric_area/parent_area if parent_area>EPS else None
            # Overall bounding extrema avoid invented setbacks at reentrant facades.
            required=[]
            boundary=getattr(brief,'boundary_widths',{})
            for face,road in boundary.items():
                if road<=0:continue
                pbox=bounds(polygon); fbox=bounds([pt for poly in under for pt in poly])
                gap={'north':pbox[1]-fbox[1],'south':fbox[3]-pbox[3],
                     'west':pbox[0]-fbox[0],'east':fbox[2]-pbox[2]}[face]
                required.append({'face':face,'offset_m':round(gap,3),'min_m':1.5})
            violations=[r for r in required if r['offset_m']<1.5-EPS]
            bad=(mismatched or valid_site is False or ratio is None or ratio>.70+EPS or bool(violations))
            # A cantilever outside lower floor needs a different authority/geometry proof:
            # it cannot be approved by simplistic polygon containment.
            unknown=(valid_site is None or not boundary or not subset)
            emit('annex-footprint-overlay','FAIL' if bad else 'PENDING' if unknown else 'PASS',
                 'مطابقة مساحة الملحق وارتداده مع مضلعات الدور الموجود تحته',20,
                 under_floor=parent,polygon_area_m2=round(geometric_area,3),
                 declared_area_m2=declared,under_area_m2=round(parent_area,3),
                 measured_ratio=round(ratio,4) if ratio is not None else None,
                 street_face_offsets=required,violations=violations,
                 inside_lower_footprint=subset,missing_special_cantilever_review=not subset)
    else:
        emit('annex-footprint-overlay','NOT_APPLICABLE' if features.get('roof_annex_absent') is True else 'PENDING',
             'لا يوجد ملحق موثق / يلزم مضلع الملحق',20)

    protrusions=features.get('projections')
    if protrusions:
        bad=[];pending=[];ok=[]
        for pr in protrusions:
            p=pr.get('polygon')
            if p is None:pending.append({'id':pr['id'],'reason':'لم تُرسل نقاط مضلع البروز'});continue
            if not valid_polygon(p):
                bad.append({'id':pr['id'],'reason':'مضلع البروز غير صالح'});continue
            f=floors.get(pr.get('floor_id','FF'))
            if f is None:
                pending.append({'id':pr['id'],'reason':'الدور الحامل للبروز غير مرسوم'});continue
            face=pr['face']
            # An attached projection must touch an external, face-matched wall.
            hits=[w for w in f.get('walls',[]) if exterior_face(w,f)==face and
                  segment_near_rect(w, {'x':bounds(p)[0],'y':bounds(p)[1],
                                        'width':bounds(p)[2]-bounds(p)[0],'depth':bounds(p)[3]-bounds(p)[1]})]
            if not hits:
                bad.append({'id':pr['id'],'reason':'البروز لا يتصل بجدار خارجي في جهته المعلنة'});continue
            boxp=bounds(p)
            extensions=[]
            for w in hits:
                fixed=w['start'][1] if face in ('north','south') else w['start'][0]
                out={'north':fixed-boxp[1],'south':boxp[3]-fixed,
                     'west':fixed-boxp[0],'east':boxp[2]-fixed}[face]
                if out>EPS:extensions.append(out)
            if not extensions:
                bad.append({'id':pr['id'],'reason':'لا يوجد امتداد خارج حائط الواجهة'});continue
            depth=max(extensions)
            projected_plot=inside_plot(p)
            off={'north':boxp[1],'south':(sd-boxp[3]) if site_ready else None,
                 'west':boxp[0],'east':(sw-boxp[2]) if site_ready else None}[face]
            sb=getattr(brief,'setbacks',None)
            setback_value=getattr(sb,face,None) if sb is not None else None
            computed_in_setback=(off<setback_value-EPS) if off is not None and setback_value is not None else None
            errors=[]
            if abs(depth-pr['depth_m'])>.025:errors.append('measured_vs_declared_depth')
            if projected_plot is not None and pr.get('crosses_property_line') is not None and pr['crosses_property_line']==projected_plot:
                errors.append('property_line_classification_mismatch')
            if computed_in_setback is not None and pr.get('within_setback') is not None and computed_in_setback!=pr['within_setback']:
                errors.append('setback_classification_mismatch')
            evidence={'id':pr['id'],'geometric_depth_m':round(depth,3),'declared_depth_m':pr['depth_m'],
                      'within_setback_computed':computed_in_setback,
                      'inside_plot':projected_plot,'errors':errors}
            if errors:bad.append(evidence)
            elif computed_in_setback is None or projected_plot is None:
                pending.append(evidence)
            else:ok.append(evidence)
        emit('projection-geometry-overlay','FAIL' if bad else 'PENDING' if pending else 'PASS',
             'ربط مضلعات البروزات بالجدار الخارجي وحد الملكية والارتداد',33,
             invalid=bad,pending=pending,measured=ok)
    else:
        emit('projection-geometry-overlay','NOT_APPLICABLE' if protrusions==[] else 'PENDING',
             'لا توجد بروزات مُعلنة / يلزم مضلعات البروزات',33)

    facades=features.get('facades')
    invalid=[];unverified=[];cleared=[]
    if not facades:
        unverified.append({'reason':'واجهات الشوارع الرئيسية ومواقع المعدات غير موثقة'})
    else:
        for survey in facades:
            face=survey['face']
            if survey.get('faces_main_street') is False:continue
            if survey.get('faces_main_street') is None:
                unverified.append({'face':face,'reason':'تصنيف الشارع الرئيسي غير معلوم'});continue
            units=survey.get('equipment')
            if units is None:
                unverified.append({'face':face,'reason':'لم تُقدم مضلعات المعدات'});continue
            hit_ids=[]
            for unit in units:
                f=floors.get(unit.get('floor_id','GF'))
                if f is None:
                    unverified.append({'face':face,'unit':unit['id'],'reason':'دور الجهاز غير موجود'});continue
                if any(segment_near_rect(w,unit) for w in f.get('walls',[]) if exterior_face(w,f)==face):
                    hit_ids.append(unit['id'])
            if hit_ids:
                invalid.append({'face':face,'equipment_on_main_street':hit_ids})
            elif survey.get('inventory_complete') is True:
                cleared.append(face)
            else:
                unverified.append({'face':face,'reason':'لا يوجد تأكيد أن جرد المعدات كامل'})
    emit('facade-equipment-overlay','FAIL' if invalid else 'PENDING' if unverified else 'PASS',
         'ربط مواقع أجهزة الواجهات بجدران الشوارع الرئيسية',32,
         invalid=invalid,pending=unverified,verified_faces=cleared)
    return overlays
