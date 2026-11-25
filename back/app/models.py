from sqlalchemy import JSON, Date, LargeBinary, Column, Integer, String, Boolean, Float, DateTime, ForeignKey, Text, Enum, CheckConstraint, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum

class RoleEnum(str, enum.Enum):
    user = "user"
    organizer = "organizer"
    admin = "admin"

class StatusEnum(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"

class FestStatusEnum(str, enum.Enum):
    draft = "draft"
    live  = "live"

class FestMemberRoleEnum(str, enum.Enum):
    owner     = "owner"
    core      = "core"
    volunteer = "volunteer"

class EventTypeEnum(str, enum.Enum):
    fest = "fest"   # belongs to a College Fest (managed by FestMember committee)
    city = "city"   # standalone City Event    (managed by a single organizer)

class ApprovalModeEnum(str, enum.Enum):
    auto   = "auto"
    manual = "manual"

class FestPassStatusEnum(str, enum.Enum):
    approved = "approved"
    blocked  = "blocked"

class RegApprovalStatusEnum(str, enum.Enum):
    pending  = "pending"
    approved = "approved"
    rejected = "rejected"

class RegPaymentStatusEnum(str, enum.Enum):
    unpaid = "unpaid"
    paid   = "paid"

class VerificationMethodEnum(str, enum.Enum):
    email = "email"
    proof = "proof"

class VerificationStatusEnum(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"

class AuthProviderEnum(str, enum.Enum):
    google = "google"
    phone = "phone"
    email = "email"

class User(Base):
    __tablename__ = "users"
    id               = Column(Integer, primary_key=True, index=True)
    name             = Column(String(255), nullable=False)   # first and last name together, shown everywhere
    date_of_birth    = Column(Date, nullable=True)
    first_name       = Column(String(120), nullable=True)
    last_name        = Column(String(120), nullable=True)
    email            = Column(String(255), unique=True, nullable=True)
    phone            = Column(String(20), unique=True, nullable=True)
    hashed_password  = Column(String(255), nullable=True)
    role             = Column(Enum(RoleEnum), default=RoleEnum.user)
    auth_provider    = Column(Enum(AuthProviderEnum), default=AuthProviderEnum.email)
    is_active        = Column(Boolean, default=True)
    interests_set    = Column(Boolean, default=False)
    college_id       = Column(Integer, ForeignKey("colleges.id", name="fk_users_college_id"), nullable=True)
    study_year       = Column(Integer, nullable=True)
    student_verified_until = Column(DateTime, nullable=True)  # a verification lasts one year
    # Set when an admin makes the account an organiser; cleared once the person has seen the welcome screen
    organizer_welcome_pending = Column(Boolean, nullable=False, default=False, server_default="0")
    # What an organiser may do. Set per person by an admin; being an organiser alone grants neither
    can_host_fests       = Column(Boolean, nullable=False, default=False, server_default="0")
    can_host_city_events = Column(Boolean, nullable=False, default=False, server_default="0")
    google_sub      = Column(String(255), unique=True, nullable=True)   # the Google account linked to this one, if any
    terms_accepted_at = Column(DateTime, nullable=True)
    created_at       = Column(DateTime(timezone=True), server_default=func.now())

    interests         = relationship("UserInterest", back_populates="user")
    events            = relationship("Event", back_populates="organizer")
    passes            = relationship("Pass", back_populates="user")
    fest_memberships  = relationship("FestMember", back_populates="user")
    fest_passes       = relationship("FestPass", back_populates="user", foreign_keys="FestPass.user_id")

    organizer_colleges = relationship("OrganizerCollege", cascade="all, delete-orphan")

    @property
    def has_password(self):
        return bool(self.hashed_password)

    @property
    def google_linked(self):
        return bool(self.google_sub)

    @property
    def profile_complete(self):
        return self.date_of_birth is not None and self.terms_accepted_at is not None

    @property
    def college_ids(self):
        return sorted(oc.college_id for oc in self.organizer_colleges)

    @property
    def is_student_verified(self):
        from datetime import datetime
        return bool(self.student_verified_until and self.student_verified_until > datetime.utcnow())

class Interest(Base):
    __tablename__ = "interests"
    id   = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)

    users = relationship("UserInterest", back_populates="interest")

class UserInterest(Base):
    __tablename__ = "user_interests"
    id          = Column(Integer, primary_key=True, index=True)
    user_id     = Column(Integer, ForeignKey("users.id"))
    interest_id = Column(Integer, ForeignKey("interests.id"))

    user     = relationship("User", back_populates="interests")
    interest = relationship("Interest", back_populates="users")

class Event(Base):
    __tablename__ = "events"
    # ── Branch discriminator ────────────────────────────────────────────────
    # "fest" → belongs to a College Fest; fest_id required, organizer_id NULL
    # "city" → standalone City Event;    organizer_id required, fest_id NULL
    # ────────────────────────────────────────────────────────────────────────
    __table_args__ = (
        CheckConstraint("event_type IN ('fest', 'city')", name="ck_event_type_values"),
        Index("ix_events_event_type", "event_type"),
    )

    id           = Column(Integer, primary_key=True, index=True)
    event_type   = Column(Enum(EventTypeEnum), nullable=False)
    title        = Column(String(255), nullable=False)
    description  = Column(Text, nullable=True)
    location     = Column(String(255), nullable=True)
    date         = Column(DateTime, nullable=False)
    time         = Column(String(50), nullable=True)
    image_url    = Column(String(500), nullable=True)
    category     = Column(String(100), nullable=True)
    price        = Column(Float, default=0.0)
    is_free      = Column(Boolean, default=True)
    status       = Column(Enum(StatusEnum), default=StatusEnum.pending)
    organizer_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # NULL for fest events
    college_id   = Column(Integer, ForeignKey("colleges.id"), nullable=True)
    fest_id      = Column(Integer, ForeignKey("fests.id"), nullable=True)  # NULL for city events
    created_at   = Column(DateTime(timezone=True), server_default=func.now())

    # ── Fest-event registration fields (ignored when event_type='city') ──────
    requires_registration = Column(Boolean, default=False)
    is_paid               = Column(Boolean, default=False)
    registration_limit    = Column(Integer, nullable=True)   # None = unlimited
    approval_mode         = Column(Enum(ApprovalModeEnum), default=ApprovalModeEnum.auto)
    end_time              = Column(String(50), nullable=True)
    extra_sections        = Column(JSON, nullable=True)   # [{"title": "Rules", "body": "..."}]
    students_only         = Column(Boolean, default=False, nullable=False, server_default="0")
    student_price         = Column(Float, nullable=True)     # cheaper price for verified students; None = same price
    # Team events: people register as a team. The leader creates it and shares a code; the seat limit then counts teams.
    is_team_event         = Column(Boolean, default=False, nullable=False, server_default="0")
    team_min              = Column(Integer, nullable=True)
    team_max              = Column(Integer, nullable=True)
    # An event can run over several days of the fest (an exhibition, a long competition): it starts on `date` and repeats daily at the same times
    span_days             = Column(Integer, nullable=False, default=1, server_default="1")
    coordinator_name      = Column(String(120), nullable=True)   # the student who runs this event
    coordinator_phone     = Column(String(30), nullable=True)
    registration_deadline = Column(Date, nullable=True)          # the last day people can register
    # When registration opens: "open_now" (instant), "scheduled" (on registration_opens_on), "not_set" (organisers have not decided) or "closed" (shut by hand)
    registration_mode     = Column(String(12), nullable=False, default="open_now", server_default="open_now")
    registration_opens_on = Column(Date, nullable=True)
    # Points a contingent earns for placing in this event, by place: {"1": 100, "2": 60, "3": 30}. None means it is not a scored competition.
    # Visiting colleges entering this event: whether they can, how many entries each may send, what an entry costs, and until when
    contingent_entries     = Column(Boolean, nullable=False, default=False, server_default="0")
    entries_per_contingent = Column(Integer, nullable=False, default=1, server_default="1")
    entry_fee_paise        = Column(Integer, nullable=False, default=0, server_default="0")
    entry_fee_per          = Column(String(12), nullable=False, default="entry", server_default="entry")   # entry | participant
    entry_deadline         = Column(Date, nullable=True)
    # When an event is full, people can queue for a seat that opens up
    waitlist_enabled       = Column(Boolean, nullable=False, default=False, server_default="0")
    price_is_from          = Column(Boolean, nullable=False, default=False, server_default="0")  # tickets differ in price, so show "From"
    waitlist_limit         = Column(Integer, nullable=True)   # longest the queue may get; None for no limit
    points_scheme         = Column(JSON(none_as_null=True), nullable=True)   # real NULL when not scored, so it can be filtered on

    # A cancelled event stays visible (so registered students see why) but cannot be registered for
    cancelled_at  = Column(DateTime, nullable=True)
    cancel_reason = Column(String(500), nullable=True)
    # Why an admin turned down a city event, shown to its organiser
    reject_reason = Column(String(500), nullable=True)

    organizer  = relationship("User", back_populates="events")
    college    = relationship("College", back_populates="events")
    fest       = relationship("Fest", back_populates="events")
    passes     = relationship("Pass", back_populates="event")
    committees = relationship("Committee", back_populates="event")
    registrations = relationship("EventRegistration", back_populates="event")
    questions     = relationship("EventQuestion", back_populates="event", cascade="all, delete-orphan", order_by="EventQuestion.position")

    @property
    def cancelled(self):
        return self.cancelled_at is not None

    @property
    def entry_fee(self):
        return round((self.entry_fee_paise or 0) / 100, 2)

    @property
    def registration_state(self):
        """None when nobody registers; otherwise "open", "scheduled" (opens on a known day), "not_open" (no date yet) or "closed"."""
        if not self.requires_registration:
            return None
        from datetime import date as _date
        today = _date.today()
        mode = self.registration_mode or "open_now"
        if mode == "closed" or (self.registration_deadline and today > self.registration_deadline):
            return "closed"
        if mode == "open_now":
            return "open"
        if mode == "scheduled" and self.registration_opens_on:
            return "open" if today >= self.registration_opens_on else "scheduled"
        return "not_open"

    @property
    def college_name(self):
        return self.college.name if self.college else None

    @property
    def fest_slug(self):
        return self.fest.slug if self.fest else None

    @property
    def fest_name(self):
        return self.fest.name if self.fest else None

class AuthSession(Base):
    """One sign-in. The JWT carries this row's id, so a session can be ended on the server and can time out."""
    __tablename__ = "auth_sessions"
    id           = Column(String(36), primary_key=True)
    user_id      = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at   = Column(DateTime, nullable=False)
    last_seen_at = Column(DateTime, nullable=False)
    expires_at   = Column(DateTime, nullable=False)
    revoked_at   = Column(DateTime, nullable=True)
    ip           = Column(String(64), nullable=True)
    user_agent   = Column(String(200), nullable=True)

class ShortLink(Base):
    """A custom short address (hiveout.in/name) for one fest or event. One table, so a name can only ever be held by one thing."""
    __tablename__ = "short_links"
    __table_args__ = (UniqueConstraint("target_type", "target_id", name="uq_short_link_target"),)
    id         = Column(Integer, primary_key=True, index=True)
    name       = Column(String(40), unique=True, nullable=False, index=True)
    target_type = Column(String(10), nullable=False)   # fest | event
    target_id  = Column(Integer, nullable=False)
    created_by = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False)

