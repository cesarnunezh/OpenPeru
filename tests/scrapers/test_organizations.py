from datetime import datetime

import pytest
from lxml.html import fromstring
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

import backend.scrapers.organizations as organizations
from backend.database.raw_models import Base, RawOrganization
from backend.scrapers.organizations import BASE_URLS, RawOrganizationScraper


# ---------- helpers ----------


def make_scraper():
    """
    Avoid calling RawOrganizationScraper.__init__ because it creates
    a real engine from settings.DB_URL.
    """
    scraper = RawOrganizationScraper.__new__(RawOrganizationScraper)
    scraper.urls = BASE_URLS
    return scraper


def setup_inmemory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return engine, SessionLocal


class FakePage:
    def __init__(
        self,
        content="<html>OK</html>",
        timeout_on_selector=False,
        timeout_on_function=False,
        timeout_on_content=False,
    ):
        self._content = content
        self.timeout_on_selector = timeout_on_selector
        self.timeout_on_function = timeout_on_function
        self.timeout_on_content = timeout_on_content

        self.goto_calls = []
        self.selector_waits = []
        self.evaluate_calls = []
        self.function_waits = []
        self.timeout_waits = []

    def goto(self, url, wait_until=None):
        self.goto_calls.append((url, wait_until))

    def wait_for_selector(self, selector, state=None):
        self.selector_waits.append((selector, state))
        if self.timeout_on_selector:
            raise PlaywrightTimeoutError("selector timed out")
        return True

    def evaluate(self, script, arg):
        self.evaluate_calls.append((script, arg))
        return [arg["value"]]

    def wait_for_function(self, script, arg=None):
        self.function_waits.append((script, arg))
        if self.timeout_on_function:
            raise PlaywrightTimeoutError("function timed out")
        return True

    def wait_for_timeout(self, timeout):
        self.timeout_waits.append(timeout)

    def content(self):
        if self.timeout_on_content:
            raise PlaywrightTimeoutError("content timed out")
        return self._content


class FakeBrowser:
    def __init__(self, page):
        self.page = page
        self.closed = False

    def new_page(self):
        return self.page

    def close(self):
        self.closed = True


class FakeChromium:
    def __init__(self, browser):
        self.browser = browser
        self.launch_calls = []

    def launch(self, headless=True):
        self.launch_calls.append(headless)
        return self.browser


class FakePlaywright:
    def __init__(self, chromium):
        self.chromium = chromium

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


# ---------- get_options ----------


def test_get_options_parses_select(monkeypatch):
    scraper = make_scraper()

    def fake_parse_url(url):
        html = """
        <html><body>
          <select name="idRegistroPadre">
            <option value="2025">2024-2025</option>
            <option value="2024">2023-2024</option>
            <option value=""></option>
          </select>
        </body></html>
        """
        return fromstring(html)

    monkeypatch.setattr(organizations, "parse_url", fake_parse_url)

    options = scraper.get_options(
        url="https://fake-url.test",
        select_name="idRegistroPadre",
    )

    assert options == {
        "2024-2025": "2025",
        "2023-2024": "2024",
    }


def test_get_options_returns_empty_when_parse_fails(monkeypatch):
    scraper = make_scraper()

    monkeypatch.setattr(organizations, "parse_url", lambda url: None)

    assert scraper.get_options("https://fake-url.test") == {}


# ---------- get_html_with_selections ----------


