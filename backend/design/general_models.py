"""Customer-owned villa brief; no adopted-family program is injected."""
from typing import Literal,Annotated
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class Setbacks(Strict):
    north: float = Field(ge=0, le=20)
    south: float = Field(ge=0, le=20)
    east: float = Field(ge=0, le=20)
    west: float = Field(ge=0, le=20)


class SpaceRequest(Strict):
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,45}$')
    name: str = Field(min_length=1, max_length=65)
    kind: Literal['bedroom','master','majlis','living','dining','kitchen','bathroom','office','storage','laundry']
    floor: int = Field(ge=0, le=1)
    count: int = Field(default=1, ge=1, le=12)
    min_area: float = Field(ge=3, le=100)
    min_side: float = Field(ge=1.4, le=10)
    capacity: int = Field(default=0, ge=0, le=2)
    ensuite_for: str | None = Field(default=None,pattern=r'^[a-zA-Z0-9_-]{1,45}$')


class GuestGroup(Strict):
    """ASSL hospitality membership; equal entry keys share one vestibule.

    A service request may belong to multiple groups without being duplicated.
    """
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,45}$')
    rooms: list[str] = Field(min_length=1, max_length=36)
    entry: str | None = Field(default=None, pattern=r'^[a-zA-Z0-9_-]{1,45}$')



class SpatialRequirement(Strict):
    source:str=Field(pattern=r'^[a-zA-Z0-9_-]{1,45}$')
    target:str=Field(pattern=r'^[a-zA-Z0-9_-]{1,45}$')
    relation:Literal['adjacent','near','separate']
    max_distance_m:float|None=Field(default=None,gt=0,le=50)

    @model_validator(mode='after')
    def valid_distance(self):
        if self.source==self.target:raise ValueError('علاقة الغرفة بنفسها غير مدعومة')
        if (self.relation=='near') != (self.max_distance_m is not None):raise ValueError('حدد مسافة لعلاقة near فقط')
        return self


# Optional dimensions for preliminary 2024 municipal checks.
# Missing information remains PENDING, not a fabricated compliance result.
class LightWell(Strict):
    id: str = Field(min_length=1, max_length=45)
    width_m: float = Field(gt=0, le=30)
    length_m: float = Field(gt=0, le=30)
    storeys_served: int = Field(ge=1, le=14)
    opposing_windows: bool
    polygon: list[tuple[float, float]] | None = Field(default=None, min_length=4, max_length=64)
    window_ids: list[str] | None = None
    open_to_sky: bool | None = None
    cleaning_door: bool | None = None
    drains_provided: bool | None = None
    light_wall_finish: bool | None = None


class RoofAnnex(Strict):
    polygon: list[tuple[float, float]] | None = Field(default=None, min_length=4, max_length=64)
    area_m2: float = Field(gt=0, le=5000)
    street_setbacks_m: dict[Literal['north','south','east','west'], Annotated[float, Field(ge=0, le=30)]] = Field(default_factory=dict)
    parapet_height_m: float | None = Field(default=None, ge=0, le=3)
    independent_unit: bool = False
    additional_parking_space: bool | None = None
    neighbor_direct_windows: bool | None = None
    staircase_continues_to_annex_roof: bool | None = None


class Projection(Strict):
    polygon: list[tuple[float, float]] | None = Field(default=None, min_length=4, max_length=64)
    floor_id: Literal['GF','FF'] = 'FF'
    id: str = Field(min_length=1, max_length=45)
    face: Literal['north','south','east','west']
    kind: Literal['facade','balcony','decorative_cornice','stair']
    depth_m: float = Field(ge=0, le=5)
    within_setback: bool | None = None
    crosses_property_line: bool | None = None
    clearance_m: float | None = Field(default=None, ge=0, le=20)
    stair_width_m: float | None = Field(default=None, gt=0, le=6)


class FacadeEquipment(Strict):
    id: str = Field(min_length=1,max_length=45)
    x: float = Field(ge=0,le=200)
    y: float = Field(ge=0,le=200)
    width: float = Field(gt=0,le=10)
    depth: float = Field(gt=0,le=10)
    floor_id: Literal['GF','FF'] = 'GF'


class FacadeSurvey(Strict):
    face: Literal['north','south','east','west']
    faces_main_street: bool | None = None
    visible_ac_or_services: bool | None = None
    ac_or_services_on_facade: bool | None = None
    equipment: list[FacadeEquipment] | None = None
    inventory_complete: bool | None = None


