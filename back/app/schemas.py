import re
from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator, model_validator
from typing import Annotated, Optional, List, Literal
from datetime import date, datetime

MIN_PASSWORD_LENGTH = 8
MIN_AGE = 13
MAX_TEAM_SIZE = 50


def check_team_settings(is_team: bool, team_min, team_max, is_fest_event: bool, requires_registration: bool) -> None:
    """Rules for a team event, shared by creating, editing and importing events."""
    if not is_team:
        return
    if not is_fest_event:
        raise ValueError("only fest events can be team events")
    if not requires_registration:
        raise ValueError("a team event needs registration turned on")
    if team_min is None or team_max is None:
        raise ValueError("a team event needs a smallest and a largest team size")
    if team_min > team_max:
        raise ValueError("the smallest team size cannot be bigger than the largest")

PHONE_PATTERN = r"^\+?[0-9 ()-]{7,20}$"
TIME_PATTERN = r"^([01][0-9]|2[0-3]):[0-5][0-9]$"
MAX_EXTRA_SECTIONS = 10


def clean_url(v):
    """Image and link fields accept an uploaded image path or an https/http address."""
    if v is None:
        return None
    v = v.strip()
    if not v:
        return None
    if v.startswith("/api/media/") or re.fullmatch(r"https?://[^\s]{3,490}", v):
        return v
    raise ValueError("must be a web address starting with http:// or https://")


class ExtraSection(BaseModel):
    """A custom block of information shown on a fest or event page, such as Rules or Prizes."""
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    body: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


def check_sections(v):
    if v is not None and len(v) > MAX_EXTRA_SECTIONS:
        raise ValueError(f"at most {MAX_EXTRA_SECTIONS} extra sections")
    return v

# Auth
def check_date_of_birth(v: date) -> date:
    today = date.today()
    age = today.year - v.year - ((today.month, today.day) < (v.month, v.day))
    if age < MIN_AGE:
        raise ValueError(f"you must be at least {MIN_AGE} years old to create an account")
    if age > 110:
        raise ValueError("please check the date of birth")
    return v

NamePart = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]

class SignupEmail(BaseModel):
    first_name: NamePart
    last_name: NamePart
    email: EmailStr
    date_of_birth: date
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=128)
    accept_terms: bool

    _check_age = field_validator("date_of_birth")(lambda cls, v: check_date_of_birth(v))

    @field_validator("accept_terms")
    @classmethod
    def must_accept(cls, v):
        if v is not True:
            raise ValueError("you need to accept the terms to create an account")
        return v

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, v):
        return v.lower()

class ForgotPassword(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, v):
        return v.lower()

class ForgotPasswordOut(BaseModel):
    message: str
    dev_link: Optional[str] = None   # development only, until email is set up: the link that would have been sent

class ResetPassword(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    new_password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=128)

class GoogleSignIn(BaseModel):
    credential: str = Field(min_length=20, max_length=4096)   # the ID token Google's button hands the browser

class CompleteProfile(BaseModel):
    date_of_birth: date
    accept_terms: bool

    _check_age = field_validator("date_of_birth")(lambda cls, v: check_date_of_birth(v))

    @field_validator("accept_terms")
    @classmethod
    def must_accept(cls, v):
        if v is not True:
            raise ValueError("you need to accept the terms to continue")
        return v

class LoginEmail(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, v):
        return v.lower()

class ProfileUpdate(BaseModel):
    first_name: Optional[NamePart] = None
    last_name: Optional[NamePart] = None
    phone: Optional[Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^\+?[0-9 ()-]{7,20}$")]] = None

class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=128)

class Token(BaseModel):
    access_token: str
    token_type: str
    role: str
    interests_set: bool
    profile_complete: Optional[bool] = None
    notice: Optional[str] = None                # something the person should be told after signing in
    expires_in: Optional[int] = None            # seconds until the token expires outright
    idle_timeout_seconds: Optional[int] = None  # seconds of inactivity before the session ends

class AuthEventOut(BaseModel):
    id: int
    at: datetime
    portal: str
    email: Optional[str] = None
    user_id: Optional[int] = None
    ip: Optional[str] = None
    success: bool
    reason: str
    class Config:
        from_attributes = True

class SessionOut(BaseModel):
    id: str
    created_at: datetime
    last_seen_at: datetime
    ip: Optional[str] = None
    user_agent: Optional[str] = None
    current: bool = False

