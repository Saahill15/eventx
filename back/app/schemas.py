import re
from pydantic import BaseModel, EmailStr, Field, StringConstraints, field_validator, model_validator
from typing import Annotated, Optional, List, Literal
from datetime import datetime

MIN_PASSWORD_LENGTH = 8

# Auth
class SignupEmail(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
    email: EmailStr
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=128)

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, v):
        return v.lower()

class LoginEmail(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, v):
        return v.lower()

class ProfileUpdate(BaseModel):
    name: Optional[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]] = None
    phone: Optional[Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^\+?[0-9 ()-]{7,20}$")]] = None
    college_id: Optional[int] = None
    study_year: Optional[int] = Field(default=None, ge=1, le=8)

class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=128)

class Token(BaseModel):
    access_token: str
    token_type: str
    role: str
    interests_set: bool

# User
class UserOut(BaseModel):
    id: int
    name: str
    email: Optional[str]
    phone: Optional[str]
    role: str
    interests_set: bool
    college_id: Optional[int] = None
    study_year: Optional[int] = None
    student_verified_until: Optional[datetime] = None
    is_student_verified: bool = False
    created_at: datetime
    class Config:
        from_attributes = True

# Interests
class InterestOut(BaseModel):
    id: int
    name: str
    class Config:
        from_attributes = True

class SetInterests(BaseModel):
    interest_ids: List[int]

    @field_validator("interest_ids")
    @classmethod
    def unique_ids(cls, v):
        return list(dict.fromkeys(v))

# Events
class EventCreate(BaseModel):
    # event_type MUST be declared first so model_validator has access to it
    event_type: Literal["fest", "city"]
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
    description: Optional[str] = None
    location: Optional[str] = None
    date: datetime
    time: Optional[str] = None
    image_url: Optional[str] = None
    category: Optional[str] = None
    price: float = Field(default=0.0, ge=0)
    is_free: bool = True
    college_id: Optional[int] = None
    fest_id: Optional[int] = None  # required when event_type="fest", must be null when "city"

    # ── Fest-event registration fields (only used when event_type='fest') ──────────
    requires_registration: Optional[bool] = False
    is_paid:               Optional[bool] = False
    registration_limit:    Optional[int]  = None
    approval_mode:         Optional[Literal["auto", "manual"]] = "auto"

    # Student verification
    students_only:         bool = False
    student_price:         Optional[float] = Field(default=None, ge=0)  # cheaper price for verified students

    @model_validator(mode="after")
    def validate_branch_constraints(self) -> "EventCreate":
        if self.student_price is not None:
            if self.is_free:
                self.student_price = None
            elif self.student_price >= self.price:
                raise ValueError("student_price must be lower than price")
        if self.is_free:
            self.price = 0.0
        elif self.price <= 0:
            raise ValueError("price must be > 0 for a paid event")
        if self.registration_limit is not None and self.registration_limit <= 0:
            raise ValueError("registration_limit must be > 0")
        if self.event_type == "fest" and self.fest_id is None:
            raise ValueError("fest_id is required when event_type is 'fest'")
        if self.event_type == "city" and self.fest_id is not None:
            raise ValueError("fest_id must be null when event_type is 'city'")
        # Registration fields only matter for fest events
        if self.event_type == "fest" and self.requires_registration:
            if self.is_paid and (self.price is None or self.price <= 0):
                raise ValueError("price must be > 0 when is_paid=True")
            if self.registration_limit is not None and self.registration_limit <= 0:
                raise ValueError("registration_limit must be > 0")
        return self

class EventOut(BaseModel):
    id: int
    event_type: str  # "fest" | "city"
    title: str
    description: Optional[str]
    location: Optional[str]
    date: datetime
    time: Optional[str]
    image_url: Optional[str]
    category: Optional[str]
    price: float
    is_free: bool
    status: str
    organizer_id: Optional[int]
    college_id: Optional[int]
    college_name: Optional[str] = None
    fest_id: Optional[int] = None
    fest_slug: Optional[str] = None
    fest_name: Optional[str] = None
    # registration fields
    requires_registration: bool = False
    is_paid: bool = False
    registration_limit: Optional[int] = None
    approval_mode: str = "auto"
    students_only: bool = False
    student_price: Optional[float] = None
    cancelled: bool = False
    cancel_reason: Optional[str] = None
    created_at: datetime
    class Config:
        from_attributes = True


