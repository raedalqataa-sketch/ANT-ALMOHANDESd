"""Evidence-based site, structural and MEP *coordination* gates.

No statutory numerical limit, structural capacity, fire approval or MEP design
may be inferred from a generated 2D room plan. Missing external documents
remain PENDING, even if the geometric design checks pass.
"""
from shapely.geometry import box as polygon_box

WET_KINDS=frozenset(("bathroom","kitchen","laundry"))


def assess(model, brief):
    plot=polygon_box(0,0,brief.plot_width,brief.plot_depth)
    buildable=polygon_box(brief.setbacks.west,brief.setbacks.north,
                         brief.plot_width-brief.setbacks.east,
                         brief.plot_depth-brief.setbacks.south)
    envelope_failures=[]
    for floor in model.get("floors",()):
        for cell in floor.get("cells",()):
            # Check occupied *gross* cells, not only net room faces.
            x,y,w,d=(float(cell[k]) for k in ("x","y","width","depth"))
            occupied=polygon_box(x,y,x+w,y+d)
            excess=occupied.difference(buildable).area
            if excess>1e-5:
                envelope_failures.append(dict(floor=floor["id"],cell=cell["id"],
                                              outside_buildable_m2=round(excess,6)))
    floors=model.get("floors",())
    wet_by_floor={
        f["id"]:[r for r in f.get("rooms",()) if r.get("kind") in WET_KINDS
                 and (r.get("request_id") or r.get("generated_feature_room"))]
        for f in floors
    }
    lower=wet_by_floor.get("GF",())
    upper=wet_by_floor.get("FF",())
    # Real plan measurements; overlap is a design coordination indicator only.
    stacking=[]
    for upper_room in upper:
        q=polygon_box(upper_room["x"],upper_room["y"],
                      upper_room["x"]+upper_room["width"],
                      upper_room["y"]+upper_room["depth"])
        supports=[]
        for ground_room in lower:
            p=polygon_box(ground_room["x"],ground_room["y"],
                          ground_room["x"]+ground_room["width"],
                          ground_room["y"]+ground_room["depth"])
            if q.intersection(p).area>0.01:
                supports.append(ground_room["id"])
        stacking.append({"upper_room":upper_room["id"],
                         "vertical_wet_overlap_ids":sorted(supports)})
    warnings=[]
    if not brief.parcel_number or not brief.plan_number:
        warnings.append("missing_land_plan_or_parcel_identifier")
    if not brief.boundary_widths:
        warnings.append("street_widths_not_survey_verified")
    return {
        "revision":"site-structure-mep-coordination-1",
        "site":{
            "geometric_status":"FAIL" if envelope_failures else "PASS",
            "plot_area_m2":round(plot.area,3),
            "assumed_buildable_area_m2":round(buildable.area,3),
            "gross_cell_setback_excess":envelope_failures,
            "assumption":"setbacks supplied or proposed, not verified against municipality",
            "survey_status":"PENDING",
            "street_frontage_status":"PENDING",
            "land_input_warnings":warnings,
        },
        "code":{
            "status":"PENDING",
            "country":brief.country,
            "region":brief.region,
            "city":brief.city,
            "required":"authoritative local parcel rules, use, setbacks, height, area ratios, daylight, fire/accessibility",
            "numeric_statutory_approval":False,
        },
        "structure":{
            "status":"PENDING",
            "available_draft_evidence":"stacked stair/core and drawn room cells only",
            "missing":["column_and_beam_grid","floor_loads","geotechnical_soil_report",
                       "foundation_design","lateral_seismic_design","stair_headroom_sections",
                       "structural_licensed_review"],
            "structural_capacity_verified":False,
        },
        "mep":{
            "status":"PENDING",
            "wet_rooms_by_floor":{k:[r["id"] for r in rooms]
                                  for k,rooms in wet_by_floor.items()},
            "wet_vertical_overlap":stacking,
            "missing":["sanitary_risers_and_vent_stacks","water_supply_and_drainage",
                       "electrical_loads_and_panel_routes","lighting_and_ventilation_sizing",
                       "hvac_ducts_and_units","fire_protection_and_egress_coordination"],
            "services_coordinated":False,
        },
        "executive_approval":False,
    }


def checks(report):
    return [
        dict(check_id="V4-site-gross-envelope",
             status=report["site"]["geometric_status"],
             label="حدود الكتلة الإجمالية داخل المساحة المتاحة وفق الارتدادات المدخلة",
             evidence=report["site"]),
        dict(check_id="V4-local-code-verified",
             status="PENDING",label="الاشتراطات والمستندات المحلية للقطعة",
             evidence=report["code"]),
        dict(check_id="V4-structural-coordination",
             status="PENDING",label="تنسيق الإنشاء والأساسات والأحمال والقطاعات",
             evidence=report["structure"]),
        dict(check_id="V4-mep-coordination",
             status="PENDING",label="تنسيق السباكة والكهرباء والتهوية والتكييف والحريق",
             evidence=report["mep"]),
    ]
