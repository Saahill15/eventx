"""Image uploads for fest banners and event covers. Stored in the database and served with long caching."""

import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Response
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth.dependencies import require_organizer
from app.database import get_db

router = APIRouter()

MAX_IMAGE_BYTES = 3 * 1024 * 1024
MAX_UPLOADS_PER_DAY = 30


def _sniff_image(data: bytes):
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


@router.post("", response_model=schemas.MediaOut, status_code=201)
async def upload_image(file: UploadFile = File(...), db: Session = Depends(get_db), current_user: models.User = Depends(require_organizer)):
    """Upload a JPEG, PNG or WebP image up to 3 MB. Use the returned url as a fest banner or event cover."""
    today = db.query(models.Media).filter(models.Media.owner_id == current_user.id, models.Media.created_at > datetime.utcnow() - timedelta(days=1)).count()
    if today >= MAX_UPLOADS_PER_DAY:
        raise HTTPException(status_code=429, detail="Upload limit reached for today. Try again tomorrow.")
    content = await file.read(MAX_IMAGE_BYTES + 1)
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="That image is too large. The limit is 3 MB.")
    mime = _sniff_image(content)
    if mime is None:
        raise HTTPException(status_code=400, detail="Upload a JPEG, PNG or WebP image.")
    media = models.Media(id=secrets.token_hex(16), owner_id=current_user.id, mime=mime, size=len(content), data=content, created_at=datetime.utcnow())
    db.add(media)
    db.commit()
    return schemas.MediaOut(id=media.id, url=f"/api/media/{media.id}")


@router.get("/{media_id}")
def get_image(media_id: str, db: Session = Depends(get_db)):
    media = db.query(models.Media).filter(models.Media.id == media_id).first()
    if not media:
        raise HTTPException(status_code=404, detail="Image not found")
    return Response(
        content=media.data,
        media_type=media.mime,
        headers={"Cache-Control": "public, max-age=31536000, immutable", "X-Content-Type-Options": "nosniff", "Content-Security-Policy": "default-src 'none'"},
    )
