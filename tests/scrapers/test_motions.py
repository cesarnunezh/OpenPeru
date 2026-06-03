import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.scrapers.motions import RawMotionScraper, BASE_URL
from backend.database.raw_models import Base, RawMotion


# ---------- create_raw_motion ----------


def test_create_raw_motion_sets_id_and_sections():
    scraper = RawMotionScraper()

    year = "2021"
    motion_number = "50"
    data = {
        "firmantes": [{"nombre": "Congresista A"}],
        "seguimientos": [{"evento": "presentada"}],
        "titulo": "Moción de prueba",
        "detalle": "Detalle de la moción",
    }

    # Keep a copy to check pops
    original_keys = set(data.keys())

    raw_motion = scraper.create_raw_motion(year, motion_number, data)

    assert isinstance(raw_motion, RawMotion)
    assert raw_motion.id == f"{year}_{motion_number}"
    assert isinstance(raw_motion.timestamp, datetime)

    # Mapped sections should be JSON strings
    assert raw_motion.congresistas == json.dumps([{"nombre": "Congresista A"}])
    assert raw_motion.steps == json.dumps([{"evento": "presentada"}])

    # firmantes and seguimientos were popped out of data,
    # and "general" holds the remaining dict
    general_dict = json.loads(raw_motion.general)
    assert "firmantes" not in general_dict
    assert "seguimientos" not in general_dict
    assert set(general_dict.keys()) == original_keys - {
        "firmantes",
        "seguimientos",
    }
    assert general_dict["titulo"] == "Moción de prueba"


def test_create_raw_motion_handles_missing_sections():
    scraper = RawMotionScraper()

    year = "2022"
    motion_number = "10"
    data = {
        # "firmantes" missing
        # "seguimientos" missing
        "titulo": "Sin firmantes",
    }

    raw_motion = scraper.create_raw_motion(year, motion_number, data)

    # When section is missing, attributes should stay None
    assert raw_motion.congresistas is None
    assert raw_motion.steps is None

    # general should contain full original data (since nothing was popped)
    general_dict = json.loads(raw_motion.general)
    assert general_dict == {"titulo": "Sin firmantes"}


# ---------- add_motions_to_db ----------


def _setup_inmemory_db():
    """Create in-memory SQLite engine and session factory for tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return engine, SessionLocal


def test_add_motions_to_db_persists_raw_motions():
    engine, SessionLocal = _setup_inmemory_db()

    scraper = RawMotionScraper()
    # Override engine + Session to use in-memory DB instead of real one
    scraper.engine = engine
    scraper.Session = SessionLocal

    motion = RawMotion(
        id="2021_5",
        timestamp=datetime(2021, 1, 1),
        general=json.dumps({"titulo": "Guardado en DB"}),
        congresistas=None,
        steps=None,
    )
    scraper.raw_motions = [motion]

    assert scraper.add_motions_to_db() is True

    with SessionLocal() as session:
        count = session.query(RawMotion).count()
        assert count == 1
        db_motion = session.query(RawMotion).first()
        assert db_motion.id == "2021_5"
        assert json.loads(db_motion.general)["titulo"] == "Guardado en DB"


def test_add_motions_to_db_raises_assertion_when_no_motions():
    scraper = RawMotionScraper()
    scraper.raw_motions = []

    with pytest.raises(AssertionError):
        scraper.add_motions_to_db()


def test_add_motions_to_db_handles_sqlalchemy_error(monkeypatch):
    scraper = RawMotionScraper()
    scraper.raw_motions = [RawMotion(id="x", timestamp=datetime.now())]

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
        return dummy_session

    monkeypatch.setattr(scraper, "Session", fake_sessionmaker)

    ok = scraper.add_motions_to_db()
    assert ok is False
    assert dummy_session.rolled_back is True


# ---------- scrape_motion ----------


def test_scrape_motion_appends_raw_motion(monkeypatch, raw_session):
    scraper = RawMotionScraper()
    scraper.session = raw_session

    def fake_get_url_text(url):
        # validate URL
        assert url == f"{BASE_URL}/mocion/2021/7"
        return json.dumps(
            {
                "data": {
                    "firmantes": [{"nombre": "Congresista X"}],
                    "seguimientos": [{"evento": "ingreso"}],
                    "titulo": "Moción X",
                }
            }
        )

    # Patch get_url_text in this module
    monkeypatch.setattr(
        "backend.scrapers.motions.get_url_text",
        fake_get_url_text,
    )
    monkeypatch.setattr(scraper, "update_tracking", lambda motion: motion)

    scraper.scrape_motion("2021", "7")

    assert len(scraper.raw_motions) == 1
    motion = scraper.raw_motions[0]
    assert motion.id == "2021_7"

    # congresistas and steps JSON
    assert json.loads(motion.congresistas)[0]["nombre"] == "Congresista X"
    assert json.loads(motion.steps)[0]["evento"] == "ingreso"

    # general contains remaining fields (after pops)
    general_dict = json.loads(motion.general)
    assert "titulo" in general_dict
    assert general_dict["titulo"] == "Moción X"


def test_get_ids_pending_weekly_refresh_filters_by_age_and_approval(raw_session):
    scraper = RawMotionScraper(session=raw_session)
    now = datetime.now()

    raw_session.add_all(
        [
            # stale + not approved => include
            RawMotion(
                id="2021_1",
                timestamp=now - timedelta(days=10),
                general=json.dumps({"desEstadoMocion": "Aprobada"}),
                last_update=True,
            ),
            # stale + approved => exclude
            RawMotion(
                id="2021_2",
                timestamp=now - timedelta(days=12),
                general=json.dumps(
                    {"desEstadoMocion": "Publicado Diario Oficial  El Peruano"}
                ),
                last_update=True,
            ),
            # fresh + not approved => exclude
            RawMotion(
                id="2021_3",
                timestamp=now - timedelta(days=2),
                general=json.dumps({"desEstadoMocion": "En Comisión"}),
                last_update=True,
            ),
        ]
    )
    raw_session.commit()

    pending = scraper.get_ids_pending_weekly_refresh(max_age_days=7)
    assert pending == ["2021_1"]


def test_scrape_pending_weekly_uses_ids_without_number_ranges(monkeypatch):
    scraper = RawMotionScraper()

    monkeypatch.setattr(
        scraper,
        "get_ids_pending_weekly_refresh",
        lambda max_age_days: ["2021_10", "2022_45"],
    )

    calls = []
    monkeypatch.setattr(
        scraper,
        "scrape_motion",
        lambda year, number: (
            calls.append((year, number)) or scraper.raw_motions.append(object())
        ),
    )

    loads = {"n": 0}
    monkeypatch.setattr(
        scraper,
        "load_raw_motions",
        lambda: (loads.__setitem__("n", loads["n"] + 1), scraper.raw_motions.clear()),
    )

    ids = scraper.scrape_pending_weekly(max_age_days=7, flush_every=1)

    assert ids == ["2021_10", "2022_45"]
    assert calls == [("2021", "10"), ("2022", "45")]
    assert loads["n"] == 2