# User
class UserOut(BaseModel):
    id: int
    name: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str]
    phone: Optional[str]
    date_of_birth: Optional[date] = None
    role: str
    interests_set: bool
    college_id: Optional[int] = None
    study_year: Optional[int] = None
    student_verified_until: Optional[datetime] = None
    is_student_verified: bool = False
    college_ids: List[int] = []   # for organisers: the colleges they may list fests for
    organizer_welcome_pending: bool = False
    can_host_fests: bool = False
    can_host_city_events: bool = False
    has_password: bool = True
    google_linked: bool = False
    profile_complete: bool = True   # false until a date of birth and the terms are on file (e.g. after signing up with Google)
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
    end_time: Optional[str] = Field(default=None, pattern=TIME_PATTERN)
    extra_sections: Optional[List[ExtraSection]] = None

    _check_sections = field_validator("extra_sections")(check_sections)
    _clean_image = field_validator("image_url")(clean_url)

    @field_validator("time")
    @classmethod
    def valid_time(cls, v):
        if v is not None and not re.fullmatch(TIME_PATTERN, v):
            raise ValueError("time must look like 18:30")
        return v

    # ── Fest-event registration fields (only used when event_type='fest') ──────────
    requires_registration: Optional[bool] = False
    is_paid:               Optional[bool] = False
    registration_limit:    Optional[int]  = None
    approval_mode:         Optional[Literal["auto", "manual"]] = "auto"

    # Student verification
    students_only:         bool = False
    student_price:         Optional[float] = Field(default=None, ge=0)  # cheaper price for verified students

    # Team events: the seat limit counts teams
    is_team_event:         bool = False
    team_min:              Optional[int] = Field(default=None, ge=1, le=MAX_TEAM_SIZE)
    team_max:              Optional[int] = Field(default=None, ge=2, le=MAX_TEAM_SIZE)

    @model_validator(mode="after")
    def validate_branch_constraints(self) -> "EventCreate":
        check_team_settings(self.is_team_event, self.team_min, self.team_max, self.event_type == "fest", bool(self.requires_registration))
        if not self.is_team_event:
            self.team_min = self.team_max = None
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
        if self.event_type == "fest":
            missing = [name for name, value in (("venue", self.location), ("start time", self.time), ("end time", self.end_time), ("description", self.description)) if not (value or "").strip()]
            if missing:
                raise ValueError("a fest event needs: " + ", ".join(missing))
        if self.time and self.end_time and self.end_time <= self.time:
            raise ValueError("end time must be after the start time")
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
    end_time: Optional[str] = None
    image_url: Optional[str]
    category: Optional[str]
    extra_sections: Optional[List[ExtraSection]] = None
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
    is_team_event: bool = False
    team_min: Optional[int] = None
    team_max: Optional[int] = None
    cancelled: bool = False
    cancel_reason: Optional[str] = None
    reject_reason: Optional[str] = None
    created_at: datetime
    class Config:
        from_attributes = True


class EventUpdate(BaseModel):
    """Fields allowed to be patched on an existing event."""
    title:              Optional[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]] = None
    description:        Optional[str]   = None
    location:           Optional[str]   = None
    date:               Optional[datetime] = None
    time:               Optional[str]   = Field(default=None, pattern=TIME_PATTERN)
    end_time:           Optional[str]   = Field(default=None, pattern=TIME_PATTERN)
    image_url:          Optional[str]   = None
    category:           Optional[str]   = None
    extra_sections:     Optional[List[ExtraSection]] = None
    # Registration mutable fields — locked if registrations exist
    requires_registration: Optional[bool]  = None
    is_paid:               Optional[bool]  = None
    price:                 Optional[float] = Field(default=None, ge=0)
    registration_limit:    Optional[int]   = Field(default=None, gt=0)
    approval_mode:         Optional[Literal["auto", "manual"]] = None
    students_only:         Optional[bool] = None
    student_price:         Optional[float] = Field(default=None, ge=0)
    is_team_event:         Optional[bool] = None
    team_min:              Optional[int] = Field(default=None, ge=1, le=MAX_TEAM_SIZE)
    team_max:              Optional[int] = Field(default=None, ge=2, le=MAX_TEAM_SIZE)

    _check_sections = field_validator("extra_sections")(check_sections)
    _clean_image = field_validator("image_url")(clean_url)

