from datetime import datetime

import pytest
from lxml.html import fromstring
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from backend.database.raw_models import Base, RawCommittee
from backend.scrapers.committees import (
    BASE_URL,
    COMMITTEE_SELECT,
    LINKS_SELECTOR,
    ROWS_SELECTOR,
    TABLE_SELECTOR,
    RawCommitteeScraper,
)


# ---------- helpers ----------


def make_scraper():
    """
    Avoid calling RawCommitteeScraper.__init__ because it creates
    a real engine from settings.DB_URL.
    """
    scraper = RawCommitteeScraper.__new__(RawCommitteeScraper)
    scraper.url = BASE_URL
    return scraper


def setup_inmemory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return engine, SessionLocal


class FakeLocator:
    def __init__(self, count_value=1, html="<tbody>before</tbody>"):
        self.count_value = count_value
        self.html = html

    def count(self):
        return self.count_value

    def inner_html(self):
        return self.html


class FakePage:
    def __init__(
        self,
        rows_count=1,
        links_count=1,
        content="<html>OK</html>",
        timeout_on_selector=False,
        timeout_on_change=False,
    ):
        self.rows_count = rows_count
        self.links_count = links_count
        self._content = content
        self.timeout_on_selector = timeout_on_selector
        self.timeout_on_change = timeout_on_change
        self.goto_calls = []

    def wait_for_selector(self, selector, state=None):
        if self.timeout_on_selector:
            raise PlaywrightTimeoutError("selector timed out")
        return True

    def wait_for_function(self, script, arg=None, timeout=None):
        if self.timeout_on_change and timeout == 5000:
            raise PlaywrightTimeoutError("table did not change")
        return True

    def locator(self, selector):
        if selector == TABLE_SELECTOR:
            return FakeLocator(html="<tbody>before</tbody>")
        if selector == ROWS_SELECTOR:
            return FakeLocator(count_value=self.rows_count)
        if selector == LINKS_SELECTOR:
            return FakeLocator(count_value=self.links_count)
        return FakeLocator()

    def evaluate(self, script, arg):
        return True

    def eval_on_selector(self, selector, script):
        assert selector == COMMITTEE_SELECT
        return {"Ordinaria": "1", "Especial": "2"}

    def content(self):
        return self._content

    def goto(self, url, wait_until=None):
        self.goto_calls.append((url, wait_until))


# ---------- get_options ----------


def test_get_options_parses_select(monkeypatch):
    scraper = make_scraper()

    def fake_parse_url(url):
        assert url == BASE_URL
        html = """
        <html><body>
          <select name="idRegistroPadre">
            <option value="2021">2021</option>
            <option value="2022">2022</option>
            <option>--Seleccione--</option>
          </select>
        </body></html>
        """
        return fromstring(html)

    monkeypatch.setattr("backend.scrapers.committees.parse_url", fake_parse_url)

    options = scraper.get_options(url=BASE_URL, select_name="idRegistroPadre")

    assert options == {
        "2021": "2021",
        "2022": "2022",
    }


def test_get_options_returns_empty_when_parse_fails(monkeypatch):
    scraper = make_scraper()

    monkeypatch.setattr("backend.scrapers.committees.parse_url", lambda url: None)

    assert scraper.get_options(BASE_URL) == {}


# ---------- _get_committee_options_current_page ----------


def test_get_committee_options_current_page():
    page = FakePage()

    options = RawCommitteeScraper._get_committee_options_current_page(page)

    assert options == {
        "Ordinaria": "1",
        "Especial": "2",
    }


# ---------- get_html_with_selections ----------


def test_get_html_with_selections_success(monkeypatch):
    scraper = make_scraper()
    page = FakePage(
        rows_count=2,
        links_count=2,
        content="<html>committee data</html>",
    )

    monkeypatch.setattr(scraper, "_select_year", lambda page, year_value: None)
    monkeypatch.setattr(
        RawCommitteeScraper,
        "_set_select",
        staticmethod(lambda page, selector, value: None),
    )

    html = scraper.get_html_with_selections(
        page=page,
        year_value="2025",
        committee_value="1",
    )

    assert html == "<html>committee data</html>"


def test_get_html_with_selections_returns_none_when_table_empty(monkeypatch):
    scraper = make_scraper()
    page = FakePage(rows_count=0, links_count=0)

    warnings = []

    monkeypatch.setattr(scraper, "_select_year", lambda page, year_value: None)
    monkeypatch.setattr(
        RawCommitteeScraper,
        "_set_select",
        staticmethod(lambda page, selector, value: None),
    )
    monkeypatch.setattr(
        "backend.scrapers.committees.logger.warning",
        lambda message: warnings.append(message),
    )

    html = scraper.get_html_with_selections(
        page=page,
        year_value="2025",
        committee_value="1",
    )

    assert html is None
    assert any(
        "No committees found for type=1 and year=2025" in msg for msg in warnings
    )


