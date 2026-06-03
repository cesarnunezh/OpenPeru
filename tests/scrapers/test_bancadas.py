from datetime import datetime

import pytest
from lxml import html as lxml_html
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

import backend.scrapers.bancadas as bancadas
from backend.database.raw_models import Base, RawBancada
from backend.scrapers.bancadas import RawBancadaScraper


# ---------- helpers ----------


def make_scraper():
    """
    Avoid calling RawBancadaScraper.__init__ because it creates
    a real engine from settings.DB_URL.
    """
    scraper = RawBancadaScraper.__new__(RawBancadaScraper)
    scraper.url = "https://fake-url.test"
    return scraper


def setup_inmemory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return engine, SessionLocal


# ---------- fakes ----------


class FakePage:
    def __init__(self, html="<html>OK</html>", fail_on=None):
        self.html = html
        self.fail_on = fail_on
        self.goto_calls = []
        self.selector_waits = []
        self.evaluate_calls = []
        self.function_waits = []
        self.timeout_waits = []

    def goto(self, url, wait_until=None):
        self.goto_calls.append((url, wait_until))
        if self.fail_on == "goto":
            raise bancadas.PlaywrightTimeoutError("goto failed")

    def wait_for_selector(self, selector, state=None):
        self.selector_waits.append((selector, state))
        if self.fail_on == "wait_for_selector":
            raise bancadas.PlaywrightTimeoutError("selector missing")

    def evaluate(self, script, arg):
        self.evaluate_calls.append((script, arg))
        if self.fail_on == "evaluate":
            raise bancadas.PlaywrightTimeoutError("evaluate failed")
        return [arg["value"]]

    def wait_for_function(self, script, arg):
        self.function_waits.append((script, arg))
        if self.fail_on == "wait_for_function":
            raise bancadas.PlaywrightTimeoutError("selection not applied")

    def wait_for_timeout(self, timeout):
        self.timeout_waits.append(timeout)
        if self.fail_on == "wait_for_timeout":
            raise bancadas.PlaywrightTimeoutError("table not stable")

    def content(self):
        if self.fail_on == "content":
            raise bancadas.PlaywrightTimeoutError("content failed")
        return self.html


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


class FakePlaywrightContext:
    def __init__(self, chromium):
        self.chromium = chromium

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


# ---------- get_options ----------


def test_get_options_returns_expected_dict(monkeypatch):
    scraper = make_scraper()

    doc = lxml_html.fromstring(
        """
        <html>
          <body>
            <select name="idPeriodo[]">
              <option value="1">2021-2026</option>
              <option value="2"></option>
            </select>
          </body>
        </html>
        """
    )

    monkeypatch.setattr(bancadas, "parse_url", lambda url: doc)

    options = scraper.get_options(
        url="https://fake-url.test",
        select_name="idPeriodo[]",
    )

    assert options == {"2021-2026": "1"}


def test_get_options_returns_empty_when_parse_fails(monkeypatch):
    scraper = make_scraper()

    monkeypatch.setattr(bancadas, "parse_url", lambda url: None)

    assert scraper.get_options("https://fake-url.test") == {}


# ---------- get_html_with_selections ----------


def test_get_html_with_selections_success(monkeypatch):
    scraper = make_scraper()

    page = FakePage(html="<html>captured</html>")
    browser = FakeBrowser(page)
    chromium = FakeChromium(browser)
    playwright = FakePlaywrightContext(chromium)

    monkeypatch.setattr(bancadas, "sync_playwright", lambda: playwright)

    html = scraper.get_html_with_selections(
        url="https://fake-url.test",
        period_value="2021",
        condition_value="eej",
    )

    assert html == "<html>captured</html>"
    assert chromium.launch_calls == [True]
    assert page.goto_calls == [("https://fake-url.test", "domcontentloaded")]
    assert page.selector_waits == [
        ('select[name="idPeriodo[]"]', "attached"),
        ('select[name="keyCondicion[]"]', "attached"),
        (".table-cng", "visible"),
    ]
    assert [call[1] for call in page.evaluate_calls] == [
        {"selector": 'select[name="idPeriodo[]"]', "value": "2021"},
        {"selector": 'select[name="keyCondicion[]"]', "value": "eej"},
    ]
    assert [call[1] for call in page.function_waits] == [
        {"selector": 'select[name="idPeriodo[]"]', "value": "2021"},
        {"selector": 'select[name="keyCondicion[]"]', "value": "eej"},
    ]
    assert page.timeout_waits == [1000]
    assert browser.closed is True


