from datetime import datetime

import pytest
from lxml.html import fromstring
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from selenium.common.exceptions import TimeoutException

from backend.scrapers.committees import (
    RawCommitteeScraper,
    BASE_URL,
)
from backend.database.raw_models import Base, RawCommittee


# ---------- helpers for DB tests ----------


def _setup_inmemory_db():
    """Create in-memory SQLite engine and session factory for tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return engine, SessionLocal


# ---------- get_options ----------


def test_get_options_parses_select(monkeypatch):
    scraper = RawCommitteeScraper()

    def fake_parse_url(url, *args, **kwargs):
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

    # At least the real options should be present
    assert options["2021"] == "2021"
    assert options["2022"] == "2022"
    # Placeholder may or may not be present; if it is, value can be None
    if "--Seleccione--" in options:
        assert options["--Seleccione--"] is None


# ---------- get_html_with_selections ----------


def test_get_html_with_selections_success(monkeypatch):
    scraper = RawCommitteeScraper()

    # We don't want to test _select_year here, only the committee selection flow
    monkeypatch.setattr(scraper, "_select_year", lambda driver, wait, year_value: None)

    class FakeElement:
        def __init__(self, driver, name):
            self.driver = driver
            self.name = name

    class FakeDriver:
        def __init__(self):
            self._page_source = "<html>BEFORE</html>"
            self.selected = {}  # track selected values per element name

        def find_element(self, by, value):
            # value will be "fld_78_Comision"
            return FakeElement(self, value)

        @property
        def page_source(self):
            return self._page_source

    class FakeSelectedOption:
        def __init__(self, driver, element_name):
            self.driver = driver
            self.element_name = element_name

        def get_attribute(self, attr):
            assert attr == "value"
            return self.driver.selected.get(self.element_name)

    class FakeSelect:
        def __init__(self, element):
            self.element = element

        def select_by_value(self, value):
            # Persist the selection on the driver
            self.element.driver.selected[self.element.name] = value
            # Simulate page updating after selection
            self.element.driver._page_source = "<html>OK</html>"

        @property
        def first_selected_option(self):
            return FakeSelectedOption(self.element.driver, self.element.name)

    class FakeWait:
        def until(self, condition):
            # condition can be:
            # - a callable(driver) -> truthy
            # - something returned by EC.presence_of_element_located (callable too)
            ok = condition(self._driver)
            if not ok:
                raise TimeoutException("condition not met")
            return ok

        def __init__(self, driver):
            self._driver = driver

    # Patch Select used inside backend.scrapers.committees module
    monkeypatch.setattr("backend.scrapers.committees.Select", FakeSelect)

    # Patch EC.presence_of_element_located to a simple callable that returns True
    monkeypatch.setattr(
        "backend.scrapers.committees.EC.presence_of_element_located",
        lambda locator: lambda d: True,
    )

    driver = FakeDriver()
    wait = FakeWait(driver)

    html = scraper.get_html_with_selections(driver, wait, "2021", "COM")
    assert html == "<html>OK</html>"


def test_get_html_with_selections_handles_no_such_element(monkeypatch):
    scraper = RawCommitteeScraper()

    class FakeElement:
        def __init__(self, driver, name):
            self.driver = driver
            self.tag_name = name

    class FakeDriver:
        def __init__(self):
            self._page_source = "<html>BEFORE</html>"
            self.selected = {}  # track selected values per element name

        def find_element(self, by, value):
            # value will be "fld_78_Comision"
            return FakeElement(self, value)

        @property
        def page_source(self):
            return self._page_source

    class FakeSelectedOption:
        def __init__(self, driver, element_name):
            self.driver = driver
            self.element_name = element_name

        def get_attribute(self, attr):
            assert attr == "value"
            return self.driver.selected.get(self.element_name)

    class FakeSelect:
        def __init__(self, element):
            self.element = element

        def select_by_value(self, value):
            # Persist the selection on the driver
            self.element.driver.selected[self.element.name] = value
            # Simulate page updating after selection
            self.element.driver._page_source = "<html>OK</html>"

        @property
        def first_selected_option(self):
            return FakeSelectedOption(self.element.driver, self.element.name)

    class FakeWait:
        def until(self, condition):
            # condition can be:
            # - a callable(driver) -> truthy
            # - something returned by EC.presence_of_element_located (callable too)
            ok = condition(self._driver)
            if not ok:
                raise TimeoutException("condition not met")
            return ok

        def __init__(self, driver):
            self._driver = driver

    monkeypatch.setattr(
        "backend.scrapers.committees.webdriver.Chrome",
        lambda *a, **k: FakeDriver(),
    )
    driver = FakeDriver()
    wait = FakeWait(driver)
    html = scraper.get_html_with_selections(driver, wait, "2021", "COM")
    assert html is None


# ---------- get_raw_committees ----------


def test_get_raw_committees_builds_committee_list(monkeypatch, raw_session):
    scraper = RawCommitteeScraper()
    scraper.session = raw_session

    monkeypatch.setattr(scraper, "_select_year", lambda driver, wait, year_value: None)
    monkeypatch.setattr(scraper, "update_tracking", lambda committee: committee)

    def fake_get_options(self, url, select_name="idRegistroPadre"):
        assert select_name == "idRegistroPadre"
        return {"2021": "2021", "2022": "2022"}

    monkeypatch.setattr(RawCommitteeScraper, "get_options", fake_get_options)

    def fake_get_html_with_selections(driver, wait, year_value, committee_value):
        if year_value == "2022" and committee_value == "2":
            return None
        return f"<html>Year={year_value},Type={committee_value}</html>"

    monkeypatch.setattr(
        scraper, "get_html_with_selections", fake_get_html_with_selections
    )

    # If your code constructs a driver/wait, just stub them to simple objects
    class DummyWait:
        def until(self, condition):
            return True

    class DummyDriver:
        def get(self, url):
            pass

        def set_page_load_timeout(self, seconds):
            pass

        def set_script_timeout(self, seconds):
            pass

        def implicitly_wait(self, seconds):
            pass

        def quit(self):
            pass

    monkeypatch.setattr(
        "backend.scrapers.committees.webdriver.Chrome", lambda *a, **k: DummyDriver()
    )
    monkeypatch.setattr(
        "backend.scrapers.committees.WebDriverWait", lambda driver, t: DummyWait()
    )

    # bypass selenium-dependent helpers
    monkeypatch.setattr(scraper, "_select_year", lambda driver, wait, year_value: None)
    monkeypatch.setattr(
        scraper,
        "_get_committee_options_current_page",
        lambda driver, wait: {"Permanente": "1", "Especial": "2"},
    )
    scraper.get_raw_committees()

    assert hasattr(scraper, "committee_list")
    assert len(scraper.committee_list) == 3


# ---------- add_committees_to_db ----------


def test_add_committees_to_db_persists(monkeypatch):
    engine, SessionLocal = _setup_inmemory_db()

    scraper = RawCommitteeScraper()
    scraper.engine = engine
    scraper.Session = SessionLocal

    committee = RawCommittee(
        timestamp=datetime(2021, 1, 1),
        legislative_year=2021,
        committee_type="Permanente",
        raw_html="<html>data</html>",
    )
    scraper.committee_list = [committee]

    assert scraper.add_committees_to_db() is True

    with SessionLocal() as session:
        count = session.query(RawCommittee).count()
        assert count == 1
        db_obj = session.query(RawCommittee).first()
        assert db_obj.legislative_year == 2021
        assert db_obj.committee_type == "Permanente"
        assert db_obj.raw_html == "<html>data</html>"


def test_add_committees_to_db_asserts_when_empty():
    scraper = RawCommitteeScraper()
    scraper.committee_list = []

    with pytest.raises(AssertionError):
        scraper.add_committees_to_db()


def test_add_committees_to_db_handles_sqlalchemy_error(monkeypatch):
    from sqlalchemy.exc import SQLAlchemyError

    scraper = RawCommitteeScraper()
    scraper.committee_list = [
        RawCommittee(
            timestamp=datetime.now(),
            legislative_year=2021,
            committee_type="Permanente",
            raw_html="<html></html>",
        )
    ]

    class DummySession:
        def __init__(self):
            self.rolled_back = False

        def bulk_save_objects(self, objs):
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

    scraper.Session = fake_sessionmaker

    ok = scraper.add_committees_to_db()
    assert ok is False
    assert dummy_session.rolled_back is True
