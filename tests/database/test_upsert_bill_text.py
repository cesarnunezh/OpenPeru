from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.crud.pipeline_bills import upsert_bill_text
from backend.database.models import Base, Bill, BillStep, BillText, Organization
from backend import TypeBillStep, Proponents, TypeOrganization


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)


def _minimal_bill_and_step(db, bill_id: str, step_id: int):
    bancada = Organization(
        org_name="Bancada Test",
        org_type=TypeOrganization.BANCADA.value,
    )
    db.add(bancada)
    db.flush()

    db.add(
        Bill(
            id=bill_id,
            title="t",
            summary_congreso="s",
            observations="o",
            status="st",
            proponent=Proponents.CONGRESO.value,
            author_id=None,
            bill_approved=False,
            summary_oc="",
        )
    )
    db.add(
        BillStep(
            step_id=step_id,
            bill_id=bill_id,
            vote_step=False,
            vote_event_id=None,
            step_type=TypeBillStep.VOTACION.value,
            step_date=datetime(2024, 1, 2),
            step_detail="d",
        )
    )
    db.commit()


def test_upsert_bill_text_insert(session):
    _minimal_bill_and_step(session, "BILL_BT", 5001)

    row = upsert_bill_text(
        session,
        bill_id="BILL_BT",
        step_id=5001,
        file_id=9001,
        version_id=1,
        text="PROYECTO DE LEY ...",
    )
    session.commit()

    assert row.file_id == 9001
    assert row.version_id == 1
    assert row.text == "PROYECTO DE LEY ..."

    loaded = session.get(BillText, ("BILL_BT", 5001, 9001, 1))
    assert loaded is not None
    assert loaded.bill_id == "BILL_BT"
    assert loaded.step_id == 5001


def test_upsert_bill_text_update_same_file_and_version(session):
    _minimal_bill_and_step(session, "BILL_BT2", 5002)

    upsert_bill_text(
        session,
        bill_id="BILL_BT2",
        step_id=5002,
        file_id=9002,
        version_id=1,
        text="first",
    )
    session.commit()
    upsert_bill_text(
        session,
        bill_id="BILL_BT2",
        step_id=5002,
        file_id=9002,
        version_id=1,
        text="second",
    )
    session.commit()

    rows = session.query(BillText).filter_by(file_id=9002, version_id=1).all()
    assert len(rows) == 1
    assert rows[0].text == "second"


def test_upsert_bill_text_allows_new_version(session):
    _minimal_bill_and_step(session, "BILL_BT3", 5003)

    upsert_bill_text(
        session,
        bill_id="BILL_BT3",
        step_id=5003,
        file_id=9003,
        version_id=1,
        text="first",
    )
    upsert_bill_text(
        session,
        bill_id="BILL_BT3",
        step_id=5003,
        file_id=9003,
        version_id=2,
        text="second",
    )
    session.commit()

    rows = (
        session.query(BillText)
        .filter_by(file_id=9003)
        .order_by(BillText.version_id)
        .all()
    )
    assert [row.version_id for row in rows] == [1, 2]
    assert [row.text for row in rows] == ["first", "second"]
