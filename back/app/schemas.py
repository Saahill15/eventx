import re
from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator, model_validator
from typing import Annotated, Dict, Optional, List, Literal
from datetime import date, datetime, timedelta

MAX_FEST_DAYS = 15
DateOnly = date  # for models that have a field called `date`, which would otherwise hide the type

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
def check_points_scheme(v):
    """Points by place for a scored event: {"1": 100, "2": 60}. None means the event is not scored."""
    if v is None:
        return None
    if not isinstance(v, dict) or not v:
        raise ValueError("points must list what at least one place earns, or be left out")
    if len(v) > 10:
        raise ValueError("points can be set for at most ten places")
    out = {}
    for place, pts in v.items():
        try:
            n, p = int(place), int(pts)
        except (TypeError, ValueError):
            raise ValueError("places and points must be whole numbers")
        if not 1 <= n <= 20 or not 0 <= p <= 10000:
            raise ValueError("a place is 1 to 20 and points are 0 to 10000")
        out[str(n)] = p
    return out


def check_registration_window(mode, opens_on, deadline, last_day):
    """Why these registration dates cannot work together, or None when they can."""
    if mode == "scheduled":
        if opens_on is None:
            return "choose the day registration opens, or pick another option"
        if opens_on > last_day:
            return "registration must open by the event's last day"
        if deadline is not None and opens_on > deadline:
            return "registration cannot open after it closes"
    return None


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

    # How many days it runs from `date`, who runs it, and the last day to register
    span_days:             int = Field(default=1, ge=1, le=15)
    coordinator_name:      Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)]] = None
    coordinator_phone:     Optional[Annotated[str, StringConstraints(strip_whitespace=True, pattern=PHONE_PATTERN)]] = None
    registration_deadline: Optional[date] = None
    # When registration opens. "open_now" is the default so a client that says nothing keeps working as before.
    registration_mode:     Literal["open_now", "scheduled", "not_set", "closed"] = "open_now"
    registration_opens_on: Optional[date] = None
    points_scheme:         Optional[Dict[str, int]] = None   # what each place earns a contingent; None: not a scored competition
    _check_points = field_validator("points_scheme")(check_points_scheme)
    # Visiting colleges entering the event, and what an entry costs (in rupees)
    contingent_entries:     bool = False
    entries_per_contingent: int = Field(default=1, ge=1, le=50)
    entry_fee:              float = Field(default=0, ge=0, le=1000000)
    entry_fee_per:          Literal["entry", "participant"] = "entry"
    entry_deadline:         Optional[date] = None
    # A queue for a full event
    waitlist_enabled:       bool = False
    waitlist_limit:         Optional[int] = Field(default=None, ge=1, le=10000)

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
        if self.registration_deadline is not None and self.registration_deadline > self.date.date() + timedelta(days=self.span_days - 1):
            raise ValueError("registration must close by the event's last day")
        if self.entry_deadline is not None and self.entry_deadline > self.date.date() + timedelta(days=self.span_days - 1):
            raise ValueError("entries must close by the event's last day")
        problem = check_registration_window(self.registration_mode, self.registration_opens_on, self.registration_deadline, self.date.date() + timedelta(days=self.span_days - 1))
        if problem:
            raise ValueError(problem)
        if self.registration_mode != "scheduled":
            self.registration_opens_on = None
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
    span_days: int = 1
    coordinator_name: Optional[str] = None
    coordinator_phone: Optional[str] = None
    registration_deadline: Optional[date] = None
    registration_mode: str = "open_now"
    registration_opens_on: Optional[date] = None
    registration_state: Optional[str] = None  # open | scheduled | not_open | closed; None when no registration is needed
    points_scheme: Optional[Dict[str, int]] = None
    contingent_entries: bool = False
    entries_per_contingent: int = 1
    entry_fee: float = 0
    entry_fee_per: str = "entry"
    entry_deadline: Optional[date] = None
    waitlist_enabled: bool = False
    price_is_from: bool = False
    waitlist_limit: Optional[int] = None
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
    span_days:             Optional[int] = Field(default=None, ge=1, le=15)
    coordinator_name:      Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)]] = None
    coordinator_phone:     Optional[Annotated[str, StringConstraints(strip_whitespace=True, pattern=PHONE_PATTERN)]] = None
    registration_deadline: Optional[DateOnly] = None
    registration_mode:     Optional[Literal["open_now", "scheduled", "not_set", "closed"]] = None
    registration_opens_on: Optional[DateOnly] = None
    points_scheme:         Optional[Dict[str, int]] = None
    _check_points = field_validator("points_scheme")(check_points_scheme)
    contingent_entries:     Optional[bool] = None
    entries_per_contingent: Optional[int] = Field(default=None, ge=1, le=50)
    entry_fee:              Optional[float] = Field(default=None, ge=0, le=1000000)
    entry_fee_per:          Optional[Literal["entry", "participant"]] = None
    entry_deadline:         Optional[DateOnly] = None
    waitlist_enabled:       Optional[bool] = None
    waitlist_limit:         Optional[int] = Field(default=None, ge=1, le=10000)

    _check_sections = field_validator("extra_sections")(check_sections)
    _clean_image = field_validator("image_url")(clean_url)

SPONSOR_LEVELS = {1: "Title Sponsor", 2: "Powered by", 3: "Associate Sponsors", 4: "Partners"}
MAX_SPONSORS = 40


def clean_web_address(v):
    """A link to a sponsor's site: http or https only."""
    if v is None:
        return None
    v = v.strip()
    if not v:
        return None
    if re.fullmatch(r"https?://[^\s]{3,490}", v):
        return v
    raise ValueError("must be a web address starting with http:// or https://")


class SponsorIn(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    level: int = Field(default=3, ge=1, le=4)
    tier_label: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=60)]] = None   # empty means the usual name for the level
    logo_url: Optional[str] = None
    website_url: Optional[str] = None
    blurb: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]] = None

    _clean_logo = field_validator("logo_url")(clean_url)
    _clean_site = field_validator("website_url")(clean_web_address)


class SponsorUpdate(BaseModel):
    """Send only what changes; null clears the logo, link and line."""
    name: Optional[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]] = None
    level: Optional[int] = Field(default=None, ge=1, le=4)
    tier_label: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=60)]] = None
    logo_url: Optional[str] = None
    website_url: Optional[str] = None
    blurb: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]] = None

    _clean_logo = field_validator("logo_url")(clean_url)
    _clean_site = field_validator("website_url")(clean_web_address)


class SponsorOut(BaseModel):
    id: int
    fest_id: int
    name: str
    level: int
    tier_label: str
    logo_url: Optional[str] = None
    website_url: Optional[str] = None
    blurb: Optional[str] = None
    position: int = 0
    class Config:
        from_attributes = True