def test_get_html_with_selections_handles_failures_and_cleans_up(monkeypatch):
    scraper = make_scraper()

    page = FakePage(fail_on="wait_for_selector")
    browser = FakeBrowser(page)
    chromium = FakeChromium(browser)
    playwright = FakePlaywrightContext(chromium)

    monkeypatch.setattr(bancadas, "sync_playwright", lambda: playwright)

    html = scraper.get_html_with_selections(
        url="https://fake-url.test",
        period_value="2021",
        condition_value="eej",
    )

    assert html is None
    assert browser.closed is True


# ---------- get_raw_bancadas ----------


def test_get_raw_bancadas_only_current(monkeypatch):
    scraper = make_scraper()

    def fake_get_options(url, select_name="idPeriodo[]"):
        assert select_name == "idPeriodo[]"
        return {
            "2021-2026": "1",
            "2016-2021": "2",
        }

    monkeypatch.setattr(scraper, "get_options", fake_get_options)
    monkeypatch.setattr(
        scraper,
        "get_html_with_selections",
        lambda url, period, cond: f"<html>{period}-{cond}</html>",
    )
    monkeypatch.setattr(scraper, "update_tracking", lambda bancada: bancada)

    scraper.get_raw_bancadas(only_current=True)

    assert len(scraper.bancadas_list) == 1

    bancada = scraper.bancadas_list[0]
    assert bancada.legislative_period == "2021-2026"
    assert bancada.raw_html == "<html>1-eej</html>"
    assert bancada.processed is False
    assert bancada.last_update is True


def test_get_raw_bancadas_all_periods_single_condition(monkeypatch):
    scraper = make_scraper()

    def fake_get_options(url, select_name="idPeriodo[]"):
        if select_name == "idPeriodo[]":
            return {
                "2021-2026": "1",
                "2016-2021": "2",
            }

        if select_name == "keyCondicion[]":
            return {
                "en Ejercicio": "eej",
            }

        return {}

    monkeypatch.setattr(scraper, "get_options", fake_get_options)
    monkeypatch.setattr(
        scraper,
        "get_html_with_selections",
        lambda url, period, cond: f"<html>{period}-{cond}</html>",
    )
    monkeypatch.setattr(scraper, "update_tracking", lambda bancada: bancada)

    scraper.get_raw_bancadas(only_current=False)

    assert len(scraper.bancadas_list) == 2
    assert [b.legislative_period for b in scraper.bancadas_list] == [
        "2021-2026",
        "2016-2021",
    ]
    assert [b.raw_html for b in scraper.bancadas_list] == [
        "<html>1-eej</html>",
        "<html>2-eej</html>",
    ]


def test_get_raw_bancadas_skips_none_html(monkeypatch):
    scraper = make_scraper()

    monkeypatch.setattr(
        scraper,
        "get_options",
        lambda url, select_name="idPeriodo[]": {
            "2021-2026": "1",
        },
    )
    monkeypatch.setattr(
        scraper,
        "get_html_with_selections",
        lambda url, period, cond: None,
    )
    monkeypatch.setattr(scraper, "update_tracking", lambda bancada: bancada)

    scraper.get_raw_bancadas(only_current=True)

    assert scraper.bancadas_list == []


# ---------- update_tracking ----------


def test_update_tracking_marks_first_snapshot_changed():
    engine, SessionLocal = setup_inmemory_db()

    scraper = make_scraper()
    scraper.Session = SessionLocal

    bancada = RawBancada(
        timestamp=datetime(2026, 1, 1),
        legislative_period="2021-2026",
        raw_html="<html>v1</html>",
        last_update=False,
        changed=False,
        processed=False,
    )

    tracked = scraper.update_tracking(bancada)

    assert tracked.changed is True
    assert tracked.last_update is True
    assert tracked.processed is False


