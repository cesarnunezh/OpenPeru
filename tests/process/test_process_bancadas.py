from types import SimpleNamespace
import pytest
import backend.process.bancadas as mod


@pytest.fixture
def html_one_bancada_one_member():
    return """
    <table class="table-cng">
      <tbody>
        <tr>
          <td><h2>ACCION POPULAR</h2></td>
        </tr>
        <tr>
          <td>
            <a class="conginfo" href="/congresista/1">Juan Perez</a>
          </td>
          <td>extra col</td>
        </tr>
      </tbody>
    </table>
    """


@pytest.fixture
def html_two_bancadas_two_members():
    return """
    <table class="table-cng">
      <tbody>
        <tr>
          <td><h2>ACCION POPULAR</h2></td>
        </tr>
        <tr>
          <td>
            <a class="conginfo" href="/congresista/1">Juan Perez</a>
          </td>
          <td>extra</td>
        </tr>

        <tr>
          <td><h2>FUERZA POPULAR</h2></td>
        </tr>
        <tr>
          <td>
            <a class="conginfo" href="/congresista/2">Maria Lopez</a>
          </td>
          <td>extra</td>
        </tr>
      </tbody>
    </table>
    """


def _raw_bancada(
    raw_html: str, timestamp="2026-01-01T00:00:00", legislative_period="2025-2026"
):
    """
    Minimal stand-in for RawBancada.
    We only need attributes used by process_bancada:
    - raw_html
    - timestamp
    - legislative_period
    """
    return SimpleNamespace(
        raw_html=raw_html,
        timestamp=timestamp,
        legislative_period=legislative_period,
    )


def test_process_bancada_current_period_no_override(
    monkeypatch, html_one_bancada_one_member
):
    # Arrange
    rb = _raw_bancada(
        raw_html=html_one_bancada_one_member,
        timestamp="2026-01-01T00:00:00",
        legislative_period="2025-2026",
    )

    # Mock: current leg year derived from timestamp
    expected_leg_year = mod.LegislativeYear("2025")
    monkeypatch.setattr(mod, "get_current_leg_year", lambda ts: expected_leg_year)

    # Mock: current period equals raw_bancada.legislative_period (no override)
    monkeypatch.setattr(mod, "find_leg_period", lambda leg_year: "2025-2026")

    # Mock scraping helpers (no network)
    seen_urls = []

    def fake_get_url_text(url: str) -> str:
        seen_urls.append(url)
        return "<html>profile page</html>"

    monkeypatch.setattr(mod, "get_url_text", fake_get_url_text)
    monkeypatch.setattr(
        mod, "get_cong_website", lambda parsed: "https://example.com/cong/juan-perez"
    )

    # Act
    bancadas, memberships = mod.process_bancada(rb)

    # Assert bancadas
    assert len(bancadas) == 1
    b = bancadas[0]
    assert b.leg_year == expected_leg_year
    assert b.bancada_name == "Accion Popular"  # .title()

    # Assert memberships
    assert len(memberships) == 1
    m = memberships[0]
    assert m.leg_year == expected_leg_year
    assert m.cong_name == "Juan Perez"
    assert m.website == "https://example.com/cong/juan-perez"
    assert m.bancada_name == "Accion Popular"

    # Ensure URL was constructed correctly
    assert seen_urls == ["https://www.congreso.gob.pe/congresista/1"]


def test_process_bancada_past_period_overrides_leg_year(
    monkeypatch, html_one_bancada_one_member
):
    # Arrange
    # Force mismatch: current_leg_period != raw_bancada.legislative_period
    # and raw_bancada.legislative_period ends with 2024 -> override year becomes 2023
    rb = _raw_bancada(
        raw_html=html_one_bancada_one_member,
        timestamp="2026-01-01T00:00:00",
        legislative_period="2023-2024",
    )

    # Mock: would normally say current year is 2025, but should be overridden for past periods
    monkeypatch.setattr(
        mod, "get_current_leg_year", lambda ts: mod.LegislativeYear("2025")
    )
    monkeypatch.setattr(
        mod, "find_leg_period", lambda leg_year: "2025-2026"
    )  # mismatch -> override

    monkeypatch.setattr(mod, "get_url_text", lambda url: "<html/>")
    monkeypatch.setattr(
        mod, "get_cong_website", lambda parsed: "https://example.com/cong/juan-perez"
    )

    # Act
    bancadas, memberships = mod.process_bancada(rb)

    # Assert: override used (2024 - 1 = 2023)
    expected_overridden = mod.LegislativeYear("2023")

    assert len(bancadas) == 1
    assert bancadas[0].leg_year == expected_overridden

    assert len(memberships) == 1
    assert memberships[0].leg_year == expected_overridden


def test_process_bancada_multiple_bancadas_updates_state(
    monkeypatch, html_two_bancadas_two_members
):
    # Arrange
    rb = _raw_bancada(
        raw_html=html_two_bancadas_two_members,
        timestamp="2026-01-01T00:00:00",
        legislative_period="2025-2026",
    )

    expected_leg_year = mod.LegislativeYear("2025")
    monkeypatch.setattr(mod, "get_current_leg_year", lambda ts: expected_leg_year)
    monkeypatch.setattr(mod, "find_leg_period", lambda leg_year: "2025-2026")

    # Give different websites depending on which profile URL was fetched
    def fake_get_url_text(url: str) -> str:
        return f"<html><body>{url}</body></html>"

    def fake_get_cong_website(parsed: str) -> str:
        if "congresista/1" in parsed:
            return "https://example.com/cong/juan-perez"
        if "congresista/2" in parsed:
            return "https://example.com/cong/maria-lopez"
        return "https://example.com/cong/unknown"

    monkeypatch.setattr(mod, "get_url_text", fake_get_url_text)
    monkeypatch.setattr(mod, "get_cong_website", fake_get_cong_website)

    # Act
    bancadas, memberships = mod.process_bancada(rb)

    # Assert bancadas list has both
    assert [b.bancada_name for b in bancadas] == ["Accion Popular", "Fuerza Popular"]
    assert all(b.leg_year == expected_leg_year for b in bancadas)

    # Assert memberships map to correct bancada (state updates after second bancada header)
    assert len(memberships) == 2

    assert memberships[0].cong_name == "Juan Perez"
    assert memberships[0].bancada_name == "Accion Popular"
    assert memberships[0].website == "https://example.com/cong/juan-perez"

    assert memberships[1].cong_name == "Maria Lopez"
    assert memberships[1].bancada_name == "Fuerza Popular"
    assert memberships[1].website == "https://example.com/cong/maria-lopez"