def test_get_html_with_selections_continues_when_table_does_not_change(monkeypatch):
    scraper = make_scraper()
    page = FakePage(
        rows_count=1,
        links_count=1,
        timeout_on_change=True,
        content="<html>still valid</html>",
    )

    warnings = []

    monkeypatch.setattr(scraper, "_select_year", lambda page, year_value: None)
    monkeypatch.setattr(
        RawCommitteeScraper,
        "_set_select",
        staticmethod(lambda page, selector, value: None),
    )
    monkeypatch.setattr(
        "backend.scrapers.committees.logger.warning",
        lambda message: warnings.append(message),
    )

    html = scraper.get_html_with_selections(
        page=page,
        year_value="2025",
        committee_value="1",
    )

    assert html == "<html>still valid</html>"
    assert any("Table content did not visibly change" in msg for msg in warnings)


def test_get_html_with_selections_returns_none_on_playwright_timeout(monkeypatch):
    scraper = make_scraper()
    page = FakePage(timeout_on_selector=True)

    monkeypatch.setattr(scraper, "_select_year", lambda page, year_value: None)

    html = scraper.get_html_with_selections(
        page=page,
        year_value="2025",
        committee_value="1",
    )

    assert html is None


# ---------- get_raw_committees ----------


def test_get_raw_committees_builds_committee_list(monkeypatch):
    scraper = make_scraper()

    monkeypatch.setattr(
        scraper,
        "get_options",
        lambda url, select_name="idRegistroPadre": {
            "2024-2025": "2025",
            "2023-2024": "2024",
        },
    )
    monkeypatch.setattr(scraper, "_select_year", lambda page, year_value: None)
    monkeypatch.setattr(
        scraper,
        "_get_committee_options_current_page",
        lambda page: {
            "Ordinaria": "1",
            "Especial": "2",
        },
    )

    def fake_get_html_with_selections(page, year_value, committee_value):
        if year_value == "2025" and committee_value == "2":
            return None
        return f"<html>year={year_value}, committee={committee_value}</html>"

    monkeypatch.setattr(
        scraper,
        "get_html_with_selections",
        fake_get_html_with_selections,
    )
    monkeypatch.setattr(scraper, "update_tracking", lambda committee: committee)

    class FakeBrowser:
        def __init__(self):
            self.closed = False
            self.page = FakePage()

        def new_page(self):
            return self.page

        def close(self):
            self.closed = True

    class FakeChromium:
        def __init__(self):
            self.browser = FakeBrowser()

        def launch(self, headless=True):
            assert headless is True
            return self.browser

    class FakePlaywright:
        def __init__(self):
            self.chromium = FakeChromium()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        "backend.scrapers.committees.sync_playwright",
        lambda: FakePlaywright(),
    )

    scraper.get_raw_committees(only_current=True)

    assert hasattr(scraper, "committee_list")
    assert len(scraper.committee_list) == 1

    committee = scraper.committee_list[0]
    assert committee.legislative_year == "2024-2025"
    assert committee.committee_type == "Ordinaria"
    assert committee.raw_html == "<html>year=2025, committee=1</html>"


def test_get_raw_committees_all_years(monkeypatch):
    scraper = make_scraper()

    monkeypatch.setattr(
        scraper,
        "get_options",
        lambda url, select_name="idRegistroPadre": {
            "2024-2025": "2025",
            "2023-2024": "2024",
        },
    )
    monkeypatch.setattr(scraper, "_select_year", lambda page, year_value: None)
    monkeypatch.setattr(
        scraper,
        "_get_committee_options_current_page",
        lambda page: {"Ordinaria": "1"},
    )
    monkeypatch.setattr(
        scraper,
        "get_html_with_selections",
        lambda page, year_value, committee_value: (
            f"<html>year={year_value}, committee={committee_value}</html>"
        ),
    )
    monkeypatch.setattr(scraper, "update_tracking", lambda committee: committee)

    class FakeBrowser:
        def new_page(self):
            return FakePage()

        def close(self):
            pass

    class FakePlaywright:
        def __enter__(self):
            self.chromium = self
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def launch(self, headless=True):
            return FakeBrowser()

    monkeypatch.setattr(
        "backend.scrapers.committees.sync_playwright",
        lambda: FakePlaywright(),
    )

    scraper.get_raw_committees(only_current=False)

    assert len(scraper.committee_list) == 2
    assert {c.legislative_year for c in scraper.committee_list} == {
        "2024-2025",
        "2023-2024",
    }


