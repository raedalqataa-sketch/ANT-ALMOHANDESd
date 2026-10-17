"""Replay exactly the seeded v0.2 synthetic sample against the new bounded packer."""
import json
import random
from pathlib import Path
from quality_review.evaluate import project, geometry_errors, known_tiling, SEED
from backend.packing import layout


def main():
    rng=random.Random(SEED)
    counts={'random_total':1200,'random_accepted':0,'random_invalid_accepted':0,'tiling_total':300,'tiling_accepted':0,'tiling_invalid_accepted':0}
    for i in range(1200):
        pw,pd=rng.randint(5,40),rng.randint(5,40)
        dims=[(rng.randint(5,pw*10)/10,rng.randint(5,pd*10)/10) for _ in range(rng.randint(1,25))]
        p=project(pw,pd,dims)
        try:rooms=layout(p)
        except ValueError:continue
        counts['random_accepted']+=1
        counts['random_invalid_accepted']+=bool(geometry_errors(p,rooms))
    for i in range(300):
        pw,pd=rng.randint(6,20),rng.randint(6,20)
        witness=known_tiling(rng,pw,pd,rng.randint(3,12))
        p=project(pw,pd,[(w,h) for x,y,w,h in witness])
        try:rooms=layout(p)
        except ValueError:continue
        counts['tiling_accepted']+=1
        counts['tiling_invalid_accepted']+=bool(geometry_errors(p,rooms))
    report={'seed':SEED,'baseline_v02':{'random_accepted':118,'random_invalid_accepted':0,'tiling_accepted':64,'tiling_total':300},'v03':counts,
            'scope':'Synthetic rectangle-packing benchmark. Not a measure of architectural quality, real-world success, or the separate villa-layout family.'}
    Path('quality_review/benchmark_v03_results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps(report,ensure_ascii=False,indent=2))
    assert counts['random_invalid_accepted']==counts['tiling_invalid_accepted']==0


if __name__=='__main__':main()
