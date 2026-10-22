"""Architectural Constitution V2: evidence-based post-generation gates.

This layer DOES NOT attest legal/code compliance and never invents measured data.
The legacy geometric solver remains unchanged unless opted in by the API caller.
"""
from __future__ import annotations

VERSION = "2.0.0-draft"
STATUS = ("PASS", "FAIL", "REVIEW", "NOT_APPLICABLE")

# Underlying geometric check IDs must exist before a gate can be reported PASS.
GATE_CHECKS = {
    "BUILDABLE_ENVELOPE": ("-site",),
    "SPACE_PROGRAM": ("-program", "-sizes"),
    "ROUTE_CONNECTIVITY": ("-doors", "-walkability", "REF-functional-route"),
    "PRIVACY": ("guest-route",),
    "DOOR_CLEARANCE": ("-door-sweeps", "-openings"),
    "FURNITURE_FIT": ("-fixtures", "-beds"),
    "STAIRS_AND_LIFTS": ("stair-geometry", "vertical-core"),
    "VEHICLE_PEDESTRIAN": ("parking-geometry",),
}
GATE_IDS = (
    "INPUT_GEOMETRY", "BUILDABLE_ENVELOPE", "SPACE_PROGRAM",
    "ROUTE_CONNECTIVITY", "PRIVACY", "DOOR_CLEARANCE", "FURNITURE_FIT",
    "NATURAL_LIGHT_AIR", "STAIRS_AND_LIFTS", "PLUMBING_STACKS",
    "STRUCTURAL_FEASIBILITY", "MEP_MAINTENANCE",
    "VEHICLE_PEDESTRIAN", "INVESTMENT_BUILDING",
    "CODE_COMPLIANCE", "EXPORT_INTEGRITY",
)
WEIGHTS = {
    "functional_completeness_and_adjacency": 20,
    "circulation_efficiency": 15,
    "privacy": 15,
    "daylight_ventilation": 15,
    "furnishing_and_room_proportions": 15,
    "services_vertical_maintenance": 10,
    "site_and_outdoor_use": 5,
    "space_economy_and_massing": 5,
}
MANUS_CROSSWALK = {
    "Z01": "PRIVACY", "Z02": "ROUTE_CONNECTIVITY",
    "Z03": "PRIVACY", "Z04": "ROUTE_CONNECTIVITY",
    "Z05": "ROUTE_CONNECTIVITY", "Z06": "ROUTE_CONNECTIVITY",
    "Z07": "STAIRS_AND_LIFTS", "Z08": "PRIVACY",
    "Z09": "FURNITURE_FIT", "Z10": "DOOR_CLEARANCE",
    "Z11": "STAIRS_AND_LIFTS", "Z12": "MEP_MAINTENANCE",
}
# Do not upgrade these matters to PASS based solely on generic room geometry.
REVIEW_ONLY = {
    "NATURAL_LIGHT_AIR": "الفتحات موجودة جزئيًا؛ كفاية الإضاءة والتهوية وحق الفتح غير معتمدة",
    "PLUMBING_STACKS": "المجاورة والتراكب ليست تصميم تمديدات معتمدًا",
    "STRUCTURAL_FEASIBILITY": "لم يُتحقق من الأعمدة والبحور والكمرات وفتحات البلاطات",
    "MEP_MAINTENANCE": "لم تُقَس خلوصات صيانة جميع التجهيزات",
    "EXPORT_INTEGRITY": "يلزم تدقيق ملفات PDF وDXF بعد التصدير وإعادة فتح DXF",
}
GATE_EXPLANATION = {
    "INPUT_GEOMETRY": "صلاحية أبعاد الأرض ومصدرها",
    "BUILDABLE_ENVELOPE": "احتواء المسقط داخل غلاف الارتدادات المدخلة؛ لا يعني قانونيتها",
    "SPACE_PROGRAM": "حضور الفراغات المطلوبة وأبعادها الصافية",
    "ROUTE_CONNECTIVITY": "الاتصال الهندسي ومسارات الحركة المقاسة",
    "PRIVACY": "فصل حركة الضيوف؛ الرؤية والصوت بحاجة لفحص مستقل",
    "DOOR_CLEARANCE": "الفتحات وأقواس الأبواب والتعارضات",
    "FURNITURE_FIT": "الأثاث الأساسي والسعة داخل الفراغات",
    "NATURAL_LIGHT_AIR": "الإنارة والتهوية الطبيعية",
    "STAIRS_AND_LIFTS": "اتصال النواة الرأسية وأبعادها الجزئية",
    "PLUMBING_STACKS": "تناسق الخدمات الرطبة",
    "STRUCTURAL_FEASIBILITY": "القابلية الإنشائية الأولية",
    "MEP_MAINTENANCE": "وصول الصيانة للخدمات",
    "VEHICLE_PEDESTRIAN": "الموقف والمناورة وعدم تعارض المشاة",
    "INVESTMENT_BUILDING": "مداخل وخدمات ووحدات الاستثمار السكني",
    "CODE_COMPLIANCE": "اشتراطات الموقع المحلية المتحققة من مصادرها",
    "EXPORT_INTEGRITY": "مطابقة مخرجات التصدير للمصدر الهندسي",
}


def _matching(rows, token):
    return [r for r in rows if token in str(r.get("check_id", ""))]