class SponsorMove(BaseModel):
    direction: Literal["up", "down"]


# The organiser's home page: everything across their fests in one call
class DashSetup(BaseModel):
    done: int
    total: int
    next_label: Optional[str] = None   # the first thing still to do
    next_tab: Optional[str] = None     # the tab of the fest manager that does it

class DashFest(BaseModel):
    id: int
    slug: str
    name: str
    tagline: Optional[str] = None
    banner_url: Optional[str] = None
    logo_url: Optional[str] = None
    college_name: Optional[str] = None
    status: str
    review_status: str
    my_role: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    days_count: Optional[int] = None
    dates_tba: bool = False
    events: int = 0
    registered: Optional[int] = None       # approved registrations, for committee who can see them
    pending: Optional[int] = None          # registrations waiting for approval
    passes_issued: Optional[int] = None
    passes_checked_in: Optional[int] = None
    setup: Optional[DashSetup] = None      # only until the fest is live

class DashAttention(BaseModel):
    kind: str            # changes_requested | rejected | approved | approvals | registration_closed | overdue
    tone: str            # red | amber | green
    fest_slug: str
    fest_name: str
    title: str
    detail: Optional[str] = None
    tab: str             # where to go in that fest

class DashTask(BaseModel):
    id: int
    fest_slug: str
    fest_name: str
    title: str
    status: str
    due_date: Optional[date] = None
    overdue: bool = False

class DashUpcoming(BaseModel):
    kind: str            # event | meeting
    fest_slug: str
    fest_name: str
    title: str
    when: datetime
    time: Optional[str] = None   # "18:30", the start time of the event or meeting
    detail: Optional[str] = None
    tab: str

class DashboardOut(BaseModel):
    fests: List[DashFest] = []
    attention: List[DashAttention] = []
    my_tasks: List[DashTask] = []
    coming_up: List[DashUpcoming] = []


class RegistrationControl(BaseModel):
    """Open or close registration by hand, without touching the rest of the event."""
    action: Literal["open", "close"]


# Fest
# Words the API itself uses after /fests/, so a fest may not take them as its address
RESERVED_FEST_SLUGS = {"all", "my-passes", "my-pass", "mine"}

class FestCreate(BaseModel):
    """
    Starting a fest needs only a name, a web address and the college. Dates are welcome if the committee already has them,
    but many colleges have not fixed them yet, so they are optional here (they are needed before the fest goes for review).
    """
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", min_length=2, max_length=100)
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
    tagline: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]] = None
    college_id: int
    start_date: Optional[date] = None
    end_date: Optional[date] = None

    @model_validator(mode="after")
    def dates_make_sense(self):
        if self.start_date and not self.end_date:
            self.end_date = self.start_date  # a one-day fest: only the start was given
        if self.end_date and not self.start_date:
            raise ValueError("add a start date as well, or leave both dates empty")
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("the end date cannot be before the start date")
        if self.start_date and (self.end_date - self.start_date).days + 1 > MAX_FEST_DAYS:
            raise ValueError(f"a fest can run for at most {MAX_FEST_DAYS} days")
        return self

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
    dates_tba: bool = False   # the dates are not fixed yet: shown as "Dates coming soon"
    days_count: Optional[int] = None   # worked out from the dates; read only
    campus_address: Optional[str] = None
    map_url: Optional[str] = None
    instagram_url: Optional[str] = None
    website_url: Optional[str] = None
    extra_sections: Optional[List[ExtraSection]] = None
    event_count: int = 0
    created_at: datetime
    class Config:
        from_attributes = True

REVIEW_FIELD_KEYS = ("name", "tagline", "dates", "banner", "description", "venue", "contact", "events", "links")


class ReviewFieldNote(BaseModel):
    """One thing the admin wants fixed, tied to a part of the fest so the organiser can find it."""
    key: Literal["name", "tagline", "dates", "banner", "description", "venue", "contact", "events", "links"]
    note: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]


class ReviewDecision(BaseModel):
    """Sending a fest back, rejecting it or taking it offline: a general note, notes on specific fields, or both."""
    note: Optional[Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=1000)]] = None
    fields: List[ReviewFieldNote] = Field(default_factory=list, max_length=len(REVIEW_FIELD_KEYS))

    @model_validator(mode="after")
    def something_to_say(self):
        if not self.note and not self.fields:
            raise ValueError("write a note, or flag at least one field")
        keys = [f.key for f in self.fields]
        if len(keys) != len(set(keys)):
            raise ValueError("each field can be flagged once")
        return self


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
    review_fields: List[ReviewFieldNote] = Field(default_factory=list)
    submitted_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None

    @field_validator("review_fields", mode="before")
    @classmethod
    def no_fields_means_empty(cls, v):
        return v or []

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
    committee_team_id: Optional[int] = None
    team_name: Optional[str] = None
    team_role: str = "member"
    title: Optional[str] = None
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
    # Where they sit in the committee
    title: Optional[str] = None
    committee_team_id: Optional[int] = None
    team_name: Optional[str] = None
    reports_to_id: Optional[int] = None   # the fest-member id of their lead
    reports_to_name: Optional[str] = None
    team_role: str = "member"             # head | co_head | member, inside their team
    class Config:
        from_attributes = True


# Committee structure: teams, titles and who reports to whom
class CommitteeTeamIn(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    description: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)]] = None

TEAM_ROLES = ("head", "co_head", "member")
MAX_CO_HEADS = 3

class CommitteeTeamUpdate(BaseModel):
    """Send only what changes. head_member_id null clears the head; co_head_member_ids is the whole list of co-heads."""
    name: Optional[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]] = None
    description: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)]] = None
    leaders_manage_team: Optional[bool] = None
    head_member_id: Optional[int] = None
    co_head_member_ids: Optional[List[int]] = Field(default=None, max_length=MAX_CO_HEADS)
    give_core_access: bool = False   # also give the head the Core team access level (the director only)

class TeamLeader(BaseModel):
    member_id: int
    user_id: int
    name: Optional[str] = None
    role: str   # their access level

class CommitteeTeamOut(BaseModel):
    id: int
    fest_id: int
    name: str
    description: Optional[str] = None
    member_count: int = 0
    leaders_manage_team: bool = True
    head: Optional[TeamLeader] = None
    co_heads: List[TeamLeader] = []

class MemberPlacement(BaseModel):
    """Change where someone sits. Send only what changes; null clears a field."""
    title: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)]] = None
    committee_team_id: Optional[int] = None
    reports_to_id: Optional[int] = None
    team_role: Optional[Literal["head", "co_head", "member"]] = None

