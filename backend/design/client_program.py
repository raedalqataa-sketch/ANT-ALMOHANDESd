"""Independent client program input; no implicit Mahfad defaults."""
from pydantic import BaseModel, Field, model_validator
from typing import Literal

class ProgramRoom(BaseModel):
    id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    count: int = Field(ge=1)
    required: bool
    allowed_floors: list[int] = Field(min_length=1)
    area_min_m2: float = Field(gt=0)
    area_target_m2: float = Field(gt=0)
    area_max_m2: float = Field(gt=0)
    privacy_zone: Literal['guest','family','private','service','shared']
    adjacency_required: list[str] = Field(default_factory=list)
    adjacency_forbidden: list[str] = Field(default_factory=list)

    @model_validator(mode='after')
    def validate_room(self):
        if not self.area_min_m2 <= self.area_target_m2 <= self.area_max_m2:
            raise ValueError('Invalid area range')
        if set(self.adjacency_required) & set(self.adjacency_forbidden):
            raise ValueError('Conflicting adjacency')
        return self

class ClientProgram(BaseModel):
    project_id: str = Field(min_length=1)
    floor_count: int = Field(ge=1, le=2)
    plot_width_m: float | None = Field(default=None, gt=0)
    plot_depth_m: float | None = Field(default=None, gt=0)
    rooms: list[ProgramRoom] = Field(min_length=1)

    @model_validator(mode='after')
    def validate_program(self):
        ids = {r.id for r in self.rooms}
        if len(ids) != len(self.rooms):
            raise ValueError('Duplicate room IDs')
        for r in self.rooms:
            if any(f < 0 or f >= self.floor_count for f in r.allowed_floors):
                raise ValueError('Unsupported floor')
            if not set(r.adjacency_required+r.adjacency_forbidden) <= ids-{r.id}:
                raise ValueError('Invalid adjacency reference')
        return self

    def mandatory_net_area_m2(self):
        return sum(r.count*r.area_min_m2 for r in self.rooms if r.required)
