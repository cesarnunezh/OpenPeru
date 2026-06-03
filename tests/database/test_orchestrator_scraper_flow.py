from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from backend.database import orchestrator as orchestrator_module
from backend.database.crud.pipeline_core import ScraperStats
from backend.database.orchestrator import OpenPeruOrchestrator
from backend.database.raw_models import RawBill, RawLey, RawMotion


class DummyStage:
    def __enter__(self):
        return SimpleNamespace(info=lambda *args, **kwargs: None)

    def __exit__(self, exc_type, exc, tb):
        return False


class DummyLogManager:
    def console_logger(self):
        return SimpleNamespace(info=lambda *args, **kwargs: None)

    def stage(self, *args, **kwargs):
        return DummyStage()


class DummyBillScraper:
    raw_bills = []

    def scrape_bill(self, *args):
        pass

    def load_raw_bills(self):
        pass


class DummyMotionScraper:
    raw_motions = []

    def scrape_motion(self, *args):
        pass

    def load_raw_motions(self):
        pass


class DummyLeyScraper:
    raw_leyes = []

    def scrape_ley(self, *args):
        pass

    def load_raw_leyes(self):
        pass


def _stats(start_second: int, end_second: int, scrapped: int) -> ScraperStats:
    return ScraperStats(
        datetime(2026, 1, 1, 0, 0, start_second),
        datetime(2026, 1, 1, 0, 0, end_second),
        scrapped,
    )


def test_bills_scrape_new_ids_before_pending_daily(monkeypatch):
    calls = []
    orch = OpenPeruOrchestrator.__new__(OpenPeruOrchestrator)

    monkeypatch.setattr(orchestrator_module, "log_manager", DummyLogManager())
    monkeypatch.setattr(
        "backend.scrapers.bills.RawBillScraper",
        DummyBillScraper,
    )
    monkeypatch.setattr(
        orch,
        "_scrape_range",
        lambda **kwargs: (
            calls.append(("range", kwargs["raw_model"])) or _stats(1, 2, 3)
        ),
    )
    monkeypatch.setattr(
        orch,
        "_scrape_pending_daily",
        lambda **kwargs: (
            calls.append(("pending", kwargs["raw_model"], kwargs["model"]))
            or _stats(3, 4, 5)
        ),
    )
    monkeypatch.setattr(
        orch, "_load_scraper_results", lambda name: calls.append(("load", name))
    )

    orch.run_scrapers(
        scrape_bills=True,
        scrape_motions=False,
        scrape_leyes=False,
        scrape_others=False,
    )

    assert calls == [
        ("range", orchestrator_module.RawBill),
        ("pending", orchestrator_module.RawBill, orchestrator_module.Bill),
        ("load", "bills.py"),
    ]
    assert orch.scraper_results["bills.py"] == _stats(1, 4, 8)


def test_motions_scrape_new_ids_before_pending_daily(monkeypatch):
    calls = []
    orch = OpenPeruOrchestrator.__new__(OpenPeruOrchestrator)

    monkeypatch.setattr(orchestrator_module, "log_manager", DummyLogManager())
    monkeypatch.setattr(
        "backend.scrapers.motions.RawMotionScraper",
        DummyMotionScraper,
    )
    monkeypatch.setattr(
        orch,
        "_scrape_range",
        lambda **kwargs: (
            calls.append(("range", kwargs["raw_model"])) or _stats(1, 2, 7)
        ),
    )
    monkeypatch.setattr(
        orch,
        "_scrape_pending_daily",
        lambda **kwargs: (
            calls.append(("pending", kwargs["raw_model"], kwargs["model"]))
            or _stats(3, 4, 11)
        ),
    )
    monkeypatch.setattr(
        orch, "_load_scraper_results", lambda name: calls.append(("load", name))
    )

    orch.run_scrapers(
        scrape_bills=False,
        scrape_motions=True,
        scrape_leyes=False,
        scrape_others=False,
    )

    assert calls == [
        ("range", orchestrator_module.RawMotion),
        ("pending", orchestrator_module.RawMotion, orchestrator_module.Motion),
        ("load", "motions.py"),
    ]
    assert orch.scraper_results["motions.py"] == _stats(1, 4, 18)


def test_leyes_only_scrape_new_ids(monkeypatch):
    calls = []
    orch = OpenPeruOrchestrator.__new__(OpenPeruOrchestrator)

    monkeypatch.setattr(orchestrator_module, "log_manager", DummyLogManager())
    monkeypatch.setattr(
        "backend.scrapers.leyes.RawLeyesScraper",
        DummyLeyScraper,
    )
    monkeypatch.setattr(
        orch,
        "_scrape_range",
        lambda **kwargs: (
            calls.append(("range", kwargs["raw_model"])) or _stats(1, 2, 13)
        ),
    )
    monkeypatch.setattr(
        orch,
        "_scrape_pending_daily",
        lambda **kwargs: calls.append(("pending", kwargs["raw_model"])),
    )
    monkeypatch.setattr(
        orch, "_load_scraper_results", lambda name: calls.append(("load", name))
    )

    orch.run_scrapers(
        scrape_bills=False,
        scrape_motions=False,
        scrape_leyes=True,
        scrape_others=False,
    )

    assert calls == [
        ("range", orchestrator_module.RawLey),
        ("load", "leyes.py"),
    ]
    assert orch.scraper_results["leyes.py"] == _stats(1, 2, 13)


def test_scrape_range_starts_after_matching_raw_model(monkeypatch, engine, session):
    session.add(
        RawBill(
            id="2021_100",
            timestamp=datetime(2026, 1, 1),
            last_update=True,
            changed=True,
            processed=False,
        )
    )
    session.add(
        RawMotion(
            id="2021_5",
            timestamp=datetime(2026, 1, 1),
            last_update=True,
            changed=True,
            processed=False,
        )
    )
    session.commit()

    calls = []
    scraper = SimpleNamespace(raw_motions=[])
    orch = OpenPeruOrchestrator(engine=engine)

    def scrape_motion(year, number):
        calls.append((year, number))
        scraper.raw_motions.append(object())

    def load_raw_motions():
        scraper.raw_motions.clear()

    monkeypatch.setattr(orchestrator_module, "get_last_id", lambda entity_name: 7)

    stats = orch._scrape_range(
        scraper=scraper,
        raw_model=RawMotion,
        scrape_fn=scrape_motion,
        buffer_attr="raw_motions",
        load_fn=load_raw_motions,
        flush_every=100,
        entity_name="Motions",
    )

    assert calls == [("2021", "6"), ("2021", "7")]
    assert stats.scrapped == 2


def test_scrape_range_uses_plain_ley_numbers(monkeypatch, engine, session):
    session.add(
        RawLey(
            id=32558,
            data="<root />",
            timestamp=datetime(2026, 1, 1),
            last_update=True,
            changed=True,
            processed=False,
        )
    )
    session.commit()

    calls = []
    scraper = SimpleNamespace(raw_leyes=[])
    orch = OpenPeruOrchestrator(engine=engine)

    def scrape_ley(number):
        calls.append(number)
        scraper.raw_leyes.append(object())

    def load_raw_leyes():
        scraper.raw_leyes.clear()

    monkeypatch.setattr(orchestrator_module, "get_last_id", lambda entity_name: 32560)

    stats = orch._scrape_range(
        scraper=scraper,
        raw_model=RawLey,
        scrape_fn=scrape_ley,
        buffer_attr="raw_leyes",
        load_fn=load_raw_leyes,
        flush_every=100,
        entity_name="Leyes",
    )

    assert calls == [32559, 32560]
    assert stats.scrapped == 2
