"""
Committee structure: the teams a fest's committee is organised into, and where each person sits.

The access level (director, core team, volunteer) stays three simple tiers, because that is what decides who can manage
what. On top of it every fest uses its own words: teams (Sponsorship, PR, Logistics...), a title for each person, and who
reports to whom, which draws the organisation chart.

  GET    /api/fests/{slug}/org                       teams and members together, for the chart (any committee member)
  POST   /api/fests/{slug}/org/teams                 add a team
  POST   /api/fests/{slug}/org/teams/suggested       add a usual set of teams (skips names that exist)
  PATCH  /api/fests/{slug}/org/teams/{id}            rename or describe a team
  DELETE /api/fests/{slug}/org/teams/{id}            delete a team; its people stay, without a team
  PATCH  /api/fests/{slug}/org/members/{member_id}   set a person's title, team and lead
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models, schemas
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
    count = db.query(models.FestMember).filter(models.FestMember.committee_team_id == team.id).count()
    return schemas.CommitteeTeamOut(id=team.id, fest_id=team.fest_id, name=team.name, description=team.description, member_count=count)


def _name_taken(db: Session, fest: models.Fest, name: str, except_id=None) -> bool:
    q = db.query(models.CommitteeTeam).filter(models.CommitteeTeam.fest_id == fest.id, func.lower(models.CommitteeTeam.name) == name.lower())
    if except_id is not None:
        q = q.filter(models.CommitteeTeam.id != except_id)
    return q.first() is not None


def _reports_in_a_loop(db: Session, member_id: int, new_lead_id) -> bool:
    """Would making new_lead_id this person's lead make the chain loop back to them?"""
    seen = set()
    current = new_lead_id
    while current is not None:
        if current == member_id or current in seen:
            return True
        seen.add(current)
        current = db.query(models.FestMember.reports_to_id).filter(models.FestMember.id == current).scalar()
    return False


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
    _require_staff(db, fest, user)
    team = _team(db, fest, team_id)
    updates = data.model_dump(exclude_unset=True)
    if "name" in updates:
        if not updates["name"]:
            raise HTTPException(status_code=400, detail="A team needs a name")
        if _name_taken(db, fest, updates["name"], except_id=team.id):
            raise HTTPException(status_code=400, detail="This fest already has a team with that name")
        team.name = updates["name"]
    if "description" in updates:
        team.description = updates["description"] or None
    db.commit()
    db.refresh(team)
    return _team_out(db, team)


@router.delete("/{slug}/org/teams/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_team(slug: str, team_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _require_staff(db, fest, user)
    team = _team(db, fest, team_id)
    db.query(models.FestMember).filter(models.FestMember.committee_team_id == team.id).update({"committee_team_id": None}, synchronize_session=False)
    db.query(models.FestTask).filter(models.FestTask.committee_team_id == team.id).update({"committee_team_id": None}, synchronize_session=False)
    db.delete(team)
    db.commit()


@router.patch("/{slug}/org/members/{member_id}", response_model=schemas.FestMemberOut)
def place_member(slug: str, member_id: int, data: schemas.MemberPlacement, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """Set someone's title, team and lead. Only fields that are sent change; null clears one."""
    fest = _fest(db, slug)
    _require_staff(db, fest, user)
    member = db.query(models.FestMember).filter(models.FestMember.id == member_id, models.FestMember.fest_id == fest.id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found in this fest")
    if member.role == models.FestMemberRoleEnum.owner and user.role != models.RoleEnum.admin and not _is_owner(db, fest, user):
        raise HTTPException(status_code=403, detail="Only the festival director can change the director's place in the chart")

    updates = data.model_dump(exclude_unset=True)
    if "title" in updates:
        member.title = updates["title"] or None
    if "committee_team_id" in updates:
        if updates["committee_team_id"] is None:
            member.committee_team_id = None
        else:
            member.committee_team_id = _team(db, fest, updates["committee_team_id"]).id
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


def _is_owner(db: Session, fest: models.Fest, user) -> bool:
    return db.query(models.FestMember).filter(
        models.FestMember.fest_id == fest.id, models.FestMember.user_id == user.id, models.FestMember.role == models.FestMemberRoleEnum.owner
    ).first() is not None
