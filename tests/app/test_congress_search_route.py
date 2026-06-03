from __future__ import annotations

from datetime import date
import unicodedata

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from backend.core.enums import TypeOrganization
from backend.database.models import (
    Base,
    ChamberMembership,
    CommitteeMembership,
    Congresista,
    Organization,
    PartyMembership,
)


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
    import app.routes.congress as congress_module
    from app.app import create_app

    monkeypatch.setattr(congress_module, "SessionProcessed", session_factory)
    flask_app = create_app()
    flask_app.testing = True
    return flask_app.test_client()


def _seed_congress_search_data(session_factory) -> None:
    with session_factory() as db:
        db.add_all(
            [
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
                    start_date=date(2021, 1, 1),
                    end_date=date(2026, 12, 31),
                ),
                CommitteeMembership(
                    person_id=1,
                    org_id=1,
                    leg_period="2021-2026",
                    role="member",
                    start_date=date(2021, 1, 1),
                    end_date=date(2026, 12, 31),
                ),
                CommitteeMembership(
                    person_id=2,
                    org_id=2,
                    leg_period="2021-2026",
                    role="member",
                    start_date=date(2021, 1, 1),
                    end_date=date(2026, 12, 31),
                ),
                ChamberMembership(
                    person_id=1,
                    org_id=1,
                    leg_period="2021-2026",
                    role="member",
                    start_date=date(2021, 1, 1),
                    end_date=date(2026, 12, 31),
                    condicion=None,
                    votes_in_election=None,
                    dist_electoral="Lima",
                ),
                ChamberMembership(
                    person_id=2,
                    org_id=1,
                    leg_period="2021-2026",
                    role="member",
                    start_date=date(2021, 1, 1),
                    end_date=date(2026, 12, 31),
                    condicion=None,
                    votes_in_election=None,
                    dist_electoral="Cusco",
                ),
            ]
        )
        db.commit()


def test_search_form_uses_selects_for_party_and_commission(client):
    response = client.get("/congress")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert '<select name="party_q">' in body
    assert '<select name="region_q">' in body
    assert '<select name="commission_q">' in body
    assert 'name="party_q" value=' not in body
    assert 'name="region_q" value=' not in body
    assert 'name="commission_q" value=' not in body


def test_search_filters_by_selected_region(client, session_factory):
    _seed_congress_search_data(session_factory)

    response = client.get(
        "/congress",
        query_string={"region_q": "Lima"},
    )
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Ana Perez" in body
    assert "Beatriz Gomez" not in body
    assert "Region: Lima" in body


def test_search_filters_by_selected_commission(client, session_factory):
    _seed_congress_search_data(session_factory)

    response = client.get(
        "/congress",
        query_string={"commission_q": "Comisión de Economía"},
    )
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Ana Perez" in body
    assert "Beatriz Gomez" not in body
    assert "Commission: Comisión de Economía" in body