def _from_checks(rows, tokens):
    """Require evidence for every applicable token, never interpret absence as PASS."""
    seen = []
    for token in tokens:
        group = _matching(rows, token)
        # A reference check may be absent if the reference preferences were disabled.
        if token == "REF-functional-route" and not group:
            continue
        if not group:
            return "REVIEW", seen, "لا توجد أدلة فحص مكتملة لجميع البنود"
        seen.extend(group)
    active = [r for r in seen if r.get("status") != "NOT_APPLICABLE"]
    if any(r.get("status") == "FAIL" for r in active):
        return "FAIL", [r["check_id"] for r in active], "فشل فحص هندسي موثق"
    if any(r.get("status") not in ("PASS", "NOT_APPLICABLE") for r in active):
        return "REVIEW", [r["check_id"] for r in active], "توجد بنود غير مكتملة"
    if not active:
        return "NOT_APPLICABLE", [r["check_id"] for r in seen], "الحالة غير مطلوبة لهذا البرنامج"
    return "PASS", [r["check_id"] for r in active], "اجتاز الفحوص الهندسية المحددة فقط"


def assess_candidate(model, intent=None):
    """Return an explicit 16-gate audit. No code certification or fake score."""
    brief = model.get("brief", {})
    checks = list(model.get("checks", []))
    floors = model.get("floors", [])
    multi = len(floors) > 1
    building = (getattr(intent, "building", None) or brief.get("building_type") or "villa")
    parking = model.get("parking") or []
    all_gates = []
    for gate in GATE_IDS:
        status, ids, reason = "REVIEW", [], "بيانات أو اختبار مستقل مطلوب"
        if gate == "INPUT_GEOMETRY":
            w, d = brief.get("plot_width"), brief.get("plot_depth")
            if not (isinstance(w, (float, int)) and isinstance(d, (float, int)) and w > 0 and d > 0):
                status, reason = "FAIL", "أبعاد الأرض مفقودة أو غير صحيحة"
            else:
                reason = "الأبعاد مدخلة؛ مصدر المسح وحدود الملكية تحتاج مراجعة"
        elif gate in REVIEW_ONLY:
            reason = REVIEW_ONLY[gate]
            if gate == "NATURAL_LIGHT_AIR":
                missing = [r["check_id"] for r in _matching(checks, "-windows") if r.get("status") == "FAIL"]
                if missing: status, ids, reason = "FAIL", missing, "فراغ مطلوب بلا نافذة خارجية وفق فحص المحرك"
        elif gate == "CODE_COMPLIANCE":
            failures = [r["check_id"] for r in checks if r.get("status") == "FAIL" and
                        (r.get("check_id", "").startswith("SA-") or
                         r.get("check_id", "").startswith("YE-"))]
            if failures: status, ids, reason = "FAIL", failures, "فشل فحص موثق من وحدة الاختصاص"
            else: reason = "مطابقة الارتدادات البلدية ومصدر الكود المحلي لا تزال غير معتمدة"
        elif gate == "INVESTMENT_BUILDING":
            status, reason = (("REVIEW", "يلزم محرك وفحوص للوحدات المستقلة والإخلاء والخدمات المشتركة")
                              if building in ("investment", "residential_investment_building")
                              else ("NOT_APPLICABLE", "ليس مبنى استثماريًا"))
        elif gate == "STAIRS_AND_LIFTS" and not multi:
            status, reason = "NOT_APPLICABLE", "دور واحد؛ لا درج بين الأدوار"
        elif gate == "VEHICLE_PEDESTRIAN" and not parking:
            status, reason = "NOT_APPLICABLE", "لا توجد مواقف مصممة"
        elif gate in GATE_CHECKS:
            status, ids, reason = _from_checks(checks, GATE_CHECKS[gate])
            if gate == "PRIVACY" and status == "PASS":
                status, reason = "REVIEW", "مسار الضيوف اجتاز الفحص؛ الرؤية والصوت لم يُتحقق منهما"
            if gate == "VEHICLE_PEDESTRIAN" and status == "PASS":
                status, reason = "REVIEW", "الهندسة الأساسية للمواقف صحيحة؛ المناورة والبوابات والمشاة غير مفحوصة"
            if gate == "STAIRS_AND_LIFTS" and status == "PASS":
                status, reason = "REVIEW", "موضع وبئر الدرج صحيحان؛ الخلوص الرأسي والإخلاء والمصعد غير معتمدين"
        all_gates.append({"id": gate, "status": status, "label_ar": GATE_EXPLANATION[gate],
                          "evidence_check_ids": ids, "reason_ar": reason})
    failures = [g["id"] for g in all_gates if g["status"] == "FAIL"]
    reviews = [g["id"] for g in all_gates if g["status"] == "REVIEW"]
    return {
        "version": VERSION, "policy": "architectural_proposal_not_building_code",
        "source": "143 visual design guidelines + adapted Manus Z01-Z12; phased implementation",
        "gate_count": len(all_gates), "gates": all_gates, "manus_crosswalk": MANUS_CROSSWALK,
        "hard_failures": failures, "review_required": reviews,
        "release_decision": "BLOCKED" if failures else "DRAFT_REVIEW",
        "executive_approval": False,
        "score_100": None, "score_note_ar": "لا تُنشأ درجة نهائية قبل قياس المعايير ومعايرتها",
        "proposed_weights_not_yet_calibrated": WEIGHTS,
        "scope": "فحوص جزئية للفلل والمسكن الخاص فقط؛ ليست تنفيذًا كاملًا لـ143 قاعدة",
    }


def public_manifest():
    return {
        "version": VERSION, "status": "EXPERIMENTAL_OPT_IN",
        "gates": [{"id": g, "label_ar": GATE_EXPLANATION[g]} for g in GATE_IDS],
        "manus_constraints": list(MANUS_CROSSWALK),
        "scoring_weights": WEIGHTS,
        "restrictions": ["لم يُنفذ مولد حر لشكل الكتلة بعد", "لا تصديق نظامي أو إنشائي",
                         "المخرجات المعتمدة لا تتغير قبل المراجعة"],
    }