class PasswordReset(Base):
    """A one-time link to choose a new password. Only a hash of the token is kept, so the table cannot be used to reset anyone."""
    __tablename__ = "password_resets"
    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), unique=True, nullable=False)
    created_at = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used_at    = Column(DateTime, nullable=True)
    ip         = Column(String(64), nullable=True)

class AuthEvent(Base):
    """One sign-in attempt, successful or not. Admins can review these in the security log."""
    __tablename__ = "auth_events"
    id      = Column(Integer, primary_key=True, index=True)
    at      = Column(DateTime, nullable=False, index=True)
    portal  = Column(String(10), nullable=False)   # public | admin
    email   = Column(String(255), nullable=True)
    user_id = Column(Integer, nullable=True)
    ip      = Column(String(64), nullable=True)
    success = Column(Boolean, nullable=False)
    reason  = Column(String(60), nullable=False)   # ok, bad_credentials, not_admin, locked, disabled, admin_on_public_page

class Pass(Base):
    __tablename__ = "passes"
    id             = Column(Integer, primary_key=True, index=True)
    user_id        = Column(Integer, ForeignKey("users.id"))
    event_id       = Column(Integer, ForeignKey("events.id"))
    pass_code      = Column(String(100), unique=True, nullable=False)
    payment_status = Column(String(50), default="free")
    created_at     = Column(DateTime(timezone=True), server_default=func.now())

    user  = relationship("User", back_populates="passes")
    event = relationship("Event", back_populates="passes")

class Committee(Base):
    __tablename__ = "committees"
    id       = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"))
    name     = Column(String(255), nullable=False)

    event       = relationship("Event", back_populates="committees")
    departments = relationship("Department", back_populates="committee")

class College(Base):
    __tablename__ = "colleges"
    id      = Column(Integer, primary_key=True, index=True)
    name    = Column(String(255), unique=True, nullable=False)
    area    = Column(String(255), nullable=True)
    emoji   = Column(String(20), nullable=True, default="🏛️")
    website = Column(String(500), nullable=True)
    email_domains = Column(String(500), nullable=True)  # comma-separated, e.g. "iitb.ac.in"; students with these emails verify automatically

    # Partnership: filled in by an admin after meeting the college. Only partner colleges can list fests.
    partner_status    = Column(String(20), nullable=False, default="prospect", server_default="prospect")  # prospect | partner
    coordinator_name  = Column(String(255), nullable=True)
    coordinator_phone = Column(String(30), nullable=True)
    coordinator_email = Column(String(255), nullable=True)
    partner_since     = Column(Date, nullable=True)
    partner_notes     = Column(Text, nullable=True)

    events = relationship("Event", back_populates="college")
    fests  = relationship("Fest", back_populates="college")

    @property
    def event_count(self):
        return len([e for e in self.events if e.status == "approved"])

class Fest(Base):
    __tablename__ = "fests"
    id         = Column(Integer, primary_key=True, index=True)
    slug       = Column(String(100), unique=True, nullable=False, index=True)
    name       = Column(String(255), nullable=False)
    tagline    = Column(String(500), nullable=True)
    banner_url = Column(String(500), nullable=True)
    logo_url   = Column(String(500), nullable=True)
    college_id = Column(Integer, ForeignKey("colleges.id"), nullable=True)
    status     = Column(Enum(FestStatusEnum), default=FestStatusEnum.draft)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    description    = Column(Text, nullable=True)
    start_date     = Column(Date, nullable=True)
    end_date       = Column(Date, nullable=True)
    campus_address = Column(String(500), nullable=True)
    map_url        = Column(String(500), nullable=True)
    instagram_url  = Column(String(500), nullable=True)
    website_url    = Column(String(500), nullable=True)
    extra_sections = Column(JSON, nullable=True)   # [{"title": "...", "body": "..."}]
    # Private: for the admin who reviews the fest
    contact_name   = Column(String(255), nullable=True)
    contact_email  = Column(String(255), nullable=True)
    contact_phone  = Column(String(30), nullable=True)
    faculty_name   = Column(String(255), nullable=True)
    faculty_phone  = Column(String(30), nullable=True)
    faculty_email  = Column(String(255), nullable=True)
    # Review: draft -> in_review -> approved (or changes_requested / rejected). Only approved fests can go live.
    review_status  = Column(String(20), nullable=False, default="draft", server_default="draft")
    review_note    = Column(String(1000), nullable=True)
    # What the admin flagged, by field: [{"key": "banner", "note": "Too blurry"}]. Cleared when the fest is submitted again
    review_fields  = Column(JSON, nullable=True)
    # True when the committee has not fixed its dates yet: the fest is listed as "Dates coming soon" and needs no events
    dates_tba      = Column(Boolean, nullable=False, default=False, server_default="0")
    submitted_at   = Column(DateTime, nullable=True)
    reviewed_by    = Column(Integer, ForeignKey("users.id", name="fk_fests_reviewed_by"), nullable=True)
    reviewed_at    = Column(DateTime, nullable=True)

    college      = relationship("College", back_populates="fests")
    events       = relationship("Event", back_populates="fest")
    members      = relationship("FestMember", back_populates="fest", cascade="all, delete-orphan")
    entry_passes = relationship("FestPass", back_populates="fest")

    @property
    def event_count(self):
        return len([e for e in self.events if e.status == "approved"])

    @property
    def days_count(self):
        """How many days the fest runs, worked out from its dates. Nobody types it in; it is None until both dates are set."""
        if self.start_date and self.end_date and self.end_date >= self.start_date:
            return (self.end_date - self.start_date).days + 1
        return None


class CommitteeTeam(Base):
    """A function inside a fest's committee, such as Sponsorship, PR or Logistics. Each fest names its own."""
    __tablename__ = "committee_teams"
    __table_args__ = (UniqueConstraint("fest_id", "name", name="uq_committee_teams_fest_name"),)

    id          = Column(Integer, primary_key=True, index=True)
    fest_id     = Column(Integer, ForeignKey("fests.id"), nullable=False, index=True)
    name        = Column(String(80), nullable=False)
    description = Column(String(300), nullable=True)
    # Whether the team's head and co-heads may place people in their team and run its tasks, even without Core team access
    leaders_manage_team = Column(Boolean, nullable=False, default=True, server_default="1")
    created_at  = Column(DateTime(timezone=True), server_default=func.now())


class FestMember(Base):
    """Maps users to fests with a role (owner / core / volunteer)."""
    __tablename__ = "fest_members"
    __table_args__ = (
        # A user can only appear once per fest; prevents duplicate membership rows
        UniqueConstraint("fest_id", "user_id", name="uq_fest_members_fest_user"),
    )

    id         = Column(Integer, primary_key=True, index=True)
    fest_id    = Column(Integer, ForeignKey("fests.id"), nullable=False)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False)
    role       = Column(Enum(FestMemberRoleEnum), default=FestMemberRoleEnum.volunteer)   # the access level: owner / core / volunteer
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Where this person sits in the committee. The access level above stays three simple tiers; these are the fest's own words
    title             = Column(String(80), nullable=True)   # for example "Sponsorship Head" or "Event Coordinator, Dance"
    committee_team_id = Column(Integer, ForeignKey("committee_teams.id", name="fk_fest_members_team"), nullable=True)
    reports_to_id     = Column(Integer, ForeignKey("fest_members.id", name="fk_fest_members_reports_to"), nullable=True)
    # Their position inside the team: "head", "co_head" or "member". Only means something while committee_team_id is set
    team_role         = Column(String(10), nullable=False, default="member", server_default="member")

    fest = relationship("Fest", back_populates="members")
    user = relationship("User", back_populates="fest_memberships")
    committee_team = relationship("CommitteeTeam")
    reports_to = relationship("FestMember", remote_side="FestMember.id")

    @property
    def user_name(self):
        return self.user.name if self.user else None

    @property
    def user_email(self):
        return self.user.email if self.user else None

    @property
    def team_name(self):
        return self.committee_team.name if self.committee_team else None

    @property
    def reports_to_name(self):
        return self.reports_to.user_name if self.reports_to else None


