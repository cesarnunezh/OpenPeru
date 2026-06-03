from datetime import datetime

import pytest
from lxml.html import fromstring
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.scrapers.congresistas import (
    RawCongresistasScraper,
    BASE_URL,
    API_MEMBERSHIP,
)
from backend.database.raw_models import Base, RawCongresista
from backend.scrapers.utils import get_cong_website

# ---------- helpers for DB tests ----------


def _setup_inmemory_db():
    """Create in-memory SQLite engine and session factory for tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return engine, SessionLocal


# ---------- small helper methods ----------


@pytest.mark.parametrize(
    "txt, expected",
    [
        ("Cargos", True),
        ("Cargos del congresista", True),
        ("cargos de la congresista", True),
        ("Información", False),
        ("", False),
        ("otros temas", False),
    ],
)
def test_is_cargos_label(txt, expected):
    s = RawCongresistasScraper()
    assert s._is_cargos_label(txt.lower()) is expected


def test_score_link_text():
    s = RawCongresistasScraper()

    base = "cargos"
    with_congresista = "cargos del congresista"
    generic = "link cualquiera"

    assert s._score_link_text(generic) == 0
    assert s._score_link_text(base) < s._score_link_text(with_congresista)


def test_get_best_cargos_link():
    s = RawCongresistasScraper()
    html = """
    <html><body>
      <a href="/link1">Otros cargos</a>
      <a href="/link2">Cargos del congresista</a>
      <a href="/link3">Página</a>
    </body></html>
    """
    doc = fromstring(html)
    base_url = "https://www.congreso.gob.pe/perfil/"

    best = s.get_best_cargos_link(doc, base_url)
    # urljoin(base_url, "/link2") => "https://www.congreso.gob.pe/link2"
    assert best == "https://www.congreso.gob.pe/link2"


def test_get_cong_website():
    s = RawCongresistasScraper()
    profile_content = """
    <html><body>
      <div class="web">
        <span>Web:</span>
        <span><a href="https://example.com/perfil/123">Sitio</a></span>
      </div>
    </body></html>
    """
    url = get_cong_website(profile_content)
    assert url == "https://example.com/perfil/123"


# ---------- get_dict_periodos ----------


def test_get_dict_periodos(monkeypatch):
    s = RawCongresistasScraper()

    def fake_parse_url(url, *args, **kwargs):
        assert url == BASE_URL
        html = """
        <html><body>
          <select name="idRegistroPadre">
            <option value="1">Periodo A</option>
            <option value="2">Periodo B</option>
          </select>
        </body></html>
        """
        return fromstring(html)

    monkeypatch.setattr("backend.scrapers.congresistas.parse_url", fake_parse_url)

    s.get_dict_periodos()
    assert s.periods == {"Periodo A": "1", "Periodo B": "2"}


# ---------- create_raw_congresista (old periods) ----------


def test_create_raw_congresista_old_period(monkeypatch):
    s = RawCongresistasScraper()

    monkeypatch.setattr(
        "backend.scrapers.congresistas.get_cong_website",
        lambda content: "https://example.com/perfil/old",
    )

    monkeypatch.setattr(
        s,
        "get_profile_content",
        lambda link: "PROFILE_HTML",
    )

    period = "Parlamentario 2001 - 2006"
    cong_link = "/perfil/1"

    raw = s.create_raw_congresista(period, cong_link)

    assert isinstance(raw, RawCongresista)
    assert raw.leg_period == period
    assert raw.url == "https://example.com/perfil/old"
    assert raw.profile_content == "PROFILE_HTML"
    assert raw.memberships_content is None


# ---------- create_raw_congresista (modern period, success path) ----------


def test_create_raw_congresista_modern_success(monkeypatch):
    s = RawCongresistasScraper()

    # Avoid network: stub profile content
    monkeypatch.setattr(s, "get_profile_content", lambda link: "<html>PROFILE</html>")

    # IMPORTANT: get_cong_website is now a module-level imported function
    monkeypatch.setattr(
        "backend.scrapers.congresistas.get_cong_website",
        lambda content: "https://example.com/perfil/123",
    )

    def fake_parse_url(url, *args, **kwargs):
        if url.startswith("https://example.com/perfil"):
            html = """
            <html><body>
              <a href="/cargos/999">Cargos del congresista</a>
            </body></html>
            """
            return fromstring(html)
        if url.startswith("https://example.com/cargos/999"):
            html = """
            <html><body>
              <div id="objContents">
                <div></div>
                <div>
                  <p><iframe src="https://some.site/listar/ABC123"></iframe></p>
                </div>
              </div>
            </body></html>
            """
            return fromstring(html)
        raise AssertionError(f"Unexpected URL in fake_parse_url: {url}")

    monkeypatch.setattr("backend.scrapers.congresistas.parse_url", fake_parse_url)

    def fake_get_url_text(url):
        assert url == API_MEMBERSHIP + "ABC123"
        return '{"ok": true}'

    monkeypatch.setattr("backend.scrapers.congresistas.get_url_text", fake_get_url_text)

    raw = s.create_raw_congresista("Congresistas 2021-2026", "/perfil/123")

    assert raw.url == "https://example.com/perfil/123"
    assert raw.profile_content == "<html>PROFILE</html>"
    assert raw.memberships_content == '{"ok": true}'


# ---------- create_raw_congresista (partial failure -> no iframe) ----------


def test_create_raw_congresista_partial_failure(monkeypatch):
    s = RawCongresistasScraper()

    monkeypatch.setattr(s, "get_profile_content", lambda link: "PROFILE")

    # get_cong_website is module-level now
    monkeypatch.setattr(
        "backend.scrapers.congresistas.get_cong_website",
        lambda content: "https://example.com/perfil/abc",
    )

    # parse_url always returns a doc without iframe, so the try-block fails
    def fake_parse_url(url, *args, **kwargs):
        html = "<html><body>No iframe here</body></html>"
        return fromstring(html)

    monkeypatch.setattr("backend.scrapers.congresistas.parse_url", fake_parse_url)

    # If get_best_cargos_link is still an instance method, this is fine:
    monkeypatch.setattr(
        s,
        "get_best_cargos_link",
        lambda doc, base_url: "https://example.com/cargos-no-iframe",
    )

    raw = s.create_raw_congresista("Congresistas 2016-2021", "/perfil/abc")

    assert isinstance(raw, RawCongresista)
    assert raw.leg_period == "Congresistas 2016-2021"
    assert raw.url == "https://example.com/perfil/abc"
    assert raw.profile_content == "PROFILE"
    # and because it fails to find the iframe / membership:
    assert raw.memberships_content is None


# ---------- extract_cong_from_period ----------


def test_extract_cong_from_period_uses_links_and_creator(monkeypatch):
    s = RawCongresistasScraper()

    monkeypatch.setattr(
        s, "get_urls_from_table", lambda value: ["/perfil/1", "/perfil/2"]
    )
    monkeypatch.setattr(
        s, "create_raw_congresista", lambda period, link: f"raw-{period}-{link}"
    )

    # avoid DB + object-shape requirements
    monkeypatch.setattr(s, "update_tracking", lambda x: x)

    res = s.extract_cong_from_period("Periodo X", "1")

    assert res == ["raw-Periodo X-/perfil/1", "raw-Periodo X-/perfil/2"]


# ---------- extract_and_load_all ----------


def test_extract_and_load_all_requires_periods():
    s = RawCongresistasScraper()
    s.periods = {}
    with pytest.raises(AssertionError):
        s.extract_and_load_all()


def test_extract_and_load_all_calls_add(monkeypatch):
    s = RawCongresistasScraper()
    s.periods = {"Periodo X": "1", "Periodo Y": "2"}

    calls = []

    def fake_extract(period_key, period_value):
        calls.append((period_key, period_value))
        return [f"raw-{period_key}"]

    def fake_add():
        calls.append("add_called")
        return True

    s.extract_cong_from_period = fake_extract
    s.add_congresistas_to_db = fake_add

    result = s.extract_and_load_all()

    # last iteration's raw_congresistas should be returned
    assert result == ["raw-Periodo Y"]
    # extract called twice, add called twice
    assert calls.count("add_called") == 2
    assert ("Periodo X", "1") in calls
    assert ("Periodo Y", "2") in calls


# ---------- add_congresistas_to_db ----------


def test_add_congresistas_to_db_persists(monkeypatch):
    engine, SessionLocal = _setup_inmemory_db()

    s = RawCongresistasScraper()
    s.engine = engine
    s.Session = SessionLocal

    cong = RawCongresista(
        timestamp=datetime(2021, 1, 1),
        leg_period="Periodo Test",
        url="https://example.com",
        profile_content="<html></html>",
        memberships_content="{}",
    )
    s.raw_congresistas = [cong]

    assert s.add_congresistas_to_db() is True

    with SessionLocal() as session:
        count = session.query(RawCongresista).count()
        assert count == 1
        db_cong = session.query(RawCongresista).first()
        assert db_cong.leg_period == "Periodo Test"
        assert db_cong.url == "https://example.com"


def test_add_congresistas_to_db_asserts_when_empty():
    s = RawCongresistasScraper()
    s.raw_congresistas = []

    with pytest.raises(AssertionError):
        s.add_congresistas_to_db()


def test_add_congresistas_to_db_handles_sqlalchemy_error(monkeypatch):
    s = RawCongresistasScraper()
    s.raw_congresistas = [
        RawCongresista(
            timestamp=datetime.now(),
            leg_period="Periodo",
            url="https://example.com",
            profile_content="HTML",
            memberships_content=None,
        )
    ]

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

    s.Session = fake_sessionmaker

    ok = s.add_congresistas_to_db()
    assert ok is False
    assert dummy_session.rolled_back is True
