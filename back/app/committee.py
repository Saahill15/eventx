"""
Where people sit in a fest's committee.

Two separate ideas, kept apart on purpose:
  - Access level (director, core team, volunteer): what someone may manage on HiveOut.
  - Position in a team (head, co-head, member): where they sit and whom they lead.

The Core team is not a team in the list. It is the access level of the people who run the fest: the director and, usually,
the head of every team. A head can have Core access (the default offered) or not; either way they lead their team.
"""

from typing import Optional

from sqlalchemy.orm import Session

from app import models

HEAD, CO_HEAD, MEMBER = "head", "co_head", "member"
LEADER_ROLES = (HEAD, CO_HEAD)


def owner_member(db: Session, fest_id: int) -> Optional[models.FestMember]:
    return db.query(models.FestMember).filter(models.FestMember.fest_id == fest_id, models.FestMember.role == models.FestMemberRoleEnum.owner).first()


def leads_team(db: Session, fest_id: int, user, team_id: Optional[int]) -> bool:
    """Is this user the head or a co-head of that team, in a team whose leaders may manage it?"""
    if user is None or team_id is None:
        return False
    team = db.query(models.CommitteeTeam).filter(models.CommitteeTeam.id == team_id, models.CommitteeTeam.fest_id == fest_id).first()
    if not team or not team.leaders_manage_team:
        return False
    return db.query(models.FestMember).filter(
        models.FestMember.fest_id == fest_id, models.FestMember.user_id == user.id,
        models.FestMember.committee_team_id == team_id, models.FestMember.team_role.in_(LEADER_ROLES),
    ).first() is not None


def reports_in_a_loop(db: Session, member_id: int, new_lead_id) -> bool:
    """Would making new_lead_id this person's lead make the chain loop back to them?"""
    seen = set()
    current = new_lead_id
    while current is not None:
        if current == member_id or current in seen:
            return True
        seen.add(current)
        current = db.query(models.FestMember.reports_to_id).filter(models.FestMember.id == current).scalar()
    return False


def place(member: models.FestMember, team: Optional[models.CommitteeTeam], team_role: str = MEMBER) -> None:
    """Put someone in a team (or none) at a position. Leaving a team always means going back to plain member."""
    member.committee_team_id = team.id if team else None
    member.team_role = team_role if team else MEMBER


def drop_old_team_lead(db: Session, member: models.FestMember, new_team_id: Optional[int]) -> None:
    """Moving to another team: someone who reported to a colleague of the old team no longer does."""
    if member.committee_team_id in (None, new_team_id) or member.reports_to_id is None:
        return
    boss = db.query(models.FestMember).filter(models.FestMember.id == member.reports_to_id).first()
    if boss and boss.committee_team_id == member.committee_team_id:
        member.reports_to_id = None


def seat_office_bearer(db: Session, member: models.FestMember) -> None:
    """Core team members who lead no team (a chairperson's deputy, a treasurer) report to the director unless told otherwise."""
    if member.role != models.FestMemberRoleEnum.core or member.committee_team_id is not None or member.reports_to_id is not None:
        return
    director = owner_member(db, member.fest_id)
    if director and director.id != member.id:
        member.reports_to_id = director.id


def demote_other_heads(db: Session, team_id: int, keep_member_id: int) -> None:
    """A team has one head. When someone takes the job, the earlier head stays on as a co-head."""
    for other in db.query(models.FestMember).filter(
        models.FestMember.committee_team_id == team_id, models.FestMember.team_role == HEAD, models.FestMember.id != keep_member_id
    ).all():
        other.team_role = CO_HEAD


def wire_reports(db: Session, fest_id: int, team_id: int, old_head_id: Optional[int] = None) -> None:
    """
    Fill in the chart from the positions, without overriding anything the committee chose:
    the head reports to the director, and everyone else in the team reports to the head.
    A person who already reports to someone else keeps that, unless it was the head who just stepped down.
    """
    members = db.query(models.FestMember).filter(models.FestMember.committee_team_id == team_id).all()
    head = next((m for m in members if m.team_role == HEAD), None)
    director = owner_member(db, fest_id)
    if head and director and head.id != director.id and head.reports_to_id is None and not reports_in_a_loop(db, head.id, director.id):
        head.reports_to_id = director.id
    if not head:
        return
    for m in members:
        if m.id == head.id or m.role == models.FestMemberRoleEnum.owner:
            continue
        if m.reports_to_id is None or (old_head_id is not None and m.reports_to_id == old_head_id):
            if not reports_in_a_loop(db, m.id, head.id):
                m.reports_to_id = head.id