# Fest
# Words the API itself uses after /fests/, so a fest may not take them as its address
RESERVED_FEST_SLUGS = {"all", "my-passes", "my-pass", "mine"}

class FestCreate(BaseModel):
    """Starting a fest needs only a name, a web address and the college. Everything else is filled in before review."""
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", min_length=2, max_length=100)
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
    tagline: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]] = None
    college_id: int

    @field_validator("slug")
    @classmethod
    def slug_not_reserved(cls, v):
        if v in RESERVED_FEST_SLUGS:
            raise ValueError("this slug is reserved")
        return v

class FestOut(BaseModel):
    """What everyone can see about a fest."""
    id: int
    slug: str
    name: str
    tagline: Optional[str]
    description: Optional[str] = None
    banner_url: Optional[str]
    logo_url: Optional[str]
    college_id: Optional[int]
    status: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    campus_address: Optional[str] = None
    map_url: Optional[str] = None
    instagram_url: Optional[str] = None
    website_url: Optional[str] = None
    extra_sections: Optional[List[ExtraSection]] = None
    event_count: int = 0
    created_at: datetime
    class Config:
        from_attributes = True

class FestManageOut(FestOut):
    """What the committee and admins see: adds private contact details and the review state."""
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    faculty_name: Optional[str] = None
    faculty_phone: Optional[str] = None
    faculty_email: Optional[str] = None
    review_status: str = "draft"
    review_note: Optional[str] = None
    submitted_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None

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

class FestInviteOut(BaseModel):
    id: int
    fest_id: int
    fest_slug: Optional[str] = None
    fest_name: Optional[str] = None
    user_id: int
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    role: str
    status: str
    invited_by_name: Optional[str] = None
    created_at: datetime
    decided_at: Optional[datetime] = None
    class Config:
        from_attributes = True

class AccountNoticeOut(BaseModel):
    id: int
    kind: str
    title: str
    body: str
    created_at: datetime
    read_at: Optional[datetime] = None
    invite_id: Optional[int] = None
    invite_status: Optional[str] = None   # the invitation's current state, when the notice is about one
    fest_slug: Optional[str] = None
    fest_name: Optional[str] = None
    role: Optional[str] = None

class NoticeCount(BaseModel):
    count: int

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
    review_status: str = "draft"
    review_note: Optional[str] = None

class FestUpdate(BaseModel):
    """Details an organiser can fill in. Name and college changes after approval send the fest back to review."""
    name: Optional[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]] = None
    tagline: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]] = None
    description: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=5000)]] = None
    banner_url: Optional[str] = None
    logo_url: Optional[str] = None
    college_id: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    campus_address: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]] = None
    map_url: Optional[str] = None
    instagram_url: Optional[str] = None
    website_url: Optional[str] = None
    extra_sections: Optional[List[ExtraSection]] = None
    contact_name: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)]] = None
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[Annotated[str, StringConstraints(strip_whitespace=True, pattern=PHONE_PATTERN)]] = None
    faculty_name: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)]] = None
    faculty_phone: Optional[Annotated[str, StringConstraints(strip_whitespace=True, pattern=PHONE_PATTERN)]] = None
    faculty_email: Optional[EmailStr] = None

    _check_sections = field_validator("extra_sections")(check_sections)
    _clean_links = field_validator("banner_url", "logo_url", "map_url", "instagram_url", "website_url")(clean_url)

    @model_validator(mode="after")
    def dates_in_order(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("the fest cannot end before it starts")
        return self

# College
class CollegeCreate(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
    area: Optional[str] = None
    emoji: Optional[str] = "🏛️"
    website: Optional[str] = None
    email_domains: Optional[str] = None  # comma-separated email domains students of this college use
    partner_status: Literal["prospect", "partner"] = "prospect"
    coordinator_name: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)]] = None
    coordinator_phone: Optional[Annotated[str, StringConstraints(strip_whitespace=True, pattern=PHONE_PATTERN)]] = None
    coordinator_email: Optional[EmailStr] = None
    partner_since: Optional[date] = None
    partner_notes: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]] = None

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
    partner_status: str = "prospect"
    event_count: int = 0
    class Config:
        from_attributes = True

