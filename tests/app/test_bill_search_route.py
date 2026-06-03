from __future__ import annotations

from datetime import date as real_date
import unicodedata

from backend.core.enums import Proponents
from backend.core.enums import TypeBillStep, TypeOrganization
from backend.database.models import (
    Base,
    Bill,
    BillOrganization,
    BillStep,
    CommitteeMembership,
    Congresista,
    Ley,
    PartyMembership,
    Organization,
)

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker


class FixedDate(real_date):
    @classmethod
    def today(cls):
        return cls(2026, 5, 24)


def _register_unaccent(engine):
    @event.listens_for(engine, "connect")
    def _unaccent_on_connect(dbapi_connection, connection_record):
        if dbapi_connection.__class__.__module__.startswith("sqlite3"):
            dbapi_connection.create_function(
                "unaccent",
                1,
                lambda value: (
                    None
                    if value is None
                    else "".join(
                        character
                        for character in unicodedata.normalize("NFKD", str(value))
                        if not unicodedata.combining(character)
                    )
                ),
            )


@pytest.fixture()
def session_factory(tmp_path):
    db_path = tmp_path / "processed_test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    _register_unaccent(engine)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    yield Session
    engine.dispose()


@pytest.fixture()
def client(monkeypatch, session_factory):
    import app.routes.bills as bills_module
    from app.app import create_app

    monkeypatch.setattr(bills_module, "SessionProcessed", session_factory)
    monkeypatch.setattr(bills_module, "date", FixedDate)
    flask_app = create_app()
    flask_app.testing = True
    return flask_app.test_client()


def _seed_bills(session_factory, count: int) -> None:
    with session_factory() as db:
        for index in range(1, count + 1):
            db.add(
                Bill(
                    id=f"2021_{index:04d}",
                    title=f"Bill {index:04d}",
                    summary_congreso="",
                    observations="",
                    status="presentado",
                    proponent=Proponents.CONGRESO,
                    bill_approved=False,
                    summary_oc="",
                )
            )
        db.commit()


