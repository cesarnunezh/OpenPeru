from __future__ import annotations

from sqlalchemy import func, tuple_
from sqlalchemy.orm import Session

from backend import find_leg_period
from backend.database import models as db_models
from backend.process import schema


def _normalize_leg_year(leg_year) -> str:
    return str(leg_year.value) if hasattr(leg_year, "value") else str(leg_year)


def find_congresista(
    db: Session, name: str, leg_period, website: str | None = None
) -> db_models.Congresista | None:
    if website:
        by_web = (
            db.query(db_models.Congresista)
            .filter(db_models.Congresista.website == website)
            .first()
        )
        if by_web is not None:
            return by_web
    return (
        db.query(db_models.Congresista)
        .filter(
            db_models.Congresista.nombre == name,
            db_models.Congresista.leg_period == leg_period,
        )
        .first()
    )


def find_organization(
    db: Session, org_name: str, leg_period, leg_year: int | str
) -> db_models.Organization | None:
    return (
        db.query(db_models.Organization)
        .filter(
            db_models.Organization.org_name == org_name,
            db_models.Organization.leg_period == find_leg_period(str(leg_year)),
            db_models.Organization.leg_year == str(leg_year),
        )
        .first()
    )


def upsert_congresista(
    db: Session, schema: schema.Congresista
) -> db_models.Congresista:
    existing = find_congresista(db, schema.nombre, schema.leg_period, schema.website)
    payload = schema.model_dump()

    if existing is None:
        obj = db_models.Congresista(**payload)
        db.add(obj)
        db.flush()
        return obj

    for key, value in payload.items():
        setattr(existing, key, value)
    db.flush()
    return existing


def upsert_organization(
    db: Session, schema: schema.Organization
) -> db_models.Organization:
    existing = (
        db.query(db_models.Organization)
        .filter(
            db_models.Organization.leg_period == schema.leg_period,
            db_models.Organization.leg_year == schema.leg_year,
            db_models.Organization.org_name == schema.org_name,
            db_models.Organization.org_type == schema.org_type,
        )
        .first()
    )
    payload = schema.model_dump()

    if existing is None:
        obj = db_models.Organization(**payload)
        db.add(obj)
        db.flush()
        return obj

    for key, value in payload.items():
        setattr(existing, key, value)
    db.flush()
    return existing


def upsert_membership(
    db: Session, *, person_id: int, org_id: int, role, start_date, end_date
) -> db_models.Membership:
    existing = (
        db.query(db_models.Membership)
        .filter(
            db_models.Membership.person_id == person_id,
            db_models.Membership.org_id == org_id,
            db_models.Membership.role == role,
            db_models.Membership.start_date == start_date,
            db_models.Membership.end_date == end_date,
        )
        .first()
    )
    if existing is not None:
        return existing

    obj = db_models.Membership(
        person_id=person_id,
        org_id=org_id,
        role=role,
        start_date=start_date,
        end_date=end_date,
    )
    db.add(obj)
    db.flush()
    return obj


def upsert_bancada(db: Session, leg_year, bancada_name: str) -> db_models.Bancada:
    normalized_leg_year = _normalize_leg_year(leg_year)
    existing = (
        db.query(db_models.Bancada)
        .filter(
            db_models.Bancada.leg_year == normalized_leg_year,
            func.lower(db_models.Bancada.bancada_name) == bancada_name.lower(),
        )
        .first()
    )
    if existing is not None:
        return existing

    obj = db_models.Bancada(leg_year=normalized_leg_year, bancada_name=bancada_name)
    db.add(obj)
    db.flush()
    return obj


def upsert_bancadas_bulk(
    db: Session, rows: list[tuple]
) -> tuple[dict[tuple[str, str], db_models.Bancada], int, int]:
    """
    Batch upsert bancadas.

    Returns:
        - index: {(leg_year_str, bancada_name_lower): Bancada}
        - inserted_count
        - existing_count
    """
    if not rows:
        return {}, 0, 0

    deduped: dict[tuple[str, str], str] = {}
    for leg_year, bancada_name in rows:
        normalized_leg_year = _normalize_leg_year(leg_year)
        key = (normalized_leg_year, bancada_name.lower())
        deduped.setdefault(key, bancada_name)

    years = {key[0] for key in deduped}
    names_lower = {key[1] for key in deduped}

    existing = (
        db.query(db_models.Bancada)
        .filter(
            db_models.Bancada.leg_year.in_(years),
            func.lower(db_models.Bancada.bancada_name).in_(names_lower),
        )
        .all()
    )
    index: dict[tuple[str, str], db_models.Bancada] = {
        (_normalize_leg_year(row.leg_year), row.bancada_name.lower()): row
        for row in existing
    }

    to_insert: list[db_models.Bancada] = []
    existing_count = 0
    for key, original_name in deduped.items():
        if key in index:
            existing_count += 1
            continue
        to_insert.append(db_models.Bancada(leg_year=key[0], bancada_name=original_name))

    if to_insert:
        db.add_all(to_insert)
        db.flush()
        for row in to_insert:
            index[(_normalize_leg_year(row.leg_year), row.bancada_name.lower())] = row

    return index, len(to_insert), existing_count


def upsert_bancada_membership(
    db: Session, *, leg_year, person_id: int, bancada_id: int
) -> db_models.BancadaMembership:
    normalized_leg_year = _normalize_leg_year(leg_year)
    existing = (
        db.query(db_models.BancadaMembership)
        .filter(
            db_models.BancadaMembership.leg_year == normalized_leg_year,
            db_models.BancadaMembership.person_id == person_id,
            db_models.BancadaMembership.bancada_id == bancada_id,
        )
        .first()
    )
    if existing is not None:
        return existing

    obj = db_models.BancadaMembership(
        leg_year=normalized_leg_year,
        person_id=person_id,
        bancada_id=bancada_id,
    )
    db.add(obj)
    db.flush()
    return obj


def upsert_bancada_memberships_bulk(db: Session, rows: list[tuple]) -> int:
    """
    Batch insert missing bancada memberships.

    Args:
        rows: [(leg_year, person_id, bancada_id), ...]

    Returns:
        inserted_count
    """
    if not rows:
        return 0

    keys = {
        (_normalize_leg_year(leg_year), person_id, bancada_id)
        for leg_year, person_id, bancada_id in rows
    }
    if not keys:
        return 0

    existing_keys = set(
        db.query(
            db_models.BancadaMembership.leg_year,
            db_models.BancadaMembership.person_id,
            db_models.BancadaMembership.bancada_id,
        )
        .filter(
            tuple_(
                db_models.BancadaMembership.leg_year,
                db_models.BancadaMembership.person_id,
                db_models.BancadaMembership.bancada_id,
            ).in_(keys)
        )
        .all()
    )

    to_insert = [
        db_models.BancadaMembership(
            leg_year=leg_year,
            person_id=person_id,
            bancada_id=bancada_id,
        )
        for leg_year, person_id, bancada_id in keys
        if (leg_year, person_id, bancada_id) not in existing_keys
    ]
    if not to_insert:
        return 0

    db.add_all(to_insert)
    db.flush()
    return len(to_insert)


def upsert_ley(db: Session, schema: schema.Ley) -> db_models.Ley:

    payload = {
        "id": schema.id,
        "title": schema.title,
        "bill_id": schema.bill_id,
    }

    existing = db.get(db_models.Ley, schema.id)
    if existing is None:
        obj = db_models.Ley(**payload)
        db.add(obj)
        db.flush()
        return obj

    for key, value in payload.items():
        setattr(existing, key, value)
    db.flush()
    return existing