class FestMeeting(Base):
    """A committee meeting: when and where, the agenda, who was invited, what was decided, and the follow-ups it produced."""
    __tablename__ = "fest_meetings"
    id            = Column(Integer, primary_key=True, index=True)
    fest_id       = Column(Integer, ForeignKey("fests.id"), nullable=False, index=True)
    title         = Column(String(200), nullable=False)
    starts_at     = Column(DateTime, nullable=False)   # a wall-clock time, like event times
    location      = Column(String(255), nullable=True)
    agenda        = Column(Text, nullable=True)
    minutes       = Column(Text, nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id", name="fk_fest_meetings_creator"), nullable=True)
    created_at    = Column(DateTime, nullable=False, server_default=func.now())

    attendees  = relationship("FestMeetingAttendee", cascade="all, delete-orphan")
    created_by = relationship("User", foreign_keys=[created_by_id])

    @property
    def created_by_name(self):
        return self.created_by.name if self.created_by else None

    @property
    def invited_count(self):
        return len(self.attendees)

    @property
    def attended_count(self):
        return len([a for a in self.attendees if a.attended])


class FestMeetingAttendee(Base):
    """Someone invited to a meeting, and whether they came."""
    __tablename__ = "fest_meeting_attendees"
    meeting_id = Column(Integer, ForeignKey("fest_meetings.id"), primary_key=True)
    member_id  = Column(Integer, ForeignKey("fest_members.id"), primary_key=True)
    attended   = Column(Boolean, nullable=False, default=False, server_default="0")

    member = relationship("FestMember")

    @property
    def user_name(self):
        return self.member.user_name if self.member else None

    @property
    def title(self):
        return self.member.title if self.member else None


class FestTask(Base):
    """A piece of work for the committee: who does what by when. Optionally tied to a team."""
    __tablename__ = "fest_tasks"
    id                 = Column(Integer, primary_key=True, index=True)
    fest_id            = Column(Integer, ForeignKey("fests.id"), nullable=False, index=True)
    title              = Column(String(200), nullable=False)
    description        = Column(Text, nullable=True)
    status             = Column(String(10), nullable=False, default="todo", server_default="todo")   # todo | doing | done
    due_date           = Column(Date, nullable=True)
    assignee_member_id = Column(Integer, ForeignKey("fest_members.id", name="fk_fest_tasks_assignee"), nullable=True)
    committee_team_id  = Column(Integer, ForeignKey("committee_teams.id", name="fk_fest_tasks_team"), nullable=True)
    meeting_id         = Column(Integer, ForeignKey("fest_meetings.id", name="fk_fest_tasks_meeting"), nullable=True)   # the meeting it came out of
    created_by_id      = Column(Integer, ForeignKey("users.id", name="fk_fest_tasks_creator"), nullable=True)
    created_at         = Column(DateTime, nullable=False, server_default=func.now())
    completed_at       = Column(DateTime, nullable=True)

    meeting        = relationship("FestMeeting", foreign_keys=[meeting_id])
    assignee       = relationship("FestMember", foreign_keys=[assignee_member_id])
    committee_team = relationship("CommitteeTeam")
    created_by     = relationship("User", foreign_keys=[created_by_id])

    @property
    def assignee_name(self):
        return self.assignee.user_name if self.assignee else None

    @property
    def team_name(self):
        return self.committee_team.name if self.committee_team else None

    @property
    def created_by_name(self):
        return self.created_by.name if self.created_by else None

    @property
    def meeting_title(self):
        return self.meeting.title if self.meeting else None

    @property
    def overdue(self):
        from datetime import date
        return bool(self.due_date and self.status != "done" and self.due_date < date.today())


class ContingentSettings(Base):
    """How a fest runs its visiting colleges. Every fest names the thing and sets the rules itself."""
    __tablename__ = "contingent_settings"
    fest_id        = Column(Integer, ForeignKey("fests.id"), primary_key=True)
    enabled        = Column(Boolean, nullable=False, default=False, server_default="0")
    # The fest's own words for things (one fest says "contingent", another "delegation")
    term           = Column(String(40), nullable=False, default="Contingent", server_default="Contingent")
    leader_term    = Column(String(60), nullable=False, default="Contingent Leader", server_default="Contingent Leader")
    assistant_term = Column(String(60), nullable=False, default="Assistant Contingent Leader", server_default="Assistant Contingent Leader")
    max_assistants = Column(Integer, nullable=False, default=2, server_default="2")
    min_members    = Column(Integer, nullable=False, default=1, server_default="1")
    max_members    = Column(Integer, nullable=True)
    allow_multiple_per_college = Column(Boolean, nullable=False, default=False, server_default="0")
    requires_approval          = Column(Boolean, nullable=False, default=True, server_default="1")
    opens_on       = Column(Date, nullable=True)
    closes_on      = Column(Date, nullable=True)
    lock_roster_after_close    = Column(Boolean, nullable=False, default=True, server_default="1")
    # What a visiting college pays. Every number is the fest's own; zero means free
    registration_fee_paise = Column(Integer, nullable=False, default=0, server_default="0")   # once per contingent
    fee_per_member_paise   = Column(Integer, nullable=False, default=0, server_default="0")   # for each person on its list
    fee_instructions       = Column(String(1000), nullable=True)   # how to pay: bank details, a UPI id...
    fees_due_on            = Column(Date, nullable=True)
    # Whether visiting colleges can ask for a place to stay, and until when
    accommodation_enabled      = Column(Boolean, nullable=False, default=False, server_default="0")
    accommodation_closes_on    = Column(Date, nullable=True)


class Contingent(Base):
    """A visiting college's team at a fest, led by one person and optionally helped by assistants."""
    __tablename__ = "contingents"
    __table_args__ = (
        UniqueConstraint("fest_id", "code", name="uq_contingents_fest_code"),
        UniqueConstraint("fest_id", "name", name="uq_contingents_fest_name"),
    )
    id             = Column(Integer, primary_key=True, index=True)
    fest_id        = Column(Integer, ForeignKey("fests.id"), nullable=False, index=True)
    college_name   = Column(String(200), nullable=False)
    college_id     = Column(Integer, ForeignKey("colleges.id", name="fk_contingents_college"), nullable=True)
    code           = Column(String(30), nullable=True)    # set by the committee
    name           = Column(String(120), nullable=True)   # the contingent's name for this fest, set by the committee (or won at a name meet)
    status         = Column(String(12), nullable=False, default="pending", server_default="pending")   # pending | approved | rejected | withdrawn
    note           = Column(String(500), nullable=True)   # the committee's note with its decision
    leader_user_id = Column(Integer, ForeignKey("users.id", name="fk_contingents_leader"), nullable=False, index=True)
    created_at     = Column(DateTime, nullable=False, server_default=func.now())
    decided_at     = Column(DateTime, nullable=True)

    leader     = relationship("User", foreign_keys=[leader_user_id])
    assistants = relationship("ContingentAssistant", cascade="all, delete-orphan")
    members    = relationship("ContingentMember", cascade="all, delete-orphan", order_by="ContingentMember.id")

    @property
    def leader_name(self):
        return self.leader.name if self.leader else None

    @property
    def leader_email(self):
        return self.leader.email if self.leader else None

    @property
    def assistant_count(self):
        return len(self.assistants)

    @property
    def member_count(self):
        return len(self.members)


class ContingentAssistant(Base):
    """Someone who helps the leader run the contingent: they can manage the roster."""
    __tablename__ = "contingent_assistants"
    contingent_id = Column(Integer, ForeignKey("contingents.id"), primary_key=True)
    user_id       = Column(Integer, ForeignKey("users.id"), primary_key=True)
    added_at      = Column(DateTime, nullable=False, server_default=func.now())

    user = relationship("User")

    @property
    def user_name(self):
        return self.user.name if self.user else None

    @property
    def user_email(self):
        return self.user.email if self.user else None


class ContingentMember(Base):
    """A person in a contingent's delegation. They do not need a HiveOut account."""
    __tablename__ = "contingent_members"
    id            = Column(Integer, primary_key=True, index=True)
    contingent_id = Column(Integer, ForeignKey("contingents.id"), nullable=False, index=True)
    name          = Column(String(120), nullable=False)
    email         = Column(String(255), nullable=True)
    phone         = Column(String(30), nullable=True)
    year          = Column(Integer, nullable=True)
    notes         = Column(String(300), nullable=True)
    created_at    = Column(DateTime, nullable=False, server_default=func.now())


class FestPass(Base):
    """Entry pass granting a user access to a Fest."""
    __tablename__ = "fest_passes"
    __table_args__ = (
        UniqueConstraint("user_id", "fest_id", name="uq_fest_pass_user_fest"),
    )

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False)
    fest_id    = Column(Integer, ForeignKey("fests.id"), nullable=False)
    status     = Column(Enum(FestPassStatusEnum), default=FestPassStatusEnum.approved)
    qr_code    = Column(String(100), unique=True, nullable=False)
    checked_in = Column(Boolean, default=False)
    checked_in_at = Column(DateTime, nullable=True)
    checked_in_by = Column(Integer, ForeignKey("users.id", name="fk_fest_passes_checked_in_by"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user          = relationship("User", back_populates="fest_passes", foreign_keys=[user_id])
    fest          = relationship("Fest", back_populates="entry_passes")
    registrations = relationship("EventRegistration", back_populates="fest_pass")

    @property
    def fest_slug(self):
        return self.fest.slug if self.fest else None

    @property
    def fest_name(self):
        return self.fest.name if self.fest else None


class EventRegistration(Base):
    """A FestPass holder registering for a specific fest event."""
    __tablename__ = "event_registrations"
    __table_args__ = (
        UniqueConstraint("fest_pass_id", "event_id", name="uq_event_reg_pass_event"),
    )

    id              = Column(Integer, primary_key=True, index=True)
    fest_pass_id    = Column(Integer, ForeignKey("fest_passes.id"), nullable=False)
    event_id        = Column(Integer, ForeignKey("events.id"), nullable=False)
    approval_status = Column(Enum(RegApprovalStatusEnum), default=RegApprovalStatusEnum.pending)
    payment_status  = Column(Enum(RegPaymentStatusEnum), default=RegPaymentStatusEnum.unpaid)
    amount_due      = Column(Float, nullable=True)   # what this student owes, after student pricing
    team_id         = Column(Integer, ForeignKey("teams.id", name="fk_event_registrations_team_id"), nullable=True, index=True)
    ticket_tier_id  = Column(Integer, ForeignKey("ticket_tiers.id", name="fk_registration_tier"), nullable=True, index=True)
    promo_code_id   = Column(Integer, ForeignKey("promo_codes.id", name="fk_registration_promo"), nullable=True, index=True)
    discount_paise  = Column(Integer, nullable=False, default=0, server_default="0")   # what a promo code took off the price
    hold_expires_at = Column(DateTime, nullable=True)   # a registration waiting for online payment keeps its seat until then
    attended        = Column(Boolean, default=False, nullable=False, server_default="0")
    attended_at     = Column(DateTime, nullable=True)
    attended_by     = Column(Integer, ForeignKey("users.id", name="fk_event_registrations_attended_by"), nullable=True)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())

    fest_pass = relationship("FestPass", back_populates="registrations")
    event     = relationship("Event", back_populates="registrations")
    answers   = relationship("RegistrationAnswer", back_populates="registration", cascade="all, delete-orphan")
    team      = relationship("Team", back_populates="registrations")

    tier       = relationship("TicketTier")
    promo      = relationship("PromoCode")

    @property
    def discount(self):
        return round((self.discount_paise or 0) / 100, 2)

    @property
    def awaiting_payment(self):
        """Registered, but the money has not arrived yet."""
        return self.payment_status == RegPaymentStatusEnum.unpaid and (self.amount_due or 0) > 0

    @property
    def tier_name(self):
        return self.tier.name if self.tier else None

    @property
    def promo_code_text(self):
        return self.promo.code if self.promo else None

    @property
    def team_name(self):
        return self.team.name if self.team else None

    @property
    def is_team_leader(self):
        return bool(self.team and self.fest_pass and self.team.leader_user_id == self.fest_pass.user_id)

    @property
    def user_name(self):
        return self.fest_pass.user.name if self.fest_pass and self.fest_pass.user else None

    @property
    def user_email(self):
        return self.fest_pass.user.email if self.fest_pass and self.fest_pass.user else None

    @property
    def checked_in(self):
        return bool(self.fest_pass and self.fest_pass.checked_in)


class Team(Base):
    """A group registering together for a team event. Each member still has their own registration."""
    __tablename__ = "teams"
    __table_args__ = (UniqueConstraint("event_id", "name", name="uq_teams_event_name"),)
    id             = Column(Integer, primary_key=True, index=True)
    event_id       = Column(Integer, ForeignKey("events.id"), nullable=False, index=True)
    name           = Column(String(80), nullable=False)
    code           = Column(String(12), unique=True, nullable=False, index=True)   # shared by the leader so others can join
    leader_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at     = Column(DateTime, nullable=False)

    event         = relationship("Event")
    registrations = relationship("EventRegistration", back_populates="team")


class FestTransfer(Base):
    """A fest's director handing the fest to another organiser. It only happens once the other person accepts."""
    __tablename__ = "fest_transfers"
    id                  = Column(Integer, primary_key=True, index=True)
    fest_id             = Column(Integer, ForeignKey("fests.id"), nullable=False, index=True)
    from_user_id        = Column(Integer, ForeignKey("users.id"), nullable=False)
    to_user_id          = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    status              = Column(String(12), nullable=False, default="pending")   # pending | accepted | declined | cancelled
    keep_previous_owner = Column(Boolean, nullable=False, default=True)            # the old director stays on as core team
    created_at          = Column(DateTime, nullable=False)
    decided_at          = Column(DateTime, nullable=True)

    fest      = relationship("Fest")
    from_user = relationship("User", foreign_keys=[from_user_id])
    to_user   = relationship("User", foreign_keys=[to_user_id])


class FestInvite(Base):
    """An offer to join a fest's committee. The person joins only after they accept it."""
    __tablename__ = "fest_invites"
    id            = Column(Integer, primary_key=True, index=True)
    fest_id       = Column(Integer, ForeignKey("fests.id"), nullable=False, index=True)
    user_id       = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    invited_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role          = Column(String(12), nullable=False, default="volunteer")
    # Where they will sit once they accept
    committee_team_id = Column(Integer, ForeignKey("committee_teams.id", name="fk_fest_invites_team"), nullable=True)
    team_role     = Column(String(10), nullable=False, default="member", server_default="member")
    title         = Column(String(80), nullable=True)   # for example "Vice Chairperson"
    status        = Column(String(12), nullable=False, default="pending")   # pending | accepted | declined | cancelled
    created_at    = Column(DateTime, nullable=False)
    decided_at    = Column(DateTime, nullable=True)

    fest    = relationship("Fest")
    user    = relationship("User", foreign_keys=[user_id])
    inviter = relationship("User", foreign_keys=[invited_by_id])
    committee_team = relationship("CommitteeTeam")


class AccountNotice(Base):
    """A message about the person's own account, shown from the bell icon. Not an email, though an email may also be sent."""
    __tablename__ = "account_notices"
    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    kind       = Column(String(30), nullable=False)   # fest_invite | fest_invite_answer
    title      = Column(String(120), nullable=False)
    body       = Column(String(500), nullable=False)
    invite_id  = Column(Integer, ForeignKey("fest_invites.id"), nullable=True)
    created_at = Column(DateTime, nullable=False)
    read_at    = Column(DateTime, nullable=True)

    invite = relationship("FestInvite")


class Department(Base):
    __tablename__ = "departments"
    id           = Column(Integer, primary_key=True, index=True)
    committee_id = Column(Integer, ForeignKey("committees.id"))
    name         = Column(String(255), nullable=False)

    committee = relationship("Committee", back_populates="departments")
    members   = relationship("DepartmentMember", back_populates="department")

class DepartmentMember(Base):
    __tablename__ = "department_members"
    id            = Column(Integer, primary_key=True, index=True)
    department_id = Column(Integer, ForeignKey("departments.id"))
    user_id       = Column(Integer, ForeignKey("users.id"))
    role          = Column(String(50), default="member")

    department = relationship("Department", back_populates="members")

class StudentVerification(Base):
    """One attempt to prove someone is a student, by college email code or by an uploaded document."""
    __tablename__ = "student_verifications"
    id            = Column(Integer, primary_key=True, index=True)
    user_id       = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    method        = Column(Enum(VerificationMethodEnum), nullable=False)
    status        = Column(Enum(VerificationStatusEnum), default=VerificationStatusEnum.pending, nullable=False)
    college_id    = Column(Integer, ForeignKey("colleges.id"), nullable=True)
    email         = Column(String(255), nullable=True)            # email method
    code_hash     = Column(String(128), nullable=True)
    code_expires_at = Column(DateTime, nullable=True)
    attempts      = Column(Integer, default=0, nullable=False, server_default="0")
    document_type = Column(String(30), nullable=True)             # proof method: id_card, fee_receipt, enrollment_form, other
    document_name = Column(String(255), nullable=True)
    document_mime = Column(String(100), nullable=True)
    document_data = Column(LargeBinary, nullable=True)            # deleted as soon as a decision is made
    reject_reason = Column(String(500), nullable=True)
    reviewed_by   = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at   = Column(DateTime, nullable=True)
    created_at    = Column(DateTime, nullable=False)

    user    = relationship("User", foreign_keys=[user_id])
    college = relationship("College")


class OrganizerCollege(Base):
    """Which colleges an organiser may list fests for. Set by an admin when promoting the account."""
    __tablename__ = "organizer_colleges"
    user_id    = Column(Integer, ForeignKey("users.id"), primary_key=True)
    college_id = Column(Integer, ForeignKey("colleges.id"), primary_key=True)


class Media(Base):
    """An uploaded image (fest banner, event cover). Stored in the database and served with long caching."""
    __tablename__ = "media"
    id         = Column(String(32), primary_key=True)
    owner_id   = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    mime       = Column(String(100), nullable=False)
    size       = Column(Integer, nullable=False)
    data       = Column(LargeBinary, nullable=False)
    created_at = Column(DateTime, nullable=False)


class EventQuestion(Base):
    """A custom question the committee asks when someone registers for an event."""
    __tablename__ = "event_questions"
    id       = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False, index=True)
    label    = Column(String(200), nullable=False)
    kind     = Column(String(20), nullable=False)          # short_text | choice | yes_no
    required = Column(Boolean, nullable=False, default=False, server_default="0")
    options  = Column(JSON, nullable=True)                 # for choice questions: list of strings
    position = Column(Integer, nullable=False, default=0, server_default="0")

    event = relationship("Event", back_populates="questions")


