import pytest
import respx
import httpx
from lxml.html import fromstring
from estecon.backend.scrapers import scrape_congresistas as sc
from estecon.backend import LegPeriod, PARTY_ALIASES

@pytest.mark.asyncio
async def test_get_cong_party_info_success(monkeypatch):
    html = """
    <html>
        <body>
            <div class="grupo"><span></span><span>Partido Prueba</span></div>
            <div class="nombres"><span></span><span>Juan Pérez</span></div>
            <div class="votacion"><span></span><span>12,345</span></div>
            <div class="representa"><span></span><span>Lima</span></div>
            <div class="condicion"><span></span><span>Titular</span></div>
            <div class="web"><span></span><span><a href="http://juanperez.pe">web</a></span></div>
        </body>
    </html>
    """

    @respx.mock
    async def run_test():
        url = "https://fake.congreso.gob.pe/perfil?id=123"
        respx.get(url).mock(return_value=httpx.Response(200, text=html))

        leg_period = LegPeriod["PERIODO_2021_2026"]
        async with httpx.AsyncClient() as client:
            result = await sc.get_cong_party_info(client, "https://fake.congreso.gob.pe", "/perfil?id=123", leg_period)

        congresista, party = result
        assert congresista.nombre == "Juan Pérez"
        assert congresista.party_id == party.party_id
        assert congresista.votes_in_election == 12345
        assert party.party_name == "Partido Prueba"

    await run_test()

@pytest.mark.asyncio
async def test_get_cong_party_info_timeout(monkeypatch):
    @respx.mock
    async def run_test():
        respx.get("https://fake.congreso.gob.pe/perfil?id=123").mock(side_effect=httpx.ReadTimeout("Timeout"))

        leg_period = LegPeriod["PERIODO_2021_2026"]
        async with httpx.AsyncClient() as client:
            congresista, party = await sc.get_cong_party_info(client, "https://fake.congreso.gob.pe", "/perfil?id=123", leg_period, retries=2)

        assert congresista is None
        assert party is None

    await run_test()

def test_normalize_party_name():
    PARTY_ALIASES["FP"] = "Fuerza Popular"
    assert sc.normalize_party_name("FP") == "Fuerza Popular"
    assert sc.normalize_party_name("Acción Popular") == "Acción Popular"

def test_get_or_create_party_respects_counter():
    sc.PARTY_ID_MAP = {p: {} for p in LegPeriod._member_names_}
    sc.PARTY_COUNTER = 1
    party = sc.get_or_create_party("Mi Partido", LegPeriod["PERIODO_2021_2026"])
    assert party.party_id == 1
    same_party = sc.get_or_create_party("Mi Partido", LegPeriod["PERIODO_2021_2026"])
    assert same_party.party_id == 1
    new_party = sc.get_or_create_party("Otro Partido", LegPeriod["PERIODO_2021_2026"])
    assert new_party.party_id == 2

@respx.mock
def test_get_dict_periodos():
    html = """
    <html>
        <select name="idRegistroPadre">
            <option value="123">PERIODO_2021_2026</option>
            <option value="456">PERIODO_2016_2021</option>
        </select>
    </html>
    """
    respx.get("https://fake.congreso.gob.pe").mock(return_value=httpx.Response(200, text=html))

    result = sc.get_dict_periodos("https://fake.congreso.gob.pe")
    assert result == {
        "PERIODO_2021_2026": "123",
        "PERIODO_2016_2021": "456"
    }

@respx.mock
def test_get_links_congres():
    html = """
    <html>
        <table class="congresistas">
            <tr>
                <td><a class="conginfo" href="/perfil?id=101"></a></td>
                <td><a class="conginfo" href="/perfil?id=102"></a></td>
            </tr>
        </table>
    </html>
    """
    respx.post("https://fake.congreso.gob.pe", data={"idRegistroPadre": "123"}).mock(
        return_value=httpx.Response(200, text=html)
    )

    result = sc.get_links_congres("https://fake.congreso.gob.pe", {"idRegistroPadre": "123"})
    assert result == ["/perfil?id=101", "/perfil?id=102"]