TASK_STATUSES = ("todo", "doing", "done")


class TaskIn(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    description: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]] = None
    status: Literal["todo", "doing", "done"] = "todo"
    due_date: Optional[date] = None
    assignee_member_id: Optional[int] = None
    committee_team_id: Optional[int] = None
    meeting_id: Optional[int] = None   # set when the task is an action item from a meeting


class TaskUpdate(BaseModel):
    """Send only what changes; null clears the optional fields."""
    title: Optional[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]] = None
    description: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]] = None
    status: Optional[Literal["todo", "doing", "done"]] = None
    due_date: Optional[date] = None
    assignee_member_id: Optional[int] = None
    committee_team_id: Optional[int] = None
    meeting_id: Optional[int] = None


class TaskOut(BaseModel):
    id: int
    fest_id: int
    title: str
    description: Optional[str] = None
    status: str
    due_date: Optional[date] = None
    assignee_member_id: Optional[int] = None
    assignee_name: Optional[str] = None
    committee_team_id: Optional[int] = None
    team_name: Optional[str] = None
    created_by_name: Optional[str] = None
    meeting_id: Optional[int] = None
    meeting_title: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    overdue: bool = False
    class Config:
        from_attributes = True


class MeetingIn(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    starts_at: datetime
    location: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)]] = None
    agenda: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=5000)]] = None
    member_ids: Optional[List[int]] = None   # who is invited; leave out to invite the whole committee


class MeetingUpdate(BaseModel):
    """Send only what changes; null clears the optional fields."""
    title: Optional[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]] = None
    starts_at: Optional[datetime] = None
    location: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)]] = None
    agenda: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=5000)]] = None
    minutes: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=20000)]] = None
    member_ids: Optional[List[int]] = None


class MeetingAttendance(BaseModel):
    attended_member_ids: List[int] = []


class MeetingAttendeeOut(BaseModel):
    member_id: int
    user_name: Optional[str] = None
    title: Optional[str] = None
    attended: bool = False
    class Config:
        from_attributes = True


class MeetingOut(BaseModel):
    id: int
    fest_id: int
    title: str
    starts_at: datetime
    location: Optional[str] = None
    agenda: Optional[str] = None
    minutes: Optional[str] = None
    created_by_name: Optional[str] = None
    invited_count: int = 0
    attended_count: int = 0
    action_count: int = 0
    open_action_count: int = 0
    class Config:
        from_attributes = True


class MeetingDetail(MeetingOut):
    attendees: List[MeetingAttendeeOut] = []
    actions: List[TaskOut] = []


class ScheduleItem(BaseModel):
    id: int
    title: str
    date: date
    time: Optional[str] = None
    end_time: Optional[str] = None
    location: Optional[str] = None
    category: Optional[str] = None
    cancelled: bool = False
    clash_ids: List[int] = []
    span_days: int = 1
    day_of_event: int = 1     # which of its days this entry is, from 1


class ScheduleClash(BaseModel):
    date: date
    venue: str
    first_id: int
    second_id: int


class ScheduleDay(BaseModel):
    date: date
    day_number: Optional[int] = None   # which day of the fest, from 1, when the fest's dates are set
    items: List[ScheduleItem] = []


class ScheduleOut(BaseModel):
    days: List[ScheduleDay] = []
    venues: List[str] = []
    clashes: List[ScheduleClash] = []
    unscheduled: List[ScheduleItem] = []   # events that cannot be placed yet: no time or no venue


class ClashCheckOut(BaseModel):
    clashes: List[ScheduleItem] = []


# Contingents: visiting colleges at a fest
Term = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]


class ContingentSettingsIn(BaseModel):
    """How this fest runs its visiting colleges. Sending it replaces the settings."""
    enabled: bool = False
    term: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)] = "Contingent"
    leader_term: Term = "Contingent Leader"
    assistant_term: Term = "Assistant Contingent Leader"
    max_assistants: int = Field(default=2, ge=0, le=10)
    min_members: int = Field(default=1, ge=1, le=500)
    max_members: Optional[int] = Field(default=None, ge=1, le=1000)
    allow_multiple_per_college: bool = False
    requires_approval: bool = True
    opens_on: Optional[date] = None
    closes_on: Optional[date] = None
    lock_roster_after_close: bool = True

    @model_validator(mode="after")
    def sensible(self):
        if self.max_members is not None and self.max_members < self.min_members:
            raise ValueError("the largest contingent cannot be smaller than the smallest")
        if self.opens_on and self.closes_on and self.closes_on < self.opens_on:
            raise ValueError("registration cannot close before it opens")
        return self


class ContingentSettingsOut(ContingentSettingsIn):
    registration_open: bool = False   # enabled, and today is inside the window
    class Config:
        from_attributes = True


class ContingentInfo(BaseModel):
    """The public part of a fest's contingent rules, so its page can invite visiting colleges to register."""
    enabled: bool = False
    registration_open: bool = False
    term: str = "Contingent"
    leader_term: str = "Contingent Leader"
    opens_on: Optional[date] = None
    closes_on: Optional[date] = None


class ContingentCreate(BaseModel):
    college_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)]
    college_id: Optional[int] = None


class ContingentUpdate(BaseModel):
    college_name: Optional[Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)]] = None
    college_id: Optional[int] = None


class ContingentDecision(BaseModel):
    note: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]] = None


class ContingentAssign(BaseModel):
    """Send only what changes; an empty value clears it."""
    code: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=30)]] = None
    name: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)]] = None


class ContingentMemberIn(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    email: Optional[EmailStr] = None
    phone: Optional[Annotated[str, StringConstraints(strip_whitespace=True, pattern=PHONE_PATTERN)]] = None
    year: Optional[int] = Field(default=None, ge=1, le=10)
    notes: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)]] = None


class ContingentMemberUpdate(BaseModel):
    name: Optional[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]] = None
    email: Optional[EmailStr] = None
    phone: Optional[Annotated[str, StringConstraints(strip_whitespace=True, pattern=PHONE_PATTERN)]] = None
    year: Optional[int] = Field(default=None, ge=1, le=10)
    notes: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)]] = None


class ContingentMemberOut(BaseModel):
    id: int
    contingent_id: int
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    year: Optional[int] = None
    notes: Optional[str] = None
    class Config:
        from_attributes = True


class ContingentAssistantIn(BaseModel):
    email: EmailStr


class ContingentAssistantOut(BaseModel):
    user_id: int
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    class Config:
        from_attributes = True