class RegistrationAnswer(Base):
    __tablename__ = "registration_answers"
    id              = Column(Integer, primary_key=True, index=True)
    registration_id = Column(Integer, ForeignKey("event_registrations.id"), nullable=False, index=True)
    question_id     = Column(Integer, ForeignKey("event_questions.id"), nullable=False)
    answer          = Column(String(500), nullable=False)

    registration = relationship("EventRegistration", back_populates="answers")
    question     = relationship("EventQuestion")

    @property
    def label(self):
        return self.question.label if self.question else ""


class Announcement(Base):
    """A notice from a fest committee to everyone holding a pass (fest-wide) or registered (one event)."""
    __tablename__ = "announcements"
    id             = Column(Integer, primary_key=True, index=True)
    fest_id        = Column(Integer, ForeignKey("fests.id"), nullable=False, index=True)
    event_id       = Column(Integer, ForeignKey("events.id"), nullable=True)
    author_id      = Column(Integer, ForeignKey("users.id"), nullable=False)
    title          = Column(String(120), nullable=False)
    body           = Column(String(2000), nullable=False)
    email_requested = Column(Boolean, nullable=False, default=False, server_default="0")
    emails_sent    = Column(Integer, nullable=False, default=0, server_default="0")
    emails_failed  = Column(Integer, nullable=False, default=0, server_default="0")
    created_at     = Column(DateTime, nullable=False)

    fest   = relationship("Fest")
    event  = relationship("Event")
    author = relationship("User")