class EventUpdate(BaseModel):
    """Fields allowed to be patched on an existing event."""
    title:              Optional[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]] = None
    description:        Optional[str]   = None
    location:           Optional[str]   = None
    date:               Optional[datetime] = None
    time:               Optional[str]   = None
    image_url:          Optional[str]   = None
    category:           Optional[str]   = None
    # Registration mutable fields — locked if registrations exist
    requires_registration: Optional[bool]  = None
    is_paid:               Optional[bool]  = None
    price:                 Optional[float] = Field(default=None, ge=0)
    registration_limit:    Optional[int]   = Field(default=None, gt=0)
    approval_mode:         Optional[Literal["auto", "manual"]] = None
    students_only:         Optional[bool] = None
    student_price:         Optional[float] = Field(default=None, ge=0)

# Fest
RESERVED_FEST_SLUGS = {"all", "my-passes", "my-pass"}

class FestCreate(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", min_length=2, max_length=100)
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
    tagline: Optional[str] = None
    banner_url: Optional[str] = None
    logo_url: Optional[str] = None
    college_id: Optional[int] = None
    status: Optional[str] = "draft"

    @field_validator("slug")
    @classmethod
    def slug_not_reserved(cls, v):
        if v in RESERVED_FEST_SLUGS:
            raise ValueError("this slug is reserved")
        return v

class FestOut(BaseModel):
    id: int
    slug: str
    name: str
    tagline: Optional[str]
    banner_url: Optional[str]
    logo_url: Optional[str]
    college_id: Optional[int]
    status: str
    event_count: int = 0
    created_at: datetime
    class Config:
        from_attributes = True

class FestWithEventsOut(BaseModel):
    id: int
    slug: str
    name: str
    tagline: Optional[str]
    banner_url: Optional[str]
    logo_url: Optional[str]
    college_id: Optional[int]
    status: str
    events: List[EventOut] = []
    class Config:
        from_attributes = True

class FestMemberOut(BaseModel):
    id: int
    fest_id: int
    user_id: int
    role: str
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    created_at: datetime
    class Config:
        from_attributes = True

class AddFestMember(BaseModel):
    user_id: Optional[int] = None
    email: Optional[EmailStr] = None   # invite by email instead of by id
    role: Optional[str] = "volunteer"  # owner | core | volunteer

    @model_validator(mode="after")
    def need_user_or_email(self):
        if self.user_id is None and self.email is None:
            raise ValueError("user_id or email is required")
        return self

class FestMineOut(FestOut):
    my_role: str  # owner | core | volunteer | admin

class FestUpdate(BaseModel):
    name: Optional[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]] = None
    tagline: Optional[str] = None
    banner_url: Optional[str] = None
    logo_url: Optional[str] = None
    college_id: Optional[int] = None

