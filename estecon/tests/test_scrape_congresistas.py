import pytest
import respx
import httpx
from estecon.backend import LegPeriod, PARTY_ALIASES
from estecon.backend.scrapers import scrape_congresistas as sc
from estecon.backend.scrapers.scrape_congresistas import (
    get_cong_party_info, normalize_party_name, get_or_create_party,
    get_dict_periodos, get_links_congres, split_names
)
from estecon.backend.scrapers.schema import Congresista, Party

def test_normalize_party_name():
    PARTY_ALIASES["FP"] = "Fuerza Popular"
    assert normalize_party_name("FP") == "Fuerza Popular"
    assert normalize_party_name("Acción Popular") == "Acción Popular"

def test_get_or_create_party_respects_counter():
    sc.PARTY_ID_MAP = {p: {} for p in LegPeriod._member_names_}
    sc.PARTY_COUNTER = 1
    party = get_or_create_party("Mi Partido", LegPeriod["PERIODO_2021_2026"])
    assert party.party_id == 1
    same_party = get_or_create_party("Mi Partido", LegPeriod["PERIODO_2021_2026"])
    assert same_party.party_id == 1
    new_party = get_or_create_party("Otro Partido", LegPeriod["PERIODO_2021_2026"])
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

    result = get_dict_periodos("https://fake.congreso.gob.pe")
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

    result = get_links_congres("https://fake.congreso.gob.pe", {"idRegistroPadre": "123"})
    assert result == ["/perfil?id=101", "/perfil?id=102"]

def test_split_names_with_3_tokens():
    lst_names = ['María Acuña Peralta',
                 'Carlos Alva Rojas',
                 'Jaime Castillo Mori']
    
    splitted_names = [split_names(name) for name in lst_names]
    assert splitted_names[0] == ("María", "Acuña Peralta")
    assert splitted_names[1] == ("Carlos", "Alva Rojas")
    assert splitted_names[2] == ("Jaime", "Castillo Mori")

def test_split_names_with_4_tokens():
    lst_names = ['María Grimaneza Acuña Peralta',
                 'Carlos Enrique Alva Rojas',
                 'Jaime del Castillo Mori']
    
    splitted_names = [split_names(name) for name in lst_names]
    assert splitted_names[0] == ("María Grimaneza", "Acuña Peralta")
    assert splitted_names[1] == ("Carlos Enrique", "Alva Rojas")
    assert splitted_names[2] == ("Jaime", "del Castillo Mori")

def test_split_names_with_5_tokens():
    lst_names = ['María del Carmen Alva Prieto',
                'Diego Alonso Fernando Bazán Calderón',
                'Luis Gustavo Cordero Jon Tay',
                'Juan Carlos Martín Lizarzaburu Lizarzaburu',
                'Susel Ana María Paredes Piqué']
    
    splitted_names = [split_names(name) for name in lst_names]
    assert splitted_names[0] == ("María del Carmen", "Alva Prieto")
    assert splitted_names[1] == ("Diego Alonso Fernando", "Bazán Calderón")
    assert splitted_names[2] == ("Luis Gustavo", "Cordero Jon Tay")
    assert splitted_names[3] == ("Juan Carlos Martín", "Lizarzaburu Lizarzaburu")
    assert splitted_names[4] == ("Susel Ana María", "Paredes Piqué")

def test_split_names_with_more_tokens():
    lst_names = ['María del Pilar Cordero Jon Tay',
                'Gladys Margot Echaíz Ramos vda de Núñez',
                'María de los Milagros Jackeline Jáuregui Martínez de Aguayo']

    splitted_names = [split_names(name) for name in lst_names]
    assert splitted_names[0] == ("María del Pilar", "Cordero Jon Tay")
    assert splitted_names[1] == ("Gladys Margot", "Echaíz Ramos vda de Núñez")
    assert splitted_names[2] == ("María de los Milagros Jackeline", "Jáuregui Martínez de Aguayo")


@pytest.mark.asyncio
async def test_get_cong_party_info_success(monkeypatch):
    html = """
    <html>
        <body>
            <div class="grupo"><span></span><span>Partido Prueba</span></div>
            <div class="nombres"><span></span><span>Juan Alberto Pérez Palma</span></div>
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
            result = await get_cong_party_info(client, "https://fake.congreso.gob.pe", "/perfil?id=123", leg_period)

        congresista, party = result
        assert congresista.full_name == "Juan Alberto Pérez Palma"
        assert congresista.first_name == "Juan Alberto"
        assert congresista.last_name == "Pérez Palma"
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
            congresista, party = await get_cong_party_info(client, "https://fake.congreso.gob.pe", "/perfil?id=123", leg_period, retries=2)

        assert congresista is None
        assert party is None

    await run_test()

@pytest.mark.asyncio
async def test_get_cong_party_list(monkeypatch):
    dummy_periodos = {
        "Parlamentario 2021 - 2026": "999"
    }

    dummy_links = [
        "/perfil?id=101", "/perfil?id=102"
    ]

    dummy_party = Party(
        party_id=1,
        party_name="Partido Simulado",
        leg_period=LegPeriod.PERIODO_2021_2026
    )

    def mock_get_dict_periodos(url):
        return dummy_periodos

    def mock_get_links_congres(url, params):
        return dummy_links

    async def mock_get_cong_party_info(client, base_url, link, leg_period, retries=3):
        cid = int(link.split("=")[1])
        return (
            Congresista(
                id=cid,
                full_name="Juan José Pérez Pérez",
                first_name="Juan José",
                last_name="Pérez Pérez",
                leg_period=leg_period,
                party_id=1,
                votes_in_election=12345,
                dist_electoral="Lima",
                condicion="Titular",
                website="http://fake.pe"
            ),
            dummy_party
        )

    # Monkeypatch all dependencies
    monkeypatch.setattr(sc, "get_dict_periodos", mock_get_dict_periodos)
    monkeypatch.setattr(sc, "get_links_congres", mock_get_links_congres)
    monkeypatch.setattr(sc, "get_cong_party_info", mock_get_cong_party_info)

    congresistas, partidos = await sc.get_cong_party_list("https://fake.congreso.gob.pe")

    assert len(congresistas) == 2
    assert len(partidos) == 2
    assert all(isinstance(c, Congresista) for c in congresistas)
    assert all(p.party_name == "Partido Simulado" for p in partidos)