def _seed_bill_search_data(session_factory) -> None:
    with session_factory() as db:
        db.add_all(
            [
                Bill(
                    id="2021_0001",
                    title="Bill 0001",
                    summary_congreso="",
                    observations="",
                    status="presentado",
                    proponent=Proponents.CONGRESO,
                    author_id=1,
                    bill_approved=False,
                    summary_oc="",
                ),
                Bill(
                    id="2021_0002",
                    title="Bill 0002",
                    summary_congreso="",
                    observations="",
                    status="presentado",
                    proponent=Proponents.CONGRESO,
                    author_id=2,
                    bill_approved=False,
                    summary_oc="",
                ),
                Congresista(
                    id=1,
                    full_name="Ana Perez",
                    first_name="Ana",
                    last_name="Perez",
                    dni="00000001",
                    gender="F",
                    photo_url="",
                    website="",
                ),
                Congresista(
                    id=2,
                    full_name="Beatriz Gomez",
                    first_name="Beatriz",
                    last_name="Gomez",
                    dni="00000002",
                    gender="F",
                    photo_url="",
                    website="",
                ),
                Organization(
                    org_id=1,
                    org_name="Comisión de Economía",
                    org_type=TypeOrganization.COMMITTEE,
                    org_subtype=None,
                    org_link=None,
                    parent_org_id=None,
                    date_founding=None,
                    date_dissolution=None,
                ),
                Organization(
                    org_id=2,
                    org_name="Comisión de Justicia",
                    org_type=TypeOrganization.COMMITTEE,
                    org_subtype=None,
                    org_link=None,
                    parent_org_id=None,
                    date_founding=None,
                    date_dissolution=None,
                ),
                Organization(
                    org_id=3,
                    org_name="Partido Verde",
                    org_type=TypeOrganization.PARTY,
                    org_subtype=None,
                    org_link=None,
                    parent_org_id=None,
                    date_founding=None,
                    date_dissolution=None,
                ),
                PartyMembership(
                    person_id=1,
                    org_id=3,
                    leg_period="2021-2026",
                    role="member",
                    start_date=real_date(2021, 1, 1),
                    end_date=real_date(2026, 12, 31),
                ),
                CommitteeMembership(
                    person_id=1,
                    org_id=1,
                    leg_period="2021-2026",
                    role="member",
                    start_date=real_date(2021, 1, 1),
                    end_date=real_date(2026, 12, 31),
                ),
                BillStep(
                    bill_id="2021_0001",
                    step_id=1,
                    step_type=TypeBillStep.PRESENTADO,
                    vote_step=False,
                    vote_event_id=None,
                    step_date=real_date(2024, 1, 1),
                    step_detail="",
                ),
                BillStep(
                    bill_id="2021_0001",
                    step_id=2,
                    step_type=TypeBillStep.VOTACION,
                    vote_step=False,
                    vote_event_id=None,
                    step_date=real_date(2024, 1, 15),
                    step_detail="",
                ),
                BillStep(
                    bill_id="2021_0002",
                    step_id=1,
                    step_type=TypeBillStep.ARCHIVADO,
                    vote_step=False,
                    vote_event_id=None,
                    step_date=real_date(2024, 2, 1),
                    step_detail="",
                ),
                BillOrganization(
                    bill_id="2021_0001",
                    org_id=1,
                    org_type=TypeOrganization.COMMITTEE,
                    presentation_date=real_date(2024, 1, 10),
                    decision_date=None,
                ),
                BillOrganization(
                    bill_id="2021_0002",
                    org_id=2,
                    org_type=TypeOrganization.COMMITTEE,
                    presentation_date=real_date(2024, 2, 10),
                    decision_date=None,
                ),
                Bill(
                    id="2021_0003",
                    title="Bill 0003",
                    summary_congreso="",
                    observations="",
                    status="presentado",
                    proponent=Proponents.CONGRESO,
                    author_id=1,
                    bill_approved=False,
                    summary_oc="",
                ),
                BillOrganization(
                    bill_id="2021_0003",
                    org_id=1,
                    org_type=TypeOrganization.COMMITTEE,
                    presentation_date=real_date(2025, 5, 1),
                    decision_date=None,
                ),
                Ley(id="L-001", title="Ley 1", bill_id="2021_0001"),
                Ley(id="L-002", title="Ley 2", bill_id="2021_0002"),
            ]
        )
        db.commit()


def test_search_results_are_paginated_by_50(client, session_factory):
    _seed_bills(session_factory, 55)

    first_page = client.get("/bills?title_q=Bill")
    first_body = first_page.get_data(as_text=True)
    assert first_page.status_code == 200
    assert "Showing 1-50 of 55 bills" in first_body
    assert "Bill 0001" in first_body
    assert "Bill 0050" in first_body
    assert "Bill 0051" not in first_body
    assert "page=2" in first_body

    second_page = client.get("/bills?title_q=Bill&page=2")
    second_body = second_page.get_data(as_text=True)
    assert second_page.status_code == 200
    assert "Showing 51-55 of 55 bills" in second_body
    assert "Bill 0051" in second_body
    assert "Bill 0055" in second_body
    assert "Bill 0001" not in second_body
    assert "page=1" in second_body


def test_search_results_cap_at_500_plus(client, session_factory):
    _seed_bills(session_factory, 501)

    first_page = client.get("/bills?title_q=Bill")
    body = first_page.get_data(as_text=True)

    assert first_page.status_code == 200
    assert "Showing 1-50 of 500+ bills" in body