class FestSponsor(Base):
    """A sponsor or partner of a fest, shown on its public page with a logo. The tier's label is the fest's own wording."""
    __tablename__ = "fest_sponsors"
    id          = Column(Integer, primary_key=True, index=True)
    fest_id     = Column(Integer, ForeignKey("fests.id"), nullable=False, index=True)
    name        = Column(String(120), nullable=False)
    tier_label  = Column(String(60), nullable=False)    # "Title Sponsor", "Powered by", "Food Partner"...
    level       = Column(Integer, nullable=False, default=3)   # 1 largest ... 4 smallest: how big the logo is shown and where it comes in the order
    logo_url    = Column(String(500), nullable=True)
    website_url = Column(String(500), nullable=True)
    blurb       = Column(String(200), nullable=True)    # a line about them or what they gave
    position    = Column(Integer, nullable=False, default=0)   # order inside a level
    created_at  = Column(DateTime(timezone=True), server_default=func.now())


# ─── Competition between colleges: points, CL meets, name auction, results, penalties, awards ───────────────────────────

class CompetitionSettings(Base):
    """How a fest scores its visiting colleges. Everything is the fest's own choice."""
    __tablename__ = "competition_settings"
    fest_id               = Column(Integer, ForeignKey("fests.id"), primary_key=True)
    starting_points       = Column(Integer, nullable=False, default=500, server_default="500")   # what every contingent begins with
    ranking_basis         = Column(String(10), nullable=False, default="total", server_default="total")   # total (the whole balance) | events (only what events earned)
    public_leaderboard    = Column(Boolean, nullable=False, default=False, server_default="0")
    default_placing_points = Column(JSON, nullable=True)   # [100, 60, 30]: the usual points for 1st, 2nd, 3rd, offered when an event is made a competition
    default_task_points    = Column(JSON, nullable=True)   # [200, 100, 50]: the usual points for 1st, 2nd, 3rd at a CL meet task


class PointsEntry(Base):
    """One change to a contingent's points. A contingent's balance is the fest's starting points plus all of its entries."""
    __tablename__ = "points_entries"
    id            = Column(Integer, primary_key=True, index=True)
    fest_id       = Column(Integer, ForeignKey("fests.id"), nullable=False, index=True)
    contingent_id = Column(Integer, ForeignKey("contingents.id", name="fk_points_contingent"), nullable=False, index=True)
    points        = Column(Integer, nullable=False)   # positive earns, negative spends or loses
    kind          = Column(String(16), nullable=False)   # meet_task | auction | event_result | penalty | adjustment
    reason        = Column(String(300), nullable=False)
    meet_task_id  = Column(Integer, ForeignKey("cl_meet_tasks.id", name="fk_points_meet_task"), nullable=True, index=True)
    auction_name_id = Column(Integer, ForeignKey("auction_names.id", name="fk_points_auction_name"), nullable=True, index=True)
    event_id      = Column(Integer, ForeignKey("events.id", name="fk_points_event"), nullable=True, index=True)
    penalty_id    = Column(Integer, ForeignKey("contingent_penalties.id", name="fk_points_penalty"), nullable=True, index=True)
    created_by_id = Column(Integer, ForeignKey("users.id", name="fk_points_creator"), nullable=True)
    created_at    = Column(DateTime, nullable=False, server_default=func.now())

    contingent = relationship("Contingent")


