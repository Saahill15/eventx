"""
Committee tasks: who does what by when.

  GET    /api/fests/{slug}/tasks              the fest's tasks (any committee member); filter with ?status= ?team_id= ?assignee=me|<member id> ?overdue=true
  POST   /api/fests/{slug}/tasks              add a task (director or core team)
  PATCH  /api/fests/{slug}/tasks/{id}         change a task. Staff change anything; the person it is assigned to can move its status
  DELETE /api/fests/{slug}/tasks/{id}         delete a task (director or core team)
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth.dependencies import get_current_user
from app.database import get_db
from app.permissions import is_fest_member, is_fest_staff

router = APIRouter()

MAX_TASKS = 500


def _fest(db: Session, slug: str) -> models.Fest:
    fest = db.query(models.Fest).filter(models.Fest.slug == slug).first()
    if not fest:
        raise HTTPException(status_code=404, detail="Fest not found")
    return fest


def _my_member(db: Session, fest: models.Fest, user):
    return db.query(models.FestMember).filter(models.FestMember.fest_id == fest.id, models.FestMember.user_id == user.id).first()


def _task(db: Session, fest: models.Fest, task_id: int) -> models.FestTask:
    task = db.query(models.FestTask).filter(models.FestTask.id == task_id, models.FestTask.fest_id == fest.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


def _check_links(db: Session, fest: models.Fest, assignee_id, team_id, meeting_id=None) -> None:
    if meeting_id is not None and not db.query(models.FestMeeting).filter(models.FestMeeting.id == meeting_id, models.FestMeeting.fest_id == fest.id).first():
        raise HTTPException(status_code=400, detail="That meeting does not belong to this fest")
    if assignee_id is not None and not db.query(models.FestMember).filter(models.FestMember.id == assignee_id, models.FestMember.fest_id == fest.id).first():
        raise HTTPException(status_code=400, detail="That person is not on this fest's committee")
    if team_id is not None and not db.query(models.CommitteeTeam).filter(models.CommitteeTeam.id == team_id, models.CommitteeTeam.fest_id == fest.id).first():
        raise HTTPException(status_code=400, detail="That team does not belong to this fest")


def _set_status(task: models.FestTask, new_status: str) -> None:
    task.status = new_status
    task.completed_at = datetime.utcnow() if new_status == "done" else None


@router.get("/{slug}/tasks", response_model=List[schemas.TaskOut])
def list_tasks(
    slug: str,
    status_filter: Optional[str] = Query(default=None, alias="status", pattern="^(todo|doing|done)$"),
    team_id: Optional[int] = None,
    assignee: Optional[str] = Query(default=None, pattern=r"^(me|\d+)$"),
    overdue: bool = False,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    fest = _fest(db, slug)
    if not is_fest_member(db, fest.id, user):
        raise HTTPException(status_code=403, detail="Only the fest's committee can see its tasks")
    q = db.query(models.FestTask).filter(models.FestTask.fest_id == fest.id)
    if status_filter:
        q = q.filter(models.FestTask.status == status_filter)
    if team_id is not None:
        q = q.filter(models.FestTask.committee_team_id == team_id)
    if assignee == "me":
        mine = _my_member(db, fest, user)
        q = q.filter(models.FestTask.assignee_member_id == (mine.id if mine else -1))
    elif assignee:
        q = q.filter(models.FestTask.assignee_member_id == int(assignee))
    tasks = q.order_by(models.FestTask.due_date.is_(None), models.FestTask.due_date, models.FestTask.id).all()
    if overdue:
        tasks = [t for t in tasks if t.overdue]
    return tasks


@router.post("/{slug}/tasks", response_model=schemas.TaskOut, status_code=status.HTTP_201_CREATED)
def add_task(slug: str, data: schemas.TaskIn, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    if not is_fest_staff(db, fest.id, user):
        raise HTTPException(status_code=403, detail="Only the fest's director or core team can add tasks")
    if db.query(models.FestTask).filter(models.FestTask.fest_id == fest.id).count() >= MAX_TASKS:
        raise HTTPException(status_code=400, detail=f"A fest can have at most {MAX_TASKS} tasks. Delete finished ones first.")
    _check_links(db, fest, data.assignee_member_id, data.committee_team_id, data.meeting_id)
    task = models.FestTask(
        fest_id=fest.id, title=data.title, description=data.description or None, due_date=data.due_date,
        assignee_member_id=data.assignee_member_id, committee_team_id=data.committee_team_id, meeting_id=data.meeting_id, created_by_id=user.id,
    )
    _set_status(task, data.status)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.patch("/{slug}/tasks/{task_id}", response_model=schemas.TaskOut)
def update_task(slug: str, task_id: int, data: schemas.TaskUpdate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    if not is_fest_member(db, fest.id, user):
        raise HTTPException(status_code=403, detail="Only the fest's committee can change its tasks")
    task = _task(db, fest, task_id)
    updates = data.model_dump(exclude_unset=True)

    if not is_fest_staff(db, fest.id, user):
        mine = _my_member(db, fest, user)
        if not mine or task.assignee_member_id != mine.id:
            raise HTTPException(status_code=403, detail="Only the director, the core team, or the person it is assigned to can change this task")
        if set(updates) - {"status"}:
            raise HTTPException(status_code=403, detail="You can move your own task along, but only the core team can change its details")

    if "title" in updates:
        if not updates["title"]:
            raise HTTPException(status_code=400, detail="A task needs a title")
        task.title = updates["title"]
    if "description" in updates:
        task.description = updates["description"] or None
    if "due_date" in updates:
        task.due_date = updates["due_date"]
    if "meeting_id" in updates:
        _check_links(db, fest, None, None, updates["meeting_id"])
        task.meeting_id = updates["meeting_id"]
    if "assignee_member_id" in updates or "committee_team_id" in updates:
        _check_links(db, fest, updates.get("assignee_member_id"), updates.get("committee_team_id"))
        if "assignee_member_id" in updates:
            task.assignee_member_id = updates["assignee_member_id"]
        if "committee_team_id" in updates:
            task.committee_team_id = updates["committee_team_id"]
    if "status" in updates and updates["status"] is not None:
        _set_status(task, updates["status"])
    db.commit()
    db.refresh(task)
    return task


@router.delete("/{slug}/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(slug: str, task_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    if not is_fest_staff(db, fest.id, user):
        raise HTTPException(status_code=403, detail="Only the fest's director or core team can delete tasks")
    db.delete(_task(db, fest, task_id))
    db.commit()
