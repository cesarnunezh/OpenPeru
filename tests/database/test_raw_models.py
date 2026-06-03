# test_models.py
from datetime import datetime, UTC

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from backend.database.raw_models import (
    Base,
    RawBill,
    RawBillDocument,
    RawCommittee,
    RawCongresista,
    RawMotion,
)


@pytest.fixture(scope="module")
def engine():
    # In-memory SQLite DB for testing
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine):
    with Session(engine) as session:
        yield session
        session.rollback()


def test_tables_created(engine):
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    assert "raw_bills" in tables
    assert "raw_bill_documents" in tables
    assert "raw_committees" in tables
    assert "raw_congresistas" in tables
    assert "raw_motions" in tables


def test_raw_bill_columns(engine):
    inspector = inspect(engine)
    cols = {c["name"]: c for c in inspector.get_columns("raw_bills")}

    # basic column presence
    for name in ["id", "timestamp", "general", "committees", "congresistas", "steps"]:
        assert name in cols

    # composite primary key (id, timestamp)
    pk_cols = inspector.get_pk_constraint("raw_bills")["constrained_columns"]
    assert set(pk_cols) == {"id", "timestamp"}


def test_raw_motion_columns(engine):
    inspector = inspect(engine)
    cols = {c["name"]: c for c in inspector.get_columns("raw_motions")}

    for name in ["id", "timestamp", "general", "congresistas", "steps"]:
        assert name in cols

    pk_cols = inspector.get_pk_constraint("raw_motions")["constrained_columns"]
    assert set(pk_cols) == {"id", "timestamp"}


def test_raw_bill_documents_columns_and_nullable(engine):
    inspector = inspect(engine)
    cols = inspector.get_columns("raw_bill_documents")
    cols_by_name = {c["name"]: c for c in cols}

    expected_not_null = {
        "timestamp",
        "bill_id",
        "step_date",
        "seguimiento_id",
        "archivo_id",
        "url",
        "text",
    }

    for name in expected_not_null:
        assert name in cols_by_name
        assert cols_by_name[name]["nullable"] is False


def test_can_create_raw_bill(session):
    now = datetime.now(UTC)
    bill = RawBill(
        id="PL-1234",
        timestamp=now,
        general="Some general info",
        committees="Some committees info",
        congresistas="Some congresistas info",
        steps="Some steps info",
    )
    session.add(bill)
    session.commit()

    fetched = (
        session.query(RawBill)
        .filter(RawBill.id == "PL-1234", RawBill.timestamp == now)
        .one()
    )
    assert fetched.general == "Some general info"


def test_can_create_raw_bill_document(session):
    now = datetime.now(UTC)
    step_date = now.date()
    doc = RawBillDocument(
        timestamp=now,
        bill_id="PL-1234",
        step_date=now,
        seguimiento_id="SEG-1",
        archivo_id="ARCH-1",
        url="https://example.com/doc.pdf",
        text="This is some extracted text",
    )
    session.add(doc)
    session.commit()

    fetched = session.query(RawBillDocument).filter_by(archivo_id="ARCH-1").one()
    assert fetched.url == "https://example.com/doc.pdf"
    assert "extracted text" in fetched.text


def test_can_create_raw_committee(session):
    now = datetime.now(UTC)
    committee = RawCommittee(
        timestamp=now,
        legislative_year=2024,
        committee_type="Permanent",
        raw_html="<html>some html</html>",
    )
    session.add(committee)
    session.commit()

    fetched = session.query(RawCommittee).filter_by(committee_type="Permanent").one()
    assert fetched.legislative_year == 2024
    assert "<html>" in fetched.raw_html


def test_can_create_raw_congresista(session):
    now = datetime.now(UTC)
    cong = RawCongresista(
        timestamp=now,
        leg_period="2021-2026",
        url="https://example.com/congresista",
        profile_content="<html>profile</html>",
        memberships_content='{"committees": []}',
    )
    session.add(cong)
    session.commit()

    fetched = session.query(RawCongresista).filter_by(leg_period="2021-2026").one()
    assert "profile" in fetched.profile_content
    assert "committees" in fetched.memberships_content


def test_can_create_raw_motion(session):
    now = datetime.now(UTC)
    motion = RawMotion(
        id="MOT-5678",
        timestamp=now,
        general="Motion general info",
        congresistas="Some authors",
        steps="Some steps",
    )
    session.add(motion)
    session.commit()

    fetched = (
        session.query(RawMotion)
        .filter(RawMotion.id == "MOT-5678", RawMotion.timestamp == now)
        .one()
    )
    assert fetched.general == "Motion general info"
