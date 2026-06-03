import json
from types import SimpleNamespace
import pytest
import backend.process.congresistas as mod
from backend import RoleOrganization
from datetime import datetime


@pytest.fixture()
def dict_data_cong():
    website = "https://www.congreso.gob.pe/congresista/juan"
    return {
        website: {
            "first_name": "Juan Alberto",
            "last_name": "Perez Quispe",
            "full_name": "Juan Alberto Perez Quispe",
            "dni": "12345678",
            "gender": "Masculino",
            "website": website,
        }
    }


@pytest.fixture
def profile_html():
    # Must match the xpaths used in process_profile_content
    return """
    <html>
      <div class="nombres"><span>Label</span><span>Juan Alberto Perez Quispe</span></div>
      <div class="grupo"><span>Label</span><span>Accion Popular</span></div>
      <div class="bancada"><span>Label</span><span>Accion Popular</span></div>
      <div class="votacion"><span>Label</span><span>12,345</span></div>
      <div class="representa"><span>Label</span><span>Lima</span></div>
      <div class="condicion"><span>Label</span><span>Titular</span></div>
      <div class="foto"><img src="/FotosCongresista/juan.jpg"/></div>
    </html>
    """


def _raw_cong(
    *,
    profile_content="",
    memberships_content=None,
    leg_period="2021-2026",
    website="https://www.congreso.gob.pe/congresista/juan",
):
    if memberships_content is None:
        memberships_content = {"data": []}
    return SimpleNamespace(
        profile_content=profile_content,
        memberships_content=json.dumps(memberships_content),
        leg_period=leg_period,
        website=website,
        timestamp=datetime(2025, 8, 1),
    )


def test_xpath2_returns_text_when_found(profile_html):
    from lxml.html import fromstring

    html = fromstring(profile_html)
    assert (
        mod.xpath2('//*[@class="nombres"]/span[2]', html) == "Juan Alberto Perez Quispe"
    )


def test_xpath2_returns_none_when_missing(profile_html):
    from lxml.html import fromstring

    html = fromstring(profile_html)
    assert mod.xpath2('//*[@class="does-not-exist"]/span[2]', html) is None


def test_process_profile_content_parses_fields_and_votes_int(
    profile_html, dict_data_cong
):
    raw = _raw_cong(profile_content=profile_html, leg_period="2021-2026")

    cong, orgs, memberships = mod.process_profile_content(raw, dict_data_cong)

    assert cong.full_name == "Juan Alberto Perez Quispe"
    assert cong.website == "https://www.congreso.gob.pe/congresista/juan"
    assert cong.photo_url == "https://www.congreso.gob.pe/FotosCongresista/juan.jpg"
    assert [org.org_name for org in orgs] == ["Accion Popular", "Cámara de Diputados"]
    assert memberships[0].org_name == "Accion Popular"
    assert memberships[1].votes_in_election == 12345
    assert memberships[1].org_name == "Cámara de Diputados"


def test_process_memberships_all_branches(monkeypatch):
    # Normalize role is external logic: mock it for deterministic tests
    monkeypatch.setattr(
        mod,
        "normalize_membership_role",
        lambda s: RoleOrganization((s or "").strip().title()),
    )

    memberships_payload = {
        "data": [
            # Special case: Subcomisión de Acusaciones Constitucionales
            {
                "period": "2021-2026",
                "anio": "2025",
                "desOrgano": "X",
                "desOrganoCongresista": "Subcomisión de Acusaciones Constitucionales",
                "desCargo": "Presidente",
                "fechaInicio": "2025-08-01",
                "fechaFin": None,
            },
            # type_org != '' => Comisión, comm_type = type_org
            {
                "period": "2021-2026",
                "anio": "2025",
                "desOrgano": "Comisión Ordinaria",
                "desOrganoCongresista": "Comisión de Economía",
                "desCargo": "Miembro",
                "fechaInicio": "2025-08-02",
                "fechaFin": "2025-12-31",
            },
            # type_org == '' => org_type = org_name, comm_type = None
            {
                "period": "2021-2026",
                "anio": "2025",
                "desOrgano": "",
                "desOrganoCongresista": "Mesa Directiva",
                "desCargo": "Secretario",
                "fechaInicio": "2025-09-01",
                "fechaFin": "2026-07-27",
            },
        ]
    }

    raw = _raw_cong(memberships_content=memberships_payload, leg_period="2021-2026")
    cong = SimpleNamespace(
        full_name="Juan Pérez",
        leg_period="2021-2026",
        website="www.congreso.gob.pe/juan",
    )

    out = mod.process_memberships(raw, cong)

    assert len(out) == 3

    # 1) Special case
    m0 = out[0]
    assert m0.cong_name == "Juan Pérez"
    assert m0.leg_period == "2021-2026"
    assert m0.role == RoleOrganization.PRESIDENTE
    assert m0.org_name == "Subcomisión de Acusaciones Constitucionales"
    assert m0.org_type == "Comisión"
    assert m0.start_date == datetime.fromisoformat("2025-08-01").date()
    assert m0.end_date is None

    # 2) type_org != ''
    m1 = out[1]
    assert m1.role == RoleOrganization.MIEMBRO
    assert m1.org_name == "Comisión de Economía"
    assert m1.org_type == "Comisión"
    assert m1.start_date == datetime.fromisoformat("2025-08-02").date()
    assert m1.end_date == datetime.fromisoformat("2025-12-31").date()

    # 3) type_org == ''
    m2 = out[2]
    assert m2.role == RoleOrganization.SECRETARIO
    assert m2.org_name == "Mesa Directiva"
    assert m2.org_type == "Administrativo"
    assert m2.start_date == datetime.fromisoformat("2025-09-01").date()
    assert m2.end_date == datetime.fromisoformat("2026-07-27").date()


def test_process_memberships_raises_if_data_is_none(monkeypatch):
    """
    Your code does: json.loads(...).get('data', None) then iterates it.
    If data is None, it will raise TypeError. This test documents current behavior.
    """
    monkeypatch.setattr(mod, "normalize_membership_role", lambda s: s)

    raw = _raw_cong(memberships_content={"data": None})
    cong = SimpleNamespace(full_name="X", leg_period="2021-2026")

    with pytest.raises(TypeError):
        mod.process_memberships(raw, cong)
