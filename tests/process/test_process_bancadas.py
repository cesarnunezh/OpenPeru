from types import SimpleNamespace
import pytest
import backend.process.bancadas as mod
from backend import RoleOrganization, TypeOrganization


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

    # Act
    bancadas, memberships = mod.process_bancada(rb)

    # Assert bancadas
    assert len(bancadas) == 1
    b = bancadas[0]
    assert b.org_name == "Accion Popular"
    assert b.org_type == TypeOrganization.BANCADA

    # Assert memberships
    assert len(memberships) == 1
    m = memberships[0]
    assert m.cong_name == "Juan Perez"
    assert m.org_name == "Accion Popular"
    assert m.org_type == TypeOrganization.BANCADA
    assert m.role == RoleOrganization.MIEMBRO


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

    # Act
    bancadas, memberships = mod.process_bancada(rb)

    assert len(bancadas) == 1
    assert bancadas[0].org_name == "Accion Popular"

    assert len(memberships) == 1
    assert memberships[0].leg_period == "2021-2026"


def test_process_bancada_multiple_bancadas_updates_state(
    monkeypatch, html_two_bancadas_two_members
):
    # Arrange
    rb = _raw_bancada(
        raw_html=html_two_bancadas_two_members,
        timestamp="2026-01-01T00:00:00",
        legislative_period="2025-2026",
    )

    # Act
    bancadas, memberships = mod.process_bancada(rb)

    # Assert bancadas list has both
    assert [b.org_name for b in bancadas] == ["Accion Popular", "Fuerza Popular"]
    assert all(b.org_type == TypeOrganization.BANCADA for b in bancadas)

    # Assert memberships map to correct bancada (state updates after second bancada header)
    assert len(memberships) == 2

    assert memberships[0].cong_name == "Juan Perez"
    assert memberships[0].org_name == "Accion Popular"

    assert memberships[1].cong_name == "Maria Lopez"
    assert memberships[1].org_name == "Fuerza Popular"
