from types import SimpleNamespace

import pytest
import backend.process.organizations as mod
from backend import RoleOrganization, TypeAdmin, TypeCommittee, TypeOrganization


def _raw_committee(*, raw_html: str, legislative_year: str = "2025"):
    return SimpleNamespace(raw_html=raw_html, legislative_year=legislative_year)


def _raw_org(
    *,
    raw_html: str,
    legislative_year: str = "2025",
    type_org: str = "Mesa Directiva",
    org_link: str = "/org/mesa",
    web_page: str = "www.org.gob.pe/org/mesa",
):
    return SimpleNamespace(
        raw_html=raw_html,
        legislative_year=legislative_year,
        type_org=type_org,
        org_link=org_link,
        web_page=web_page,
        timestamp=f"{legislative_year}-08-01T00:00:00",
    )


@pytest.fixture
def committee_html_two_rows():
    return """
    <table class="congresistas">
      <tbody>
        <tr>
          <td>Comisión Ordinaria</td>
          <td><a href="/comisiones/economia">Comisión de Economía</a></td>
        </tr>
        <tr>
          <td>Comisiones Especiales</td>
          <td><a href="/comisiones/salud">Comisión Especial de Salud</a></td>
        </tr>
      </tbody>
    </table>
    """


@pytest.fixture
def org_membership_html():
    return """
    <table class="congresistas">
      <tbody>
        <tr>
          <th>#</th><th>Nombre</th><th>Web</th><th>Dato</th><th>Cargo</th>
        </tr>
        <tr>
          <td>1</td>
          <td>Juan Pérez</td>
          <td><a href="https://example.com/juan">Perfil</a></td>
          <td>-</td>
          <td>presidente</td>
        </tr>
        <tr>
          <td>2</td>
          <td>Maria Lopez</td>
          <td><a href="https://example.com/maria">Perfil</a></td>
          <td>-</td>
          <td>miembro</td>
        </tr>
      </tbody>
    </table>
    """


def test_process_committee_builds_organizations(monkeypatch, committee_html_two_rows):
    raw = _raw_committee(raw_html=committee_html_two_rows, legislative_year="2025")

    out = mod.process_committee(raw)

    assert len(out) == 2

    assert out[0].org_type == TypeOrganization.COMMITTEE
    assert out[0].org_subtype == TypeCommittee.COM_ORD
    assert out[0].org_name == "Comisión de Economía"
    assert out[0].org_link == "/comisiones/economia"

    assert out[1].org_subtype == TypeCommittee.COM_ESP
    assert out[1].org_name == "Comisión Especial de Salud"
    assert out[1].org_link == "/comisiones/salud"


def test_process_org_maps_fields(monkeypatch):
    raw = _raw_org(
        raw_html="<table/>",
        legislative_year="2024",
        type_org="Mesa Directiva",
        org_link="/org/mesa",
        web_page="www.org.gob.pe/org/mesa",
    )

    org = mod.process_org(raw)

    assert org.org_name == "Mesa Directiva"
    assert org.org_type == TypeOrganization.ADMINISTRATIVE
    assert org.org_subtype == TypeAdmin.MESA_DIRECTIVA
    assert org.org_link == "/org/mesa"


def test_process_org_membership_creates_memberships_with_year_window(
    monkeypatch, org_membership_html
):
    raw_org = _raw_org(
        raw_html=org_membership_html,
        legislative_year="2025",
        type_org="Mesa Directiva",
        org_link="/org/mesa",
        web_page="www.org.gob.pe/org/mesa",
    )

    org = mod.process_org(raw_org)
    out = mod.process_org_membership(raw_org, org)

    assert len(out) == 2

    assert out[0].cong_name == "Juan Pérez"
    assert out[0].role == RoleOrganization.PRESIDENTE
    assert out[0].start_date is None
    assert out[0].end_date is None

    assert out[1].cong_name == "Maria Lopez"
    assert out[1].role == RoleOrganization.MIEMBRO
    assert out[1].start_date is None
    assert out[1].end_date is None