class ClMeet(Base):
    """A meeting of the contingent leaders before the fest, where the committee runs tasks and auctions names."""
    __tablename__ = "cl_meets"
    id        = Column(Integer, primary_key=True, index=True)
    fest_id   = Column(Integer, ForeignKey("fests.id"), nullable=False, index=True)
    title     = Column(String(200), nullable=False)
    starts_at = Column(DateTime, nullable=False)   # a wall-clock time, like event times
    location  = Column(String(255), nullable=True)
    notes     = Column(Text, nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id", name="fk_cl_meets_creator"), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    tasks      = relationship("ClMeetTask", cascade="all, delete-orphan", order_by="ClMeetTask.position")
    attendance = relationship("ClMeetAttendance", cascade="all, delete-orphan")


class ClMeetAttendance(Base):
    """A contingent that came to a CL meet."""
    __tablename__ = "cl_meet_attendance"
    meet_id       = Column(Integer, ForeignKey("cl_meets.id"), primary_key=True)
    contingent_id = Column(Integer, ForeignKey("contingents.id", name="fk_cl_attendance_contingent"), primary_key=True)


class ClMeetTask(Base):
    """A game or challenge at a CL meet. Contingents that do well earn points."""
    __tablename__ = "cl_meet_tasks"
    id          = Column(Integer, primary_key=True, index=True)
    meet_id     = Column(Integer, ForeignKey("cl_meets.id"), nullable=False, index=True)
    title       = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    position    = Column(Integer, nullable=False, default=0)
    placing_points = Column(JSON, nullable=True)   # [200, 100, 50]: what 1st, 2nd and 3rd earn; the committee can still award any amount
    created_at  = Column(DateTime, nullable=False, server_default=func.now())


class NameAuction(Base):
    """An auction where contingents bid points for the names (and codes) the committee has put up."""
    __tablename__ = "name_auctions"
    id       = Column(Integer, primary_key=True, index=True)
    fest_id  = Column(Integer, ForeignKey("fests.id"), nullable=False, index=True)
    meet_id  = Column(Integer, ForeignKey("cl_meets.id", name="fk_name_auctions_meet"), nullable=True)
    title    = Column(String(200), nullable=False)
    status   = Column(String(8), nullable=False, default="draft", server_default="draft")   # draft | open | closed
    min_bid  = Column(Integer, nullable=False, default=1, server_default="1")
    show_highest_bid = Column(Boolean, nullable=False, default=False, server_default="0")   # leaders see the top bid on each name; otherwise bids are sealed
    opened_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    names = relationship("AuctionName", cascade="all, delete-orphan", order_by="AuctionName.position")


class AuctionName(Base):
    """One name (with an optional code) up for bidding."""
    __tablename__ = "auction_names"
    id         = Column(Integer, primary_key=True, index=True)
    auction_id = Column(Integer, ForeignKey("name_auctions.id"), nullable=False, index=True)
    name       = Column(String(120), nullable=False)
    code       = Column(String(30), nullable=True)
    position   = Column(Integer, nullable=False, default=0)
    winner_contingent_id = Column(Integer, ForeignKey("contingents.id", name="fk_auction_name_winner"), nullable=True)
    winning_bid = Column(Integer, nullable=True)

    bids   = relationship("AuctionBid", cascade="all, delete-orphan")
    winner = relationship("Contingent", foreign_keys=[winner_contingent_id])


class AuctionBid(Base):
    """A contingent's bid on a name. It can be raised while the auction is open. Only the winning bid is ever paid."""
    __tablename__ = "auction_bids"
    __table_args__ = (UniqueConstraint("auction_name_id", "contingent_id", name="uq_auction_bid_name_contingent"),)
    id              = Column(Integer, primary_key=True, index=True)
    auction_name_id = Column(Integer, ForeignKey("auction_names.id"), nullable=False, index=True)
    contingent_id   = Column(Integer, ForeignKey("contingents.id", name="fk_auction_bid_contingent"), nullable=False, index=True)
    amount          = Column(Integer, nullable=False)
    placed_by_id    = Column(Integer, ForeignKey("users.id", name="fk_auction_bid_user"), nullable=True)
    created_at      = Column(DateTime, nullable=False, server_default=func.now())   # when the first bid on this name was placed: it settles ties
    updated_at      = Column(DateTime, nullable=False, server_default=func.now())

    contingent = relationship("Contingent")


class EventResult(Base):
    """Who placed where in a scored event."""
    __tablename__ = "event_results"
    __table_args__ = (UniqueConstraint("event_id", "contingent_id", name="uq_event_result_contingent"),)
    id            = Column(Integer, primary_key=True, index=True)
    event_id      = Column(Integer, ForeignKey("events.id"), nullable=False, index=True)
    contingent_id = Column(Integer, ForeignKey("contingents.id", name="fk_event_result_contingent"), nullable=False, index=True)
    place         = Column(Integer, nullable=False)   # 1 is first. Equal places are ties
    note          = Column(String(300), nullable=True)   # the winners' names, for the record
    created_at    = Column(DateTime, nullable=False, server_default=func.now())

    contingent = relationship("Contingent")


class CompetitionRule(Base):
    """A rule of the competition and what breaking it costs. It may apply to one event or to all of them."""
    __tablename__ = "competition_rules"
    id             = Column(Integer, primary_key=True, index=True)
    fest_id        = Column(Integer, ForeignKey("fests.id"), nullable=False, index=True)
    event_id       = Column(Integer, ForeignKey("events.id", name="fk_competition_rule_event"), nullable=True)   # None: applies to every event
    title          = Column(String(200), nullable=False)
    description    = Column(Text, nullable=True)
    penalty_points = Column(Integer, nullable=False, default=0, server_default="0")   # taken off when applied; 0 for none
    disqualifies   = Column(Boolean, nullable=False, default=False, server_default="0")
    created_at     = Column(DateTime, nullable=False, server_default=func.now())


class ContingentPenalty(Base):
    """A penalty applied to a contingent: points off, and/or disqualification from one event or from the whole competition."""
    __tablename__ = "contingent_penalties"
    id            = Column(Integer, primary_key=True, index=True)
    fest_id       = Column(Integer, ForeignKey("fests.id"), nullable=False, index=True)
    contingent_id = Column(Integer, ForeignKey("contingents.id", name="fk_penalty_contingent"), nullable=False, index=True)
    rule_id       = Column(Integer, ForeignKey("competition_rules.id", name="fk_penalty_rule"), nullable=True)
    event_id      = Column(Integer, ForeignKey("events.id", name="fk_penalty_event"), nullable=True)   # None: not tied to one event
    points        = Column(Integer, nullable=False, default=0)   # how many points were taken off (a positive number)
    disqualified  = Column(Boolean, nullable=False, default=False)   # from event_id, or from the whole competition when event_id is None
    reason        = Column(String(500), nullable=False)
    created_by_id = Column(Integer, ForeignKey("users.id", name="fk_penalty_creator"), nullable=True)
    created_at    = Column(DateTime, nullable=False, server_default=func.now())
    revoked_at    = Column(DateTime, nullable=True)   # an appeal succeeded: the penalty no longer counts

    contingent = relationship("Contingent")
    rule       = relationship("CompetitionRule")


class Award(Base):
    """A prize of the fest. Most are worked out from the standings; a custom one is given to a contingent by hand."""
    __tablename__ = "awards"
    id        = Column(Integer, primary_key=True, index=True)
    fest_id   = Column(Integer, ForeignKey("fests.id"), nullable=False, index=True)
    title     = Column(String(120), nullable=False)
    basis     = Column(String(12), nullable=False)   # college (rank among colleges) | contingent (rank among contingents) | event (place in one event) | custom
    rank      = Column(Integer, nullable=False, default=1)
    event_id  = Column(Integer, ForeignKey("events.id", name="fk_award_event"), nullable=True)
    winner_contingent_id = Column(Integer, ForeignKey("contingents.id", name="fk_award_winner"), nullable=True)   # custom awards only
    position  = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    winner = relationship("Contingent", foreign_keys=[winner_contingent_id])


# ─── Finance: budget, spending with approvals, income and sponsorship money ──────────────────────────────────────────
# Money is kept in paise (whole numbers), so adding it up is always exact. The API speaks in rupees.

class FinanceSettings(Base):
    """A fest's own rules for money. Every fest chooses what needs approval and what needs a receipt."""
    __tablename__ = "finance_settings"
    fest_id = Column(Integer, ForeignKey("fests.id"), primary_key=True)
    auto_approve_below_paise      = Column(Integer, nullable=False, default=0, server_default="0")   # a request smaller than this is approved on the spot; 0 means every request is decided by the committee
    receipt_required_above_paise  = Column(Integer, nullable=True, default=100000)                   # a request above this must have a receipt; NULL means receipts are never required
    refund_on_cancel              = Column(Boolean, nullable=False, default=True, server_default="1")   # a student who cancels is refunded on their own
    refund_cutoff_days            = Column(Integer, nullable=False, default=0, server_default="0")      # ...up to this many days before the event (0 means until the day it starts)


class FinanceCategory(Base):
    """A kind of money in or out, named by the fest (Sponsorship, Venue, Prizes...)."""
    __tablename__ = "finance_categories"
    __table_args__ = (UniqueConstraint("fest_id", "name", name="uq_finance_category_fest_name"),)
    id       = Column(Integer, primary_key=True, index=True)
    fest_id  = Column(Integer, ForeignKey("fests.id"), nullable=False, index=True)
    name     = Column(String(80), nullable=False)
    kind     = Column(String(8), nullable=False)   # income | expense
    position = Column(Integer, nullable=False, default=0)


class BudgetLine(Base):
    """Money planned for something, in a category, optionally owned by a committee team."""
    __tablename__ = "budget_lines"
    id            = Column(Integer, primary_key=True, index=True)
    fest_id       = Column(Integer, ForeignKey("fests.id"), nullable=False, index=True)
    category_id   = Column(Integer, ForeignKey("finance_categories.id", name="fk_budget_line_category"), nullable=False)
    title         = Column(String(200), nullable=False)
    planned_paise = Column(Integer, nullable=False, default=0)
    committee_team_id = Column(Integer, ForeignKey("committee_teams.id", name="fk_budget_line_team"), nullable=True)
    notes         = Column(String(500), nullable=True)
    created_at    = Column(DateTime, nullable=False, server_default=func.now())

    category = relationship("FinanceCategory")
    team     = relationship("CommitteeTeam")


class Expense(Base):
    """A request to spend money, and what became of it: pending, approved or rejected, then paid."""
    __tablename__ = "expenses"
    id             = Column(Integer, primary_key=True, index=True)
    fest_id        = Column(Integer, ForeignKey("fests.id"), nullable=False, index=True)
    budget_line_id = Column(Integer, ForeignKey("budget_lines.id", name="fk_expense_budget_line"), nullable=True, index=True)
    category_id    = Column(Integer, ForeignKey("finance_categories.id", name="fk_expense_category"), nullable=False)
    title          = Column(String(200), nullable=False)
    amount_paise   = Column(Integer, nullable=False)
    spent_on       = Column(Date, nullable=False)
    vendor         = Column(String(120), nullable=True)
    notes          = Column(String(500), nullable=True)
    receipts       = Column(JSON, nullable=True)   # up to five links to uploaded receipts
    status         = Column(String(10), nullable=False, default="pending", server_default="pending")   # pending | approved | rejected | paid | cancelled
    requested_by_id = Column(Integer, ForeignKey("users.id", name="fk_expense_requester"), nullable=False)
    paid_by_member_id = Column(Integer, ForeignKey("fest_members.id", name="fk_expense_paid_by"), nullable=True)   # a member who paid out of their own pocket and is owed it back
    decided_by_id  = Column(Integer, ForeignKey("users.id", name="fk_expense_decider"), nullable=True)
    decided_at     = Column(DateTime, nullable=True)
    decision_note  = Column(String(300), nullable=True)
    paid_on        = Column(Date, nullable=True)
    paid_note      = Column(String(200), nullable=True)   # how it was paid, or the reference
    created_at     = Column(DateTime, nullable=False, server_default=func.now())

    budget_line = relationship("BudgetLine")
    category    = relationship("FinanceCategory")
    requested_by = relationship("User", foreign_keys=[requested_by_id])
    decided_by   = relationship("User", foreign_keys=[decided_by_id])
    paid_by      = relationship("FestMember", foreign_keys=[paid_by_member_id])


class IncomeItem(Base):
    """Money the fest expects to receive: a sponsor's pledge, a college grant, a stall fee. Payments come in against it."""
    __tablename__ = "income_items"
    id             = Column(Integer, primary_key=True, index=True)
    fest_id        = Column(Integer, ForeignKey("fests.id"), nullable=False, index=True)
    category_id    = Column(Integer, ForeignKey("finance_categories.id", name="fk_income_category"), nullable=False)
    title          = Column(String(200), nullable=False)
    source         = Column(String(120), nullable=True)   # who it comes from
    sponsor_id     = Column(Integer, ForeignKey("fest_sponsors.id", name="fk_income_sponsor"), nullable=True)
    expected_paise = Column(Integer, nullable=False, default=0)
    due_on         = Column(Date, nullable=True)
    notes          = Column(String(500), nullable=True)
    created_at     = Column(DateTime, nullable=False, server_default=func.now())

    category = relationship("FinanceCategory")
    sponsor  = relationship("FestSponsor")
    payments = relationship("IncomePayment", cascade="all, delete-orphan", order_by="IncomePayment.received_on")


class IncomePayment(Base):
    """One payment received against an income item."""
    __tablename__ = "income_payments"
    id           = Column(Integer, primary_key=True, index=True)
    income_id    = Column(Integer, ForeignKey("income_items.id"), nullable=False, index=True)
    amount_paise = Column(Integer, nullable=False)
    received_on  = Column(Date, nullable=False)
    method       = Column(String(40), nullable=True)   # cash, UPI, cheque, bank transfer...
    note         = Column(String(200), nullable=True)
    recorded_by_id = Column(Integer, ForeignKey("users.id", name="fk_income_payment_recorder"), nullable=True)
    created_at   = Column(DateTime, nullable=False, server_default=func.now())


# ─── Contingents in events, accommodation and fees ───────────────────────────────────────────────────────────────────

class ContingentEntry(Base):
    """A contingent's entry into an event: which of its people take part."""
    __tablename__ = "contingent_entries"
    id            = Column(Integer, primary_key=True, index=True)
    fest_id       = Column(Integer, ForeignKey("fests.id"), nullable=False, index=True)
    contingent_id = Column(Integer, ForeignKey("contingents.id", name="fk_entry_contingent"), nullable=False, index=True)
    event_id      = Column(Integer, ForeignKey("events.id", name="fk_entry_event"), nullable=False, index=True)
    status        = Column(String(10), nullable=False, default="confirmed", server_default="confirmed")   # confirmed | withdrawn | removed
    note          = Column(String(300), nullable=True)   # why the committee removed it
    created_by_id = Column(Integer, ForeignKey("users.id", name="fk_entry_creator"), nullable=True)
    created_at    = Column(DateTime, nullable=False, server_default=func.now())

    contingent = relationship("Contingent")
    event      = relationship("Event")
    members    = relationship("ContingentEntryMember", cascade="all, delete-orphan")


class ContingentEntryMember(Base):
    """One person from the contingent's list, taking part in an entry."""
    __tablename__ = "contingent_entry_members"
    entry_id  = Column(Integer, ForeignKey("contingent_entries.id"), primary_key=True)
    member_id = Column(Integer, ForeignKey("contingent_members.id", name="fk_entry_member"), primary_key=True)

    member = relationship("ContingentMember")


class AccommodationOption(Base):
    """A place visiting colleges can be put up: a hostel block, a guest house. The fest names and prices its own."""
    __tablename__ = "accommodation_options"
    id          = Column(Integer, primary_key=True, index=True)
    fest_id     = Column(Integer, ForeignKey("fests.id"), nullable=False, index=True)
    name        = Column(String(120), nullable=False)
    description = Column(String(500), nullable=True)
    capacity    = Column(Integer, nullable=False)   # how many people it holds
    gender_policy = Column(String(8), nullable=False, default="any", server_default="any")   # any | boys | girls
    fee_per_night_paise = Column(Integer, nullable=False, default=0, server_default="0")   # for each person, each night
    position    = Column(Integer, nullable=False, default=0)


class AccommodationRequest(Base):
    """A contingent asking for somewhere to stay: how many people, and for which nights."""
    __tablename__ = "accommodation_requests"
    id             = Column(Integer, primary_key=True, index=True)
    fest_id        = Column(Integer, ForeignKey("fests.id"), nullable=False, index=True)
    contingent_id  = Column(Integer, ForeignKey("contingents.id", name="fk_stay_contingent"), nullable=False, unique=True)
    boys           = Column(Integer, nullable=False, default=0, server_default="0")
    girls          = Column(Integer, nullable=False, default=0, server_default="0")
    others         = Column(Integer, nullable=False, default=0, server_default="0")
    arrival_date   = Column(Date, nullable=False)
    departure_date = Column(Date, nullable=False)
    notes          = Column(String(500), nullable=True)
    status         = Column(String(10), nullable=False, default="requested", server_default="requested")   # requested | allocated | declined | cancelled
    decision_note  = Column(String(300), nullable=True)
    decided_by_id  = Column(Integer, ForeignKey("users.id", name="fk_stay_decider"), nullable=True)
    decided_at     = Column(DateTime, nullable=True)
    created_at     = Column(DateTime, nullable=False, server_default=func.now())

    contingent  = relationship("Contingent")
    allocations = relationship("AccommodationAllocation", cascade="all, delete-orphan")

    @property
    def nights(self):
        return max((self.departure_date - self.arrival_date).days, 0)

    @property
    def people(self):
        return (self.boys or 0) + (self.girls or 0) + (self.others or 0)


class AccommodationAllocation(Base):
    """Part of a request placed in one option: this many boys (or girls, or others) go here."""
    __tablename__ = "accommodation_allocations"
    __table_args__ = (UniqueConstraint("request_id", "option_id", "grp", name="uq_stay_allocation"),)
    id         = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("accommodation_requests.id"), nullable=False, index=True)
    option_id  = Column(Integer, ForeignKey("accommodation_options.id", name="fk_stay_alloc_option"), nullable=False, index=True)
    grp        = Column(String(8), nullable=False)   # boys | girls | others
    people     = Column(Integer, nullable=False)

    option = relationship("AccommodationOption")