class ContingentOut(BaseModel):
    id: int
    fest_id: int
    college_name: str
    college_id: Optional[int] = None
    code: Optional[str] = None
    name: Optional[str] = None
    status: str
    note: Optional[str] = None
    leader_user_id: int
    leader_name: Optional[str] = None
    leader_email: Optional[str] = None
    assistant_count: int = 0
    member_count: int = 0
    created_at: datetime
    decided_at: Optional[datetime] = None
    class Config:
        from_attributes = True


class ContingentDetail(ContingentOut):
    assistants: List[ContingentAssistantOut] = []
    members: List[ContingentMemberOut] = []
    my_role: Optional[str] = None     # leader | assistant | staff
    roster_open: bool = True          # whether the leader and assistants may still change the roster
    roster_ok: bool = True            # whether the roster size is within the fest's limits


class OrgOut(BaseModel):
    teams: List[CommitteeTeamOut] = []
    members: List[FestMemberOut] = []

class AddFestMember(BaseModel):
    user_id: Optional[int] = None
    email: Optional[EmailStr] = None   # invite by email instead of by id
    role: Optional[str] = "volunteer"  # owner | core | volunteer
    committee_team_id: Optional[int] = None   # the team they will sit in
    team_role: Literal["head", "co_head", "member"] = "member"
    title: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)]] = None   # "Chairperson", "Vice Chairperson"...

    @model_validator(mode="after")
    def need_user_or_email(self):
        if self.team_role != "member" and self.committee_team_id is None:
            raise ValueError("pick a team for a head or co-head")
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
    dates_tba: Optional[bool] = None   # true = "dates coming soon": clears the dates, and needs no events yet
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
    ticket_tier_id: Optional[int] = None
    discount: float = 0
    created_at: datetime
    class Config:
        from_attributes = True

class EventRegistrationDetailOut(EventRegistrationOut):
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    tier_name: Optional[str] = None
    promo_code_text: Optional[str] = None
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
    ticket_tier_id: Optional[int] = None   # needed when the event sells more than one kind of ticket
    promo_code: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)]] = None

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

class ChecklistItem(BaseModel):
    key: str
    label: str                 # what to do, e.g. "Add a banner image"
    done: bool
    required: bool = True      # optional items never block sending for review
    tab: str                   # which tab of the fest manager completes it: details | events | team
    hint: Optional[str] = None
    problems: List[str] = []   # specifics still wrong inside this item (for example, which event lacks a venue)
    flag: Optional[str] = None  # what HiveOut asked to change about this item, while the fest is back with the organiser

class ChecklistOut(BaseModel):
    missing: List[str] = []
    items: List[ChecklistItem] = []

class SubmitOut(BaseModel):
    fest: FestManageOut
    missing: List[str] = []


# Teams
class TeamCreate(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    answers: List[AnswerIn] = []
    ticket_tier_id: Optional[int] = None
    promo_code: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)]] = None

class TeamJoin(BaseModel):
    code: Annotated[str, StringConstraints(strip_whitespace=True, to_upper=True, min_length=4, max_length=12)]
    answers: List[AnswerIn] = []
    ticket_tier_id: Optional[int] = None
    promo_code: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)]] = None

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


# ─── Competition between colleges ────────────────────────────────────────────────────────────────────────────────────
PointsInt = Annotated[int, Field(ge=-100000, le=100000)]


class CompetitionSettingsIn(BaseModel):
    starting_points: Optional[int] = Field(default=None, ge=0, le=100000)
    ranking_basis: Optional[Literal["total", "events"]] = None
    public_leaderboard: Optional[bool] = None
    default_placing_points: Optional[List[Annotated[int, Field(ge=0, le=10000)]]] = Field(default=None, max_length=10)
    default_task_points: Optional[List[Annotated[int, Field(ge=0, le=10000)]]] = Field(default=None, max_length=10)


class CompetitionSettingsOut(BaseModel):
    starting_points: int = 500
    ranking_basis: str = "total"
    public_leaderboard: bool = False
    default_placing_points: List[int] = [100, 60, 30]
    default_task_points: List[int] = [200, 100, 50]


class Breakdown(BaseModel):
    meet_tasks: int = 0
    auction: int = 0
    event_points: int = 0
    penalties: int = 0
    adjustments: int = 0


class ContingentStanding(BaseModel):
    contingent_id: int
    name: Optional[str] = None
    code: Optional[str] = None
    college_name: str
    rank: Optional[int] = None   # None for a contingent disqualified from the whole competition
    score: int                   # what the ranking uses (the balance, or only event points, by the fest's setting)
    balance: int                 # the points it holds now
    starting_points: int
    breakdown: Breakdown
    disqualified: bool = False


class CollegeStanding(BaseModel):
    college_name: str
    rank: Optional[int] = None
    score: int
    contingents: int
    contingent_names: List[str] = []


class AwardWinner(BaseModel):
    contingent_id: Optional[int] = None
    name: str
    college_name: Optional[str] = None


class AwardIn(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    basis: Literal["college", "contingent", "event", "custom"]
    rank: int = Field(default=1, ge=1, le=20)
    event_id: Optional[int] = None
    winner_contingent_id: Optional[int] = None

    @model_validator(mode="after")
    def basis_needs(self):
        if self.basis == "event" and self.event_id is None:
            raise ValueError("choose the event for this award")
        if self.basis != "event":
            self.event_id = None
        if self.basis != "custom":
            self.winner_contingent_id = None
        return self


class AwardUpdate(BaseModel):
    title: Optional[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]] = None
    rank: Optional[int] = Field(default=None, ge=1, le=20)
    event_id: Optional[int] = None
    winner_contingent_id: Optional[int] = None


class AwardOut(BaseModel):
    id: int
    title: str
    basis: str
    rank: int
    event_id: Optional[int] = None
    event_title: Optional[str] = None
    winner_contingent_id: Optional[int] = None
    winners: List[AwardWinner] = []


class LeaderboardOut(BaseModel):
    ranking_basis: str
    contingents: List[ContingentStanding] = []
    colleges: List[CollegeStanding] = []
    awards: List[AwardOut] = []


class PointsEntryOut(BaseModel):
    id: int
    contingent_id: int
    contingent_label: Optional[str] = None
    points: int
    kind: str
    reason: str
    created_at: datetime


class AdjustIn(BaseModel):
    contingent_id: int
    points: PointsInt
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=300)]

    @field_validator("points")
    @classmethod
    def not_zero(cls, v):
        if v == 0:
            raise ValueError("points cannot be zero")
        return v


class TaskAward(BaseModel):
    contingent_id: int
    points: PointsInt
    note: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]] = None


class TaskResultIn(BaseModel):
    awards: List[TaskAward] = Field(max_length=200)