# College
class CollegeCreate(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
    area: Optional[str] = None
    emoji: Optional[str] = "🏛️"
    website: Optional[str] = None
    email_domains: Optional[str] = None  # comma-separated email domains students of this college use

    @field_validator("email_domains")
    @classmethod
    def clean_domains(cls, v):
        if v is None or not v.strip():
            return None
        domains = []
        for raw in v.split(","):
            d = raw.strip().lower().lstrip("@")
            if not re.fullmatch(r"[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+", d):
                raise ValueError(f"'{raw.strip()}' is not a valid email domain")
            domains.append(d)
        return ",".join(dict.fromkeys(domains))

class CollegeOut(BaseModel):
    id: int
    name: str
    area: Optional[str]
    emoji: Optional[str]
    website: Optional[str]
    email_domains: Optional[str] = None
    event_count: int = 0
    class Config:
        from_attributes = True

# Pass
class PassOut(BaseModel):
    id: int
    pass_code: str
    event_id: int
    payment_status: str
    created_at: datetime
    class Config:
        from_attributes = True


# FestPass
class FestPassOut(BaseModel):
    id: int
    user_id: int
    fest_id: int
    status: str
    qr_code: str
    checked_in: bool
    created_at: datetime
    class Config:
        from_attributes = True


class FestPassDetailOut(FestPassOut):
    fest_slug: Optional[str] = None
    fest_name: Optional[str] = None


# EventRegistration
class EventRegistrationOut(BaseModel):
    id: int
    fest_pass_id: int
    event_id: int
    approval_status: str
    payment_status: str
    amount_due: Optional[float] = None
    created_at: datetime
    class Config:
        from_attributes = True

class EventRegistrationDetailOut(EventRegistrationOut):
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    checked_in: bool = False

class FestEventManageOut(EventOut):
    registration_count: int = 0   # approved + pending
    pending_count: int = 0        # waiting for committee approval

# Admin: user management
class AdminUserOut(BaseModel):
    id: int
    name: str
    email: Optional[str]
    role: str
    is_active: bool
    created_at: datetime
    class Config:
        from_attributes = True

class RoleChange(BaseModel):
    role: Literal["user", "organizer"]

# Committee
class CommitteeCreate(BaseModel):
    name: str

class CommitteeOut(BaseModel):
    id: int
    event_id: int
    name: str
    class Config:
        from_attributes = True

# Department
class DepartmentCreate(BaseModel):
    name: str

class DepartmentOut(BaseModel):
    id: int
    committee_id: int
    name: str
    class Config:
        from_attributes = True

# Department Member
class MemberAdd(BaseModel):
    user_id: int
    role: str = "member"

# Gate / check-in
class QrCodeIn(BaseModel):
    qr_code: str = Field(min_length=8, max_length=100)

class GateRegistration(BaseModel):
    event_id: int
    title: str
    approval_status: str
    attended: bool

class GatePassOut(BaseModel):
    pass_id: int
    user_name: Optional[str]
    user_email: Optional[str]
    status: str
    checked_in: bool
    checked_in_at: Optional[datetime] = None
    registrations: List[GateRegistration] = []

class EventCheckInOut(BaseModel):
    registration_id: int
    user_name: Optional[str]
    attended: bool
    attended_at: Optional[datetime] = None

class CancelEvent(BaseModel):
    reason: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]] = None

class EventStat(BaseModel):
    id: int
    title: str
    date: datetime
    cancelled: bool
    requires_registration: bool
    registration_limit: Optional[int]
    registered: int       # approved
    pending: int
    attended: int

class FestStats(BaseModel):
    passes_issued: int
    passes_checked_in: int
    events: List[EventStat]


# Student verification
class StudentEmailRequest(BaseModel):
    email: EmailStr
    college_id: Optional[int] = None  # needed only when the email domain is not one we know

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, v):
        return v.lower()

class StudentCodeConfirm(BaseModel):
    code: str = Field(pattern=r"^[0-9]{6}$")

class PendingVerification(BaseModel):
    id: int
    method: str
    created_at: datetime
    email: Optional[str] = None
    document_type: Optional[str] = None

class StudentStatus(BaseModel):
    verified: bool
    verified_until: Optional[datetime] = None
    college_id: Optional[int] = None
    can_verify: bool                      # false while a long verification is still running
    pending: Optional[PendingVerification] = None
    last_rejection: Optional[str] = None

class VerificationReview(BaseModel):
    id: int
    user_id: int
    user_name: Optional[str]
    user_email: Optional[str]
    method: str
    status: str
    college_id: Optional[int]
    college_name: Optional[str]
    document_type: Optional[str]
    document_name: Optional[str]
    has_file: bool
    created_at: datetime

class RejectVerification(BaseModel):
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)]