class FeeAdjustment(Base):
    """A line the committee adds to a contingent's fees by hand: a late fee, a waiver, a discount (negative)."""
    __tablename__ = "fee_adjustments"
    id            = Column(Integer, primary_key=True, index=True)
    fest_id       = Column(Integer, ForeignKey("fests.id"), nullable=False, index=True)
    contingent_id = Column(Integer, ForeignKey("contingents.id", name="fk_fee_adj_contingent"), nullable=False, index=True)
    label         = Column(String(200), nullable=False)
    amount_paise  = Column(Integer, nullable=False)   # positive adds to what is owed, negative takes off
    created_by_id = Column(Integer, ForeignKey("users.id", name="fk_fee_adj_creator"), nullable=True)
    created_at    = Column(DateTime, nullable=False, server_default=func.now())


class FeePayment(Base):
    """Money received from a contingent, recorded by the committee."""
    __tablename__ = "fee_payments"
    id            = Column(Integer, primary_key=True, index=True)
    fest_id       = Column(Integer, ForeignKey("fests.id"), nullable=False, index=True)
    contingent_id = Column(Integer, ForeignKey("contingents.id", name="fk_fee_pay_contingent"), nullable=False, index=True)
    amount_paise  = Column(Integer, nullable=False)
    received_on   = Column(Date, nullable=False)
    method        = Column(String(40), nullable=True)
    reference     = Column(String(100), nullable=True)   # a transaction id or cheque number
    note          = Column(String(200), nullable=True)
    recorded_by_id = Column(Integer, ForeignKey("users.id", name="fk_fee_pay_recorder"), nullable=True)
    created_at    = Column(DateTime, nullable=False, server_default=func.now())

    contingent = relationship("Contingent")


# ─── Ticketing: tiers, promo codes, waitlist and certificates ────────────────────────────────────────────────────────

class TicketTier(Base):
    """One kind of ticket for an event (Early bird, Regular, VIP) with its own price, seats and sale window."""
    __tablename__ = "ticket_tiers"
    id          = Column(Integer, primary_key=True, index=True)
    fest_id     = Column(Integer, ForeignKey("fests.id"), nullable=False, index=True)
    event_id    = Column(Integer, ForeignKey("events.id", name="fk_tier_event"), nullable=False, index=True)
    name        = Column(String(80), nullable=False)
    description = Column(String(300), nullable=True)
    price_paise         = Column(Integer, nullable=False, default=0)
    student_price_paise = Column(Integer, nullable=True)   # cheaper for verified students; None means the same price
    quantity    = Column(Integer, nullable=True)           # how many of this ticket in all; None for no limit
    sales_open_on  = Column(Date, nullable=True)
    sales_close_on = Column(Date, nullable=True)
    position    = Column(Integer, nullable=False, default=0)
    active      = Column(Boolean, nullable=False, default=True, server_default="1")
    created_at  = Column(DateTime, nullable=False, server_default=func.now())


class PromoCode(Base):
    """A code that takes money off a paid ticket: a percentage or a fixed amount, for some events or all, with its own limits."""
    __tablename__ = "promo_codes"
    __table_args__ = (UniqueConstraint("fest_id", "code", name="uq_promo_fest_code"),)
    id          = Column(Integer, primary_key=True, index=True)
    fest_id     = Column(Integer, ForeignKey("fests.id"), nullable=False, index=True)
    code        = Column(String(40), nullable=False)   # stored in capitals; people can type it in any case
    description = Column(String(200), nullable=True)
    kind        = Column(String(8), nullable=False)    # percent | flat
    value       = Column(Integer, nullable=False)      # a percentage (1 to 100), or paise for a flat discount
    event_ids   = Column(JSON(none_as_null=True), nullable=True)   # the events it works for; None means every event of the fest
    max_uses    = Column(Integer, nullable=True)       # in all; None for no limit
    per_user_limit = Column(Integer, nullable=False, default=1, server_default="1")
    valid_from  = Column(Date, nullable=True)
    valid_until = Column(Date, nullable=True)
    students_only = Column(Boolean, nullable=False, default=False, server_default="0")
    active      = Column(Boolean, nullable=False, default=True, server_default="1")
    created_at  = Column(DateTime, nullable=False, server_default=func.now())