class ClMeetTaskIn(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    description: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]] = None
    placing_points: Optional[List[Annotated[int, Field(ge=0, le=10000)]]] = Field(default=None, max_length=10)


class ClMeetTaskUpdate(BaseModel):
    title: Optional[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]] = None
    description: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]] = None
    placing_points: Optional[List[Annotated[int, Field(ge=0, le=10000)]]] = Field(default=None, max_length=10)


class TaskResultOut(BaseModel):
    contingent_id: int
    contingent_label: Optional[str] = None
    points: int
    note: Optional[str] = None


class ClMeetTaskOut(BaseModel):
    id: int
    meet_id: int
    title: str
    description: Optional[str] = None
    position: int
    placing_points: Optional[List[int]] = None
    results: List[TaskResultOut] = []   # what each contingent got (a leader sees only their own)


class ClMeetIn(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    starts_at: datetime
    location: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)]] = None
    notes: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=5000)]] = None


class ClMeetUpdate(BaseModel):
    title: Optional[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]] = None
    starts_at: Optional[datetime] = None
    location: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)]] = None
    notes: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=5000)]] = None


class ClMeetOut(BaseModel):
    id: int
    fest_id: int
    title: str
    starts_at: datetime
    location: Optional[str] = None
    notes: Optional[str] = None
    tasks: List[ClMeetTaskOut] = []
    attended: List[int] = []   # contingent ids


class AttendanceIn(BaseModel):
    contingent_ids: List[int] = Field(max_length=500)


class AuctionIn(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    meet_id: Optional[int] = None
    min_bid: int = Field(default=1, ge=0, le=100000)
    show_highest_bid: bool = False


class AuctionUpdate(BaseModel):
    title: Optional[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]] = None
    meet_id: Optional[int] = None
    min_bid: Optional[int] = Field(default=None, ge=0, le=100000)
    show_highest_bid: Optional[bool] = None


class AuctionNameIn(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    code: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=30)]] = None


class BidIn(BaseModel):
    contingent_id: Optional[int] = None   # the committee bids for a contingent; a leader's own is assumed
    amount: int = Field(ge=0, le=1000000)


class BidOut(BaseModel):
    contingent_id: int
    contingent_label: Optional[str] = None
    amount: int


class AuctionNameOut(BaseModel):
    id: int
    name: str
    code: Optional[str] = None
    winner_contingent_id: Optional[int] = None
    winner_label: Optional[str] = None
    winning_bid: Optional[int] = None
    bids: List[BidOut] = []          # the committee sees every bid; a leader sees only their own
    top_bid: Optional[int] = None    # shown to leaders only when the auction is not sealed


class AuctionOut(BaseModel):
    id: int
    fest_id: int
    meet_id: Optional[int] = None
    title: str
    status: str
    min_bid: int
    show_highest_bid: bool
    names: List[AuctionNameOut] = []


class EventResultIn(BaseModel):
    contingent_id: int
    place: int = Field(ge=1, le=20)
    note: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)]] = None


class EventResultsIn(BaseModel):
    results: List[EventResultIn] = Field(max_length=100)


class EventResultOut(BaseModel):
    contingent_id: int
    contingent_label: Optional[str] = None
    place: int
    points: int = 0
    note: Optional[str] = None
    disqualified: bool = False


class EventResultsOut(BaseModel):
    event_id: int
    title: str
    points_scheme: Optional[Dict[str, int]] = None
    results: List[EventResultOut] = []


class RuleIn(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    description: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]] = None
    event_id: Optional[int] = None
    penalty_points: int = Field(default=0, ge=0, le=100000)
    disqualifies: bool = False


class RuleUpdate(BaseModel):
    title: Optional[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]] = None
    description: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]] = None
    event_id: Optional[int] = None
    penalty_points: Optional[int] = Field(default=None, ge=0, le=100000)
    disqualifies: Optional[bool] = None


class RuleOut(BaseModel):
    id: int
    event_id: Optional[int] = None
    event_title: Optional[str] = None
    title: str
    description: Optional[str] = None
    penalty_points: int
    disqualifies: bool


class PenaltyIn(BaseModel):
    contingent_id: int
    rule_id: Optional[int] = None
    event_id: Optional[int] = None
    points: Optional[int] = Field(default=None, ge=0, le=100000)   # taken from the rule when left out
    disqualified: Optional[bool] = None
    reason: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]] = None


class PenaltyOut(BaseModel):
    id: int
    contingent_id: int
    contingent_label: Optional[str] = None
    rule_id: Optional[int] = None
    rule_title: Optional[str] = None
    event_id: Optional[int] = None
    event_title: Optional[str] = None
    points: int
    disqualified: bool
    reason: str
    created_at: datetime
    revoked: bool = False


class MyAuctionName(BaseModel):
    id: int
    name: str
    code: Optional[str] = None
    my_bid: Optional[int] = None
    top_bid: Optional[int] = None
    winner_label: Optional[str] = None
    i_won: bool = False


class MyAuction(BaseModel):
    id: int
    title: str
    status: str
    min_bid: int
    show_highest_bid: bool
    names: List[MyAuctionName] = []


class MyMeet(BaseModel):
    id: int
    title: str
    starts_at: datetime
    location: Optional[str] = None
    notes: Optional[str] = None
    tasks: List[ClMeetTaskOut] = []
    attended: bool = False


class CompetitionMine(BaseModel):
    contingent_id: int
    name: Optional[str] = None
    code: Optional[str] = None
    college_name: str
    balance: int
    starting_points: int
    breakdown: Breakdown
    rank: Optional[int] = None          # only once the leaderboard is public
    disqualified: bool = False
    ledger: List[PointsEntryOut] = []
    penalties: List[PenaltyOut] = []
    meets: List[MyMeet] = []
    auctions: List[MyAuction] = []
    events: List[EventResultOut] = []   # where the contingent placed, with the event title in the label


# ─── Visiting colleges: event entries, accommodation and fees ─────────────────────────────────────────────────────────
Rupees = Annotated[float, Field(ge=0, le=10000000)]
SignedRupees = Annotated[float, Field(ge=-10000000, le=10000000)]
STAY_GROUPS = ("boys", "girls", "others")


class EntryIn(BaseModel):
    event_id: int
    member_ids: List[int] = Field(min_length=1, max_length=100)
    contingent_id: Optional[int] = None   # the committee enters on a contingent's behalf; a leader's own is assumed


class EntryUpdate(BaseModel):
    member_ids: List[int] = Field(min_length=1, max_length=100)


class EntryMemberOut(BaseModel):
    member_id: int
    name: str
    year: Optional[int] = None
    phone: Optional[str] = None   # shown to the committee and the contingent's own leaders


