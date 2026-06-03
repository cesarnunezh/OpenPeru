import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Adjust this import to your actual module path
from backend.scrapers.bills import RawBillScraper
from backend.database.raw_models import Base, RawBill

API_URL = "https://api.congreso.gob.pe/spley-portal-service/expediente/"
# ---------- create_raw_bill ----------


def test_create_raw_bill_sets_id_and_sections():
    scraper = RawBillScraper()

    year = "2021"
    bill_number = "1234"
    data = {
        "general": {"titulo": "Ley X"},
        "firmantes": [{"nombre": "Congresista A"}],
        # "comisiones" intentionally omitted to test "Not Found" branch
        "seguimientos": [{"evento": "derivado"}],
    }

    raw_bill = scraper.create_raw_bill(year, bill_number, data)

    assert isinstance(raw_bill, RawBill)
    assert raw_bill.id == f"{year}_{bill_number}"
    assert isinstance(raw_bill.timestamp, datetime)

    # Sections that exist should be JSON-dumped strings
    assert raw_bill.general == json.dumps(data["general"])
    assert raw_bill.congresistas == json.dumps(data["firmantes"])
    assert raw_bill.steps == json.dumps(data["seguimientos"])

    # Missing section in data => attribute should remain None
    assert raw_bill.committees is None


# ---------- add_bills_to_db ----------


def _setup_inmemory_db():
    """Create in-memory SQLite engine and session factory for tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return engine, SessionLocal


def test_add_bills_to_db_persists_raw_bills():
    engine, SessionLocal = _setup_inmemory_db()

    scraper = RawBillScraper()
    # Override engine + Session to use in-memory DB instead of real one
    scraper.engine = engine
    scraper.Session = SessionLocal

    # Prepare one RawBill object in memory
    bill = RawBill(
        id="2021_1",
        timestamp=datetime(2021, 1, 1),
        general=json.dumps({"foo": "bar"}),
        congresistas=None,
        committees=None,
        steps=None,
    )
    scraper.raw_bills = [bill]

    assert scraper.add_bills_to_db() is True

    # Verify it actually exists in the database
    with SessionLocal() as session:
        count = session.query(RawBill).count()
        assert count == 1
        db_bill = session.query(RawBill).first()
        assert db_bill.id == "2021_1"
        assert db_bill.general == json.dumps({"foo": "bar"})


def test_add_bills_to_db_raises_assertion_when_no_bills():
    scraper = RawBillScraper()
    scraper.raw_bills = []

    with pytest.raises(AssertionError):
        scraper.add_bills_to_db()


def test_add_bills_to_db_handles_sqlalchemy_error(monkeypatch):
    scraper = RawBillScraper()
    scraper.raw_bills = [RawBill(id="x", timestamp=datetime.now())]

    class DummySession:
        def __init__(self):
            self.rolled_back = False

        def bulk_save_objects(self, objs):
            from sqlalchemy.exc import SQLAlchemyError

            raise SQLAlchemyError("boom")

        def commit(self):
            pass

        def rollback(self):
            self.rolled_back = True

        def close(self):
            pass

    dummy_session = DummySession()

    def fake_sessionmaker():
        # each call returns the same dummy session (enough for this test)
        return dummy_session

    monkeypatch.setattr(scraper, "Session", fake_sessionmaker)

    ok = scraper.add_bills_to_db()
    assert ok is False
    assert dummy_session.rolled_back is True


# ---------- scrape_bill ----------


def test_scrape_bill_appends_raw_bill(monkeypatch, raw_session):
    scraper = RawBillScraper()
    scraper.session = raw_session

    monkeypatch.setattr(
        scraper,
        "_RawBillScraper__search_api_url",
        lambda bill_url: f"{API_URL}2021/1234",
    )

    # Fake JSON response from get_url_text
    def fake_get_url_text(url: str):
        # Make sure URL is what we expect
        assert url.startswith(API_URL)
        return json.dumps(
            {
                "data": {
                    "general": {"titulo": "Ley de Prueba"},
                    "firmantes": [{"nombre": "Congresista X"}],
                    "comisiones": [{"nombre": "Comisión Y"}],
                    "seguimientos": [{"evento": "ingreso"}],
                }
            }
        )

    # Patch get_url_text in the scraper module
    monkeypatch.setattr("backend.scrapers.bills.get_url_text", fake_get_url_text)
    monkeypatch.setattr(scraper, "update_tracking", lambda bill: bill)

    scraper.scrape_bill("2021", "1234")

    assert len(scraper.raw_bills) == 1
    bill = scraper.raw_bills[0]
    assert bill.id == "2021_1234"
    assert json.loads(bill.general)["titulo"] == "Ley de Prueba"
    assert json.loads(bill.committees)[0]["nombre"] == "Comisión Y"
    assert json.loads(bill.steps)[0]["evento"] == "ingreso"


def test_get_ids_pending_weekly_refresh_filters_by_age_and_approval(raw_session):
    scraper = RawBillScraper(session=raw_session)
    now = datetime.now()

    raw_session.add_all(
        [
            # stale + not approved => include
            RawBill(
                id="2021_1",
                timestamp=now - timedelta(days=10),
                general=json.dumps({"desEstado": "En Comisión"}),
                last_update=True,
            ),
            # stale + approved => exclude
            RawBill(
                id="2021_2",
                timestamp=now - timedelta(days=12),
                general=json.dumps(
                    {"desEstado": "Publicada en el Diario Oficial El Peruano"}
                ),
                last_update=True,
            ),
            # fresh + not approved => exclude
            RawBill(
                id="2021_3",
                timestamp=now - timedelta(days=2),
                general=json.dumps({"desEstado": "En Agenda del Pleno"}),
                last_update=True,
            ),
        ]
    )
    raw_session.commit()

    pending = scraper.get_ids_pending_weekly_refresh(max_age_days=7)
    assert pending == ["2021_1"]


def test_scrape_pending_weekly_uses_ids_without_number_ranges(monkeypatch):
    scraper = RawBillScraper()

    monkeypatch.setattr(
        scraper,
        "get_ids_pending_weekly_refresh",
        lambda max_age_days: ["2021_10", "2022_45"],
    )

    calls = []
    monkeypatch.setattr(
        scraper,
        "scrape_bill",
        lambda year, number: (
            calls.append((year, number)) or scraper.raw_bills.append(object())
        ),
    )

    loads = {"n": 0}
    monkeypatch.setattr(
        scraper,
        "load_raw_bills",
        lambda: (loads.__setitem__("n", loads["n"] + 1), scraper.raw_bills.clear()),
    )

    ids = scraper.scrape_pending_weekly(max_age_days=7, flush_every=1)

    assert ids == ["2021_10", "2022_45"]
    assert calls == [("2021", "10"), ("2022", "45")]
    assert loads["n"] == 2
