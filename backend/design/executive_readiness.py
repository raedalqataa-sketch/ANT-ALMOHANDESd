"""Evidence-bound executive drawing readiness.

An automated geometric draft cannot be certified as an executable building plan.
This checklist is always NOT_APPROVED until signed, site-specific external
verification occurs outside the generator; never infer approvals from PASS.
"""

SIGNOFFS=(
    ("PARCEL_SURVEY","رفع مساحي موثق وحدود وواجهات الشوارع وارتدادات القطعة"),
    ("LOCAL_CODE","تدقيق الاشتراطات المحلية والكود المنطبق من مختص مخول"),
    ("ARCHITECTURE","مراجعة معمارية تنفيذية للأبعاد والأبواب والخصوصية والتهوية"),
    ("STRUCTURE","تصميم إنشائي وحساب الأحمال والأساسات والقطاعات"),
    ("MEP_FIRE","مخططات كهرباء وسباكة وتكييف وسلامة وإخلاء معتمدة"),
    ("COORDINATION","تنسيق جميع التخصصات وإصدار اللوحات والتفاصيل والمواصفات"),
    ("LICENSED_SIGNOFF","توقيع واعتماد مهني وموافقات الجهات المختصة"),
)


def assess(model):
    """Record evidence and genuine missing authorizations, not an automatic seal."""
    checks=model.get("checks",())
    audit=model.get("constitution_v2") or {}
    fail=[c.get("check_id") for c in checks if c.get("status")=="FAIL"]
    pending=[c.get("check_id") for c in checks if c.get("status")=="PENDING"]
    v2=[g.get("id") for g in audit.get("gates",())
        if g.get("status") in ("FAIL","REVIEW","UNKNOWN")]
    return {
        "status":"NOT_APPROVED",
        "issue_type":"PRELIMINARY_ARCHITECTURAL_DESIGN_ONLY",
        "geometry_review_passed":not fail and bool(model.get("floors")),
        "failed_checks":fail,
        "pending_checks":pending,
        "unresolved_constitution_gates":v2,
        "required_signoffs":[{"id":key,"label_ar":label,"status":"NOT_VERIFIED"}
                             for key,label in SIGNOFFS],
        "authorization_granted":False,
        "scope":"تقرير مراجعة أولية فقط؛ لا توقيع ولا ترخيص ولا اعتماد تنفيذي آلي",
    }