def test_get_html_with_selections_success(monkeypatch):
    scraper = make_scraper()

    page = FakePage(content="<html>organization data</html>")
    browser = FakeBrowser(page)
    chromium = FakeChromium(browser)
    playwright = FakePlaywright(chromium)

    monkeypatch.setattr(organizations, "sync_playwright", lambda: playwright)

    html = scraper.get_html_with_selections(
        url="https://fake-url.test",
        period_value="2025",
    )

    assert html == "<html>organization data</html>"
    assert chromium.launch_calls == [True]
    assert page.goto_calls == [("https://fake-url.test", "domcontentloaded")]
    assert page.selector_waits == [
        ('select[name="idRegistroPadre"]', "attached"),
        ("table.congresistas", "visible"),
    ]
    assert [call[1] for call in page.evaluate_calls] == [
        {
            "selector": 'select[name="idRegistroPadre"]',
            "value": "2025",
        }
    ]
    assert [call[1] for call in page.function_waits] == [
        {
            "selector": 'select[name="idRegistroPadre"]',
            "value": "2025",
        }
    ]
    assert page.timeout_waits == [1000]
    assert browser.closed is True


def test_get_html_with_selections_returns_none_on_playwright_timeout(monkeypatch):
    scraper = make_scraper()

    page = FakePage(timeout_on_selector=True)
    browser = FakeBrowser(page)
    chromium = FakeChromium(browser)
    playwright = FakePlaywright(chromium)

    monkeypatch.setattr(organizations, "sync_playwright", lambda: playwright)

    html = scraper.get_html_with_selections(
        url="https://fake-url.test",
        period_value="2025",
    )

    assert html is None
    assert browser.closed is True


# ---------- get_raw_organizations ----------


def test_get_raw_organizations_builds_organization_list_only_current(monkeypatch):
    scraper = make_scraper()
    scraper.urls = {
        "Mesa Directiva": "https://mesa.test",
        "Consejo Directivo": "https://consejo.test",
    }

    monkeypatch.setattr(
        scraper,
        "get_options",
        lambda url, select_name="idRegistroPadre": {
            "2024-2025": "2025",
            "2023-2024": "2024",
        },
    )

    def fake_get_html_with_selections(url, period_value):
        if url == "https://consejo.test":
            return None
        return f"<html>url={url}, period={period_value}</html>"

    monkeypatch.setattr(
        scraper,
        "get_html_with_selections",
        fake_get_html_with_selections,
    )
    monkeypatch.setattr(scraper, "update_tracking", lambda org: org)

    scraper.get_raw_organizations(only_current=True)

    assert hasattr(scraper, "organizations_list")
    assert len(scraper.organizations_list) == 1

    org = scraper.organizations_list[0]
    assert org.legislative_year == "2024-2025"
    assert org.type_org == "Mesa Directiva"
    assert org.raw_html == "<html>url=https://mesa.test, period=2025</html>"
    assert org.processed is False
    assert org.last_update is True


def test_get_raw_organizations_all_years(monkeypatch):
    scraper = make_scraper()
    scraper.urls = {
        "Mesa Directiva": "https://mesa.test",
    }

    monkeypatch.setattr(
        scraper,
        "get_options",
        lambda url, select_name="idRegistroPadre": {
            "2024-2025": "2025",
            "2023-2024": "2024",
        },
    )
    monkeypatch.setattr(
        scraper,
        "get_html_with_selections",
        lambda url, period_value: f"<html>period={period_value}</html>",
    )
    monkeypatch.setattr(scraper, "update_tracking", lambda org: org)

    scraper.get_raw_organizations(only_current=False)

    assert len(scraper.organizations_list) == 2
    assert [org.legislative_year for org in scraper.organizations_list] == [
        "2024-2025",
        "2023-2024",
    ]
    assert [org.raw_html for org in scraper.organizations_list] == [
        "<html>period=2025</html>",
        "<html>period=2024</html>",
    ]


# ---------- update_tracking ----------


def test_update_tracking_first_version_marks_changed():
    engine, SessionLocal = setup_inmemory_db()

    scraper = make_scraper()
    scraper.Session = SessionLocal

    org = RawOrganization(
        timestamp=datetime(2026, 1, 1),
        legislative_year="2025-2026",
        type_org="Mesa Directiva",
        raw_html="<html>new</html>",
        changed=False,
        processed=True,
        last_update=False,
    )

    result = scraper.update_tracking(org)

    assert result.changed is True
    assert result.processed is False
    assert result.last_update is True


