from __future__ import annotations

from backend import cli


class FakeOrchestrator:
    instances: list["FakeOrchestrator"] = []

    def __init__(self):
        self.scraper_calls = []
        self.processing_calls = []
        self.instances.append(self)

    def run_scrapers(self, **kwargs):
        self.scraper_calls.append(kwargs)

    def run_processing(self, **kwargs):
        self.processing_calls.append(kwargs)


def run_cli(monkeypatch, argv):
    FakeOrchestrator.instances = []
    monkeypatch.setattr(cli, "OpenPeruOrchestrator", FakeOrchestrator)

    cli.main(argv)

    assert len(FakeOrchestrator.instances) == 1
    return FakeOrchestrator.instances[0]


def test_cli_scrape_only_others_matches_make_target(monkeypatch):
    orch = run_cli(
        monkeypatch,
        ["--scrape", "--skip-processing", "--only-others", "--only-current"],
    )

    assert orch.scraper_calls == [
        {
            "scrape_bills": False,
            "scrape_motions": False,
            "scrape_leyes": False,
            "scrape_others": True,
            "only_current": True,
            "scrape_documents": False,
        }
    ]
    assert orch.processing_calls == []


def test_cli_scrape_only_bills_matches_make_target(monkeypatch):
    orch = run_cli(monkeypatch, ["--scrape", "--skip-processing", "--only-bills"])

    assert orch.scraper_calls == [
        {
            "scrape_bills": True,
            "scrape_motions": False,
            "scrape_leyes": False,
            "scrape_others": False,
            "only_current": False,
            "scrape_documents": False,
        }
    ]
    assert orch.processing_calls == []


def test_cli_scrape_only_motions_matches_make_target(monkeypatch):
    orch = run_cli(monkeypatch, ["--scrape", "--skip-processing", "--only-motions"])

    assert orch.scraper_calls == [
        {
            "scrape_bills": False,
            "scrape_motions": True,
            "scrape_leyes": False,
            "scrape_others": False,
            "only_current": False,
            "scrape_documents": False,
        }
    ]
    assert orch.processing_calls == []


def test_cli_scrape_only_leyes_matches_make_target(monkeypatch):
    orch = run_cli(monkeypatch, ["--scrape", "--skip-processing", "--only-leyes"])

    assert orch.scraper_calls == [
        {
            "scrape_bills": False,
            "scrape_motions": False,
            "scrape_leyes": True,
            "scrape_others": False,
            "only_current": False,
            "scrape_documents": False,
        }
    ]
    assert orch.processing_calls == []


def test_cli_process_target_runs_all_processing(monkeypatch):
    orch = run_cli(monkeypatch, [])

    assert orch.scraper_calls == []
    assert orch.processing_calls == [
        {
            "process_bills": True,
            "process_motions": True,
            "process_leyes": True,
            "process_others": True,
            "process_documents": False,
            "first_load": False,
        }
    ]
