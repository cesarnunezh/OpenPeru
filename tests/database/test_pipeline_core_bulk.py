from datetime import date

import pytest

from backend import LegPeriod, RoleOrganization, TypeOrganization
from backend.database import models as db_models
from backend.database.crud import pipeline_core as crud_core
from backend.process import schema


@pytest.fixture()
def create_congresista(session):
    def _create_congresista(
        full_name: str = "María Grimaneza Acuña Peralta",
        first_name: str = "María Grimaneza",
        last_name: str = "Acuña Peralta",
        dni: str = "12345678",
        gender: str = "F",
        photo_url: str = "www.congreso.gob.pe/photo1",
        website: str = "https://www.congreso.gob.pe/congresistas2021/GrimanezaAcuna/",
    ) -> db_models.Congresista:
        cong = db_models.Congresista(
            full_name=full_name,
            first_name=first_name,
            last_name=last_name,
            dni=dni,
            gender=gender,
            photo_url=photo_url,
            website=website,
        )
        session.add(cong)
        session.flush()
        return cong

    return _create_congresista


def test_upsert_bancada_uses_organization_rows(session):
    existing = crud_core.upsert_organization(
        session,
        schema.Organization(
            org_name="Accion Popular",
            org_type=TypeOrganization.BANCADA,
        ),
    )

    same = crud_core.upsert_organization(
        session,
        schema.Organization(
            org_name="Accion Popular",
            org_type="Bancada",
        ),
    )
    inserted = crud_core.upsert_organization(
        session,
        schema.Organization(
            org_name="Fuerza Popular",
            org_type=TypeOrganization.BANCADA,
        ),
    )

    assert same.org_id == existing.org_id
    assert inserted.org_id != existing.org_id
    assert session.query(db_models.Organization).count() == 2


def test_upsert_bancada_membership_is_idempotent(session, create_congresista):
    congresista = create_congresista()
    bancada = crud_core.upsert_organization(
        session,
        schema.Organization(
            org_name="Accion Popular",
            org_type=TypeOrganization.BANCADA,
        ),
    )

    first = crud_core.upsert_membership(
        session,
        person_id=congresista.id,
        org_id=bancada.org_id,
        leg_period=LegPeriod.PERIODO_2021_2026,
        org_type=TypeOrganization.BANCADA,
        role=RoleOrganization.MIEMBRO,
        start_date=date(2025, 7, 28),
        end_date=date(2026, 7, 28),
    )
    second = crud_core.upsert_membership(
        session,
        person_id=congresista.id,
        org_id=bancada.org_id,
        leg_period="2021-2026",
        org_type="Bancada",
        role="Miembro",
        start_date=date(2025, 7, 28),
        end_date=date(2026, 7, 28),
    )

    assert second.id == first.id
    assert session.query(db_models.BancadaMembership).count() == 1
    assert session.query(db_models.Membership).count() == 1
