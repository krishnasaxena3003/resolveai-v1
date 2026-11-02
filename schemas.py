"""Pydantic models and allowed values. Every AI output passes through here."""
from datetime import datetime
from typing import Literal
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Category(str, Enum):
    ELECTRICITY = "Electricity"
    NETWORK = "Wi-Fi/Network"
    PLUMBING = "Water/Plumbing"
    HOSTEL = "Hostel/Maintenance"
    EQUIPMENT = "Equipment"
    OTHER = "Other"


class Priority(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class Status(str, Enum):
    OPEN = "Open"
    IN_PROGRESS = "In Progress"
    PENDING = "Pending Sign-off"  # staff marked it fixed; waiting for the student to confirm
    REOPENED = "Reopened"  # the student said it is not fixed
    RESOLVED = "Resolved"
    WITHDRAWN = "Withdrawn"


DEPARTMENT_FOR = {
    Category.ELECTRICITY: "Electrical Maintenance",
    Category.NETWORK: "IT/Network Support",
    Category.PLUMBING: "Plumbing",
    Category.HOSTEL: "Hostel Maintenance",
    Category.EQUIPMENT: "Equipment/Lab Support",
    Category.OTHER: "General Administration",
}
SAFETY_DEPARTMENT = "Campus Safety & Emergency Response"
DEPARTMENTS = [*DEPARTMENT_FOR.values(), SAFETY_DEPARTMENT]

LIVE_STATUSES = (Status.OPEN, Status.IN_PROGRESS, Status.REOPENED)  # staff still have work to do
# Staff-driven moves. Pending -> Resolved/Reopened belongs to the student (or a timed close by staff), see ticket_service.
ALLOWED_TRANSITIONS = {
    Status.OPEN: {Status.IN_PROGRESS, Status.PENDING},
    Status.IN_PROGRESS: {Status.PENDING},
    Status.REOPENED: {Status.IN_PROGRESS, Status.PENDING},
    Status.PENDING: set(),
    Status.RESOLVED: set(),
}


class AnalysisResult(BaseModel):
    """Validated AI recommendation. Routing is decided by code, not by the model."""
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)
    summary: str = Field(min_length=3, max_length=200)
    category: Category
    priority: Priority
    department: str
    rationale: str = Field(default="", max_length=400)
    review_required: bool = False

    @model_validator(mode="before")
    @classmethod
    def normalize(cls, data):
        if not isinstance(data, dict):
            raise ValueError("model output must be a JSON object")
        d = dict(data)
        review = bool(d.get("review_required", False))
        for key, enum in (("category", Category), ("priority", Priority)):  # tolerate case/spacing only
            match = {m.value.lower(): m.value for m in enum}.get(str(d.get(key, "")).strip().lower())
            if match:
                d[key] = match
        d["summary"] = " ".join(str(d.get("summary", "")).split())[:200]
        d["rationale"] = str(d.get("rationale", ""))[:400]
        if d.get("category") not in {c.value for c in Category}:
            d["category"], review = Category.OTHER.value, True  # unknown -> Other + staff review
        d["department"] = DEPARTMENT_FOR[Category(d["category"])]  # deterministic routing
        d["review_required"] = review
        return d


class User(BaseModel):
    id: int
    name: str
    email: str
    role: Literal["student", "staff", "worker"]
    department: str | None = None


class TicketRecord(BaseModel):
    ticket_id: str
    description: str
    summary: str
    category: Category
    priority: Priority
    department: str
    status: Status
    location: str | None = None
    location_id: str | None = None
    duplicate_of: str | None = None
    review_required: bool = False
    ai_mode: str
    created_at: datetime
    updated_at: datetime
    resolution_note: str | None = None
    is_sample: bool = False
    reporter_id: int | None = None
    is_anonymous: bool = False
    assignee_id: int | None = None
    resolved_at: datetime | None = None
    fixed_at: datetime | None = None
    resolved_by: str | None = None
    rating: int | None = None
    reopen_count: int = 0
    withdrawal_review: bool = False
    withdrawal_reason: str | None = None
    staff_removed: bool = False
    staff_removal_reason: str | None = None
    deadline_at: datetime | None = None
    critical_alert: bool = False


class PublicStatus(BaseModel):
    """What a student may see. No internal fields."""
    ticket_id: str
    summary: str
    category: Category
    status: Status
    created_at: datetime
    updated_at: datetime
    resolution_note: str | None = None
    staff_removed: bool = False
    staff_removal_reason: str | None = None
    deadline_at: datetime | None = None
    updates: list[dict] = []


class CreatedTicket(BaseModel):
    ticket: TicketRecord
    tracking_code: str  # shown once; only a hash is stored


class DuplicateCandidate(BaseModel):
    ticket_id: str
    summary: str
    status: Status
    score: float
    evidence: str
