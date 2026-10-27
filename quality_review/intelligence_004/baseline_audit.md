# تدقيق خط الأساس

الفرع الأساس feature/ai-auto-keys-002 عند 32be0b05a4d36ea4e5bf8aee36eb9721d52a57b8. فرع العمل مستقل، والنسخة الكاملة وبصمات الملفات السابقة محفوظة خارج المستودع /workspace/ant-arch-004-safety. لا تُستورد الملفات المحلية غير المتتبعة إلى فرع التنفيذ.

## مسار التوليد الفعلي
- backend/design/api.py وgeneral_api.py -> architect_planner.generate_automatic أو general_engine.generate_general.
- architect_planner.propose يحول ClientIntent إلى VillaBrief وبرنامج مقترح؛ الحد الأدنى في البرنامج لا يُخفض في التجربة.
- general_engine.search يولد topology ثم يحجز الدرج المتطابق بين الأدوار، وallocate يوزع حزم الغرف على lanes، وmoderate_room_expansion يقلص العرض الخارجي بعد التخصيص، ثم trim_corridor_tails.
- generate_general -> materialize -> make_walls/add_room_door/add_windows/furnish_floor، ثم validate_general وfunctional_program.validate وفحص constitution_v2. ArchitectureAutoRepairEngine يعيد الفحص بعد إصلاحات محدودة.
- export_general_model -> general_drawing/presentation -> ملفات JSON/SVG/PDF/DXF من النموذج نفسه، مع export_audit.
- AI lab pipeline.run يتلقى Structured SearchPlan من providers.Provider.propose ثم يستخدم نفس المحرك والبوابات. validate_candidate يضيف استبعاد جيوب تشخيصي خاص بالمختبر. select يستخدم مقاييس هندسية وتنوع إحداثيات/ترتيب، وليس graph topology كاملًا.

## أسباب الجودة المتبقية
length_for يعتمد على مساحة الطلب وعرض الشريط، ثم allocate يوزع الاحتياطي بالتناسب، وmoderate_room_expansion يخفض العرض مع تثبيت العمق. هذه المراحل قد تنتج غرفة 3.50×9.23 رغم اجتياز الفرش. نجاح الفحص لا يثبت جودة تناسبها أو جدوى الممر الطويل. لا يُعد ارتفاع نسبة الأبعاد وحده إخفاقًا نظاميًا.

## مصادر ناقصة
الملفات التاريخية الثلاثة المطلوبة غير موجودة في شجرة المستودع ولا مرفقات الجلسة المتاحة. لا يمكن مقارنة نصوصها بالدستور الحالي. runtime_coverage_v04.json موجود لكنه قائمة تغطية وليس بديلًا عن الأصل. المصادر السعودية محفوظة دون تغيير. صور المراجع الأصلية غير موجودة في filesystem الحالي، بينما فهرس البصمات والقراءة البصرية موجود؛ لا نستنتج أبعادًا غير مقاسة.

## إعادة الإنتاج
البحث حتمي وبذره المعلنة صفر؛ معرفات uuid وأزمنة التشغيل تتغير، لذا المقارنة بهندسة الغرف واتحاد المضلعات وتوقيع العلاقات، لا بمطابقة الملفات بايتًا. الحالة السعودية من quality_review/gemini_sa600_case.json، واليمنية والركنية من quality_review/v4_benchmark.py، دون تغيير البرنامج. آثار Gemini الحية A/B/C موجودة خارج المستودع في /workspace/ant-gemini-live-generation-002/run-40417998987؛ ستُقاس باعتبارها LIVE_API سابقًا، ولا تُعرض مقارناتنا المحلية كاستدلال حي جديد.

## بحث المحتوى الموسع بعد استعادة البيئة
جرى تحديث الفروع البعيدة وفحص تاريخ جميع المراجع وأسماء JSON ومحتواها، وفهارس الأرشيفات وملفات /workspace/ant-reference. عثرنا على حزمة SRC-06 المتضمنة في floor_plan_rules_v1.json (نسخة2.0.0)، وفيها master_schema/planning_engine/cad_output_contract وrules_engine/orchestrator/workflow وproject_memory. تحققنا من بصمة المحتوى القانونية للحزمة كما حفظها المصدر. هذه مكافئات وظيفية جزئية للملفات الثلاثة، وليست إثباتًا لاستعادة نصوصها الأصلية. ملفات المصدر الثلاثة نفسها وهويتها التاريخية تبقى غير متحققة.

## تحديث حاسم — استلام المصادر الأصلية
أرفق المستخدم الحزم الخمس الأصلية لاحقًا، وحُفظت نسخها دون تغيير تحت constitution/source_bundles_004 مع بصمات source_registry.json. زال نقص الملفات الثلاثة؛ تُحفظ نتيجة البحث القديمة كتاريخ قبل وصولها. تشمل الحزم17 مصدرًا، منها20 إخفاقًا معروفًا، ومحرك القرار والتحسين والذاكرة والمخطط الرئيسي. لا تُفعّل numeric placeholders كاشتراطاتSBC. حالات المخرجات النهائية في المصدر أشد من DRAFT الحالي؛ جميع رسومات التجربة مسودات ولا تتحول إلىFINAL لمجرد نجاحV4 الجزئي. الواجهات والقطاعات و3D ومراجعة الإنشاء والخدمات الشاملة لا تُدعى منفذة.
