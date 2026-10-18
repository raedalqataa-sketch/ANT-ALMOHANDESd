"""Reproducible before/after symbol board, unchanged villa layout and R2010 sample.

python -m quality_review.export_furniture_review --output quality_review/furniture_review
"""
import argparse
import copy
import json
import shutil
from pathlib import Path
from backend.design.api import design, OUT
from backend.design.models import DesignOptions
from backend.design.scene import Scene, furniture_symbol, legacy_furniture_symbol
from backend.design.presentation import scene_svg, scene_pdf


def fixture(kind,x,y,width,depth,rotation=0,**extra):
    return dict(kind=kind,x=x,y=y,width=width,depth=depth,rotation=rotation,**extra)


def board(before=False):
    scene=Scene((0,0,20,21))
    scene.rect(0,0,20,21,'#f7f4ed',layer='PAPER')
    scene.text(10,1.0,'تفاصيل الأثاث — '+('قبل التحسين' if before else 'المكتبة الجديدة'),.55,'#433d33')
    scene.text(10,1.65,'المقاسات والتوزيع ثابتان؛ المقارنة في تفاصيل الرسم والخامات فقط',.25,'#8e806b')
    cards=[('الجلوس والتنجيد',[fixture('sofa',2.5,0,3.5,.85,seats=5),fixture('coffee_table',3.6,1.45,1.2,.7)]),
           ('السرير الرئيسي وطبقات المفروشات',[fixture('double_bed',3.3,0,1.8,2),fixture('bedside',2.7,.12,.45,.45),fixture('bedside',5.25,.12,.45,.45)]),
           ('طاولة الطعام والكراسي المنحنية',[]),
           ('السرير المفرد',[fixture('single_bed',3.65,0,1,2),fixture('bedside',4.85,.12,.45,.45)]),
           ('الخشب والخزائن والمكتب',[fixture('wardrobe',3.15,0,2,.55),fixture('desk',3.25,1.30,1.8,.70)]),
           ('الطاولات المتداخلة ووحدة المغسلة',[fixture('coffee_table',3.35,.12,1.6,.85),fixture('basin',3.6,1.6,1.1,.55)])]
    # This is the same ten-seat arrangement used by the model, not added capacity.
    items=[fixture('dining_table',2.90,.65,2.5,1.05)]
    for i in range(4):
        x=2.95+i*1.95/3
        items.extend([fixture('dining_chair',x,.05,.5,.45),fixture('dining_chair',x,1.85,.5,.45,rotation=180)])
    items.extend([fixture('dining_chair',2.3,.90,.45,.5,rotation=270),fixture('dining_chair',5.55,.90,.45,.5,rotation=90)])
    cards[2]=(cards[2][0],items)
    renderer=legacy_furniture_symbol if before else furniture_symbol
    for index,(title,items) in enumerate(cards):
        x=.55+(index%2)*9.7;y=2.2+(index//2)*5.75
        scene.rect(x,y,9.2,5.25,'#fffdf8','#ded5c6',.016,'BOARD',radius=.12)
        scene.text(x+4.6,y+.58,title,.31,'#5d503f')
        scene.line((x+.45,y+.95),(x+8.75,y+.95),'#e4dac8',.012,'BOARD')
        for item in items:
            item=dict(item,x=x+item['x'],y=y+1.55+item['y']);renderer(scene,item)
    scene.text(10,20.4,'أنت المهندس · تفاصيل متجهة قابلة للتكبير · DXF 2010 / AC1024',.24,'#8e806b')
    return scene


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('quality_review/furniture_review'))
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    model=design(DesignOptions(layout_family='social_hub'))['candidates'][0]
    for ext,url in model['downloads'].items():shutil.copyfile(OUT/Path(url).name,args.output/f'villa-furniture-review.{ext}')
    for fid,url in model['previews'].items():
        if fid!='SITE':shutil.copyfile(OUT/Path(url).name,args.output/f'villa-{fid}.svg')
    boards=[board(True),board(False)];floors=[dict(id='BEFORE',name='قبل التحسين'),dict(id='AFTER',name='المكتبة الجديدة')]
    for f,drawing in zip(floors,boards):(args.output/f'furniture-{f["id"].lower()}.svg').write_text(scene_svg(model,f,drawing=drawing),encoding='utf-8')
    review=copy.deepcopy(model);review['floors']=floors
    scene_pdf(review,args.output/'furniture-before-after.pdf',drawings=boards,include_report=False)
    summary={k:model[k] for k in ('model_revision_id','geometry_sha256','presentation','export_audit','metrics')}
    (args.output/'verification.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Furniture comparison and R2010 villa sample:',args.output)


if __name__=='__main__':main()
