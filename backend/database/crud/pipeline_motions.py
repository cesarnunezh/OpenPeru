from __future__ import annotations

from typing import Iterable

from sqlalchemy.orm import Session

from backend import classify_motion_des_estado
from backend.database import models as db_models
from backend.database.crud.pipeline_core import find_congresista
from backend.database.raw_models import RawMotionDocument


def upsert_motion(db: Session, schema) -> db_models.Motion:
    author = None
    if schema.author_name:
        author = find_congresista(
            db,
            name=schema.author_name,
            leg_period=schema.leg_period,
            website=schema.author_web,
        )

    payload = {
        "id": schema.id,
        "leg_period": schema.leg_period,
        "legislature": schema.legislature,
        "presentation_date": schema.presentation_date,
        "motion_type": schema.motion_type,
        "summary": schema.summary,
        "observations": schema.observations or "",
        "complete_text": schema.complete_text or "",
        "status": schema.status,
        "author_id": author.id if author else None,
        "motion_approved": schema.motion_approved,
    }

    existing = db.get(db_models.Motion, schema.id)
    if existing is None:
        obj = db_models.Motion(**payload)
        db.add(obj)
        db.flush()
        return obj

    for key, value in payload.items():
        setattr(existing, key, value)
    db.flush()
    return existing


def upsert_motion_congresista(
    db: Session, motion_id: str, person_id: int, role_type
) -> db_models.MotionCongresistas:
    existing = db.get(db_models.MotionCongresistas, (motion_id, person_id))
    if existing is None:
        obj = db_models.MotionCongresistas(
            motion_id=motion_id,
            person_id=person_id,
            role_type=role_type,
        )
        db.add(obj)
        db.flush()
        return obj

    existing.role_type = role_type
    db.flush()
    return existing


def upsert_motion_step(
    db: Session,
    *,
    step_id: int,
    motion_id: str,
    step_date,
    step_detail: str,
    step_status: str | None = None,
) -> db_models.MotionStep:
    step_type = classify_motion_des_estado(step_status or step_detail)
    existing = db.get(db_models.MotionStep, step_id)
    if existing is None:
        obj = db_models.MotionStep(
            id=step_id,
            motion_id=motion_id,
            step_type=step_type,
            step_date=step_date,
            step_detail=step_detail,
        )
        db.add(obj)
        db.flush()
        return obj

    existing.motion_id = motion_id
    existing.step_type = step_type
    existing.step_date = step_date
    existing.step_detail = step_detail
    db.flush()
    return existing


def find_raw_motion_documents(
    raw_db: Session, motion_id: str
) -> Iterable[RawMotionDocument]:
    return (
        raw_db.query(RawMotionDocument)
        .filter(
            RawMotionDocument.motion_id == motion_id,
            RawMotionDocument.last_update.is_(True),
            RawMotionDocument.processed.is_(False),
        )
        .all()
    )


def upsert_motion_document(
    db: Session,
    *,
    motion_id: str,
    step_id: int,
    archivo_id: int,
    url: str,
    text: str,
    vote_doc: bool,
) -> db_models.MotionDocument:
    existing = db.get(db_models.MotionDocument, archivo_id)
    if existing is None:
        obj = db_models.MotionDocument(
            motion_id=motion_id,
            step_id=step_id,
            archivo_id=archivo_id,
            url=url,
            text=text,
            vote_doc=vote_doc,
        )
        db.add(obj)
        db.flush()
        return obj

    existing.motion_id = motion_id
    existing.step_id = step_id
    existing.url = url
    existing.text = text
    existing.vote_doc = vote_doc
    db.flush()
    return existing
