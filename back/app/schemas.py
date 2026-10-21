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

    @model_validator(mode="after")
    def validate_branch_constraints(self) -> "EventCreate":
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

class CollegeOut(BaseModel):
    id: int
    name: str
    area: Optional[str]
    emoji: Optional[str]
    website: Optional[str]
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

# Organizer request
class OrganizerRequestOut(BaseModel):
    id: int
    user_id: int
    status: str
    requested_at: datetime
    class Config:
        from_attributes = True

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