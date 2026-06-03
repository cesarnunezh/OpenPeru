from __future__ import annotations

from sqlalchemy import select, or_, func
from sqlalchemy.orm import Session
from datetime import datetime, date
from dataclasses import dataclass
from typing import Type
from enum import Enum

from backend import TypeOrganization
from backend.database import models as db_models
from backend.process import schema
from backend.database.raw_models import ScraperRun


@dataclass
class ProcessStats:
    processed: int = 0
    skipped: int = 0
    errors: int = 0


@dataclass
class ScraperStats:
    start_time: datetime
    end_time: datetime
    scrapped: int = 0


MEMBERSHIP_MODELS = {
    TypeOrganization.BANCADA.value: db_models.BancadaMembership,
    TypeOrganization.PARTY.value: db_models.PartyMembership,
    TypeOrganization.CHAMBER.value: db_models.ChamberMembership,
    TypeOrganization.COMMITTEE.value: db_models.CommitteeMembership,
    TypeOrganization.ADMINISTRATIVE.value: db_models.AdminMembership,
}


def _enum_value(value: Enum | str) -> str:
    return value.value if hasattr(value, "value") else str(value)


def find_congresista(
    db: Session,
    name: str,
    website: str | None = None,
    threshold: float = 0.9,
) -> db_models.Congresista | None:
    """
    Find a congressperson by website or fuzzy full-name match.

    The function first searches by website when a website is provided, since it is
    expected to be a more stable identifier than the person's name. If no match is
    found by website, or if no website is provided, it falls back to searching by
    full name.

    Args:
        db (Session): Active SQLAlchemy database session.
        name (str): Full name of the congressperson to search for.
        website (str | None, optional): Congressperson website URL. Defaults to None.
        threshold (float, optional): Minimum Jaro-Winkler similarity score.
            Defaults to 0.9.

    Returns:
        db_models.Congresista | None: The matching congressperson if found;
        otherwise, None.
    """

    if website:
        by_web = db.scalar(
            select(db_models.Congresista).where(
                db_models.Congresista.website == website.strip()
            )
        )
        if by_web is not None:
            return by_web

    normalized_name = name.strip().lower()

    score = func.jarowinkler(
        func.unaccent(func.lower(db_models.Congresista.full_name)),
        func.unaccent(normalized_name),
    )

    stmt = (
        select(db_models.Congresista)
        .where(score >= threshold)
        .order_by(
            score.desc(),
            db_models.Congresista.id.asc(),
        )
        .limit(1)
    )

    return db.scalar(stmt)


def find_organization(
    db: Session,
    org_name: str,
    org_type: TypeOrganization | str,
    threshold: float = 0.9,
) -> db_models.Organization | None:
    """
    Find the closest organization by fuzzy name match and organization type.
    """

    if isinstance(org_type, str):
        org_type = TypeOrganization(org_type)

    normalized_name = org_name.strip().lower()

    score = func.jarowinkler(
        func.unaccent(func.lower(db_models.Organization.org_name)),
        func.unaccent(normalized_name),
    )

    stmt = (
        select(db_models.Organization)
        .where(
            db_models.Organization.org_type == org_type,
            score >= threshold,
        )
        .order_by(
            score.desc(),
            db_models.Organization.org_id.asc(),
        )
        .limit(1)
    )

    return db.scalar(stmt)


def find_active_bancada_for_person(
    db: Session, person_id: int, at_date: date | datetime
) -> db_models.Organization | None:
    if isinstance(at_date, datetime):
        at_date = at_date.date()

    return db.scalar(
        select(db_models.Organization)
        .join(
            db_models.Membership,
            db_models.Membership.org_id == db_models.Organization.org_id,
        )
        .where(
            db_models.Membership.person_id == person_id,
            db_models.Membership.org_type == TypeOrganization.BANCADA.value,
            db_models.Membership.start_date <= at_date,
            or_(
                db_models.Membership.end_date.is_(None),
                db_models.Membership.end_date >= at_date,
            ),
        )
        .order_by(db_models.Membership.start_date.desc())
        .limit(1)
    )


