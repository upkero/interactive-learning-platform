"""Validation of private answer keys stored in published content."""

from pydantic import BaseModel, Field, StrictFloat, StrictStr


class SingleChoiceKey(BaseModel):
    correct_id: StrictStr
    explanation: StrictStr | None = None
    why_wrong: dict[StrictStr, StrictStr] | None = None


class MultipleChoiceKey(BaseModel):
    correct_ids: list[StrictStr]
    explanation: StrictStr | None = None
    why_wrong: dict[StrictStr, StrictStr] | None = None


class OrderingKey(BaseModel):
    correct_order: list[StrictStr]
    explanation: StrictStr | None = None
    common_mistakes: list[StrictStr] | None = None


class NumericKey(BaseModel):
    answer: StrictFloat = Field(allow_inf_nan=False)
    tolerance: StrictFloat = Field(default=0.01, ge=0, allow_inf_nan=False)
    explanation: StrictStr | None = None
    common_mistakes: list[StrictStr] | None = None
