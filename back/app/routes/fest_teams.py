"""
Committee structure: the teams a fest's committee is organised into, and where each person sits.

The access level (director, core team, volunteer) stays three simple tiers, because that is what decides who can manage
what. On top of it every fest uses its own words: teams (Sponsorship, PR, Logistics...), a title for each person, and who
reports to whom, which draws the organisation chart.

  GET    /api/fests/{slug}/org                       teams and members together, for the chart (any committee member)
  POST   /api/fests/{slug}/org/teams                 add a team
  POST   /api/fests/{slug}/org/teams/suggested       add a usual set of teams (skips names that exist)
  PATCH  /api/fests/{slug}/org/teams/{id}            rename a team, change its description, head, co-heads and permissions
  DELETE /api/fests/{slug}/org/teams/{id}            delete a team; its people stay, without a team
  PATCH  /api/fests/{slug}/org/members/{member_id}   set a person's title, team and lead
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import committee, models, schemas
from app.auth.dependencies import get_current_user
from app.database import get_db
from app.permissions import is_fest_member, is_fest_staff

router = APIRouter()

MAX_TEAMS = 30
SUGGESTED_TEAMS = [
    ("Events", "Plans and runs the competitions, shows and workshops."),
    ("Sponsorship", "Finds sponsors and looks after what they were promised."),
    ("PR and Marketing", "Publicity, social media and reaching other colleges."),
    ("Design and Creatives", "Posters, video, merchandise and the look of the fest."),
    ("Logistics", "Venues, equipment, security and supplies."),
    ("Registration and Help desk", "Registrations, passes and answering questions."),
    ("Hospitality and Accommodation", "Guests, performers and visiting colleges."),
    ("Finance", "Budget, spending and settling payments."),
    ("Tech", "The website, sound, lights and screens."),
]


def _fest(db: Session, slug: str) -> models.Fest:
    fest = db.query(models.Fest).filter(models.Fest.slug == slug).first()
    if not fest:
        raise HTTPException(status_code=404, detail="Fest not found")
    return fest


def _require_member(db: Session, fest: models.Fest, user) -> None:
    if not is_fest_member(db, fest.id, user):
        raise HTTPException(status_code=403, detail="Only the fest's committee can see this")


def _require_staff(db: Session, fest: models.Fest, user) -> None:
    if not is_fest_staff(db, fest.id, user):
        raise HTTPException(status_code=403, detail="Only the fest's director or core team can change the committee structure")


def _team(db: Session, fest: models.Fest, team_id: int) -> models.CommitteeTeam:
    team = db.query(models.CommitteeTeam).filter(models.CommitteeTeam.id == team_id, models.CommitteeTeam.fest_id == fest.id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


def _team_out(db: Session, team: models.CommitteeTeam) -> schemas.CommitteeTeamOut:
    members = db.query(models.FestMember).filter(models.FestMember.committee_team_id == team.id).order_by(models.FestMember.id).all()
    leader = lambda m: schemas.TeamLeader(member_id=m.id, user_id=m.user_id, name=m.user_name, role=m.role.value)
    head = next((m for m in members if m.team_role == committee.HEAD), None)
    return schemas.CommitteeTeamOut(
        id=team.id, fest_id=team.fest_id, name=team.name, description=team.description, member_count=len(members),
        leaders_manage_team=bool(team.leaders_manage_team), head=leader(head) if head else None,
        co_heads=[leader(m) for m in members if m.team_role == committee.CO_HEAD],
    )


def _name_taken(db: Session, fest: models.Fest, name: str, except_id=None) -> bool:
    q = db.query(models.CommitteeTeam).filter(models.CommitteeTeam.fest_id == fest.id, func.lower(models.CommitteeTeam.name) == name.lower())
    if except_id is not None:
        q = q.filter(models.CommitteeTeam.id != except_id)
    return q.first() is not None


_reports_in_a_loop = committee.reports_in_a_loop


@router.get("/{slug}/org", response_model=schemas.OrgOut)
def get_org(slug: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _require_member(db, fest, user)
    teams = db.query(models.CommitteeTeam).filter(models.CommitteeTeam.fest_id == fest.id).order_by(models.CommitteeTeam.name).all()
    members = db.query(models.FestMember).filter(models.FestMember.fest_id == fest.id).order_by(models.FestMember.id).all()
    return schemas.OrgOut(teams=[_team_out(db, t) for t in teams], members=[schemas.FestMemberOut.model_validate(m) for m in members])


@router.post("/{slug}/org/teams", response_model=schemas.CommitteeTeamOut, status_code=status.HTTP_201_CREATED)
def add_team(slug: str, data: schemas.CommitteeTeamIn, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _require_staff(db, fest, user)
    if db.query(models.CommitteeTeam).filter(models.CommitteeTeam.fest_id == fest.id).count() >= MAX_TEAMS:
        raise HTTPException(status_code=400, detail=f"A fest can have at most {MAX_TEAMS} teams")
    if _name_taken(db, fest, data.name):
        raise HTTPException(status_code=400, detail="This fest already has a team with that name")
    team = models.CommitteeTeam(fest_id=fest.id, name=data.name, description=data.description or None)
    db.add(team)
    db.commit()
    db.refresh(team)
    return _team_out(db, team)


@router.post("/{slug}/org/teams/suggested", response_model=List[schemas.CommitteeTeamOut], status_code=status.HTTP_201_CREATED)
def add_suggested_teams(slug: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """Add the usual teams a fest has. Names the fest already uses are skipped, so it is safe to press twice."""
    fest = _fest(db, slug)
    _require_staff(db, fest, user)
    created = []
    for name, description in SUGGESTED_TEAMS:
        if db.query(models.CommitteeTeam).filter(models.CommitteeTeam.fest_id == fest.id).count() >= MAX_TEAMS:
            break
        if _name_taken(db, fest, name):
            continue
        team = models.CommitteeTeam(fest_id=fest.id, name=name, description=description)
        db.add(team)
        db.flush()
        created.append(team)
    db.commit()
    return [_team_out(db, t) for t in created]


@router.patch("/{slug}/org/teams/{team_id}", response_model=schemas.CommitteeTeamOut)
def update_team(slug: str, team_id: int, data: schemas.CommitteeTeamUpdate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    team = _team(db, fest, team_id)
    updates = data.model_dump(exclude_unset=True)
    staff = is_fest_staff(db, fest.id, user)
    if not staff:
        # A head or co-head may describe their own team; naming it, choosing its leaders and its permissions stay with the core team
        if not committee.leads_team(db, fest.id, user, team.id):
            raise HTTPException(status_code=403, detail="Only the fest's director or core team can change the committee structure")
        if set(updates) - {"description"}:
            raise HTTPException(status_code=403, detail="A team's leaders can change its description. The core team sets its name, leaders and permissions.")
    if "name" in updates:
        if not updates["name"]:
            raise HTTPException(status_code=400, detail="A team needs a name")
        if _name_taken(db, fest, updates["name"], except_id=team.id):
            raise HTTPException(status_code=400, detail="This fest already has a team with that name")
        team.name = updates["name"]
    if "description" in updates:
        team.description = updates["description"] or None
    if updates.get("leaders_manage_team") is not None:
        team.leaders_manage_team = updates["leaders_manage_team"]
    if "head_member_id" in updates or "co_head_member_ids" in updates:
        _set_leaders(db, fest, team, user, updates)
    db.commit()
    db.refresh(team)
    return _team_out(db, team)


def _set_leaders(db: Session, fest: models.Fest, team: models.CommitteeTeam, actor, updates: dict) -> None:
    """
    Choose the head and co-heads. What is sent is the full picture for the team's leadership: anyone who led before and is
    not in it any more stays in the team as a plain member. Choosing someone moves them into this team.
    """
    current = db.query(models.FestMember).filter(models.FestMember.committee_team_id == team.id).all()
    old_head = next((m for m in current if m.team_role == committee.HEAD), None)
    head_id = updates["head_member_id"] if "head_member_id" in updates else (old_head.id if old_head else None)
    co_ids = updates["co_head_member_ids"] if "co_head_member_ids" in updates else [m.id for m in current if m.team_role == committee.CO_HEAD]
    if len(set(co_ids)) != len(co_ids):
        raise HTTPException(status_code=400, detail="The same person is listed twice")
    if head_id is not None and head_id in co_ids:
        raise HTTPException(status_code=400, detail="Someone cannot be both the head and a co-head")
    if len(co_ids) > schemas.MAX_CO_HEADS:
        raise HTTPException(status_code=400, detail=f"A team can have at most {schemas.MAX_CO_HEADS} co-heads")

    wanted = {}
    for member_id in ([head_id] if head_id is not None else []) + list(co_ids):
        m = db.query(models.FestMember).filter(models.FestMember.id == member_id, models.FestMember.fest_id == fest.id).first()
        if not m:
            raise HTTPException(status_code=400, detail="That person is not on this fest's committee")
        wanted[m.id] = m

    for m in current:
        if m.id not in wanted:
            m.team_role = committee.MEMBER
    for member_id, m in wanted.items():
        committee.drop_old_team_lead(db, m, team.id)
        committee.place(m, team, committee.HEAD if member_id == head_id else committee.CO_HEAD)
        # Only the head is offered Core access. A co-head keeps the access they have, unless the director raises it by hand
        if updates.get("give_core_access") and member_id == head_id and m.role == models.FestMemberRoleEnum.volunteer and _can_grant_core(db, fest, actor):
            m.role = models.FestMemberRoleEnum.core
    db.flush()
    committee.wire_reports(db, fest.id, team.id, old_head.id if old_head and old_head.id != head_id else None)


def _can_grant_core(db: Session, fest: models.Fest, user) -> bool:
    """Only the director (or an admin) can give someone the Core team access level."""
    return user.role == models.RoleEnum.admin or _is_owner(db, fest, user)


@router.delete("/{slug}/org/teams/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_team(slug: str, team_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _require_staff(db, fest, user)
    team = _team(db, fest, team_id)
    db.query(models.FestMember).filter(models.FestMember.committee_team_id == team.id).update({"committee_team_id": None, "team_role": committee.MEMBER}, synchronize_session=False)
    db.query(models.FestInvite).filter(models.FestInvite.committee_team_id == team.id).update({"committee_team_id": None, "team_role": committee.MEMBER}, synchronize_session=False)
    db.query(models.FestTask).filter(models.FestTask.committee_team_id == team.id).update({"committee_team_id": None}, synchronize_session=False)
    db.delete(team)
    db.commit()


@router.patch("/{slug}/org/members/{member_id}", response_model=schemas.FestMemberOut)
def place_member(slug: str, member_id: int, data: schemas.MemberPlacement, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """Set someone's title, team and lead. Only fields that are sent change; null clears one."""
    fest = _fest(db, slug)
    member = db.query(models.FestMember).filter(models.FestMember.id == member_id, models.FestMember.fest_id == fest.id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found in this fest")
    updates = data.model_dump(exclude_unset=True)
    if not is_fest_staff(db, fest.id, user):
        _check_leader_may_place(db, fest, user, member, updates)
    if member.role == models.FestMemberRoleEnum.owner and user.role != models.RoleEnum.admin and not _is_owner(db, fest, user):
        raise HTTPException(status_code=403, detail="Only the festival director can change the director's place in the chart")

    if "title" in updates:
        member.title = updates["title"] or None
    old_team_id, old_head_id = member.committee_team_id, None
    if "committee_team_id" in updates or "team_role" in updates:
        team = _team(db, fest, updates["committee_team_id"]) if updates.get("committee_team_id") is not None else (
            None if "committee_team_id" in updates else member.committee_team)
        role = updates.get("team_role") or (committee.MEMBER if (team is None or team.id != old_team_id) else member.team_role)
        if team is None and role != committee.MEMBER:
            raise HTTPException(status_code=400, detail="Pick a team first: a head or co-head leads a team")
        if role == committee.HEAD:
            previous = db.query(models.FestMember).filter(models.FestMember.committee_team_id == team.id, models.FestMember.team_role == committee.HEAD, models.FestMember.id != member.id).first()
            old_head_id = previous.id if previous else None
            committee.demote_other_heads(db, team.id, member.id)
        committee.drop_old_team_lead(db, member, team.id if team else None)
        committee.place(member, team, role)
        db.flush()
        if team is not None:
            committee.wire_reports(db, fest.id, team.id, old_head_id)
    if "reports_to_id" in updates:
        lead_id = updates["reports_to_id"]
        if lead_id is None:
            member.reports_to_id = None
        else:
            lead = db.query(models.FestMember).filter(models.FestMember.id == lead_id, models.FestMember.fest_id == fest.id).first()
            if not lead:
                raise HTTPException(status_code=400, detail="That person is not on this fest's committee")
            if lead.id == member.id:
                raise HTTPException(status_code=400, detail="Nobody can report to themselves")
            if _reports_in_a_loop(db, member.id, lead.id):
                raise HTTPException(status_code=400, detail="That would make the chart loop back on itself: that person already reports to them")
            member.reports_to_id = lead.id
    db.commit()
    db.refresh(member)
    return member


def _check_leader_may_place(db: Session, fest: models.Fest, user, member: models.FestMember, updates: dict) -> None:
    """A head or co-head can arrange people inside their own team: take them in or send them out, set their title and lead. Nothing wider."""
    mine = db.query(models.FestMember).filter(models.FestMember.fest_id == fest.id, models.FestMember.user_id == user.id).first()
    team_id = mine.committee_team_id if mine else None
    if not committee.leads_team(db, fest.id, user, team_id):
        raise HTTPException(status_code=403, detail="Only the fest's director or core team can change the committee structure")
    if member.role == models.FestMemberRoleEnum.owner:
        raise HTTPException(status_code=403, detail="Only the festival director can change the director's place in the chart")
    if member.committee_team_id not in (None, team_id):
        raise HTTPException(status_code=403, detail="That person is in another team. Ask the core team to move them.")
    target = updates.get("committee_team_id", member.committee_team_id)
    if target not in (None, team_id):
        raise HTTPException(status_code=403, detail="You can only place people in your own team")
    if updates.get("team_role") not in (None, committee.MEMBER):
        raise HTTPException(status_code=403, detail="Only the core team chooses a team's head and co-heads")
    if member.team_role in committee.LEADER_ROLES and member.id != (mine.id if mine else None) and "committee_team_id" in updates and target is None:
        raise HTTPException(status_code=403, detail="Only the core team can take a head or co-head out of the team")


def _is_owner(db: Session, fest: models.Fest, user) -> bool:
    return db.query(models.FestMember).filter(
        models.FestMember.fest_id == fest.id, models.FestMember.user_id == user.id, models.FestMember.role == models.FestMemberRoleEnum.owner
    ).first() is not None
