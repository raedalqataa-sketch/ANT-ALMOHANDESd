"""LLMs choose bounded search options, never code, regulatory rules or accepted geometry."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from ..architect_planner import ClientIntent

ProviderName = Literal['GEMINI', 'OPENROUTER', 'EXISTING_ENGINE', 'HYBRID']

class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

class SearchOption(Strict):
    family: Literal['adaptive', 'freeform', 'spine', 'cross', 'meander']
    policy: Literal['social_front', 'family_front', 'service_aligned', 'relationship_aware']
    core_position: Literal['front', 'rear']
    guest_strategy: Literal['linear', 'side_spine', 'compact_side']

class SearchPlan(Strict):
    options: list[SearchOption] = Field(min_length=3, max_length=6)

    @model_validator(mode='after')
    def unique(self):
        keys = [tuple(o.model_dump().values()) for o in self.options]
        if len(set(keys)) != len(keys):
            raise ValueError('duplicate search options')
        return self

class LabRequest(Strict):
    intent: ClientIntent
    provider: ProviderName = 'EXISTING_ENGINE'
    model: str = Field(default='', max_length=180, pattern=r'^[A-Za-z0-9_./:@-]*$')
    primary_provider: Literal['GEMINI', 'OPENROUTER'] = 'GEMINI'
    critic_provider: Literal['GEMINI', 'OPENROUTER'] | None = None
    critic_model: str = Field(default='', max_length=180, pattern=r'^[A-Za-z0-9_./:@-]*$')
    allow_engine_fallback: bool = False
    max_corrections: int = Field(default=1, ge=0, le=2)
    allow_remote_program: bool = False
    architectural_intelligence: bool = False
    intelligence_search_budget: int = Field(default=12, ge=1, le=18)
    reference_conditioning: bool = True

    @model_validator(mode='after')
    def configured(self):
        if self.provider != 'EXISTING_ENGINE' and not self.model:
            raise ValueError('explicit model identifier required')
        if self.critic_provider and not self.critic_model:
            raise ValueError('explicit critic model required')
        if self.provider != 'EXISTING_ENGINE' and not self.allow_remote_program:
            raise ValueError('confirm sending site/program without personal notes to provider')
        return self
