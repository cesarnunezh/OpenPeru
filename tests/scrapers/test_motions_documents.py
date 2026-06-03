import json
import base64
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.raw_models import Base as RawBase, RawMotion, RawMotionDocument
import backend.scrapers.motions_documents as motions_documents
from backend.scrapers.motions_documents import (
    RawMotionDocumentScraper,
    BASE_URL,
)


def _setup_inmemory_db():
    """
    Helper to create an in-memory SQLite DB with the raw models.
    """
    engine = create_engine("sqlite:///:memory:")
    RawBase.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return engine, SessionLocal


# --------------------------------------------------------------------------------------
# filter_steps
# --------------------------------------------------------------------------------------


def test_filter_steps_skips_existing_steps(monkeypatch):
    """
    filter_steps should drop steps whose seguimientoId is already in the DB.
    """
    engine, SessionLocal = _setup_inmemory_db()

    scraper = RawMotionDocumentScraper()
    scraper.engine = engine
    scraper.Session = SessionLocal

    motion_id = "2021_1"

    # Insert one existing RawMotionDocument with seguimiento_id = 10
    with SessionLocal() as session:
        session.add(
            RawMotionDocument(
                timestamp=datetime.now(),
                motion_id=motion_id,
                step_date=datetime.now(),
                seguimiento_id=10,
                archivo_id=111,
                url="http://example.com/existing.pdf",
                text="existing text",
            )
        )
        session.commit()

    extracted_steps = [
        {
            "seguimientoId": 10,  # already in DB -> should be filtered out
        },
        {
            "seguimientoId": 11,  # new -> should remain
        },
    ]

    filtered = scraper.filter_steps(extracted_steps, motion_id=motion_id)

    assert len(filtered) == 1
    assert filtered[0]["seguimientoId"] == 11


# --------------------------------------------------------------------------------------
# get_motion_documents
# --------------------------------------------------------------------------------------


def test_get_motion_documents_populates_urls_and_calls_render_pdf(monkeypatch):
    """
    get_motion_documents should:
      - fetch the latest RawMotion
      - filter/prioritize steps
      - call render_pdf for each file
      - populate scraper.documents with RawMotionDocument objects
    """
    engine, SessionLocal = _setup_inmemory_db()

    scraper = RawMotionDocumentScraper()
    scraper.engine = engine
    scraper.Session = SessionLocal

    motion_id = "2021_1"
    step_date_str = "2021-01-01T12:00:00.000000+0000"

    steps = [
        {
            "seguimientoId": 10,
            "desEstadoMocion": "Aprobada",  # in PRIORITIES
            "fecSeguimiento": step_date_str,
            "adjuntos": [
                {
                    "seguimientoAdjuntoId": 111,
                    "seguimientoId": 10,
                }
            ],
        }
    ]

    with SessionLocal() as session:
        session.add(
            RawMotion(
                id=motion_id,
                timestamp=datetime.now(timezone.utc),
                # assuming these fields exist and are nullable
                general=None,
                congresistas=None,
                steps=json.dumps(steps),
            )
        )
        session.commit()

    # Patch render_pdf so we don't hit the network
    captured = {}

    def fake_render_pdf(url):
        captured["url"] = url
        return "dummy text"

    monkeypatch.setattr(motions_documents, "render_pdf", fake_render_pdf)

    scraper.get_motion_documents(motion_id=motion_id)

    # One document should have been created
    assert len(scraper.documents) == 1
    doc = scraper.documents[0]
    assert isinstance(doc, RawMotionDocument)

    # URL should match the BASE_URL + encoded id
    expected_b64 = base64.b64encode(str(111).encode()).decode()
    expected_url = f"{BASE_URL}/seguimiento-adjunto/{expected_b64}/pdf"
    assert doc.url == expected_url
    assert captured["url"] == expected_url
    assert doc.text == "dummy text"
    assert doc.motion_id == motion_id
    assert doc.seguimiento_id == 10
    assert doc.archivo_id == 111
    # Check that step_date was parsed correctly
    assert doc.step_date == datetime.strptime(step_date_str, "%Y-%m-%dT%H:%M:%S.%f%z")


