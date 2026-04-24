"""
NPIDE — API Schemas (Pydantic v2)
===================================
All request/response models. Used for validation + auto-docs.
"""

from typing import Optional, Any
from pydantic import BaseModel, Field


# ── Eligibility ───────────────────────────────────────────────

class EligibilityByProfile(BaseModel):
    """Profile submitted by chatbot onboarding."""
    name:         Optional[str] = None
    age:          int           = Field(..., ge=0, le=120)
    income:       Optional[int] = None
    income_range: Optional[str] = None  # chatbot uses range; converted to income
    gender:       str           = "All"
    location:     str           = Field(..., min_length=1)
    occupation:   str           = Field(..., min_length=1)
    education:    Optional[str] = None

    model_config = {"json_schema_extra": {
        "example": {
            "name": "Ramu Gowda", "age": 45,
            "income_range": "Below ₹1 Lakh",
            "gender": "Male", "location": "Karnataka",
            "occupation": "Farmer", "education": "10th Pass"
        }
    }}


class EligibleScheme(BaseModel):
    scheme_id:       int
    scheme_name:     str
    description:     Optional[str]
    benefit_amount:  Optional[int]
    eligible_location: Optional[str]


class EligibilityResponse(BaseModel):
    source:  str
    matched: int
    schemes: list[EligibleScheme]


# ── Gap Detection ─────────────────────────────────────────────

class GapDetectionRequest(BaseModel):
    location: Optional[str] = None  # state name or None for all


class GapEntry(BaseModel):
    scheme_name:          str
    eligible_location:    Optional[str]
    expected_eligible:    Optional[int]
    actually_applied:     Optional[int]
    application_rate_pct: Optional[float]
    missed_beneficiaries: Optional[int]


class GapResponse(BaseModel):
    location:                 str
    total_anomalous_schemes:  int
    top_gaps:                 list[dict]
    db_gap_report:            list[dict]
    computed_at:              float


# ── Grievances ────────────────────────────────────────────────

class GrievanceClassifyRequest(BaseModel):
    text:       str         = Field(..., min_length=5, max_length=2000)
    citizen_id: Optional[int] = None
    scheme_id:  Optional[int] = None
    location:   Optional[str] = None

    model_config = {"json_schema_extra": {
        "example": {
            "text": "My PM Kisan payment has not arrived for 3 months. I was told to pay a bribe.",
            "citizen_id": 1, "location": "Karnataka"
        }
    }}


class GrievanceSubmitRequest(BaseModel):
    citizen_id:  Optional[int] = None
    scheme_id:   Optional[int] = None
    location:    str
    description: str = Field(..., min_length=10)
    severity:    str = "medium"  # low | medium | high


class GrievanceClassifyResponse(BaseModel):
    category:   str
    confidence: float
    priority:   int
    route_to:   str
    escalate:   bool
    source:     str


# ── Policy Efficiency ─────────────────────────────────────────

class PolicyEfficiencyResponse(BaseModel):
    scheme_id:       Optional[int] = None
    scheme_name:     Optional[str] = None
    total_eligible:  Optional[int] = None
    total_applied:   Optional[int] = None
    total_approved:  Optional[int] = None
    efficiency_score:Optional[float] = None
    rating:          Optional[str] = None
    gap_count:       Optional[int] = None
    source:          str


# ── Health ────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status:    str
    db:        bool
    redis:     bool
    ai_engine: bool
    schemes_loaded: int


class SchemeMutation(BaseModel):
    name: str = Field(..., min_length=3, max_length=200)
    description: str = ""
    min_income: int = Field(0, ge=0)
    max_income: int = Field(999999999, ge=0)
    gender: str = "All"
    location: str = "All"
    occupation: str = "All"
    min_age: int = Field(0, ge=0, le=120)
    max_age: int = Field(120, ge=0, le=120)
    benefit: Optional[int] = Field(None, ge=0)
    active: bool = True


class SchemeResponse(SchemeMutation):
    id: int
