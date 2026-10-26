"""Shared permission checks for fests and events."""

from sqlalchemy.orm import Session
from app import models

FEST_STAFF_ROLES = (models.FestMemberRoleEnum.owner, models.FestMemberRoleEnum.core)


def can_host_fests(user) -> bool:
    """Admins always can. An organiser can only if an admin switched fest hosting on for them."""
    if user is None:
        return False
    if user.role == models.RoleEnum.admin:
        return True
    return user.role == models.RoleEnum.organizer and bool(user.can_host_fests)


def can_host_city_events(user) -> bool:
    """Admins always can. An organiser can only if an admin switched city events on for them."""
    if user is None:
        return False
    if user.role == models.RoleEnum.admin:
        return True
    return user.role == models.RoleEnum.organizer and bool(user.can_host_city_events)


def fest_hosting_switched_off(user) -> bool:
    """True only for an organiser whose fest hosting an admin has switched off. Other fest team members are not affected."""
    return user is not None and user.role == models.RoleEnum.organizer and not user.can_host_fests


def is_fest_staff(db: Session, fest_id, user) -> bool:
    """True for admins and for owner/core members of the fest, as long as they may still host fests."""
    if user is None or fest_id is None:
        return False
    if user.role == models.RoleEnum.admin:
        return True
    if fest_hosting_switched_off(user):
        return False
    return (
        db.query(models.FestMember)
        .filter(
            models.FestMember.fest_id == fest_id,
            models.FestMember.user_id == user.id,
            models.FestMember.role.in_(FEST_STAFF_ROLES),
        )
        .first()
    ) is not None


def is_fest_member(db: Session, fest_id, user) -> bool:
    """True for admins and for any member of the fest (including volunteers). Used for gate work."""
    if user is None or fest_id is None:
        return False
    if user.role == models.RoleEnum.admin:
        return True
    return (
        db.query(models.FestMember)
        .filter(models.FestMember.fest_id == fest_id, models.FestMember.user_id == user.id)
        .first()
    ) is not None


def can_view_event(db: Session, event: models.Event, user) -> bool:
    """Approved events are public. Others are visible only to their owner, fest staff and admins."""
    if event.status == models.StatusEnum.approved:
        return True
    if user is None:
        return False
    if user.role == models.RoleEnum.admin:
        return True
    if event.event_type == models.EventTypeEnum.city:
        return event.organizer_id == user.id
    return is_fest_staff(db, event.fest_id, user)


def can_view_fest(db: Session, fest: models.Fest, user) -> bool:
    """Live fests are public. Drafts are visible only to fest staff and admins."""
    if fest.status == models.FestStatusEnum.live:
        return True
    if user is None:
        return False
    if user.role == models.RoleEnum.admin:
        return True
    return (
        db.query(models.FestMember)
        .filter(models.FestMember.fest_id == fest.id, models.FestMember.user_id == user.id)
        .first()
    ) is not None
