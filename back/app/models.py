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
    google_sub       = Column(String(255), unique=True, nullable=True)   # the Google account linked to this one, if any
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
    role       = Column(Enum(FestMemberRoleEnum), default=FestMemberRoleEnum.volunteer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    fest = relationship("Fest", back_populates="members")
    user = relationship("User", back_populates="fest_memberships")

    @property
    def user_name(self):
        return self.user.name if self.user else None

    @property
    def user_email(self):
        return self.user.email if self.user else None


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
    attended        = Column(Boolean, default=False, nullable=False, server_default="0")
    attended_at     = Column(DateTime, nullable=True)
    attended_by     = Column(Integer, ForeignKey("users.id", name="fk_event_registrations_attended_by"), nullable=True)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())

    fest_pass = relationship("FestPass", back_populates="registrations")
    event     = relationship("Event", back_populates="registrations")
    answers   = relationship("RegistrationAnswer", back_populates="registration", cascade="all, delete-orphan")
    team      = relationship("Team", back_populates="registrations")

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