class EntryOut(BaseModel):
    id: int
    contingent_id: int
    contingent_label: Optional[str] = None
    college_name: Optional[str] = None
    event_id: int
    event_title: str
    event_date: datetime
    event_time: Optional[str] = None
    location: Optional[str] = None
    status: str
    note: Optional[str] = None
    members: List[EntryMemberOut] = []
    fee: float = 0
    warnings: List[str] = []   # for example a person who is entered in two events at the same time


class EnterableEvent(BaseModel):
    event_id: int
    title: str
    date: datetime
    time: Optional[str] = None
    end_time: Optional[str] = None
    location: Optional[str] = None
    span_days: int = 1
    is_team_event: bool = False
    team_min: Optional[int] = None
    team_max: Optional[int] = None
    entries_per_contingent: int = 1
    entry_fee: float = 0
    entry_fee_per: str = "entry"
    deadline: Optional[date] = None
    open: bool = True
    closed_reason: Optional[str] = None
    my_entries: int = 0


class MyEntries(BaseModel):
    contingent_id: int
    events: List[EnterableEvent] = []
    entries: List[EntryOut] = []


class AccomOptionIn(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    description: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]] = None
    capacity: int = Field(ge=1, le=100000)
    gender_policy: Literal["any", "boys", "girls"] = "any"
    fee_per_night: Rupees = 0


class AccomOptionUpdate(BaseModel):
    name: Optional[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]] = None
    description: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]] = None
    capacity: Optional[int] = Field(default=None, ge=1, le=100000)
    gender_policy: Optional[Literal["any", "boys", "girls"]] = None
    fee_per_night: Optional[Rupees] = None


class AccomOptionOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    capacity: int
    gender_policy: str
    fee_per_night: float
    allocated: int = 0
    free: int = 0


class AccomSettings(BaseModel):
    enabled: bool = False
    closes_on: Optional[date] = None
    open: bool = False   # enabled, and the closing date has not passed


class AccomSettingsIn(BaseModel):
    enabled: Optional[bool] = None
    closes_on: Optional[date] = None


class StayRequestIn(BaseModel):
    boys: int = Field(default=0, ge=0, le=1000)
    girls: int = Field(default=0, ge=0, le=1000)
    others: int = Field(default=0, ge=0, le=1000)
    arrival_date: date
    departure_date: date
    notes: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]] = None

    @model_validator(mode="after")
    def sensible(self):
        if self.boys + self.girls + self.others < 1:
            raise ValueError("say how many people need a place to stay")
        if self.departure_date <= self.arrival_date:
            raise ValueError("the departure must be after the arrival")
        if (self.departure_date - self.arrival_date).days > 30:
            raise ValueError("a stay can be at most 30 nights")
        return self


class StayAllocationIn(BaseModel):
    option_id: int
    group: Literal["boys", "girls", "others"]
    people: int = Field(ge=1, le=1000)


class StayAllocationsIn(BaseModel):
    allocations: List[StayAllocationIn] = Field(max_length=100)


class StayDeclineIn(BaseModel):
    note: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=300)]


class StayAllocationOut(BaseModel):
    option_id: int
    option_name: str
    group: str
    people: int
    nights: int
    fee: float


class StayRequestOut(BaseModel):
    id: int
    contingent_id: int
    contingent_label: Optional[str] = None
    college_name: Optional[str] = None
    boys: int
    girls: int
    others: int
    people: int
    arrival_date: date
    departure_date: date
    nights: int
    notes: Optional[str] = None
    status: str
    decision_note: Optional[str] = None
    allocations: List[StayAllocationOut] = []
    unplaced: Dict[str, int] = {}   # how many of each group still have no place
    fee: float = 0


class FeeSettingsIn(BaseModel):
    registration_fee: Optional[Rupees] = None
    fee_per_member: Optional[Rupees] = None
    fee_instructions: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]] = None
    fees_due_on: Optional[date] = None


class FeeSettingsOut(BaseModel):
    registration_fee: float = 0
    fee_per_member: float = 0
    fee_instructions: Optional[str] = None
    fees_due_on: Optional[date] = None


class FeeLine(BaseModel):
    kind: str   # registration | members | entry | stay | adjustment
    label: str
    quantity: int = 1
    unit: float = 0
    amount: float = 0
    adjustment_id: Optional[int] = None


class FeePaymentIn(BaseModel):
    amount: float = Field(gt=0, le=10000000)
    received_on: Optional[date] = None
    method: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)]] = None
    reference: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)]] = None
    note: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]] = None


class FeePaymentOut(BaseModel):
    id: int
    amount: float
    received_on: date
    method: Optional[str] = None
    reference: Optional[str] = None
    note: Optional[str] = None


class FeeAdjustmentIn(BaseModel):
    label: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)]
    amount: SignedRupees

    @field_validator("amount")
    @classmethod
    def not_zero(cls, v):
        if v == 0:
            raise ValueError("the amount cannot be zero")
        return v


class FeeStatement(BaseModel):
    contingent_id: int
    contingent_label: Optional[str] = None
    college_name: str
    lines: List[FeeLine] = []
    total: float = 0
    paid: float = 0
    balance: float = 0
    status: str = "no_fees"   # no_fees | unpaid | part | paid | overpaid
    payments: List[FeePaymentOut] = []
    due_on: Optional[date] = None
    instructions: Optional[str] = None


class FeeSummaryRow(BaseModel):
    contingent_id: int
    contingent_label: Optional[str] = None
    college_name: str
    total: float
    paid: float
    balance: float
    status: str


class FeeSummary(BaseModel):
    total: float = 0
    paid: float = 0
    balance: float = 0
    rows: List[FeeSummaryRow] = []


# ─── Finance ─────────────────────────────────────────────────────────────────────────────────────────────────────────
MAX_RECEIPTS = 5
EXPENSE_STATUSES = ("pending", "approved", "rejected", "paid", "cancelled")


def check_receipts(v):
    """Receipts are links to files uploaded through the finance receipt upload."""
    if v is None:
        return []
    if len(v) > MAX_RECEIPTS:
        raise ValueError(f"at most {MAX_RECEIPTS} receipts")
    for url in v:
        if not re.fullmatch(r"/api/media/[0-9a-f]{32}", url):
            raise ValueError("a receipt must be a file uploaded here")
    return v


class FinanceSettingsIn(BaseModel):
    auto_approve_below: Optional[Rupees] = None        # requests under this are approved on the spot; 0 means every request is decided by the committee
    receipt_required_above: Optional[Rupees] = None    # a request above this needs a receipt; null means never
    receipts_never_needed: Optional[bool] = None       # send true to switch receipts off