class RegulatoryGeometry(Strict):
    light_wells: list[LightWell] | None = None
    roof_annex: RoofAnnex | None = None
    roof_annex_absent: bool | None = None
    projections: list[Projection] | None = None
    facades: list[FacadeSurvey] | None = None

    @model_validator(mode='after')
    def consistent(self):
        if self.roof_annex_absent and self.roof_annex is not None:
            raise ValueError('لا يمكن اختيار عدم وجود ملحق علوي وتقديم قياساته في الوقت نفسه')
        for group in (self.light_wells, self.projections):
            if group is not None and len({row.id for row in group}) != len(group):
                raise ValueError('معرفات العناصر الهندسية يجب أن تكون فريدة')
        if self.facades is not None and len({row.face for row in self.facades}) != len(self.facades):
            raise ValueError('لا تكرر جهة الواجهة')
        return self


class AutomaticFeatures(Strict):
    lightwell: bool = False
    lightwell_length_m: float = Field(default=2.0, ge=1.8, le=4)
    roof_annex: bool = False
    annex_lounge_min_m2: float = Field(default=14, ge=11.2, le=40)
    balcony: bool = False
    balcony_depth_m: float = Field(default=1.0, ge=.6, le=1.25)
    balcony_face: Literal['auto','north','south','east','west'] = 'auto'
    service_yard: bool = False
    main_street_faces: list[Literal['north','south','east','west']] | None = None


class VillaProgram(Strict):
    project_name: str = Field(default='فيلا جديدة', min_length=1, max_length=100)
    floors: int = Field(default=2, ge=1, le=2)
    entrance_face: Literal['north','south','east','west'] = 'south'
    wall_thickness: float = Field(default=.2, ge=.15, le=.4)
    main_entry_width: float = Field(default=1.0, ge=.9, le=2.4)
    entry_plinth_height_m: float = Field(default=0.0, ge=0, le=1.2)
    corridor_width: float = Field(default=1.5, ge=1.2, le=2.4)
    compact_core: bool = False  # opt-in V4: reserve a program-sized stair, not the full room wing
    proposed_room_area_factor: float | None = Field(default=None, ge=1, le=2.5)
    floor_height: float = Field(default=3.2, ge=2.8, le=3.8)
    rooms: list[SpaceRequest] = Field(min_length=1, max_length=30)
    guest_groups: list[GuestGroup] = Field(default_factory=list, max_length=12)
    spatial_requirements:list[SpatialRequirement]=Field(default_factory=list,max_length=40)
    country: Literal['SA','YE'] = 'SA'
    city: str = Field(default='',max_length=100)
    region: str = Field(default='',max_length=100)
    neighborhood: str = Field(default='',max_length=100)
    building_type: Literal['villa','house']='villa'
    district: str = Field(default='',max_length=100)
    plan_number: str = Field(default='',max_length=80)
    parcel_number: str = Field(default='',max_length=80)
    design_parking_count: int = Field(default=1,ge=0,le=4)
    dining_seats: Literal[4,6,8,10,12] = 6
    municipality: str = Field(default='',max_length=140)
    parcel_reference: str = Field(default='',max_length=300)
    boundary_widths: dict[Literal['north','south','east','west'],Annotated[float,Field(ge=0,le=100)]] = Field(default_factory=dict)
    apply_saudi_rules: bool = True
    regulatory_geometry: RegulatoryGeometry | None = None
    automatic_features: AutomaticFeatures = Field(default_factory=AutomaticFeatures)
    separate_guest_entry: bool = True
    flexible_space_policy: Literal['remove','keep'] = 'remove'
    reference_strategy: Literal['none','design-principles-v1'] = 'none'
    adaptive_search: bool = False
    massing_strategy: Literal['legacy','coherent'] = 'legacy'
    site_placement: Literal['legacy','auto_rear_corner'] = 'legacy'
    stair_headroom: float = Field(default=2.1, ge=2, le=2.5)
    notes: str = Field(default='', max_length=4000)

    @model_validator(mode='after')
    def coherent(self):
        if self.country=='YE' and self.apply_saudi_rules:
            raise ValueError('لا يجوز تطبيق اشتراطات المملكة العربية السعودية على أرض داخل اليمن')
        if self.automatic_features.balcony and self.floors < 2:
            raise ValueError('الشرفة العلوية تتطلب دورًا أول؛ اختر أرضي + أول')
        if self.regulatory_geometry:
            a=self.automatic_features;g=self.regulatory_geometry
            if ((a.lightwell and g.light_wells is not None) or
                (a.roof_annex and (g.roof_annex is not None or g.roof_annex_absent)) or
                (a.balcony and g.projections is not None) or
                (a.service_yard and g.facades is not None)):
                raise ValueError('اختر التوليد التلقائي أو القياسات اليدوية للعنصر نفسه، ولا تجمعهما')
        if len({r.id for r in self.rooms}) != len(self.rooms):
            raise ValueError('معرفات صفوف البرنامج يجب أن تكون فريدة')
        if len({g.id for g in self.guest_groups}) != len(self.guest_groups):
            raise ValueError('معرفات مجموعات الضيافة يجب أن تكون فريدة')
        known={r.id:r for r in self.rooms}
        for room in self.rooms:
            if room.ensuite_for:
                parent=known.get(room.ensuite_for)
                if room.kind!='bathroom' or parent is None or parent.kind not in ('bedroom','master') or room.floor!=parent.floor or room.count!=1 or parent.count!=1:
                    raise ValueError('الحمام الخاص يحتاج غرفة نوم واحدة معروفة في الدور نفسه')
        pairs={}
        for relation in self.spatial_requirements:
            if relation.source not in known or relation.target not in known:raise ValueError('علاقة مكانية تشير إلى فراغ غير موجود')
            if known[relation.source].floor!=known[relation.target].floor:raise ValueError('العلاقات المكانية الحالية تخص الدور نفسه')
            key=tuple(sorted((relation.source,relation.target)))
            pairs.setdefault(key,set()).add(relation.relation)
            if {'adjacent','separate'}<=pairs[key]:raise ValueError('علاقتا الالتصاق والفصل متعارضتان')
        if self.guest_groups:
            requests={r.id:r for r in self.rooms}
            covered=set()
            for group in self.guest_groups:
                if len(set(group.rooms))!=len(group.rooms):
                    raise ValueError('لا تكرر غرفة داخل مجموعة الضيافة')
                if any(i not in requests or requests[i].floor!=0 or
                       requests[i].kind not in ('majlis','bathroom','storage','dining') for i in group.rooms):
                    raise ValueError('مجموعة الضيافة تحتاج غرف ضيافة وخدمات أرضية معروفة')
                covered.update(group.rooms)
            if any(r.kind=='majlis' and r.floor==0 and r.id not in covered for r in self.rooms):
                raise ValueError('يجب ربط جميع مجالس الأرضي بمجموعات الضيافة')
        if sum(r.count for r in self.rooms)>36:
            raise ValueError('هذا الإصدار يدعم حتى 36 فراغًا مطلوبًا')
        if any(r.floor>=self.floors for r in self.rooms):
            raise ValueError('أحد الفراغات موضوع في دور غير موجود')
        if any(not any(r.floor==f for r in self.rooms) for f in range(self.floors)):
            raise ValueError('أضف برنامجًا لكل دور مطلوب')
        if any(r.capacity and r.kind not in ('master','bedroom') for r in self.rooms):
            raise ValueError('سعة النوم تخص غرف النوم فقط')
        return self


