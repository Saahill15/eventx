from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, ForeignKey, Text, Enum, CheckConstraint, Index, UniqueConstraint
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

class AuthProviderEnum(str, enum.Enum):
    google = "google"
    phone = "phone"
    email = "email"

class User(Base):
    __tablename__ = "users"
    id               = Column(Integer, primary_key=True, index=True)
    name             = Column(String(255), nullable=False)
    email            = Column(String(255), unique=True, nullable=True)
    phone            = Column(String(20), unique=True, nullable=True)
    hashed_password  = Column(String(255), nullable=True)
    role             = Column(Enum(RoleEnum), default=RoleEnum.user)
    auth_provider    = Column(Enum(AuthProviderEnum), default=AuthProviderEnum.email)
    is_active        = Column(Boolean, default=True)
    interests_set    = Column(Boolean, default=False)
    college_id       = Column(Integer, ForeignKey("colleges.id", name="fk_users_college_id"), nullable=True)
    study_year       = Column(Integer, nullable=True)
    created_at       = Column(DateTime(timezone=True), server_default=func.now())

    interests         = relationship("UserInterest", back_populates="user")
    events            = relationship("Event", back_populates="organizer")
    passes            = relationship("Pass", back_populates="user")
    fest_memberships  = relationship("FestMember", back_populates="user")
    fest_passes       = relationship("FestPass", back_populates="user", foreign_keys="FestPass.user_id")

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

    # A cancelled event stays visible (so registered students see why) but cannot be registered for
    cancelled_at  = Column(DateTime, nullable=True)
    cancel_reason = Column(String(500), nullable=True)

    organizer  = relationship("User", back_populates="events")
    college    = relationship("College", back_populates="events")
    fest       = relationship("Fest", back_populates="events")
    passes     = relationship("Pass", back_populates="event")
    committees = relationship("Committee", back_populates="event")
    registrations = relationship("EventRegistration", back_populates="event")

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
    attended        = Column(Boolean, default=False, nullable=False, server_default="0")
    attended_at     = Column(DateTime, nullable=True)
    attended_by     = Column(Integer, ForeignKey("users.id", name="fk_event_registrations_attended_by"), nullable=True)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())

    fest_pass = relationship("FestPass", back_populates="registrations")
    event     = relationship("Event", back_populates="registrations")

    @property
    def user_name(self):
        return self.fest_pass.user.name if self.fest_pass and self.fest_pass.user else None

    @property
    def user_email(self):
        return self.fest_pass.user.email if self.fest_pass and self.fest_pass.user else None

    @property
    def checked_in(self):
        return bool(self.fest_pass and self.fest_pass.checked_in)


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