class FinanceSettingsOut(BaseModel):
    auto_approve_below: float = 0
    receipt_required_above: Optional[float] = None


class CategoryIn(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    kind: Literal["income", "expense"]


class CategoryUpdate(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


class CategoryOut(BaseModel):
    id: int
    name: str
    kind: str
    position: int = 0
    used: bool = False   # something is filed under it, so it cannot be deleted


class BudgetLineIn(BaseModel):
    category_id: int
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    planned: Rupees
    committee_team_id: Optional[int] = None
    notes: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]] = None


class BudgetLineUpdate(BaseModel):
    category_id: Optional[int] = None
    title: Optional[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]] = None
    planned: Optional[Rupees] = None
    committee_team_id: Optional[int] = None
    notes: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]] = None


class BudgetLineOut(BaseModel):
    id: int
    category_id: int
    category_name: str
    title: str
    planned: float
    committee_team_id: Optional[int] = None
    team_name: Optional[str] = None
    notes: Optional[str] = None
    pending: float = 0       # asked for, not decided yet
    committed: float = 0     # approved or paid
    paid: float = 0
    remaining: float = 0     # planned less committed (negative when over budget)
    over_budget: bool = False


class SpendOptions(BaseModel):
    """What anyone on the committee needs to file a spend request: the expense categories and the budget lines, with no amounts."""
    categories: List[CategoryOut] = []
    lines: List[Dict[str, object]] = []


class ExpenseIn(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    amount: float = Field(gt=0, le=10000000)
    spent_on: Optional[date] = None
    budget_line_id: Optional[int] = None
    category_id: Optional[int] = None   # needed when no budget line is chosen
    vendor: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)]] = None
    notes: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]] = None
    receipts: Optional[List[str]] = None
    paid_by_me: bool = False   # I paid it from my own pocket and need it back
    _check_receipts = field_validator("receipts")(check_receipts)

    @model_validator(mode="after")
    def where(self):
        if self.budget_line_id is None and self.category_id is None:
            raise ValueError("choose a budget line or a category")
        return self


class ExpenseUpdate(BaseModel):
    title: Optional[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]] = None
    amount: Optional[float] = Field(default=None, gt=0, le=10000000)
    spent_on: Optional[date] = None
    budget_line_id: Optional[int] = None
    category_id: Optional[int] = None
    vendor: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)]] = None
    notes: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]] = None
    receipts: Optional[List[str]] = None
    paid_by_me: Optional[bool] = None
    _check_receipts = field_validator("receipts")(check_receipts)


class ExpenseDecision(BaseModel):
    note: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)]] = None


class ExpenseReject(BaseModel):
    note: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=300)]


class ExpensePay(BaseModel):
    paid_on: Optional[date] = None
    note: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]] = None


class ExpenseOut(BaseModel):
    id: int
    title: str
    amount: float
    spent_on: date
    status: str
    budget_line_id: Optional[int] = None
    line_title: Optional[str] = None
    category_id: int
    category_name: str
    vendor: Optional[str] = None
    notes: Optional[str] = None
    receipts: List[str] = []
    requested_by_id: int
    requested_by_name: Optional[str] = None
    out_of_pocket_by: Optional[str] = None   # the member who paid and is owed it back
    decided_by_name: Optional[str] = None
    decided_at: Optional[datetime] = None
    decision_note: Optional[str] = None
    paid_on: Optional[date] = None
    paid_note: Optional[str] = None
    created_at: datetime
    auto_approved: bool = False


class IncomeIn(BaseModel):
    category_id: int
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    source: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)]] = None
    sponsor_id: Optional[int] = None
    expected: Rupees
    due_on: Optional[date] = None
    notes: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]] = None


class IncomeUpdate(BaseModel):
    category_id: Optional[int] = None
    title: Optional[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]] = None
    source: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)]] = None
    sponsor_id: Optional[int] = None
    expected: Optional[Rupees] = None
    due_on: Optional[date] = None
    notes: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]] = None


class IncomePaymentIn(BaseModel):
    amount: float = Field(gt=0, le=10000000)
    received_on: Optional[date] = None
    method: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)]] = None
    note: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]] = None


class IncomePaymentOut(BaseModel):
    id: int
    amount: float
    received_on: date
    method: Optional[str] = None
    note: Optional[str] = None


class IncomeOut(BaseModel):
    id: int
    category_id: int
    category_name: str
    title: str
    source: Optional[str] = None
    sponsor_id: Optional[int] = None
    sponsor_name: Optional[str] = None
    expected: float
    received: float
    outstanding: float
    status: str   # pledged | partial | received | overdue
    due_on: Optional[date] = None
    notes: Optional[str] = None
    payments: List[IncomePaymentOut] = []


class CategoryTotal(BaseModel):
    category_id: int
    name: str
    kind: str
    planned: float = 0      # expense categories: budgeted. income categories: expected
    committed: float = 0    # expense: approved or paid. income: received
    paid: float = 0


class TeamTotal(BaseModel):
    team_id: Optional[int] = None
    name: str
    planned: float = 0
    committed: float = 0
    paid: float = 0


class OwedToMember(BaseModel):
    member_id: int
    name: str
    amount: float
    expenses: int


class FinanceSummary(BaseModel):
    # Money coming in
    income_expected: float = 0
    income_received: float = 0
    registration_income: float = 0          # collected through HiveOut registrations for paid events
    college_fees_due: float = 0             # what visiting colleges owe in total
    college_fees_received: float = 0
    # Money going out
    budget_planned: float = 0
    pending: float = 0
    approved: float = 0                     # approved but not yet paid
    paid: float = 0
    committed: float = 0                    # approved + paid
    # Where it leaves the fest
    cash_in: float = 0
    cash_out: float = 0
    cash_position: float = 0                # received so far, less paid so far
    expected_income: float = 0              # everything expected to arrive
    projected_net: float = 0                # expected income less the larger of the budget and what is committed
    pending_requests: int = 0
    over_budget_lines: int = 0
    unbudgeted: float = 0                   # committed spending that is not under any budget line
    by_category: List[CategoryTotal] = []
    by_team: List[TeamTotal] = []
    owed_to_members: List[OwedToMember] = []


# ─── Ticketing: tiers, promo codes, quotes ───────────────────────────────────────────────────────────────────────────
class TierIn(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    description: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)]] = None
    price: Rupees = 0
    student_price: Optional[Rupees] = None
    quantity: Optional[int] = Field(default=None, ge=1, le=100000)
    sales_open_on: Optional[date] = None
    sales_close_on: Optional[date] = None
    active: bool = True

    @model_validator(mode="after")
    def sensible(self):
        if self.student_price is not None and self.student_price >= self.price:
            raise ValueError("the student price must be lower than the price")
        if self.sales_open_on and self.sales_close_on and self.sales_close_on < self.sales_open_on:
            raise ValueError("sales cannot close before they open")
        return self


