"""HTTP adapter; orchestration is shared with the browser-local runtime."""
from pathlib import Path
from fastapi import APIRouter, File, HTTPException, UploadFile
from .models import DesignOptions
from .requirements import import_brief
from .service import get_project,coverage,design as design_service

router=APIRouter(prefix='/api/v2',tags=['architectural-drafts'])
OUT=Path(__file__).resolve().parents[2]/'outputs'
router.get('/project')(get_project)


@router.post('/import-excel')
async def import_excel_brief(file:UploadFile=File(...)):
    if not (file.filename or '').lower().endswith('.xlsx'):
        raise HTTPException(400,'ارفع ملف XLSX')
    data=await file.read(5_000_001)
    if len(data)>5_000_000:
        raise HTTPException(413,'حجم الملف أكبر من 5 ميغابايت')
    try:
        return import_brief(data)
    except Exception as exc:
        raise HTTPException(422,f'تعذرت معاينة مدخلات الفيلا: {exc}')


@router.post('/design')
def design(options:DesignOptions):
    try:
        return design_service(options,output_dir=OUT)
    except ValueError as exc:
        raise HTTPException(422,str(exc))