class CollegeAdminOut(CollegeOut):
    """Adds the private partnership details only admins see."""
    coordinator_name: Optional[str] = None
    coordinator_phone: Optional[str] = None
    coordinator_email: Optional[str] = None
    partner_since: Optional[date] = None
    partner_notes: Optional[str] = None

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
    team_id: Optional[int] = None
    approval_status: str
    payment_status: str
    amount_due: Optional[float] = None
    created_at: datetime
    class Config:
        from_attributes = True

class EventRegistrationDetailOut(EventRegistrationOut):
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    team_name: Optional[str] = None
    is_team_leader: bool = False
    checked_in: bool = False
    answers: List["AnswerOut"] = []

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
    college_ids: List[int] = []
    can_host_fests: bool = False
    can_host_city_events: bool = False
    created_at: datetime
    class Config:
        from_attributes = True

class AdminProfileUpdate(BaseModel):
    """What an admin may correct on someone's profile. Sign-in details, passwords, roles and Google links are deliberately not here."""
    model_config = ConfigDict(extra="forbid")   # sending email, password, role etc. is rejected
    first_name: Optional[NamePart] = None
    last_name: Optional[NamePart] = None
    phone: Optional[Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^\+?[0-9 ()-]{7,20}$")]] = None
    date_of_birth: Optional[date] = None
    study_year: Optional[int] = Field(default=None, ge=1, le=6)
    college_id: Optional[int] = None

class AdminSignIn(BaseModel):
    at: datetime
    portal: str
    success: bool
    reason: str
    ip: Optional[str] = None

class AdminSession(BaseModel):
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    ip: Optional[str] = None
    user_agent: Optional[str] = None

class AdminStudentInfo(BaseModel):
    verified: bool
    verified_until: Optional[datetime] = None
    latest_method: Optional[str] = None
    latest_status: Optional[str] = None
    latest_at: Optional[datetime] = None
    latest_college: Optional[str] = None
    latest_reject_reason: Optional[str] = None

class AdminUserFest(BaseModel):
    slug: str
    name: str
    my_role: str
    status: str
    review_status: str

class AdminUserDetail(BaseModel):
    id: int
    name: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    date_of_birth: Optional[date] = None
    role: str
    is_active: bool
    created_at: datetime
    terms_accepted_at: Optional[datetime] = None
    interests_set: bool
    study_year: Optional[int] = None
    home_college: Optional[str] = None
    has_password: bool
    google_linked: bool
    can_host_fests: bool
    can_host_city_events: bool
    colleges: List[str] = []
    student: AdminStudentInfo
    active_sessions: List[AdminSession] = []
    last_seen_at: Optional[datetime] = None
    recent_sign_ins: List[AdminSignIn] = []
    fests: List[AdminUserFest] = []

class RoleChange(BaseModel):
    role: Literal["user", "organizer"]
    college_ids: List[int] = []   # required (at least one) when making someone an organiser that hosts fests
    can_host_fests: bool = True
    can_host_city_events: bool = False

class PermissionChange(BaseModel):
    can_host_fests: bool
    can_host_city_events: bool

class ActiveChange(BaseModel):
    is_active: bool

class AdminOverview(BaseModel):
    members: int
    organizers: int
    admins: int
    suspended: int
    partner_colleges: int
    prospect_colleges: int
    fests_live: int
    fests_in_review: int
    fests_changes_requested: int
    fests_draft: int
    events_total: int
    city_events_pending: int
    registrations: int
    fest_passes: int
    verifications_pending: int
    verified_students: int

class CollegeAssignment(BaseModel):
    college_ids: List[int] = Field(min_length=1)

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


# Custom registration questions
QUESTION_KINDS = ("short_text", "choice", "yes_no")
MAX_QUESTIONS = 10

class QuestionIn(BaseModel):
    id: Optional[int] = None   # present when keeping an existing question
    label: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    kind: Literal["short_text", "choice", "yes_no"]
    required: bool = False
    options: Optional[List[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]]] = None

    @model_validator(mode="after")
    def options_match_kind(self):
        if self.kind == "choice":
            if not self.options or not (2 <= len(self.options) <= 20):
                raise ValueError("a choice question needs between 2 and 20 options")
            if len(set(o.lower() for o in self.options)) != len(self.options):
                raise ValueError("options must be different from each other")
        else:
            self.options = None
        return self

class QuestionsPut(BaseModel):
    questions: List[QuestionIn] = Field(max_length=MAX_QUESTIONS)

