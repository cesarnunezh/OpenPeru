import datetime

import pytest
from lxml import html as lxml_html
from sqlalchemy import Column, DateTime, Integer, String, create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import declarative_base, sessionmaker
from selenium.common.exceptions import NoSuchElementException

import backend.scrapers.bancadas as bancadas
from backend.scrapers.bancadas import RawBancadaScraper


# ---------- Unit tests for get_options ----------


def test_get_options_returns_expected_dict(monkeypatch):
    """
    get_options should parse the select and return a {text: value} dict,
    ignoring options without text.
    """

    # Build a tiny HTML snippet with a select and options
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

    # Monkeypatch parse_url to return our fake HTML element
    monkeypatch.setattr(
        bancadas,
        "parse_url",
        lambda url: doc,
    )

    scraper = RawBancadaScraper()
    options = scraper.get_options(
        url="https://fake-url.test",
        select_name="idPeriodo[]",
    )

    assert options == {"2021-2026": "1"}


# ---------- Unit tests for get_html_with_selections (Selenium heavily mocked) ----------


class _DummyDriver:
    def __init__(self, page_source="<html>OK</html>"):
        self.page_source = page_source
        self.got_url = None
        self.executed_scripts = []
        self.quit_called = False

    def get(self, url):
        self.got_url = url

    def execute_script(self, *args, **kwargs):
        self.executed_scripts.append((args, kwargs))

    def quit(self):
        self.quit_called = True


class _DummyWait:
    def __init__(self, driver, timeout):
        self.driver = driver
        self.timeout = timeout
        self.calls = 0

    def until(self, method):
        # Do not evaluate the condition; just return True
        self.calls += 1
        return True


class _FailingWait:
    def __init__(self, driver, timeout):
        self.driver = driver
        self.timeout = timeout

    def until(self, method):
        # Simulate Selenium not finding an element
        raise NoSuchElementException("Element not found")


def test_get_html_with_selections_success(monkeypatch):
    """
    When the selects exist and nothing fails, get_html_with_selections should
    return the driver's page_source.
    """
    dummy_driver = _DummyDriver(page_source="<html>OK</html>")

    # Patch webdriver.Chrome to return our dummy driver
    monkeypatch.setattr(
        bancadas.webdriver,
        "Chrome",
        lambda service=None, options=None: dummy_driver,
    )

    # Patch WebDriverWait used in the module to avoid real waiting/EC logic
    monkeypatch.setattr(
        bancadas,
        "WebDriverWait",
        _DummyWait,
    )

    scraper = RawBancadaScraper()
    html = scraper.get_html_with_selections(
        url="https://fake-url.test",
        period_value="2021",
        condition_value="",
    )

    assert html == "<html>OK</html>"
    assert dummy_driver.got_url == "https://fake-url.test"
    # Driver should not be quit in the success path
    assert dummy_driver.quit_called is False


def test_get_html_with_selections_handles_no_such_element(monkeypatch):
    """
    If Selenium raises NoSuchElementException, the method should log the error,
    quit the driver and return None.
    """
    dummy_driver = _DummyDriver(page_source="<html>ShouldNotMatter</html>")

    monkeypatch.setattr(
        bancadas.webdriver,
        "Chrome",
        lambda service=None, options=None: dummy_driver,
    )

    monkeypatch.setattr(
        bancadas,
        "WebDriverWait",
        _FailingWait,
    )

    scraper = RawBancadaScraper()
    html = scraper.get_html_with_selections(
        url="https://fake-url.test",
        period_value="2021",
        condition_value="",
    )

    assert html is None
    assert dummy_driver.quit_called is True


# ---------- Unit tests for get_raw_bancadas (logic only, no Selenium/real DB) ----------


class _DummyRawBancada:
    def __init__(
        self, timestamp, legislative_period, raw_html, last_update, changed, processed
    ):
        self.timestamp = timestamp
        self.legislative_period = legislative_period
        self.raw_html = raw_html
        self.last_update = last_update
        self.changed = changed
        self.processed = processed


