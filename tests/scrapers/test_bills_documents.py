import base64
import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.scrapers.bills_documents import (
    RawBillDocumentScraper,
    BASE_URL,
)
from backend.database.raw_models import Base, RawBill, RawBillDocument
from sqlalchemy.exc import SQLAlchemyError


# ---------- helpers for in-memory DB ----------


def _setup_inmemory_db():
    """Create in-memory SQLite engine and session factory for tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return engine, SessionLocal


# ---------- filter_steps ----------


def test_filter_steps_filters_existing(monkeypatch):
    engine, SessionLocal = _setup_inmemory_db()

    scraper = RawBillDocumentScraper()
    scraper.engine = engine
    scraper.Session = SessionLocal

    # Seed DB with some RawBillDocument for a given bill_id
    with SessionLocal() as session:
        session.add_all(
            [
                RawBillDocument(
                    bill_id="2021_1",
                    step_id=1,
                    file_id=111,
                    step_date=datetime.now(timezone.utc),
                    url="http://example.com/a",
                    s3_key="some_aws_s3_key",
                    local_path="~/some/local/path",
                    timestamp=datetime.now(timezone.utc),
                ),
                RawBillDocument(
                    bill_id="2021_1",
                    step_id=3,
                    file_id=333,
                    step_date=datetime.now(timezone.utc),
                    url="http://example.com/c",
                    s3_key="some_aws_s3_key",
                    local_path="~/some/local/path",
                    timestamp=datetime.now(timezone.utc),
                ),
            ]
        )
        session.commit()

    extracted_steps = [
        {"seguimientoPleyId": 1},
        {"seguimientoPleyId": 2},
        {"seguimientoPleyId": 3},
    ]

    remaining = scraper.filter_steps(extracted_steps, bill_id="2021_1")
    # seguimiento 1 and 3 exist in DB => only 2 should remain
    assert len(remaining) == 1
    assert remaining[0]["seguimientoPleyId"] == 2


# ---------- get_bill_documents ----------


def test_get_bill_documents_raises_if_bill_not_found():
    engine, SessionLocal = _setup_inmemory_db()

    scraper = RawBillDocumentScraper()
    scraper.engine = engine
    scraper.Session = SessionLocal

    with pytest.raises(AssertionError):
        scraper.get_bill_documents(bill_id="2021_999")


def test_get_bill_documents_populates_documents(monkeypatch):
    engine, SessionLocal = _setup_inmemory_db()

    scraper = RawBillDocumentScraper()
    scraper.engine = engine
    scraper.Session = SessionLocal

    # Create a RawBill with one step and one file
    bill_id = "2021_1"
    step_date_str = "2021-01-01T12:00:00.000000+0000"
    steps = [
        {
            "seguimientoPleyId": 10,
            "fecha": step_date_str,
            "desEstado": "Publicada en el Diario Oficial El Peruano",
            "archivos": [
                {
                    "proyectoArchivoId": 111,
                    "seguimientoPleyId": 10,
                }
            ],
        }
    ]

    with SessionLocal() as session:
        session.add(
            RawBill(
                id=bill_id,
                timestamp=datetime.now(timezone.utc),
                general=None,
                committees=None,
                congresistas=None,
                steps=json.dumps(steps),
            )
        )
        session.commit()

    scraper.get_bill_documents(bill_id=bill_id)

    expected_b64 = base64.b64encode(b"111").decode()
    expected_url = f"{BASE_URL}/archivo/{expected_b64}/pdf"

    # Scraper should have one RawBillDocument object
    assert len(scraper.documents) == 1
    doc = scraper.documents[0]
    assert doc.bill_id == bill_id
    assert doc.file_id == "111"
    assert doc.step_id == "10"
    assert doc.url == expected_url
    # step_date parsed correctly
    assert isinstance(doc.step_date, datetime)


def test_get_bill_documents_respects_update_flag(monkeypatch):
    """When update=False, filter_steps is used; when update=True, it should not be used."""
    engine, SessionLocal = _setup_inmemory_db()

    scraper = RawBillDocumentScraper()
    scraper.engine = engine
    scraper.Session = SessionLocal

    bill_id = "2021_2"
    steps = [
        {
            "seguimientoPleyId": 1,
            "desEstado": "Publicada en el Diario Oficial El Peruano",
            "fecha": "2021-01-01T00:00:00.000000+0000",
            "archivos": [
                {"proyectoArchivoId": 999, "seguimientoPleyId": 1},
            ],
        }
    ]

    with SessionLocal() as session:
        session.add(
            RawBill(
                id=bill_id,
                timestamp=datetime.now(timezone.utc),
                general=None,
                committees=None,
                congresistas=None,
                steps=json.dumps(steps),
            )
        )
        session.commit()

    # Case 1: update=False and filter_steps returns empty -> no URLs
    def fake_filter_steps(_steps, _bill_id):
        return []

    monkeypatch.setattr(scraper, "filter_steps", fake_filter_steps)

    scraper.get_bill_documents(bill_id=bill_id, update=False)
    assert len(scraper.documents) == 0

    # Case 2: update=True should bypass filter_steps
    scraper.documents = []  # reset

    scraper.get_bill_documents(bill_id=bill_id, update=True)
    assert len(scraper.documents) == 1
    assert scraper.documents[0].bill_id == bill_id


# ---------- add_documents_to_db ----------


def test_add_documents_to_db_persists(monkeypatch):
    engine, SessionLocal = _setup_inmemory_db()

    scraper = RawBillDocumentScraper()
    scraper.engine = engine
    scraper.Session = SessionLocal

    bill_id = "2021_3"
    doc = RawBillDocument(
        bill_id="2021_3",
        step_id="1",
        file_id="111",
        step_date=datetime.now(timezone.utc),
        url="http://example.com/a",
        s3_key="some_aws_s3_key",
        local_path="~/some/local/path",
        timestamp=datetime.now(timezone.utc),
    )
    scraper.documents = [doc]

    assert scraper.add_documents_to_db() is True

    with SessionLocal() as session:
        count = session.query(RawBillDocument).count()
        assert count == 1
        db_doc = session.query(RawBillDocument).first()
        assert db_doc.bill_id == bill_id
        assert db_doc.file_id == "111"


def test_add_documents_to_db_asserts_when_empty():
    scraper = RawBillDocumentScraper()
    scraper.documents = []

    with pytest.raises(AssertionError):
        scraper.add_documents_to_db()


def test_add_documents_to_db_handles_sqlalchemy_error():
    scraper = RawBillDocumentScraper()
    scraper.documents = [
        RawBillDocument(
            bill_id="2021_1",
            step_id=1,
            file_id=111,
            step_date=datetime.now(timezone.utc),
            url="http://example.com/a",
            s3_key="some_aws_s3_key",
            local_path="~/some/local/path",
            timestamp=datetime.now(timezone.utc),
        )
    ]

    class DummyQuery:
        def filter(self, *args, **kwargs):
            return self

        def all(self):
            return []

    class DummySession:
        def __init__(self):
            self.rolled_back = False

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            self.close()
            return False

        def query(self, *args, **kwargs):
            return DummyQuery()

        def add_all(self, documents):
            raise SQLAlchemyError("boom")  # <-- key change

        def commit(self):
            pass

        def rollback(self):
            self.rolled_back = True

        def close(self):
            pass

    dummy_session = DummySession()
    scraper.Session = lambda: dummy_session

    ok = scraper.add_documents_to_db()
    assert ok is False
    assert dummy_session.rolled_back is True


# ---------- load_raw_documents ----------


def test_load_raw_documents_calls_add_and_clears(monkeypatch):
    scraper = RawBillDocumentScraper()
    # Put a dummy object so assertion in add_documents_to_db would pass
    scraper.documents = ["dummy"]

    calls = {"added": False}

    def fake_add():
        calls["added"] = True
        return True

    monkeypatch.setattr(scraper, "add_documents_to_db", fake_add)

    scraper.load_raw_documents()

    assert calls["added"] is True
    assert scraper.documents == []