def test_search_form_includes_new_filters(client):
    response = client.get("/bills")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'name="bill_id_q"' in body
    assert 'name="law_id_q"' in body
    assert 'name="current_step_q"' in body
    assert 'name="presentation_date_from_year"' in body
    assert 'name="presentation_date_from_month"' in body
    assert 'name="presentation_date_from_day"' in body
    assert 'name="presentation_date_to_year"' in body
    assert 'name="presentation_date_to_month"' in body
    assert 'name="presentation_date_to_day"' in body
    assert 'name="author_party_q"' in body
    assert 'name="organization_name_q"' in body
    assert "Presentation date" in body
    assert "From" in body
    assert "To" in body
    assert "Author party" in body
    assert 'name="presentation_date_from_year"' in body and 'value="" selected' in body
    assert 'name="presentation_date_from_month"' in body and 'value="" selected' in body
    assert 'name="presentation_date_from_day"' in body and 'value="" selected' in body
    assert 'name="presentation_date_to_year"' in body and 'value="" selected' in body
    assert 'name="presentation_date_to_month"' in body and 'value="" selected' in body
    assert 'name="presentation_date_to_day"' in body and 'value="" selected' in body


def test_search_filters_bill_id_law_id_step_date_and_committee(client, session_factory):
    _seed_bill_search_data(session_factory)

    response = client.get(
        "/bills",
        query_string={
            "bill_id_q": "2021_0001",
            "law_id_q": "L-001",
            "current_step_q": TypeBillStep.VOTACION.value,
            "author_party_q": "Partido Verde",
            "presentation_date_from_year": 2024,
            "presentation_date_from_month": 1,
            "presentation_date_from_day": 1,
            "presentation_date_to_year": 2024,
            "presentation_date_to_month": 1,
            "presentation_date_to_day": 31,
            "organization_name_q": "Comisión de Economía",
        },
    )
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Showing 1-1 of 1 bills" in body
    assert "2021_0001" in body
    assert "2021_0002" not in body
    assert "Law ID: L-001" in body
    assert "Current Step: Votación" in body
    assert "Author party: Partido Verde" in body
    assert "2024-01-01 - 2024-01-31" in body


def test_search_ignores_spanish_accents_for_text_filters(client, session_factory):
    with session_factory() as db:
        db.add_all(
            [
                Congresista(
                    id=10,
                    full_name="José Álvarez",
                    first_name="José",
                    last_name="Álvarez",
                    dni="00000010",
                    gender="M",
                    photo_url="",
                    website="",
                ),
                Organization(
                    org_id=20,
                    org_name="Partido Perú",
                    org_type=TypeOrganization.PARTY,
                    org_subtype=None,
                    org_link=None,
                    parent_org_id=None,
                    date_founding=None,
                    date_dissolution=None,
                ),
                Bill(
                    id="2021_0099",
                    title="Análisis del café",
                    summary_congreso="",
                    observations="",
                    status="presentado",
                    proponent=Proponents.CONGRESO,
                    author_id=10,
                    bill_approved=False,
                    summary_oc="",
                ),
                PartyMembership(
                    person_id=10,
                    org_id=20,
                    leg_period="2021-2026",
                    role="member",
                    start_date=real_date(2021, 1, 1),
                    end_date=real_date(2026, 12, 31),
                ),
            ]
        )
        db.commit()

    response = client.get(
        "/bills",
        query_string={"title_q": "Analisis del cafe", "author_q": "Jose Alvarez"},
    )
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "2021_0099" in body
    assert "Análisis del café" in body
    assert "José Álvarez" in body


def test_date_picker_builds_valid_february_days_for_leap_year():
    import app.routes.bills as bills_module

    picker = bills_module._build_date_picker(
        "presentation_date_from",
        {
            "presentation_date_from_year": "2024",
            "presentation_date_from_month": "2",
            "presentation_date_from_day": "29",
        },
        FixedDate.today(),
    )

    assert picker["selected_date"] == real_date(2024, 2, 29)
    assert len(picker["day_options"]) == 29
    assert picker["day_options"][-1] == 29