def test_get_motion_documents_returns_none_when_no_priority_steps(monkeypatch):
    """
    If prioritize=True and no steps match PRIORITIES, the method
    should log and return None without populating urls.
    """
    engine, SessionLocal = _setup_inmemory_db()

    scraper = RawMotionDocumentScraper()
    scraper.engine = engine
    scraper.Session = SessionLocal

    motion_id = "2021_2"
    step_date_str = "2021-01-01T12:00:00.000000+0000"

    # desEstadoMocion is not in PRIORITIES -> should be filtered out
    steps = [
        {
            "seguimientoId": 10,
            "desEstadoMocion": "En trámite",
            "fecSeguimiento": step_date_str,
            "adjuntos": [
                {
                    "seguimientoAdjuntoId": 111,
                    "seguimientoId": 10,
                }
            ],
        }
    ]

    with SessionLocal() as session:
        session.add(
            RawMotion(
                id=motion_id,
                timestamp=datetime.now(timezone.utc),
                general=None,
                congresistas=None,
                steps=json.dumps(steps),
            )
        )
        session.commit()

    # Patch render_pdf just to be safe (should not be called)
    def fake_render_pdf(url):
        raise AssertionError("render_pdf should not be called when no steps remain")

    monkeypatch.setattr(motions_documents, "render_pdf", fake_render_pdf)

    result = scraper.get_motion_documents(motion_id=motion_id, prioritize=True)

    assert result is None
    assert scraper.documents == []


# --------------------------------------------------------------------------------------
# add_documents_to_db / load_raw_documents
# --------------------------------------------------------------------------------------


def test_add_documents_to_db_persists_urls(monkeypatch):
    """
    add_documents_to_db should insert all documents in scraper.documents
    and return True on success.
    """
    engine, SessionLocal = _setup_inmemory_db()

    scraper = RawMotionDocumentScraper()
    scraper.engine = engine
    scraper.Session = SessionLocal

    motion_id = "2021_3"

    # Manually populate scraper.documents with two docs
    scraper.documents = [
        RawMotionDocument(
            timestamp=datetime.now(),
            motion_id=motion_id,
            step_date=datetime.now(),
            seguimiento_id=1,
            archivo_id=101,
            url="http://example.com/1.pdf",
            text="doc1",
        ),
        RawMotionDocument(
            timestamp=datetime.now(),
            motion_id=motion_id,
            step_date=datetime.now(),
            seguimiento_id=2,
            archivo_id=102,
            url="http://example.com/2.pdf",
            text="doc2",
        ),
    ]

    success = scraper.add_documents_to_db()
    assert success is True

    # Verify they are really in the DB
    with SessionLocal() as session:
        docs = session.query(RawMotionDocument).filter_by(motion_id=motion_id).all()
        assert len(docs) == 2
        urls = {d.url for d in docs}
        assert "http://example.com/1.pdf" in urls
        assert "http://example.com/2.pdf" in urls


def test_load_raw_documents_calls_add_and_resets_urls(monkeypatch):
    """
    load_raw_documents should call add_documents_to_db and then reset urls.
    """
    engine, SessionLocal = _setup_inmemory_db()

    scraper = RawMotionDocumentScraper()
    scraper.engine = engine
    scraper.Session = SessionLocal

    # Put one doc in urls
    scraper.documents = [
        RawMotionDocument(
            timestamp=datetime.now(),
            motion_id="2021_4",
            step_date=datetime.now(),
            seguimiento_id=1,
            archivo_id=101,
            url="http://example.com/1.pdf",
            text="doc1",
        )
    ]

    # Spy on add_documents_to_db
    called = {}

    def fake_add_documents_to_db():
        called["called"] = True
        return True

    monkeypatch.setattr(scraper, "add_documents_to_db", fake_add_documents_to_db)

    scraper.load_raw_documents()

    assert called.get("called") is True
    assert scraper.documents == []