def test_update_tracking_marks_identical_snapshot_processed():
    engine, SessionLocal = setup_inmemory_db()

    scraper = make_scraper()
    scraper.Session = SessionLocal

    old = RawBancada(
        timestamp=datetime(2026, 1, 1),
        legislative_period="2021-2026",
        raw_html="<html>same</html>",
        last_update=True,
        changed=True,
        processed=False,
    )

    with SessionLocal() as session:
        session.add(old)
        session.commit()

    new = RawBancada(
        timestamp=datetime(2026, 1, 2),
        legislative_period="2021-2026",
        raw_html="<html>same</html>",
        last_update=False,
        changed=False,
        processed=False,
    )

    tracked = scraper.update_tracking(new)

    assert tracked.changed is False
    assert tracked.last_update is True
    assert tracked.processed is True

    with SessionLocal() as session:
        previous = session.query(RawBancada).first()
        assert previous.last_update is False


def test_update_tracking_marks_changed_snapshot_and_flips_previous():
    engine, SessionLocal = setup_inmemory_db()

    scraper = make_scraper()
    scraper.Session = SessionLocal

    old = RawBancada(
        timestamp=datetime(2026, 1, 1),
        legislative_period="2021-2026",
        raw_html="<html>old</html>",
        last_update=True,
        changed=True,
        processed=False,
    )

    with SessionLocal() as session:
        session.add(old)
        session.commit()

    new = RawBancada(
        timestamp=datetime(2026, 1, 2),
        legislative_period="2021-2026",
        raw_html="<html>new</html>",
        last_update=False,
        changed=False,
        processed=False,
    )

    tracked = scraper.update_tracking(new)

    assert tracked.changed is True
    assert tracked.last_update is True
    assert tracked.processed is False

    with SessionLocal() as session:
        previous = session.query(RawBancada).first()
        assert previous.last_update is False


# ---------- add_bancadas_to_db ----------


def test_add_bancadas_to_db_success():
    engine, SessionLocal = setup_inmemory_db()

    scraper = make_scraper()
    scraper.Session = SessionLocal

    scraper.bancadas_list = [
        RawBancada(
            timestamp=datetime(2026, 1, 1),
            legislative_period="2021-2026",
            raw_html="<html>1</html>",
            changed=True,
            processed=False,
            last_update=True,
        ),
        RawBancada(
            timestamp=datetime(2026, 1, 1),
            legislative_period="2016-2021",
            raw_html="<html>2</html>",
            changed=True,
            processed=False,
            last_update=True,
        ),
    ]

    result = scraper.add_bancadas_to_db()

    assert result is True

    with SessionLocal() as session:
        rows = session.query(RawBancada).all()

    assert len(rows) == 2
    assert {row.legislative_period for row in rows} == {
        "2021-2026",
        "2016-2021",
    }


def test_add_bancadas_to_db_raises_when_empty_list():
    scraper = make_scraper()
    scraper.bancadas_list = []

    with pytest.raises(AssertionError):
        scraper.add_bancadas_to_db()


def test_add_bancadas_to_db_handles_sqlalchemy_error():
    scraper = make_scraper()

    scraper.bancadas_list = [
        RawBancada(
            timestamp=datetime.now(),
            legislative_period="2021-2026",
            raw_html="<html></html>",
        )
    ]

    class DummySession:
        def __init__(self):
            self.rollback_called = False
            self.close_called = False

        def bulk_save_objects(self, objs):
            raise SQLAlchemyError("boom")

        def commit(self):
            pass

        def rollback(self):
            self.rollback_called = True

        def close(self):
            self.close_called = True

    dummy_session = DummySession()
    scraper.Session = lambda: dummy_session

    result = scraper.add_bancadas_to_db()

    assert result is False
    assert dummy_session.rollback_called is True
    assert dummy_session.close_called is True
