from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.core.enums import Proponents, TypeBillStep
from backend.database.crud.pipeline_bills import (
    get_billtext_for_step,
    upsert_bill_difference,
)
from backend.database.models import (
    Base,
    Bill,
    BillDifference,
    BillStep,
    BillText,
)


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


def _setup_bill_step(db, bill_id="BILL_1", step_id=1):
    db.add(
        Bill(
            id=bill_id,
            title="t",
            summary_congreso="",
            observations="",
            status="st",
            proponent=Proponents.CONGRESO,
            bill_approved=False,
            summary_oc="",
        )
    )
    db.add(
        BillStep(
            bill_id=bill_id,
            step_id=step_id,
            vote_step=False,
            step_type=TypeBillStep.VOTACION,
            step_date=date(2024, 1, 2),
            step_detail="d",
        )
    )
    db.commit()


def _add_billtext(db, bill_id, step_id, file_id, version_id, text):
    db.add(
        BillText(
            bill_id=bill_id,
            step_id=step_id,
            file_id=file_id,
            version_id=version_id,
            text=text,
        )
    )
    db.commit()


# ── upsert_bill_difference ──────────────────────────────────────────────────


def test_upsert_bill_difference_insert(session):
    _setup_bill_step(session)
    row = upsert_bill_difference(
        session,
        bill_id="BILL_1",
        step_id=1,
        prev_step_id=None,
        difference_type="first_version",
        difference_content=None,
    )
    session.commit()
    assert row.step_id == 1
    assert row.difference_type == "first_version"
    loaded = session.get(BillDifference, ("BILL_1", 1))
    assert loaded is not None
    assert loaded.bill_id == "BILL_1"
    assert loaded.prev_step_id is None


def test_upsert_bill_difference_update(session):
    _setup_bill_step(session)
    upsert_bill_difference(
        session,
        bill_id="BILL_1",
        step_id=1,
        prev_step_id=None,
        difference_type="first_version",
        difference_content=None,
    )
    session.commit()
    upsert_bill_difference(
        session,
        bill_id="BILL_1",
        step_id=1,
        prev_step_id=None,
        difference_type="modified",
        difference_content='{"nodes": []}',
    )
    session.commit()
    rows = session.query(BillDifference).filter_by(bill_id="BILL_1", step_id=1).all()
    assert len(rows) == 1
    assert rows[0].difference_type == "modified"
    assert rows[0].difference_content == '{"nodes": []}'


# ── get_billtext_for_step ───────────────────────────────────────────────────


def test_get_billtext_for_step_returns_canonical(session):
    _setup_bill_step(session, step_id=10)
    _add_billtext(session, "BILL_1", 10, file_id=200, version_id=1, text="body v1")

    bt = get_billtext_for_step(session, "BILL_1", 10)
    assert bt is not None
    assert bt.text == "body v1"
    assert bt.file_id == 200


def test_get_billtext_for_step_prefers_lowest_file_id(session):
    _setup_bill_step(session, step_id=10)
    _add_billtext(session, "BILL_1", 10, file_id=300, version_id=1, text="other file")
    _add_billtext(session, "BILL_1", 10, file_id=200, version_id=1, text="lower file")

    bt = get_billtext_for_step(session, "BILL_1", 10)
    assert bt.file_id == 200
    assert bt.text == "lower file"


def test_get_billtext_for_step_prefers_latest_version(session):
    _setup_bill_step(session, step_id=10)
    _add_billtext(session, "BILL_1", 10, file_id=200, version_id=1, text="v1")
    _add_billtext(session, "BILL_1", 10, file_id=200, version_id=2, text="v2")

    bt = get_billtext_for_step(session, "BILL_1", 10)
    assert bt.version_id == 2
    assert bt.text == "v2"


def test_get_billtext_for_step_missing_returns_none(session):
    _setup_bill_step(session)
    assert get_billtext_for_step(session, "BILL_1", 9999) is None
