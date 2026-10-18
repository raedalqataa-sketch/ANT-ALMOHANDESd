"""Measured 2024 municipal checks for explicitly declared villa geometry.

PASS refers only to a stated, preliminary dimensional/feature check.
Drawing overlay, municipal approvals and SBC 2024 remain separately PENDING.
No approval is inferred from a user-declared dimension.
"""
from .saudi_2024_extension import registry

EPS = 1e-6
FACES = ("north", "south", "east", "west")


def well_minimum(storeys, opposing):
    """Table in 2024 municipal requirements, printed PDF page 29, §5-1-6."""
    base = {
        1: ((0.9, 1.8), (1.5, 1.8)),
        2: ((1.5, 1.8), (1.8, 1.8)),
        3: ((1.8, 2.4), (2.1, 2.4)),
        4: ((2.1, 3.0), (2.4, 3.0)),
    }
    if not isinstance(storeys, int) or not 1 <= storeys <= 14:
        return None
    if storeys <= 4:
        return base[storeys][bool(opposing)]
    w, l = base[4][bool(opposing)]
    return round(w + (storeys - 4) * .3, 5), round(l + (storeys - 4) * .6, 5)


def checks(model, brief):
    if not getattr(brief, "apply_saudi_rules", False):
        return []
    registry_source = registry()["source"]
    features = model.get("regulatory_geometry")  # Produced only from explicit brief.regulatory_geometry
    if not isinstance(features, dict):
        features = {}
    results = []

    def put(key, status, title, section, page, evidence):
        results.append({
            "check_id": "SA-2024-" + key,
            "status": status,
            "label": title,
            "evidence": {
                **evidence,
                "design_stage": "CUSTOMER_DECLARED_PRELIMINARY_GEOMETRY",
                "full_sbc_2024_verified": False,
                "local_permit_verified": False,
            },
            "source": {
                "id": registry_source["id"],
                "title": registry_source["title"],
                "year": registry_source["document_year"],
                "referenced_sbc_edition": registry_source["referenced_sbc_edition"],
                "pdf_page": page,
                "section": section,
                "url": registry_source["official_page"],
            },
        })

    wells = features.get("light_wells")
    if wells is None:
        put("lightwell-dimensions", "PENDING", "المناور: أبعاد واتجاه النوافذ لم تدخل بعد",
            "5-1-6(1)", 29, {"required_action": "أدخل عدد أدوار المنور والعرض والطول واتجاهات نوافذه، أو أكد عدم وجود منور"})
    elif not wells:
        put("lightwell-dimensions", "NOT_APPLICABLE", "المناور: لا يوجد منور معلن في التصميم",
            "5-1-6(1)", 29, {"scope": "لا يثبت هذا اتصال نوافذ الغرف بواجهة خارجية مشروعة"})
    else:
        invalid, observations = [], []
        required_service = ("open_to_sky", "cleaning_door", "drains_provided", "light_wall_finish")
        service_fail, service_missing = [], []
        for well in wells:
            minimum = well_minimum(well["storeys_served"], well["opposing_windows"])
            if minimum is None:
                invalid.append({"id": well["id"], "reason": "storey count invalid"})
                continue
            mw, ml = minimum
            row = {
                "id": well["id"], "storeys_served": well["storeys_served"],
                "opposing_windows": well["opposing_windows"],
                "actual_width_m": well["width_m"], "actual_length_m": well["length_m"],
                "minimum_width_m": mw, "minimum_length_m": ml,
            }
            observations.append(row)
            if well["width_m"] + EPS < mw or well["length_m"] + EPS < ml:
                invalid.append(row)
            for field in required_service:
                if well.get(field) is False:
                    service_fail.append({"id": well["id"], "missing": field})
                elif well.get(field) is not True:
                    service_missing.append({"id": well["id"], "unverified": field})
        put("lightwell-dimensions", "FAIL" if invalid else "PASS",
            "المناور: جدول الأبعاد حسب الارتفاع واتجاه النوافذ", "5-1-6(1)", 29,
            {"wells": observations, "nonconforming": invalid})
        put("lightwell-service", "FAIL" if service_fail else "PENDING" if service_missing else "PASS",
            "المناور: مفتوحة للسماء وباب صيانة وتصريف وتشطيبات فاتحة", "5-1-6(3-7)", 30,
            {"nonconforming": service_fail, "unverified": service_missing})
        put("lightwell-opening-overlay", "PENDING",
            "المناور: مطابقة واجهات النوافذ مع مواقع المناور المرسومة", "5-1-6;5-1-15", 29,
            {"required_action": "يلزم تمثيل مناور حقيقية كفراغات في المسقط وربط النوافذ بواجهاتها والأدوار التي تخدمها"})

    annex = features.get("roof_annex")
    if annex is None:
        st = "NOT_APPLICABLE" if features.get("roof_annex_absent") is True else "PENDING"
        put("annex-area", st, "الملحق العلوي: مساحة الملحق مقارنة بالدور أسفله",
            "4-1(3);5-1-14(2)", 34,
            {"required_action": None if st == "NOT_APPLICABLE" else
             "حدد وجود ملحق علوي وأدخل مساحته المقترحة؛ لا يستنتج وجوده من الدور الأول"})
    else:
        areas = model.get("metrics", {}).get("floor_built_by_id", {})
        parent = "FF" if "FF" in areas else "GF" if "GF" in areas else None
        parent_area = areas.get(parent) if parent else None
        ratio = annex["area_m2"] / parent_area if isinstance(parent_area, (int, float)) and parent_area > 0 else None
        put("annex-area", "PENDING" if ratio is None else "PASS" if ratio <= .70 + EPS else "FAIL",
            "الملحق العلوي: نسبة المساحة لا تتجاوز 70٪", "4-1(3);5-1-14(2)", 34,
            {"annex_area_m2": annex["area_m2"], "below_floor": parent,
             "below_floor_area_m2": parent_area, "ratio": ratio, "max_ratio": .70,
             "area_scope": "مساحة الدور تحسب شاملة حركة السلالم؛ قياس الملحق مُدخل مقترح وليس مضلعًا مرسومًا"})

        street_faces = [f for f in FACES if getattr(brief, "boundary_widths", {}).get(f, 0) > 0]
        setbacks = annex.get("street_setbacks_m") or {}
        wrong = [{"face": face, "measured_m": setbacks[face]} for face in street_faces
                 if face in setbacks and setbacks[face] + EPS < 1.5]
        missing = [face for face in street_faces if face not in setbacks]
        put("annex-street-setback", "FAIL" if wrong else "PENDING" if missing or not
            getattr(brief, "boundary_widths", None) else "PASS",
            "الملحق العلوي: ارتداد 1.50م جهة الشوارع والساحات", "4-1(6)", 20,
            {"violations": wrong, "missing_faces": missing,
             "minimum_m": 1.5, "street_faces": street_faces,
             "required_action": "حدد جهات الشوارع والساحات فعليًا؛ الارتداد من حد الدور أسفل الملحق وليس حد الملكية"})

        problems, unknown = [], []
        for field, bad in (("neighbor_direct_windows", True),
                           ("staircase_continues_to_annex_roof", True)):
            if annex.get(field) is None:unknown.append(field)
            elif annex[field] is bad:problems.append(field)
        parapet = annex.get("parapet_height_m")
        if parapet is None:unknown.append("parapet_height_m")
        elif not .4 - EPS <= parapet <= .8 + EPS:problems.append("parapet_height_m")
        if annex.get("independent_unit"):
            if annex.get("additional_parking_space") is None:unknown.append("additional_parking_space")
            elif annex["additional_parking_space"] is False:problems.append("additional_parking_space")
        put("annex-other-conditions", "FAIL" if problems else "PENDING" if unknown else "PASS",
            "الملحق العلوي: فتحات الجيران وسترة السطح واستقلال الوحدة والدرج",
            "5-1-14(1-5)", 34,
            {"violations": problems, "missing": unknown, "parapet_min_m": .4,
             "parapet_max_m": .8, "independent_unit": annex.get("independent_unit")})
        put("annex-footprint-overlay", "PENDING",
            "الملحق العلوي: مطابقة المساحة والارتدادات مع رسم الملحق", "4-1;5-1-14", 34,
            {"required_action": "يلزم مسقط مستقل للملحق، ومضلع له، ومواقع النوافذ والسلم قبل اعتماد حساب المساحة أو الارتدادات"})

    projections = features.get("projections")
    if projections is None:
        put("projection-regulation", "PENDING", "البروزات: لم تُحدد بروزات الواجهات بعد",
            "5-1-11(1-4)", 32,
            {"required_action": "أدخل لكل بروز جهته وعمقه ونوعه وهل هو داخل الارتداد"})
    elif not projections:
        put("projection-regulation", "NOT_APPLICABLE", "البروزات: لا توجد بروزات معلنة",
            "5-1-11(1-4)", 32, {"scope": "لا يثبت خلو الرسم من البروزات إن لم تُنمذج واجهات/كتل الأدوار"})
    else:
        for pr in projections:
            face = pr["face"]
            street_width = getattr(brief, "boundary_widths", {}).get(face)
            inside = pr.get("within_setback")
            cross = pr.get("crosses_property_line")
            issues, missing = [], []
            if cross is True:
                if pr["kind"] == "stair" or street_width == 0:
                    issues.append("property_line_stair_or_neighbor_protrusion")
                else:
                    # The document allows qualifying street projections; municipal
                    # encroachment/ownership permission cannot be inferred.
                    missing.append("street_property_projection_approval")
            elif cross is None:missing.append("crosses_property_line")
            if inside is None:missing.append("within_setback")
            elif inside:
                if street_width is None:
                    missing.append("street_classification")
                elif street_width == 0:
                    if pr["kind"] != "decorative_cornice" or pr["depth_m"] > .25 + EPS:
                        issues.append("side_or_rear_setback_projection")
                elif pr["kind"] == "stair":
                    if pr["depth_m"] > 1 + EPS:issues.append("stair_projection_gt_1m")
                    if pr.get("clearance_m") is None:missing.append("stair_clearance_m")
                    elif pr["clearance_m"] + EPS < 2.1:issues.append("stair_clearance_lt_2.1m")
                    if pr.get("stair_width_m") is None:missing.append("stair_width_m")
                    elif pr["stair_width_m"] > 2.8 + EPS:issues.append("stair_width_gt_2.8m")
                elif street_width < 10:issues.append("street_narrower_than_10m")
                elif pr["depth_m"] > 1.25 + EPS:issues.append("street_setback_projection_gt_1.25m")
            put("projection-" + pr["id"],
                "FAIL" if issues else "PENDING" if missing else "PASS",
                "البروزات: المسموح في الارتداد للعنصر " + pr["id"],
                "5-1-11(1-4)", 33,
                {"face": face, "kind": pr["kind"], "depth_m": pr["depth_m"],
                 "street_width_m": street_width, "within_setback": inside,
                 "issues": issues, "missing": missing,
                 "special_note": "البروز خارج حيز الارتداد له حكم مختلف؛ تصنيف موقعه يجب أن يكون هندسيًا موثقًا"})
        put("projection-geometry-overlay", "PENDING",
            "البروزات: الإسقاط على حدود الملكية وخطوط الارتداد في مساقط الأدوار",
            "5-1-11", 33,
            {"required_action": "مطلوب رسم البروزات فعليًا كأشكال قابلة للقياس وربطها بمضلع الملكية وخط تنظيم الشارع"})

    facades = features.get("facades")
    if not facades:
        put("facade-main-street-services", "PENDING",
            "الواجهات: تصنيف الشوارع الرئيسية وظهور التكييف والتمديدات غير موثق",
            "5-1-10(4)", 32,
            {"required_action": "حدد الواجهات الواقعة على الشوارع الرئيسية وأماكن معدات التكييف والتمديدات"})
    else:
        for survey in facades:
            if survey.get("faces_main_street") is False:
                status = "NOT_APPLICABLE"
            elif survey.get("faces_main_street") is None:
                status = "PENDING"
            elif survey.get("ac_or_services_on_facade") is True or survey.get("visible_ac_or_services") is True:
                status = "FAIL"
            elif survey.get("ac_or_services_on_facade") is False:
                status = "PASS"
            else:
                status = "PENDING"
            put("facade-main-street-" + survey["face"], status,
                "الواجهات: منع وضع وحدات التكييف والتمديدات على الشوارع الرئيسية - " + survey["face"],
                "5-1-10(4)", 32,
                {"is_main_street": survey.get("faces_main_street"),
                 "visible_ac_or_services": survey.get("visible_ac_or_services"),
                 "ac_or_services_on_facade": survey.get("ac_or_services_on_facade")})
    put("facade-local-identity", "PENDING",
        "الواجهات: مطابقة الكود العمراني المحلي والمواد والتنسيق العام",
        "5-1-10(1-6)", 32,
        {"required_action": "بطاقة اشتراطات الموقع، مخططات الواجهات التفصيلية، واعتماد مواد مقاومة للحريق",
         "reason": "الهوية العمرانية المحلية ومواصفات التنفيذ لا تُحسم من مسقط ثنائي الأبعاد"})
    return results