def test_get_raw_bancadas_only_current(monkeypatch):
    """
    With only_current=True, get_raw_bancadas should:
      - use get_options for periods
      - use a fixed dict for conditions {"Todas": ""}
      - create one RawBancada per (period, condition) combination
    """
    # Use our dummy RawBancada class
    monkeypatch.setattr(
        bancadas,
        "RawBancada",
        _DummyRawBancada,
    )

    def fake_get_options(url, select_name="idPeriodo[]"):
        # Only period options are fetched in this branch
        assert select_name == "idPeriodo[]"
        return {"2021-2026": "1"}

    # Patch instance method get_options
    scraper = RawBancadaScraper()
    monkeypatch.setattr(scraper, "get_options", fake_get_options)
    monkeypatch.setattr(
        scraper,
        "get_html_with_selections",
        lambda url, period, cond: f"<html>{period}-{cond}</html>",
    )
    monkeypatch.setattr(scraper, "update_tracking", lambda b: b)

    # Patch get_html_with_selections to avoid Selenium
    monkeypatch.setattr(
        scraper,
        "get_html_with_selections",
        lambda url, period, cond: f"<html>{period}-{cond}</html>",
    )

    scraper.get_raw_bancadas(only_current=True)

    assert hasattr(scraper, "bancadas_list")
    assert len(scraper.bancadas_list) == 1

    bancada = scraper.bancadas_list[0]
    assert isinstance(bancada, _DummyRawBancada)
    assert bancada.legislative_period == "2021-2026"
    assert bancada.raw_html == "<html>1-eej</html>"


def test_get_raw_bancadas_all_conditions(monkeypatch):
    """
    With only_current=False, get_raw_bancadas should build the Cartesian
    product of periods and conditions.
    """
    monkeypatch.setattr(
        bancadas,
        "RawBancada",
        _DummyRawBancada,
    )

    def fake_get_options(url, select_name="idPeriodo[]"):
        if select_name == "idPeriodo[]":
            return {"2021-2026": "1", "2016-2021": "2"}
        elif select_name == "keyCondicion[]":
            return {"Todas": "", "Vigentes": "1"}
        else:
            raise AssertionError("Unexpected select_name")

    scraper = RawBancadaScraper()
    monkeypatch.setattr(scraper, "get_options", fake_get_options)

    monkeypatch.setattr(
        scraper,
        "get_html_with_selections",
        lambda url, period, cond: f"<html>{period}-{cond}</html>",
    )
    monkeypatch.setattr(scraper, "update_tracking", lambda b: b)

    scraper.get_raw_bancadas(only_current=False)

    assert len(scraper.bancadas_list) == 4  # 2 periods x 2 conditions

    periods = {b.legislative_period for b in scraper.bancadas_list}
    assert periods == {"2021-2026", "2016-2021"}


# ---------- Unit tests for add_bancadas_to_db ----------


Base = declarative_base()


class RawBancadaTest(Base):
    """
    Simple test model to use with an in-memory SQLite DB.
    It mimics the fields the scraper uses.
    """

    __tablename__ = "raw_bancadas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False)
    legislative_period = Column(String, nullable=False)
    raw_html = Column(String, nullable=False)


def test_add_bancadas_to_db_success(monkeypatch):
    """
    add_bancadas_to_db should insert all bancadas and return True on success.
    """
    # Use our test model instead of the real RawBancada
    monkeypatch.setattr(
        bancadas,
        "RawBancada",
        RawBancadaTest,
    )

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)

    scraper = RawBancadaScraper()
    scraper.engine = engine
    scraper.Session = TestSession

    now = datetime.datetime.now()
    scraper.bancadas_list = [
        RawBancadaTest(
            timestamp=now,
            legislative_period="2021-2026",
            raw_html="<html>1</html>",
        ),
        RawBancadaTest(
            timestamp=now,
            legislative_period="2016-2021",
            raw_html="<html>2</html>",
        ),
    ]

    result = scraper.add_bancadas_to_db()
    assert result is True

    # Verify rows actually in DB
    with TestSession() as session:
        count = session.query(RawBancadaTest).count()
        assert count == 2


def test_add_bancadas_to_db_raises_when_empty_list():
    """
    If bancadas_list is empty, the assertion at the top should fail.
    """
    scraper = RawBancadaScraper()
    scraper.bancadas_list = []

    with pytest.raises(AssertionError):
        scraper.add_bancadas_to_db()


def test_add_bancadas_to_db_handles_sqlalchemy_error(monkeypatch):
    """
    If SQLAlchemyError is raised during bulk_save_objects/commit,
    add_bancadas_to_db should catch it and return False.
    """

    class DummySession:
        def __init__(self):
            self.rollback_called = False
            self.close_called = False

        def bulk_save_objects(self, objs):
            raise SQLAlchemyError("Boom")

        def commit(self):
            pass

        def rollback(self):
            self.rollback_called = True

        def close(self):
            self.close_called = True

    scraper = RawBancadaScraper()
    scraper.bancadas_list = [object()]

    # Make Session() return our DummySession
    dummy_session = DummySession()
    scraper.Session = lambda: dummy_session

    result = scraper.add_bancadas_to_db()

    assert result is False
    assert dummy_session.rollback_called is True
    assert dummy_session.close_called is True
