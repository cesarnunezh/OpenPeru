import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import LegPeriod, LegislativeYear
from backend.database import models as db_models
from backend.database.crud import pipeline_core as crud_core


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    db_models.Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as db:
        yield db


def _create_congresista(
    db, *, name: str, website: str, leg_period=LegPeriod.PERIODO_2021_2026
):
    cong = db_models.Congresista(
        nombre=name,
        leg_period=leg_period,
        party_name="party",
        current_bancada="bancada",
        votes_in_election=1,
        dist_electoral="Lima",
        condicion="Activo",
        website=website,
        photo_url="https://example.com/photo.png",
    )
    db.add(cong)
    db.flush()
    return cong


def test_upsert_bancadas_bulk_inserts_missing_and_reuses_existing(session):
    session.add(
        db_models.Bancada(
            leg_year=LegislativeYear.YEAR_2025_2026,
            bancada_name="Accion Popular",
        )
    )
    session.flush()

    index, inserted_count, existing_count = crud_core.upsert_bancadas_bulk(
        session,
        [
            ("2025", "ACCION POPULAR"),
            ("2025", "Fuerza Popular"),
            ("2025", "Fuerza Popular"),
        ],
    )

    assert inserted_count == 1
    assert existing_count == 1
    assert ("2025", "accion popular") in index
    assert ("2025", "fuerza popular") in index

    _, inserted_count_2, existing_count_2 = crud_core.upsert_bancadas_bulk(
        session,
        [("2025", "Accion Popular"), ("2025", "Fuerza Popular")],
    )
    assert inserted_count_2 == 0
    assert existing_count_2 == 2


def test_upsert_bancada_memberships_bulk_is_idempotent(session):
    b1 = db_models.Bancada(
        leg_year=LegislativeYear.YEAR_2025_2026,
        bancada_name="Accion Popular",
    )
    b2 = db_models.Bancada(
        leg_year=LegislativeYear.YEAR_2025_2026,
        bancada_name="Fuerza Popular",
    )
    session.add_all([b1, b2])
    session.flush()

    c1 = _create_congresista(
        session, name="Juan Perez", website="https://example.com/1"
    )
    c2 = _create_congresista(
        session, name="Maria Lopez", website="https://example.com/2"
    )

    session.add(
        db_models.BancadaMembership(
            leg_year=LegislativeYear.YEAR_2025_2026,
            person_id=c1.id,
            bancada_id=b1.bancada_id,
        )
    )
    session.flush()

    inserted_count = crud_core.upsert_bancada_memberships_bulk(
        session,
        [
            ("2025", c1.id, b1.bancada_id),
            ("2025", c1.id, b1.bancada_id),
            ("2025", c2.id, b2.bancada_id),
        ],
    )
    assert inserted_count == 1
    assert session.query(db_models.BancadaMembership).count() == 2

    inserted_count_2 = crud_core.upsert_bancada_memberships_bulk(
        session,
        [("2025", c1.id, b1.bancada_id), ("2025", c2.id, b2.bancada_id)],
    )
    assert inserted_count_2 == 0
    assert session.query(db_models.BancadaMembership).count() == 2
