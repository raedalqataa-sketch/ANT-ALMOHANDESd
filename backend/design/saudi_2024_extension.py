"""Additional source-bound municipal residential requirements, 2024.

These checks measure a villa draft, not permit approval or full SBC compliance.
Unmodelled measurements remain PENDING, never inferred from suggested geometry.
"""
import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def registry():
    path = Path(__file__).resolve().parents[2] / "constitution/saudi/residential-2024-extension.json"
    return json.loads(path.read_text(encoding="utf-8"))


def checks(model, brief):
    if not brief.apply_saudi_rules:
        return []
    rules = registry()
    source_url = rules["source"]["official_page"]
    results = []

    def record(key, status, label, measured, requirement, evidence, section, page):
        results.append({
            "check_id": "SA-2024-" + key, "status": status, "label": label,
            "evidence": {"measured": measured, "criterion": requirement, **evidence},
            "source": {"id": rules["source"]["id"], "section": section,
                       "pdf_page": page, "url": source_url},
        })

    storey_rule = rules["automated"]["villa_storeys"]
    floors = getattr(brief, "floors", None)
    record("villa-storeys", "PENDING" if floors is None else
           ("PASS" if 1 <= floors <= storey_rule["max"] else "FAIL"),
           "2024: حد أدوار الفيلا السكنية", floors,
           {"max_storeys": storey_rule["max"]},
           {"scope": "الأدوار السكنية فقط؛ الملحق والقبو لهما أحكام مستقلة"},
           storey_rule["section"], storey_rule["page"])

    ground = next((floor for floor in model.get("floors", [])
                   if floor.get("id") == "GF"), None)
    if ground is None and model.get("floors"):
        ground = model["floors"][0]
    entries = [o for o in (ground or {}).get("openings", [])
               if o.get("main_entry") and o.get("kind") == "door"]
    rule = rules["automated"]["main_entrance_width"]
    if not ground:
        status, width = "PENDING", None
    elif not entries:
        status, width = "FAIL", None
    else:
        widths = [o.get("width") for o in entries]
        width = min(widths) if all(isinstance(w, (int, float)) for w in widths) else None
        status = "PENDING" if width is None else ("PASS" if width + 1e-6 >= rule["min_m"] else "FAIL")
    record("main-entrance", status, "2024: عرض مدخل الفيلا", width,
           {"min_m": rule["min_m"]},
           {"entry_count": len(entries), "scope": "عرض فتحة المدخل المرسومة؛ الأبعاد التنفيذية تعتمد بعد المراجعة"},
           rule["section"], rule["page"])

    corridor_rule = rules["automated"]["internal_corridor_width"]
    corridors = [r for f in model.get("floors", []) for r in f.get("rooms", [])
                 if r.get("kind") == "corridor"]
    invalid, missing = [], []
    for room in corridors:
        width, depth = room.get("width"), room.get("depth")
        if not all(isinstance(x, (int, float)) for x in (width, depth)):
            missing.append(room.get("id"))
        elif min(width, depth) + 1e-6 < corridor_rule["min_m"]:
            invalid.append({"id": room.get("id"), "narrowest_m": min(width, depth)})
    status = ("FAIL" if invalid else "PENDING" if missing or not corridors else "PASS")
    record("corridors", status, "2024: الحد الأدنى لعرض الممر الداخلي",
           {"corridors": len(corridors), "invalid": invalid},
           {"min_m": corridor_rule["min_m"]},
           {"missing_measurements": missing, "scope": "فحص محافظ للعرض الصافي المستطيل؛ لا يثبت خلوص الأثاث والأبواب"},
           corridor_rule["section"], corridor_rule["page"])

    # Required evidence cannot be derived safely from 2D floor-plan sketches.
    for item in rules["needs_model_evidence"]:
        if item["when"] != "always":
            continue
        record(item["id"], "PENDING",
               "2024: تحقق إضافي مطلوب — " + item["id"].replace("-", " "),
               None,
               {k: v for k, v in item.items() if k not in ("id", "section", "page", "when", "required")},
               {"required_action": item["required"], "reason": "غير ممثل بقياسات هندسية معتمدة داخل النموذج الحالي"},
               item["section"], item["page"])
    if model.get("stairs"):
        item = next(x for x in rules["needs_model_evidence"] if x["id"] == "guards")
        record(item["id"], "PENDING", "2024: درابزين السلم والفتحات الآمنة",
               None, {}, {"required_action": item["required"]}, item["section"], item["page"])
    if model.get("parking"):
        item = next(x for x in rules["needs_model_evidence"] if x["id"] == "vehicle-entry-width")
        record(item["id"], "PENDING", "2024: عرض مدخل السيارة",
               None, {"min_m": item["min_m"]},
               {"required_action": item["required"]}, item["section"], item["page"])
    return results