class QuestionOut(BaseModel):
    id: int
    label: str
    kind: str
    required: bool
    options: Optional[List[str]] = None
    position: int
    class Config:
        from_attributes = True

class AnswerIn(BaseModel):
    question_id: int
    value: Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)]

class RegisterIn(BaseModel):
    answers: List[AnswerIn] = []

class AnswerOut(BaseModel):
    question_id: int
    label: str
    answer: str


# Media
class MediaOut(BaseModel):
    id: str
    url: str


# Announcements
class AnnouncementIn(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    body: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
    event_id: Optional[int] = None   # none = the whole fest
    send_email: bool = False

class AnnouncementOut(BaseModel):
    id: int
    fest_id: int
    fest_slug: Optional[str] = None
    fest_name: Optional[str] = None
    event_id: Optional[int] = None
    event_title: Optional[str] = None
    title: str
    body: str
    email_requested: bool = False
    emails_sent: int = 0
    emails_failed: int = 0
    created_at: datetime


# Fest review
class ReviewNote(BaseModel):
    note: Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=1000)]

class ReviewEvent(BaseModel):
    id: int
    title: str
    date: datetime
    time: Optional[str] = None
    end_time: Optional[str] = None
    location: Optional[str] = None
    requires_registration: bool = False
    price: float = 0

class ReviewCollege(BaseModel):
    id: int
    name: str
    partner_status: str
    coordinator_name: Optional[str] = None
    coordinator_phone: Optional[str] = None
    coordinator_email: Optional[str] = None
    partner_since: Optional[date] = None
    partner_notes: Optional[str] = None

class FestReviewOut(BaseModel):
    fest: FestManageOut
    college: Optional[ReviewCollege] = None
    events: List[ReviewEvent] = []
    missing: List[str] = []           # anything still incomplete
    owners: List[str] = []            # names and emails of the fest's directors
    short_link: Optional[str] = None  # the custom short name the fest holds, if any

class ShortLinkIn(BaseModel):
    name: str

class ShortLinkOut(BaseModel):
    name: Optional[str] = None        # the short name the fest holds, if any
    path: Optional[str] = None        # "/the-name"
    target_path: str                  # where it leads, e.g. "/fests/mood-indigo"
    enabled: bool = True              # false when the feature is part of a plan this account does not have

class ShortLinkCheck(BaseModel):
    name: str
    available: bool
    reason: Optional[str] = None      # invalid | reserved | taken

class EventRejection(BaseModel):
    reason: Optional[Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)]] = None

class ChecklistOut(BaseModel):
    missing: List[str] = []

class SubmitOut(BaseModel):
    fest: FestManageOut
    missing: List[str] = []


# Teams
class TeamCreate(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    answers: List[AnswerIn] = []

class TeamJoin(BaseModel):
    code: Annotated[str, StringConstraints(strip_whitespace=True, to_upper=True, min_length=4, max_length=12)]
    answers: List[AnswerIn] = []

class TeamMemberOut(BaseModel):
    registration_id: int
    name: Optional[str] = None
    email: Optional[str] = None        # only shown to the committee
    is_leader: bool = False
    approval_status: str
    attended: bool = False

class TeamOut(BaseModel):
    id: int
    event_id: int
    name: str
    code: Optional[str] = None         # only shown to the team and the committee
    size: int
    team_min: Optional[int] = None
    team_max: Optional[int] = None
    complete: bool                     # has at least the smallest allowed number of members
    status: str                        # the team's approval status: pending | approved | rejected
    i_am_leader: bool = False
    members: List[TeamMemberOut] = []


# Fest transfers
class TransferCreate(BaseModel):
    email: EmailStr
    keep_me: bool = True               # stay on as core team after handing over

class AdminOwnerChange(BaseModel):
    email: EmailStr
    keep_previous_owner: bool = True

class TransferOut(BaseModel):
    id: int
    fest_slug: str
    fest_name: str
    from_name: Optional[str] = None
    from_email: Optional[str] = None
    to_name: Optional[str] = None
    to_email: Optional[str] = None
    status: str
    keep_previous_owner: bool
    created_at: datetime


# Bulk import
class ImportRowOut(BaseModel):
    line: int
    title: str = ""
    errors: List[str] = []

class ImportResult(BaseModel):
    dry_run: bool
    rows: List[ImportRowOut] = []
    file_errors: List[str] = []
    valid: int = 0
    created: int = 0
