
from __future__ import annotations

from enum import Enum
from typing import List

from pydantic import BaseModel, Field, field_validator


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Category(str, Enum):
    BUG = "bug"
    SECURITY = "security"
    PERFORMANCE = "performance"
    READABILITY = "readability"
    MAINTAINABILITY = "maintainability"


class Issue(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1)
    severity: Severity
    confidence_score: int = Field(..., ge=0, le=100)
    category: Category
    line_number: int = Field(..., ge=0)
    suggested_fix: str = Field(..., min_length=1)

    @field_validator("severity", mode="before")
    @classmethod
    def normalise_severity(cls, v: str) -> str:
        return v.lower().strip() if isinstance(v, str) else v

    @field_validator("category", mode="before")
    @classmethod
    def normalise_category(cls, v: str) -> str:
        return v.lower().strip() if isinstance(v, str) else v


class ReviewResponse(BaseModel):
    issues: List[Issue] = Field(default_factory=list)
