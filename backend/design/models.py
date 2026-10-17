from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class Rect(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    x: float
    y: float
    width: float = Field(gt=0)
    depth: float = Field(gt=0)


class RoomEntity(Rect):
    id: str
    floor_id: str
    name: str
    kind: str
    zone: str
    source_ref: str
    status: str = 'DESIGNER_PROPOSED'
    revision_id: str
    area_m2: float


class WallEntity(BaseModel):
    id: str
    floor_id: str
    axis: Literal['horizontal', 'vertical']
    start: tuple[float, float]
    end: tuple[float, float]
    thickness: float
    room_ids: list[str]
    exterior: bool
    revision_id: str
    source_ref: str = 'PROPOSED_WALL_PARAMETERS'


class OpeningEntity(BaseModel):
    id: str
    floor_id: str
    wall_id: str
    kind: Literal['door', 'window']
    center: tuple[float, float]
    width: float
    height: float
    sill: float
    connects: list[str]
    face: str | None = None
    swing_rect: Rect | None = None
    revision_id: str
    source_ref: str = 'DESIGNER_PROPOSED_OPENINGS'
    status: str = 'PROPOSED_NOT_REGULATORY_APPROVAL'


class Fixture(Rect):
    id: str
    room_id: str
    floor_id: str
    kind: str
    capacity: int = 0
    revision_id: str
    status: str = 'PROPOSED'


class FloorModel(BaseModel):
    id: str
    name: str
    level_m: float
    rooms: list[RoomEntity]
    walls: list[WallEntity] = Field(default_factory=list)
    openings: list[OpeningEntity] = Field(default_factory=list)
    furniture: list[Fixture] = Field(default_factory=list)


class DesignOptions(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra='forbid')
    candidate_count: int = Field(default=3, ge=1, le=3)
    footprint_width: float | None = Field(default=None, ge=14, le=17)
    footprint_depth: float | None = Field(default=None, ge=19.2, le=23)
    floor_height: float = Field(default=3.2, ge=2.8, le=4)
    confirmed_opening_faces: list[Literal['north','south','east','west']] | None = None
    project_profile: dict | None = None


class CheckResult(BaseModel):
    check_id: str
    rule_id: str
    project_id: str
    model_revision_id: str
    status: Literal['PASS','FAIL','PENDING','NOT_APPLICABLE']
    applicable: bool | None = True
    entity_ids: list[str] = Field(default_factory=list)
    observed_value: object = None
    expected_criterion: str
    criterion_source: str
    evidence: dict = Field(default_factory=dict)
    reason: str
    validator_version: str = '0.3.0'