def _upsert_model(
    db: Session,
    *,
    existing: db_models.Congresista
    | db_models.Organization
    | db_models.Membership
    | db_models.Ley,
    model: Type[db_models.Congresista]
    | Type[db_models.Organization]
    | Type[db_models.Membership]
    | Type[db_models.Ley],
    payload: dict,
) -> (
    db_models.Congresista
    | db_models.Organization
    | db_models.Membership
    | db_models.Ley
):
    if existing is None:
        obj = model(**payload)
        db.add(obj)
        db.flush()
        return obj

    for key, value in payload.items():
        setattr(existing, key, value)

    db.flush()
    return existing


def upsert_congresista(
    db: Session, schema: schema.Congresista
) -> db_models.Congresista:
    existing = find_congresista(db, schema.full_name, schema.website)
    payload = schema.model_dump()

    return _upsert_model(
        db,
        existing=existing,
        model=db_models.Congresista,
        payload=payload,
    )


def upsert_organization(
    db: Session, schema: schema.Organization
) -> db_models.Organization:
    payload = schema.model_dump()

    parent_name = payload.pop("parent_org_name", None)
    parent_type = payload.pop("parent_org_type", None)

    parent_id = None
    if parent_name and parent_type:
        parent = find_organization(
            db,
            org_name=parent_name,
            org_type=parent_type,
        )

        if parent is None:
            raise ValueError(
                f"Parent organization not found: {parent_name} ({parent_type})"
            )

        parent_id = parent.org_id

    payload["parent_org_id"] = parent_id

    payload["org_type"] = _enum_value(payload["org_type"])
    if payload.get("org_subtype") is not None:
        payload["org_subtype"] = _enum_value(payload["org_subtype"])

    existing = find_organization(db, schema.org_name, schema.org_type)

    return _upsert_model(
        db,
        existing=existing,
        model=db_models.Organization,
        payload=payload,
    )


def upsert_membership(
    db: Session,
    *,
    person_id: int,
    org_id: int,
    leg_period: str,
    org_type: str | TypeOrganization,
    role: str,
    start_date: date,
    end_date: date,
    extra_fields: dict | None = None,
) -> db_models.Membership:
    org_type_value = _enum_value(org_type)
    role_value = _enum_value(role)
    leg_period_value = _enum_value(leg_period)
    model = MEMBERSHIP_MODELS[org_type_value]

    payload = {
        "person_id": person_id,
        "org_id": org_id,
        "leg_period": leg_period_value,
        "org_type": org_type_value,
        "role": role_value,
        "start_date": start_date,
        "end_date": end_date,
    }

    if extra_fields:
        payload.update(extra_fields)

    existing = db.scalars(
        select(db_models.Membership).where(
            db_models.Membership.person_id == person_id,
            db_models.Membership.org_id == org_id,
            db_models.Membership.leg_period == leg_period_value,
            db_models.Membership.org_type == org_type_value,
            db_models.Membership.role == role_value,
            db_models.Membership.start_date == start_date,
            db_models.Membership.end_date == end_date,
        )
    ).first()

    return _upsert_model(
        db,
        existing=existing,
        model=model,
        payload=payload,
    )


def upsert_ley(db: Session, schema: schema.Ley) -> db_models.Ley:
    payload = {
        "id": schema.id,
        "title": schema.title,
        "bill_id": schema.bill_id,
    }

    existing = db.get(db_models.Ley, schema.id)

    return _upsert_model(db, existing=existing, model=db_models.Ley, payload=payload)


def upsert_scraper_run(db: Session, scraper_name: str, stats: ScraperStats):
    obj = ScraperRun(
        scraper_name=scraper_name,
        start_time=stats.start_time,
        end_time=stats.end_time,
        scraped_rows=stats.scrapped,
    )

    db.add(obj)
    db.commit()
