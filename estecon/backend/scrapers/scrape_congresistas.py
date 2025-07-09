import re
import httpx
import asyncio
from loguru import logger
from lxml.html import fromstring
from typing import List, Dict, Tuple
from estecon.backend import URL, LegPeriod, PARTY_ALIASES
from estecon.backend.scrapers.scrape_utils import parse_url, xpath2
from estecon.backend.scrapers.schema import Congresista, Party

PARTY_ID_MAP = {period: {} for period in LegPeriod._member_names_}
PARTY_COUNTER = 1
semaphore = asyncio.Semaphore(10)
timeout = httpx.Timeout(20.0, connect=10.0)

def normalize_party_name(name: str) -> str:
    if name in PARTY_ALIASES.keys():
        canonical_name = PARTY_ALIASES[name]
        return canonical_name
    return name

def get_or_create_party(party_name: str, leg_period: LegPeriod) -> Party:
    global PARTY_ID_MAP, PARTY_COUNTER
    if not party_name:
        party_name = "Ninguno"
    
    norm_name = normalize_party_name(party_name)
    leg_key = leg_period.name
    
    if norm_name not in PARTY_ID_MAP[leg_key].keys():
        party_id = PARTY_COUNTER
        PARTY_ID_MAP[leg_key][norm_name] = party_id
        PARTY_COUNTER += 1
        logger.info(f"New Party created: {norm_name} with ID {party_id}")
        return Party(
            leg_period=leg_period,
            party_id=party_id,
            party_name=norm_name
        )
    return Party(
        leg_period=leg_period,
        party_id=PARTY_ID_MAP[leg_key][norm_name],
        party_name=party_name
    )
    
def get_dict_periodos(url: str) -> Dict[str,str]:
    parse = parse_url(url)
    periodos = parse.xpath('//*[@name="idRegistroPadre"]/option')
    return {elem.text: elem.get('value') for elem in periodos}

def get_links_congres(url: str, params:dict) -> List[str]:
    parse = parse_url(url, params)
    links = parse.xpath('//*[@class="congresistas"]//tr//td//*[@class="conginfo"]/@href')
    return [elem for elem in links]

# Async version can be implemented later if needed
async def get_cong_party_info(client: httpx.AsyncClient, base_url: str, cong_link: str, leg_period: LegPeriod, retries: int = 3) -> Tuple[Congresista, Party]:
    url = base_url + cong_link
    for attempt in range(retries):
        try:
            async with semaphore:
                r = await client.get(url, timeout=timeout)
            tree = fromstring(r.text)
            search = re.search(r"(?<=id=)\d+", cong_link)
            id = int(search.group()) if search else None
            if id:
                party_name = xpath2('//*[@class="grupo"]/span[2]', tree)
                party = get_or_create_party(party_name, leg_period)
                web_site = tree.xpath('//*[@class="web"]/span[2]/a/@href')

                congresista = Congresista(
                    id=id,
                    leg_period=leg_period,
                    nombre=xpath2('//*[@class="nombres"]/span[2]', tree),
                    party_id=party.party_id,
                    votes_in_election=int(xpath2('//*[@class="votacion"]/span[2]', tree).replace(",", "").replace("'","")),
                    dist_electoral=xpath2('//*[@class="representa"]/span[2]', tree),
                    condicion=xpath2('//*[@class="condicion"]/span[2]', tree) or "Desconocido",
                    website=web_site[0] if web_site else None
                )
                return congresista, party
        except httpx.ReadTimeout:
            if attempt < retries - 1:
                await asyncio.sleep(1)
                continue
            else:
                logger.error(f"ReadTimeout: {url}")
        except Exception as e:
            logger.error(f"Error al procesar {url}: {e}")
            break
    return None, None

async def get_cong_party_list(base_url: str = URL['congresistas']) -> Tuple[List[Congresista], List[Party]]:
    congresistas = []
    partidos = []

    async with httpx.AsyncClient(verify=False) as client:
        periodos = get_dict_periodos(base_url)
        for periodo, valor in periodos.items():
            links = get_links_congres(base_url, {'idRegistroPadre': valor})
            logger.info(f"Scraping {len(links)} congresistas for the period: {periodo}")

            leg_period_enum = LegPeriod(periodo)
            tasks = [get_cong_party_info(client, base_url, link, leg_period_enum) for link in links]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            filtered_results = [
                r for r in results
                if isinstance(r, tuple) and r[0] is not None
            ]

            congresistas.extend([r[0] for r in filtered_results])
            partidos.extend([r[1] for r in filtered_results])

    return congresistas, partidos
