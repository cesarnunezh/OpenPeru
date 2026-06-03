from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import Proponents, TypeOrganization, VoteOption, VoteResult
from backend.database.models import (
    Base,
    Bill,
    BillStep,
    Congresista,
    Organization,
    PartyMembership,
    Vote,
    VoteCounts,
    VoteEvent,
)
from app.routes.generate_seats import generate_seats


@pytest.fixture()
def session_factory(tmp_path):
    db_path = tmp_path / "processed_test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    yield Session
    engine.dispose()


@pytest.fixture()
def client(monkeypatch, session_factory):
    import app.routes.bills as bills_module
    from app.app import create_app

    monkeypatch.setattr(bills_module, "SessionProcessed", session_factory)
    flask_app = create_app()
    flask_app.testing = True
    return flask_app.test_client()


def _seed_vote_page(session_factory) -> None:
    with session_factory() as db:
        db.add_all(
            [
                Bill(
                    id="2021_0001",
                    title="Bill with votes",
                    summary_congreso="",
                    observations="",
                    status="presentado",
                    proponent=Proponents.CONGRESO,
                    bill_approved=True,
                    summary_oc="",
                ),
                BillStep(
                    bill_id="2021_0001",
                    step_id=1,
                    vote_step=True,
                    vote_event_id="VE-1",
                    step_type="Votación",
                    step_date=date(2024, 1, 15),
                    step_detail="Vote in committee",
                ),
                Organization(
                    org_id=10,
                    org_name="Comisión de Economía",
                    org_type=TypeOrganization.COMMITTEE,
                    org_subtype=None,
                    org_link=None,
                    parent_org_id=None,
                    date_founding=None,
                    date_dissolution=None,
                ),
                Organization(
                    org_id=20,
                    org_name="Partido Azul",
                    org_type=TypeOrganization.PARTY,
                    org_subtype=None,
                    org_link=None,
                    parent_org_id=None,
                    date_founding=None,
                    date_dissolution=None,
                ),
                Organization(
                    org_id=21,
                    org_name="Partido Verde",
                    org_type=TypeOrganization.PARTY,
                    org_subtype=None,
                    org_link=None,
                    parent_org_id=None,
                    date_founding=None,
                    date_dissolution=None,
                ),
                Organization(
                    org_id=22,
                    org_name="Partido Rojo",
                    org_type=TypeOrganization.PARTY,
                    org_subtype=None,
                    org_link=None,
                    parent_org_id=None,
                    date_founding=None,
                    date_dissolution=None,
                ),
                Organization(
                    org_id=30,
                    org_name="Bancada Test",
                    org_type=TypeOrganization.BANCADA,
                    org_subtype=None,
                    org_link=None,
                    parent_org_id=None,
                    date_founding=None,
                    date_dissolution=None,
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
                Congresista(
                    id=3,
                    full_name="Carlos Diaz",
                    first_name="Carlos",
                    last_name="Diaz",
                    dni="00000003",
                    gender="M",
                    photo_url="",
                    website="",
                ),
                PartyMembership(
                    person_id=1,
                    org_id=20,
                    leg_period="2021-2026",
                    role="member",
                    start_date=date(2021, 1, 1),
                    end_date=date(2026, 12, 31),
                ),
                PartyMembership(
                    person_id=2,
                    org_id=21,
                    leg_period="2021-2026",
                    role="member",
                    start_date=date(2021, 1, 1),
                    end_date=date(2026, 12, 31),
                ),
                PartyMembership(
                    person_id=3,
                    org_id=22,
                    leg_period="2021-2026",
                    role="member",
                    start_date=date(2021, 1, 1),
                    end_date=date(2026, 12, 31),
                ),
                VoteEvent(
                    vote_event_id="VE-1",
                    org_id=10,
                    bill_id="2021_0001",
                    motion_id=None,
                    event_date=date(2024, 1, 15),
                    result=VoteResult.APROBADO,
                    votes_in_favor=5,
                    votes_against=2,
                    votes_abstention=1,
                ),
                Vote(
                    vote_event_id="VE-1",
                    voter_id=1,
                    option=VoteOption.SI,
                    bancada_id=30,
                ),
                Vote(
                    vote_event_id="VE-1",
                    voter_id=2,
                    option=VoteOption.NO,
                    bancada_id=30,
                ),
                Vote(
                    vote_event_id="VE-1",
                    voter_id=3,
                    option=VoteOption.ABSTENCION,
                    bancada_id=30,
                ),
                VoteCounts(
                    vote_event_id="VE-1",
                    option=VoteOption.SI,
                    bancada_id=30,
                    count=5,
                ),
                VoteCounts(
                    vote_event_id="VE-1",
                    option=VoteOption.NO,
                    bancada_id=30,
                    count=2,
                ),
                VoteCounts(
                    vote_event_id="VE-1",
                    option=VoteOption.ABSTENCION,
                    bancada_id=30,
                    count=1,
                ),
            ]
        )
        db.commit()


def test_vote_page_uses_real_vote_data(client, session_factory):
    _seed_vote_page(session_factory)

    body = client.get("/bills/2021_0001/votes/VE-1").get_data(as_text=True)

    assert "Bill with votes" in body
    assert "Vote date:" in body
    assert "15-01-2024" in body
    assert "Organization:" in body
    assert "Comisión de Economía" in body
    assert "Results by bancada" in body
    assert "vote-members-table-wrap" in body
    assert body.count('<button type="button" class="vote-sort-button"') == 3
    assert "legend-swatch--others" in body
    assert "Others" in body
    assert "vote-members-table" in body
    assert "Ana Perez" in body
    assert "/congress/1" in body
    assert "Partido Azul" in body
    assert "In favor" in body
    assert "Against" in body
    assert "Abstain" in body


def test_generate_seats_adds_gray_others_without_labels():
    seats = generate_seats(
        {"yes": 5, "no": 2, "abstain": 1, "others": 122},
        {"yes": ["A"], "no": ["B"], "abstain": ["C"]},
    )

    assert len(seats) == 130
    assert sum(1 for seat in seats if seat["color"] == "#b8b8b8") == 122
    assert any(seat["label"] == "A" for seat in seats)
    assert any(seat["label"] == "B" for seat in seats)
    assert any(seat["label"] == "C" for seat in seats)
    assert all(seat["label"] == "" for seat in seats if seat["color"] == "#b8b8b8")
