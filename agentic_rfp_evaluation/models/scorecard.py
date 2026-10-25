from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class CriterionScore(BaseModel):
    criterion_id: int
    score: float = Field(..., ge=0, le=10)
    max_score: float = Field(default=10, gt=0)
    justification: str = ""
    evidence: str = ""


class Scorecard(BaseModel):
    supplier_name: str
    criteria: list[CriterionScore]
    risks: list[str] = []
    overall_summary: str = ""

    @field_validator("criteria")
    @classmethod
    def validate_criteria(cls, value):
        if not value:
            raise ValueError("At least one criterion score is required.")
        return value
