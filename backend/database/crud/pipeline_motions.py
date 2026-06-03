from __future__ import annotations

from typing import Iterable

from sqlalchemy.orm import Session
from enum import Enum

from backend.database import models as db_models
from backend.process import schema
from backend.database.crud.pipeline_core import find_congresista, _enum_value
from backend.database.raw_models import RawMotionDocument, RawMotionPage


def upsert_motion(db: Session, schema: schema.Motion) -> db_models.Motion:
    author = None
    if schema.author_name:
        author = find_congresista(
            db,
            name=schema.author_name,
            website=schema.author_web,
        )

    payload = {
        "id": schema.id,
        "motion_type": _enum_value(schema.motion_type),
        "summary_congreso": schema.summary_congreso,
        "observations": schema.observations or "",
        "status": schema.status,
        "author_id": author.id if author else None,
        "motion_approved": schema.motion_approved,
        "summary_oc": schema.summary_opencongress,
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
    db: Session,
    motion_id: str,
    person_id: int,
    role_type: Enum | str,
) -> db_models.MotionCongresistas:
    existing = db.get(db_models.MotionCongresistas, (motion_id, person_id))
    role_type = _enum_value(role_type)
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


def upsert_motion_organization(
    db: Session,
    motion_id: str,
    org_id: int,
    schema: schema.MotionOrganization,
) -> db_models.MotionOrganization:
    existing = db.get(db_models.MotionOrganization, (motion_id, org_id))
    payload = {
        "motion_id": motion_id,
        "org_id": org_id,
        "org_type": _enum_value(schema.org_type),
        "presentation_date": schema.presentation_date,
        "decision_date": schema.decision_date,
    }
    if existing is None:
        obj = db_models.MotionOrganization(**payload)
        db.add(obj)
        db.flush()
        return obj

    for key, value in payload.items():
        setattr(existing, key, value)
    db.flush()
    return existing


def upsert_motion_step(
    db: Session,
    schema: schema.MotionStep,
) -> db_models.MotionStep:
    existing = db.get(db_models.MotionStep, (schema.motion_id, schema.step_id))
    payload = {
        "motion_id": schema.motion_id,
        "step_id": schema.step_id,
        "vote_step": schema.vote_step,
        "vote_event_id": schema.vote_event_id,
        "step_type": _enum_value(schema.step_type),
        "step_date": schema.step_date,
        "step_detail": schema.step_detail,
    }
    if existing is None:
        obj = db_models.MotionStep(**payload)
        db.add(obj)
        db.flush()
        return obj

    for key, value in payload.items():
        setattr(existing, key, value)
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


def find_raw_motion_pages(
    raw_db: Session, motion_id: str, step_id: str | int, file_id: str | int
) -> list[RawMotionPage]:
    return (
        raw_db.query(RawMotionPage)
        .filter(
            RawMotionPage.motion_id == motion_id,
            RawMotionPage.step_id == str(step_id),
            RawMotionPage.file_id == str(file_id),
            RawMotionPage.last_update.is_(True),
        )
        .order_by(RawMotionPage.page_num)
        .all()
    )


def upsert_motion_text(
    db: Session,
    *,
    motion_id: str,
    step_id: int,
    file_id: int,
    version_id: int,
    text: str,
) -> db_models.MotionText:
    existing = db.get(db_models.MotionText, (motion_id, step_id, file_id, version_id))
    payload = {
        "motion_id": motion_id,
        "step_id": step_id,
        "file_id": file_id,
        "version_id": version_id,
        "text": text,
    }
    if existing is None:
        obj = db_models.MotionText(**payload)
        db.add(obj)
        db.flush()
        return obj

    for key, value in payload.items():
        setattr(existing, key, value)
    db.flush()
    return existing
