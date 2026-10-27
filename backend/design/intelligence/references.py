"""Measured visual preferences condition geometry; never training or legal rules."""
import json
import math
import statistics
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def feature_index():
    path=Path(__file__).resolve().parents[3]/'quality_review/reference_library/measured_features_004.json'
    return json.loads(path.read_text(encoding='utf-8'))


def matching_features(kind):
    rows=[r for r in feature_index()['observations'] if r['kind']==kind and r['project'] not in ('P02','P05')]
    if not rows:return None
    return dict(preferred_aspect_ratio=statistics.median(r['aspect_ratio'] for r in rows),
                observed_range=[min(r['aspect_ratio'] for r in rows),max(r['aspect_ratio'] for r in rows)],
                sample_count=len(rows),source_projects=sorted({r['project'] for r in rows}),
                source_images=sorted({r['image_id'] for r in rows}),legal_rule=False,confidence='small visual printed-label sample')


def preferred_shape(room,lane,t,factor):
    if not room.get('request_id') or room.get('zone')=='guest':return None
    match=matching_features(room['kind'])
    if not match:return None
    area=room['min_area']*max(1.,factor or 1.)
    short=math.sqrt(area/match['preferred_aspect_ratio']);long=area/short
    choices=[]
    for width,depth in ((long,short),(short,long)):
        if min(width,depth)+1e-6<room['min_side']:continue
        if width+t>lane['width']+1e-6 or depth+t>lane['depth']+1e-6:continue
        # Prefer a short run while preserving a corridor-facing edge. Furniture
        # and actual hosted doors still decide feasibility after materialization.
        choices.append((depth if lane['axis']=='y' else width,width,depth))
    if not choices:return None
    _,width,depth=min(choices)
    return dict(net_width=width,net_depth=depth,aspect_ratio=max(width,depth)/min(width,depth),
                source_projects=match['source_projects'],source_images=match['source_images'],sample_count=match['sample_count'],
                method='printed reference proportions scaled to unchanged client program target',legal_rule=False)