class WaitlistEntry(Base):
    """Someone queuing for a seat in a full event. First in, first offered."""
    __tablename__ = "waitlist_entries"
    id             = Column(Integer, primary_key=True, index=True)
    event_id       = Column(Integer, ForeignKey("events.id", name="fk_waitlist_event"), nullable=False, index=True)
    user_id        = Column(Integer, ForeignKey("users.id", name="fk_waitlist_user"), nullable=False, index=True)
    ticket_tier_id = Column(Integer, ForeignKey("ticket_tiers.id", name="fk_waitlist_tier"), nullable=True)
    promo_code     = Column(String(40), nullable=True)   # the code they typed, checked again when a seat opens
    team_name      = Column(String(80), nullable=True)   # a team event: the team this person will lead
    answers        = Column(JSON(none_as_null=True), nullable=True)   # their answers to the event's questions
    status         = Column(String(10), nullable=False, default="waiting", server_default="waiting")   # waiting | promoted | left | removed
    note           = Column(String(300), nullable=True)
    created_at     = Column(DateTime, nullable=False, server_default=func.now())
    promoted_at    = Column(DateTime, nullable=True)

    user  = relationship("User")
    event = relationship("Event")


class CertificateTemplate(Base):
    """The wording and signatures of a kind of certificate, for the whole fest or one event."""
    __tablename__ = "certificate_templates"
    id        = Column(Integer, primary_key=True, index=True)
    fest_id   = Column(Integer, ForeignKey("fests.id"), nullable=False, index=True)
    event_id  = Column(Integer, ForeignKey("events.id", name="fk_cert_template_event"), nullable=True)   # None: usable for any event
    kind      = Column(String(16), nullable=False, default="participation")   # participation | winner | appreciation
    title     = Column(String(120), nullable=False)
    body      = Column(String(1000), nullable=False)   # may use {name}, {event}, {fest}, {college}, {date} and {award}
    signatories = Column(JSON(none_as_null=True), nullable=True)   # [{"name": "...", "title": "..."}]
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class Certificate(Base):
    """A certificate given to someone. It keeps its own copy of the wording, so editing a template later changes nothing already issued."""
    __tablename__ = "certificates"
    id          = Column(Integer, primary_key=True, index=True)
    fest_id     = Column(Integer, ForeignKey("fests.id"), nullable=False, index=True)
    event_id    = Column(Integer, ForeignKey("events.id", name="fk_certificate_event"), nullable=True, index=True)
    user_id     = Column(Integer, ForeignKey("users.id", name="fk_certificate_user"), nullable=True, index=True)   # their HiveOut account, when they have one
    kind        = Column(String(16), nullable=False)
    code        = Column(String(12), nullable=False, unique=True, index=True)   # printed on it; anyone can check it
    recipient_name = Column(String(120), nullable=False)
    college_name   = Column(String(200), nullable=True)
    award_text     = Column(String(120), nullable=True)   # for example "First place"
    title       = Column(String(120), nullable=False)
    body        = Column(String(1200), nullable=False)    # the wording with the names filled in
    signatories = Column(JSON(none_as_null=True), nullable=True)
    fest_name   = Column(String(255), nullable=False)
    event_title = Column(String(255), nullable=True)
    issued_at   = Column(DateTime, nullable=False, server_default=func.now())
    issued_by_id = Column(Integer, ForeignKey("users.id", name="fk_certificate_issuer"), nullable=True)
    revoked_at  = Column(DateTime, nullable=True)
    revoked_reason = Column(String(200), nullable=True)


class Shift(Base):
    """A duty on the fest's roster: where someone is needed, when, and how many people. Committee members take it or are given it."""
    __tablename__ = "shifts"
    id                = Column(Integer, primary_key=True, index=True)
    fest_id           = Column(Integer, ForeignKey("fests.id"), nullable=False, index=True)
    title             = Column(String(120), nullable=False)             # "Main gate", "Registration desk"
    event_id          = Column(Integer, ForeignKey("events.id", name="fk_shift_event"), nullable=True)
    committee_team_id = Column(Integer, ForeignKey("committee_teams.id", name="fk_shift_team"), nullable=True)
    location          = Column(String(255), nullable=True)
    starts_at         = Column(DateTime, nullable=False)                # wall-clock, like event and meeting times
    ends_at           = Column(DateTime, nullable=False)
    needed            = Column(Integer, nullable=False, default=1, server_default="1")
    open_signup       = Column(Boolean, nullable=False, default=False, server_default="0")   # members may put themselves down
    notes             = Column(Text, nullable=True)
    created_by_id     = Column(Integer, ForeignKey("users.id", name="fk_shift_creator"), nullable=True)
    created_at        = Column(DateTime, nullable=False, server_default=func.now())

    event          = relationship("Event")
    committee_team = relationship("CommitteeTeam")
    assignments    = relationship("ShiftAssignment", cascade="all, delete-orphan", order_by="ShiftAssignment.created_at")

    @property
    def event_title(self):
        return self.event.title if self.event else None

    @property
    def team_name(self):
        return self.committee_team.name if self.committee_team else None

    @property
    def filled(self):
        return len(self.assignments)


class ShiftAssignment(Base):
    """One person on one duty, and whether they turned up."""
    __tablename__ = "shift_assignments"
    shift_id   = Column(Integer, ForeignKey("shifts.id"), primary_key=True)
    member_id  = Column(Integer, ForeignKey("fest_members.id"), primary_key=True)
    arrived_at = Column(DateTime, nullable=True)       # they said "I am here", or the committee marked them
    no_show    = Column(Boolean, nullable=False, default=False, server_default="0")
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    member = relationship("FestMember")

    @property
    def user_name(self):
        return self.member.user_name if self.member else None

    @property
    def title(self):
        return self.member.title if self.member else None

    @property
    def user_id(self):
        return self.member.user_id if self.member else None


# ─── Online payments ─────────────────────────────────────────────────────────────────────────────────────────────────

class Payment(Base):
    """One attempt to pay online: an order at the payment gateway. What it pays for is recorded here, so it survives the registration."""
    __tablename__ = "payments"
    id            = Column(Integer, primary_key=True, index=True)
    order_id      = Column(String(60), nullable=False, unique=True, index=True)   # our reference, also the gateway's order id
    fest_id       = Column(Integer, ForeignKey("fests.id"), nullable=False, index=True)
    user_id       = Column(Integer, ForeignKey("users.id", name="fk_payment_user"), nullable=False, index=True)
    purpose       = Column(String(20), nullable=False)                 # registration | contingent_fee
    event_id      = Column(Integer, ForeignKey("events.id", name="fk_payment_event"), nullable=True)
    registration_id = Column(Integer, nullable=True, index=True)       # not a foreign key: the registration can be cancelled, the payment stays on record
    contingent_id = Column(Integer, ForeignKey("contingents.id", name="fk_payment_contingent"), nullable=True)
    description   = Column(String(200), nullable=True)
    amount_paise  = Column(Integer, nullable=False)
    status        = Column(String(12), nullable=False, default="created", server_default="created")   # created | paid | failed | expired
    session_id    = Column(String(500), nullable=True)                 # the gateway's checkout session
    gateway_payment_id = Column(String(60), nullable=True)
    method        = Column(String(40), nullable=True)
    paid_at       = Column(DateTime, nullable=True)
    applied_at    = Column(DateTime, nullable=True)                    # when what it paid for was updated (a registration confirmed, a fee recorded)
    created_at    = Column(DateTime, nullable=False, server_default=func.now())

    user      = relationship("User")
    event     = relationship("Event")
    contingent = relationship("Contingent")
    refunds   = relationship("Refund", cascade="all, delete-orphan", order_by="Refund.id")

    @property
    def user_name(self):
        return self.user.name if self.user else None

    @property
    def user_email(self):
        return self.user.email if self.user else None

    @property
    def event_title(self):
        return self.event.title if self.event else None

    @property
    def refunded_paise(self):
        return sum(r.amount_paise for r in self.refunds if r.status in ("pending", "done"))


class Refund(Base):
    """Money sent back through the gateway for a payment."""
    __tablename__ = "refunds"
    id            = Column(Integer, primary_key=True, index=True)
    payment_id    = Column(Integer, ForeignKey("payments.id"), nullable=False, index=True)
    ref           = Column(String(60), nullable=False, unique=True)    # our refund id at the gateway
    amount_paise  = Column(Integer, nullable=False)
    status        = Column(String(10), nullable=False, default="pending", server_default="pending")   # pending | done | failed
    reason        = Column(String(200), nullable=True)
    note          = Column(String(300), nullable=True)                 # why it failed, when it did
    by_user_id    = Column(Integer, ForeignKey("users.id", name="fk_refund_by"), nullable=True)   # empty when it happened on its own
    created_at    = Column(DateTime, nullable=False, server_default=func.now())
