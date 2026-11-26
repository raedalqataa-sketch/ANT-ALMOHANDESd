"""Convert an Arabic room description to a reviewable program draft."""
import re

from .general_models import SpaceRequest, UpperFloorProgram

DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹٫", "01234567890123456789.")
SPECS = (
    ("majlis", r"مجلس|مجالس", 35, 5),
    ("dining", r"طعام|سفرة", 26.8, 4),
    ("living", r"صالة|معيشة", 25, 5),
    ("kitchen", r"مطبخ|مطابخ", 20, 4),
    ("bathroom", r"حمام|دورة مياه|دورات مياه|مغاسل|حمامات", 7, 2),
    ("master", r"ماستر|نوم رئيسية", 20, 4),
    ("bedroom", r"غرف[ةت]? (?:نوم|أبناء|للنوم|للاطفال|كبار السن)|غرفتان|غرفتين", 16, 3.5),
    ("storage", r"مستودع|مخزن", 5, 1.5),
    ("office", r"مكتب", 9, 2.5),
    ("laundry", r"غسيل", 6, 2),
)


def draft_from_text(brief, text):
    rooms, groups, unresolved = [], {}, []
    last_bed = None
    on_upper = False
    upper_program = None
    for raw in re.split(r"[،,؛;\n]+|\s+و(?=مجلس|صالة|غرفة|مطبخ|حمام|مستودع|طعام)", text):
        phrase = raw.strip().translate(DIGITS)
        if not phrase:
            continue
        upper_marker = re.match(r"(?:الدور الأول|الدور العلوي|الطابق الأول)\s*[:：]?\s*", phrase)
        ground_marker = re.match(r"(?:الدور الأرضي|الطابق الأرضي)\s*[:：]?\s*", phrase)
        if upper_marker or ground_marker:
            on_upper = bool(upper_marker)
            marker = upper_marker or ground_marker
            phrase = phrase[marker.end():]
            if not phrase:
                continue
        if on_upper:
            count_match = re.search(r"(?:غرفتان|غرفتين)|([23]) غرف|ثلاث(?:ة)? غرف", phrase)
            if not count_match or not re.search("نوم|أبناء|اولاد|أولاد|أطفال", phrase) or upper_program is not None:
                unresolved.append(raw.strip())
                continue
            count = int(count_match[1]) if count_match[1] else 3 if "ثلاث" in phrase else 2
            area_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:م²|م2|متر مربع)", phrase)
            side_match = re.search(r"(?:العرض|عرض|أقصر ضلع)\s*(\d+(?:\.\d+)?)\s*م", phrase)
            upper_program = UpperFloorProgram(
                children=count, child_area_m2=float(area_match[1]) if area_match else 11.5,
                child_min_side_m=float(side_match[1]) if side_match else 2.7,
            ).model_dump()
            continue
        found = [(kind, area, side) for kind, pattern, area, side in SPECS if re.search(pattern, phrase)]
        if len(found) != 1:
            unresolved.append(raw.strip())
            continue
        kind, area, side = found[0]
        guest = "women" if "نساء" in phrase else "men" if re.search("رجال|ضيوف|الضيافة", phrase) else None
        if kind == "majlis":
            guest = guest or "men"
            if guest == "women":
                area, side = 21.2, 4
        if kind == "dining" and guest:
            area, side = 12.25, 3.5
        area_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:م²|م2|متر مربع)", phrase)
        side_match = re.search(r"(?:العرض|عرض|أقصر ضلع)\s*(\d+(?:\.\d+)?)\s*م", phrase)
        count_match = re.search(r"^\s*(\d+)\s+", phrase)
        count = int(count_match[1]) if count_match else 2 if re.search(r"غرفتان|غرفتين", phrase) else (
            3 if re.search(r"ثلاث(?:ة)? غرف", phrase) else 1
        )
        name = re.split(r"\s+(?:بمساحة|مساحة|العرض|عرض|أقصر ضلع)|\s+\d+(?:\.\d+)?\s*م", raw.strip(), maxsplit=1)[0]
        req_id = f"text-{len(rooms)+1}"
        ensuite_for = last_bed if kind == "bathroom" and "خاص" in phrase else None
        if kind == "bathroom" and "خاص" in phrase and not ensuite_for:
            unresolved.append(raw.strip())
            continue
        room = SpaceRequest(id=req_id, name=name, kind=kind, floor=0, count=count,
                            min_area=float(area_match[1]) if area_match else area,
                            min_side=float(side_match[1]) if side_match else side, ensuite_for=ensuite_for)
        rooms.append(room.model_dump())
        if kind in ("bedroom", "master"):
            last_bed = req_id if count == 1 else None
        if guest and kind in ("majlis","dining","bathroom","storage") and not ensuite_for:
            groups.setdefault(guest, []).append(req_id)
    if not rooms:
        raise ValueError("لم يتعرّف المحرك على غرف في الوصف. افصل الفراغات بفواصل أو أسطر.")
    snapshot = {
        **brief.model_dump(), "floors":1, "rooms":rooms, "spatial_requirements":[],
        "guest_groups":[{"id":key, "entry":key, "rooms":ids} for key, ids in groups.items()],
    }
    result = type(brief).model_validate(snapshot)
    return {"brief":result.model_dump(), "unresolved":unresolved, "upper_program":upper_program}