class TierUpdate(BaseModel):
    name: Optional[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]] = None
    description: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)]] = None
    price: Optional[Rupees] = None
    student_price: Optional[Rupees] = None
    quantity: Optional[int] = Field(default=None, ge=1, le=100000)
    sales_open_on: Optional[date] = None
    sales_close_on: Optional[date] = None
    active: Optional[bool] = None


class TierOut(BaseModel):
    id: int
    event_id: int
    name: str
    description: Optional[str] = None
    price: float
    student_price: Optional[float] = None
    quantity: Optional[int] = None
    remaining: Optional[int] = None       # seats left; None when there is no limit
    sold: Optional[int] = None            # only shown to the committee
    sales_open_on: Optional[date] = None
    sales_close_on: Optional[date] = None
    active: bool = True
    status: str = "on_sale"               # on_sale | not_yet | ended | sold_out | off
    position: int = 0


class QuoteIn(BaseModel):
    ticket_tier_id: Optional[int] = None
    promo_code: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)]] = None


class QuoteOut(BaseModel):
    tier_id: Optional[int] = None
    tier_name: Optional[str] = None
    price: float            # before any code
    discount: float = 0
    total: float
    promo_description: Optional[str] = None
    free: bool = False


class PromoIn(BaseModel):
    code: Annotated[str, StringConstraints(strip_whitespace=True, to_upper=True, min_length=3, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")]
    description: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]] = None
    kind: Literal["percent", "flat"]
    value: float = Field(gt=0, le=10000000)   # a percentage for "percent" (1 to 100), rupees for "flat"
    event_ids: Optional[List[int]] = Field(default=None, max_length=100)   # none: every event of the fest
    max_uses: Optional[int] = Field(default=None, ge=1, le=1000000)
    per_user_limit: int = Field(default=1, ge=1, le=100)
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None
    students_only: bool = False
    active: bool = True

    @model_validator(mode="after")
    def sensible(self):
        if self.kind == "percent" and not (0 < self.value <= 100):
            raise ValueError("a percentage must be between 1 and 100")
        if self.valid_from and self.valid_until and self.valid_until < self.valid_from:
            raise ValueError("a code cannot expire before it starts")
        return self


class PromoUpdate(BaseModel):
    description: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]] = None
    value: Optional[float] = Field(default=None, gt=0, le=10000000)
    event_ids: Optional[List[int]] = Field(default=None, max_length=100)
    max_uses: Optional[int] = Field(default=None, ge=1, le=1000000)
    per_user_limit: Optional[int] = Field(default=None, ge=1, le=100)
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None
    students_only: Optional[bool] = None
    active: Optional[bool] = None


class PromoOut(BaseModel):
    id: int
    code: str
    description: Optional[str] = None
    kind: str
    value: float                      # percent, or rupees
    event_ids: Optional[List[int]] = None
    max_uses: Optional[int] = None
    per_user_limit: int = 1
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None
    students_only: bool = False
    active: bool = True
    used: int = 0
    discount_given: float = 0         # rupees taken off so far
    status: str = "live"              # live | not_yet | expired | used_up | off


# ─── Waitlist ────────────────────────────────────────────────────────────────────────────────────────────────────────
class WaitlistJoin(BaseModel):
    answers: List[AnswerIn] = []
    ticket_tier_id: Optional[int] = None
    promo_code: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)]] = None
    team_name: Optional[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]] = None   # for a team event: the team you will lead


class WaitlistMine(BaseModel):
    position: int
    status: str            # waiting | promoted | left | removed
    note: Optional[str] = None


class WaitlistStatus(BaseModel):
    enabled: bool = False
    full: bool = False
    waiting: int = 0
    limit: Optional[int] = None
    open: bool = False     # a seat can be queued for right now: it is full, there is a list, and it is not full too
    mine: Optional[WaitlistMine] = None


class WaitlistRow(BaseModel):
    id: int
    event_id: int
    event_title: str
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    position: Optional[int] = None   # place in the queue while waiting
    status: str
    team_name: Optional[str] = None
    ticket_tier_name: Optional[str] = None
    promo_code: Optional[str] = None
    note: Optional[str] = None
    created_at: datetime
    promoted_at: Optional[datetime] = None


# ─── Certificates ────────────────────────────────────────────────────────────────────────────────────────────────────
CERT_KINDS = ("participation", "winner", "appreciation")


class Signatory(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    title: Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)] = ""


class CertTemplateIn(BaseModel):
    event_id: Optional[int] = None   # none: usable for any event of the fest
    kind: Literal["participation", "winner", "appreciation"] = "participation"
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    body: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
    signatories: List[Signatory] = Field(default_factory=list, max_length=3)


class CertTemplateUpdate(BaseModel):
    title: Optional[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]] = None
    body: Optional[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]] = None
    kind: Optional[Literal["participation", "winner", "appreciation"]] = None
    event_id: Optional[int] = None
    signatories: Optional[List[Signatory]] = Field(default=None, max_length=3)


class CertTemplateOut(BaseModel):
    id: int
    event_id: Optional[int] = None
    event_title: Optional[str] = None
    kind: str
    title: str
    body: str
    signatories: List[Signatory] = []


class IssueAttendedIn(BaseModel):
    event_id: int
    template_id: int


class IssueEntriesIn(BaseModel):
    event_id: int
    template_id: int
    award_text: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)]] = None


class IssueOneIn(BaseModel):
    template_id: int
    recipient_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    event_id: Optional[int] = None
    email: Optional[EmailStr] = None   # their HiveOut account, so it appears on their page
    college_name: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]] = None
    award_text: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)]] = None


class IssueResult(BaseModel):
    issued: int
    skipped: int   # they already had one


class RevokeIn(BaseModel):
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=200)]


class CertificateOut(BaseModel):
    id: int
    code: str
    kind: str
    recipient_name: str
    college_name: Optional[str] = None
    award_text: Optional[str] = None
    title: str
    body: str
    signatories: List[Signatory] = []
    fest_name: str
    event_title: Optional[str] = None
    issued_at: datetime
    revoked: bool = False
    revoked_reason: Optional[str] = None
    has_account: bool = False


class CertificateCheck(BaseModel):
    """What anyone sees when they check a certificate's code."""
    valid: bool
    revoked: bool = False
    certificate: Optional[CertificateOut] = None