class VillaBrief(VillaProgram):
    plot_width: float = Field(ge=8, le=60)
    plot_depth: float = Field(ge=8, le=80)
    setbacks: Setbacks

    @model_validator(mode='after')
    def valid_buildable_envelope(self):
        if self.plot_width-self.setbacks.west-self.setbacks.east<6 or self.plot_depth-self.setbacks.north-self.setbacks.south<6:
            raise ValueError('المساحة المتاحة بعد الارتدادات أصغر من نطاق البحث الحالي')
        return self


class CompositionPlotBrief(VillaBrief):
    @model_validator(mode="after")
    def valid_buildable_envelope(self):
        # Intake reports the deficit before calling an engine that requires a usable envelope.
        return self


CompositionBrief = CompositionPlotBrief | VillaProgram
ProposalBrief = VillaBrief | VillaProgram
PROPOSAL_BRIEF = TypeAdapter(ProposalBrief)


class TransferredSuite(Strict):
    bedroom: SpaceRequest
    bathroom: SpaceRequest

    @model_validator(mode="after")
    def validate_suite(self):
        if (self.bedroom.kind not in ("bedroom", "master") or self.bathroom.kind != "bathroom"
                or self.bathroom.ensuite_for != self.bedroom.id or self.bathroom.id == self.bedroom.id
                or any(r.count != 1 or r.floor != 0 for r in (self.bedroom, self.bathroom))):
            raise ValueError("VERTICAL_REQUIRES_ONE_LINKED_BEDROOM_SUITE")
        return self


class UpperFloorProgram(Strict):
    """User-selected clear dimensions for the family stack's children’s rooms."""
    children: int = Field(default=3, ge=2, le=3)
    child_area_m2: float = Field(default=11.5, ge=9, le=100)
    child_min_side_m: float = Field(default=2.7, ge=2.5, le=10)


def from_reference_program(rows):
    """Explicit migration of the reference repo's editable program contract.

    accessVia/private bathrooms cannot silently become corridor-access bathrooms.
    """
    kinds={'guest':'majlis','bed':'bedroom','living':'living','dining':'dining',
           'kitchen':'kitchen','bath':'bathroom','service':'storage'}
    if any(r.get('accessVia') or r.get('zone','family')!='family' for r in rows):
        raise ValueError('المداخل المستقلة والحمامات المرتبطة تحتاج ربطًا معماريًا غير مدعوم في البحث العام الحالي')
    return [SpaceRequest(id=r['id'],name=r['name'],kind=kinds[r['use']],floor=r['floor'],
                         min_area=r['area'],min_side=r['minWidth'],capacity=r.get('capacity',0)) for r in rows]