def test_get_raw_committees_aborts_when_no_years(monkeypatch):
    scraper = make_scraper()

    monkeypatch.setattr(scraper, "get_options", lambda url, select_name: {})

    scraper.get_raw_committees()

    assert scraper.committee_list == []


# ---------- update_tracking ----------


def test_update_tracking_first_version_marks_changed():
    engine, SessionLocal = setup_inmemory_db()
    scraper = make_scraper()
    scraper.Session = SessionLocal

    committee = RawCommittee(
        timestamp=datetime(2026, 1, 1),
        legislative_year="2025-2026",
        committee_type="Ordinaria",
        raw_html="<html>new</html>",
        changed=False,
        processed=True,
        last_update=False,
    )

    result = scraper.update_tracking(committee)

    assert result.changed is True
    assert result.processed is False
    assert result.last_update is True


def test_update_tracking_existing_same_version_marks_not_changed():
    engine, SessionLocal = setup_inmemory_db()
    scraper = make_scraper()
    scraper.Session = SessionLocal

    old = RawCommittee(
        timestamp=datetime(2026, 1, 1),
        legislative_year="2025-2026",
        committee_type="Ordinaria",
        raw_html="<html>same</html>",
        changed=True,
        processed=False,
        last_update=True,
    )

    with SessionLocal() as session:
        session.add(old)
        session.commit()

    new = RawCommittee(
        timestamp=datetime(2026, 1, 2),
        legislative_year="2025-2026",
        committee_type="Ordinaria",
        raw_html="<html>same</html>",
        changed=False,
        processed=False,
        last_update=True,
    )

    result = scraper.update_tracking(new)

    assert result.changed is False
    assert result.processed is True
    assert result.last_update is True

    with SessionLocal() as session:
        old_from_db = session.query(RawCommittee).first()
        assert old_from_db.last_update is False


def test_update_tracking_existing_different_version_marks_changed():
    engine, SessionLocal = setup_inmemory_db()
    scraper = make_scraper()
    scraper.Session = SessionLocal

    old = RawCommittee(
        timestamp=datetime(2026, 1, 1),
        legislative_year="2025-2026",
        committee_type="Ordinaria",
        raw_html="<html>old</html>",
        changed=True,
        processed=False,
        last_update=True,
    )

    with SessionLocal() as session:
        session.add(old)
        session.commit()

    new = RawCommittee(
        timestamp=datetime(2026, 1, 2),
        legislative_year="2025-2026",
        committee_type="Ordinaria",
        raw_html="<html>new</html>",
        changed=False,
        processed=False,
        last_update=True,
    )

    result = scraper.update_tracking(new)

    assert result.changed is True
    assert result.processed is False
    assert result.last_update is True


# ---------- add_committees_to_db ----------


def test_add_committees_to_db_persists():
    engine, SessionLocal = setup_inmemory_db()

    scraper = make_scraper()
    scraper.Session = SessionLocal

    scraper.committee_list = [
        RawCommittee(
            timestamp=datetime(2026, 1, 1),
            legislative_year="2025-2026",
            committee_type="Ordinaria",
            raw_html="<html>data</html>",
            changed=True,
            processed=False,
            last_update=True,
        )
    ]

    assert scraper.add_committees_to_db() is True

    with SessionLocal() as session:
        rows = session.query(RawCommittee).all()

    assert len(rows) == 1
    assert rows[0].legislative_year == "2025-2026"
    assert rows[0].committee_type == "Ordinaria"
    assert rows[0].raw_html == "<html>data</html>"


def test_add_committees_to_db_asserts_when_empty():
    scraper = make_scraper()
    scraper.committee_list = []

    with pytest.raises(AssertionError):
        scraper.add_committees_to_db()


def test_add_committees_to_db_handles_sqlalchemy_error():
    scraper = make_scraper()

    scraper.committee_list = [
        RawCommittee(
            timestamp=datetime.now(),
            legislative_year="2025-2026",
            committee_type="Ordinaria",
            raw_html="<html></html>",
        )
    ]

    class DummySession:
        def __init__(self):
            self.rolled_back = False
            self.closed = False

        def bulk_save_objects(self, objs):
            raise SQLAlchemyError("boom")

        def commit(self):
            pass

        def rollback(self):
            self.rolled_back = True

        def close(self):
            self.closed = True

    dummy_session = DummySession()
    scraper.Session = lambda: dummy_session

    assert scraper.add_committees_to_db() is False
    assert dummy_session.rolled_back is True
    assert dummy_session.closed is True
