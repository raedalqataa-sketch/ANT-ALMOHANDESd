"""Source-preserving mapping for the adopted project brief (not free-text NLP)."""
import copy
import hashlib
import json
from pathlib import Path
from io import BytesIO
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT/'requirements'/'villa-almahfad.json'
BUNDLE = ROOT/'constitution'/'references'/'floor_plan_rules_v1.json'


def project_profile():
    return json.loads(PROFILE.read_text(encoding='utf-8'))


def rules_summary():
    data = json.loads(BUNDLE.read_text(encoding='utf-8'))
    return {'schema_id':data['schema_id'], 'schema_version':data['schema_version'],
            'sha256':hashlib.sha256(BUNDLE.read_bytes()).hexdigest(), 'counts':data['counts'],
            'known_gaps':data['known_gaps'], 'runtime_note':'فهرس القواعد مرجع. لا يعني تحميله اجتيازها أو تنفيذها جميعًا.',
            'active_scope':'مقترحات ثنائية الدور من عائلة توزيع محدودة، وفحوص هندسية معلنة؛ ليست جاهزية تنفيذية'}


def normalize_number(value):
    text = str(value).translate(str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹٫','01234567890123456789.')).strip()
    result = float(text)
    if not 0 < result < 10000:
        raise ValueError('القيمة العددية خارج النطاق المدعوم')
    return result


def import_brief(data):
    wb = load_workbook(BytesIO(data), read_only=True, data_only=True)
    try:
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
    finally:
        wb.close()
    cells = {str(r[0]).strip():r[1] for r in rows if len(r)>1 and r[0] is not None}
    required = ['اسم المشروع','عرض الأرض بالمتر','عمق الأرض بالمتر','عدد الأدوار','عدد أفراد الأسرة']
    if not all(key in cells for key in required):
        raise ValueError('استخدم نموذج مدخلات الفيلا العربي الذي يحتوي اسم المشروع وأبعاد الأرض والأدوار والأسرة')
    profile = project_profile()
    digest = hashlib.sha256(data).hexdigest()
    known = digest == profile['source']['sha256']
    # Program text is not inferred by keyword matching. Only adopted source activates its program.
    mapped = {'title':str(cells[required[0]]), 'plot_width':normalize_number(cells[required[1]]),
              'plot_depth':normalize_number(cells[required[2]]), 'floor_count':normalize_number(cells[required[3]]),
              'household_count':normalize_number(cells[required[4]])}
    return {'document_type':'architectural_brief','recognized_approved_source':known,'requires_mapping_confirmation':True,
            'mapped_fields':mapped, 'raw_fields':[{'field':str(k),'value':v} for k,v in cells.items()],
            'source_sha256':digest,'profile':profile if known else None,
            'reason':'المصدر المعتمد معروف؛ راجع الربط ثم اعتمد المدخلات' if known else 'تمت قراءة الحقول. نص الطلبات المعدل يحتاج مراجعة ربط؛ لم تُفعّل متطلبات المشروع السابق عليه'}