def test_update_tracking_existing_same_version_marks_not_changed():
    engine, SessionLocal = setup_inmemory_db()

    scraper = make_scraper()
    scraper.Session = SessionLocal

    old = RawOrganization(
        timestamp=datetime(2026, 1, 1),
        legislative_year="2025-2026",
        type_org="Mesa Directiva",
        raw_html="<html>same</html>",
        changed=True,
        processed=False,
        last_update=True,
    )

    with SessionLocal() as session:
        session.add(old)
        session.commit()

    new = RawOrganization(
        timestamp=datetime(2026, 1, 2),
        legislative_year="2025-2026",
        type_org="Mesa Directiva",
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
        old_from_db = session.query(RawOrganization).first()
        assert old_from_db.last_update is False


def test_update_tracking_existing_different_version_marks_changed():
    engine, SessionLocal = setup_inmemory_db()

    scraper = make_scraper()
    scraper.Session = SessionLocal

    old = RawOrganization(
        timestamp=datetime(2026, 1, 1),
        legislative_year="2025-2026",
        type_org="Mesa Directiva",
        raw_html="<html>old</html>",
        changed=True,
        processed=False,
        last_update=True,
    )

    with SessionLocal() as session:
        session.add(old)
        session.commit()

    new = RawOrganization(
        timestamp=datetime(2026, 1, 2),
        legislative_year="2025-2026",
        type_org="Mesa Directiva",
        raw_html="<html>new</html>",
        changed=False,
        processed=False,
        last_update=True,
    )

    result = scraper.update_tracking(new)

    assert result.changed is True
    assert result.processed is False
    assert result.last_update is True

    with SessionLocal() as session:
        old_from_db = session.query(RawOrganization).first()
        assert old_from_db.last_update is False


# ---------- add_organizations_to_db ----------


def test_add_organizations_to_db_persists():
    engine, SessionLocal = setup_inmemory_db()

    scraper = make_scraper()
    scraper.Session = SessionLocal

    scraper.organizations_list = [
        RawOrganization(
            timestamp=datetime(2026, 1, 1),
            legislative_year="2025-2026",
            type_org="Mesa Directiva",
            raw_html="<html>data</html>",
            changed=True,
            processed=False,
            last_update=True,
        )
    ]

    assert scraper.add_organizations_to_db() is True

    with SessionLocal() as session:
        rows = session.query(RawOrganization).all()

    assert len(rows) == 1
    assert rows[0].legislative_year == "2025-2026"
    assert rows[0].type_org == "Mesa Directiva"
    assert rows[0].raw_html == "<html>data</html>"


def test_add_organizations_to_db_asserts_when_empty():
    scraper = make_scraper()
    scraper.organizations_list = []

    with pytest.raises(AssertionError):
        scraper.add_organizations_to_db()


def test_add_organizations_to_db_handles_sqlalchemy_error():
    scraper = make_scraper()

    scraper.organizations_list = [
        RawOrganization(
            timestamp=datetime.now(),
            legislative_year="2025-2026",
            type_org="Mesa Directiva",
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

    assert scraper.add_organizations_to_db() is False
    assert dummy_session.rolled_back is True
    assert dummy_session.closed is True


def test_get_raw_organizations_aborts_when_no_years(monkeypatch):
    scraper = make_scraper()
    scraper.urls = {
        "Mesa Directiva": "https://mesa.test",
    }

    warnings = []

    monkeypatch.setattr(
        scraper,
        "get_options",
        lambda url, select_name="idRegistroPadre": {},
    )
    monkeypatch.setattr(
        "backend.scrapers.organizations.logger.warning",
        lambda message: warnings.append(message),
    )

    scraper.get_raw_organizations()

    assert scraper.organizations_list == []
    assert any("No years found for type=Mesa Directiva" in msg for msg in warnings)
