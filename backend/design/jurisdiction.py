"""Explicit missing local evidence. No Yemen legal values are invented."""

def checks(model,brief):
    if brief.country!='YE':return []
    documents={
      'parcel':['وثيقة حدود القطعة والمخطط المعتمد وتصنيف الشوارع وعروضها','إفادة استعمال الأرض والارتدادات ونسبة البناء والارتفاع من جهة الترخيص'],
      'daylight':['اشتراطات الإضاءة والتهوية المحلية ونسب الفتحات والمناور المسموح بها'],
      'stairs-fire':['متطلبات السلالم والإخلاء والحريق والدرابزين والارتفاع الصافي المحلية'],
      'parking':['متطلبات عدد وأبعاد المواقف والمناورة ومواقع مداخل المركبات'],
      'structure-services':['مرجع الأحمال والزلازل والتصميم الإنشائي والتمديدات الصحية والكهربائية'],
    }
    return [{'check_id':'YE-'+key,'status':'PENDING','label':'اليمن: '+{
      'parcel':'اعتماد حدود الأرض والارتدادات ونسبة البناء','daylight':'اعتماد الإضاءة والتهوية',
      'stairs-fire':'اعتماد الدرج والسلامة والإخلاء','parking':'اعتماد المواقف والمداخل',
      'structure-services':'اعتماد الإنشاء والخدمات'}[key],
      'evidence':{'country':'YE','region':brief.region,'city':brief.city,'district':brief.district,'neighborhood':brief.neighborhood,
        'required_documents':docs,'assumed_setbacks_m':brief.setbacks.model_dump() if key=='parcel' else None,
        'status':'no documented Yemeni legal rules in repository; design assumptions only'}}
      for key,docs in documents.items()]
