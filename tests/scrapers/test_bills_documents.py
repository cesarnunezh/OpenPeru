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
                    timestamp=datetime.now(timezone.utc),
                    bill_id="2021_1",
                    step_date=datetime.now(timezone.utc),
                    seguimiento_id=1,
                    archivo_id=111,
                    url="http://example.com/a",
                    text="A",
                ),
                RawBillDocument(
                    timestamp=datetime.now(timezone.utc),
                    bill_id="2021_1",
                    step_date=datetime.now(timezone.utc),
                    seguimiento_id=3,
                    archivo_id=333,
                    url="http://example.com/c",
                    text="C",
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


def test_get_bill_documents_populates_documents_and_calls_render_pdf(monkeypatch):
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

    # Patch render_pdf so we don't hit network/PDF
    calls = []

    def fake_render_pdf(url):
        calls.append(url)
        return f"TEXT_FROM_{url}"

    monkeypatch.setattr("backend.scrapers.bills_documents.render_pdf", fake_render_pdf)

    scraper.get_bill_documents(bill_id=bill_id)
    # Should have called render_pdf once
    assert len(calls) == 1
    # b64 of "111"
    expected_b64 = base64.b64encode(b"111").decode()
    expected_url = f"{BASE_URL}/archivo/{expected_b64}/pdf"
    assert calls[0] == expected_url

    # Scraper should have one RawBillDocument object
    assert len(scraper.documents) == 1
    doc = scraper.documents[0]
    assert doc.bill_id == bill_id
    assert doc.archivo_id == 111
    assert doc.seguimiento_id == 10
    assert doc.url == expected_url
    assert doc.text == f"TEXT_FROM_{expected_url}"
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

    # Patch render_pdf to avoid network
    monkeypatch.setattr(
        "backend.scrapers.bills_documents.render_pdf",
        lambda url: "OK",
    )

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
        timestamp=datetime.now(timezone.utc),
        bill_id=bill_id,
        step_date=datetime.now(timezone.utc),
        seguimiento_id=1,
        archivo_id=123,
        url="http://example.com/doc.pdf",
        text="SOME TEXT",
    )
    scraper.documents = [doc]

    assert scraper.add_documents_to_db() is True

    with SessionLocal() as session:
        count = session.query(RawBillDocument).count()
        assert count == 1
        db_doc = session.query(RawBillDocument).first()
        assert db_doc.bill_id == bill_id
        assert db_doc.archivo_id == "123"
        assert db_doc.text == "SOME TEXT"


def test_add_documents_to_db_asserts_when_empty():
    scraper = RawBillDocumentScraper()
    scraper.documents = []

    with pytest.raises(AssertionError):
        scraper.add_documents_to_db()


def test_add_documents_to_db_handles_sqlalchemy_error():
    scraper = RawBillDocumentScraper()
    scraper.documents = [
        RawBillDocument(
            timestamp=datetime.now(timezone.utc),
            bill_id="2021_4",
            step_date=datetime.now(timezone.utc),
            seguimiento_id=1,
            archivo_id=1,
            url="http://example.com",
            text="TEXT",
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
