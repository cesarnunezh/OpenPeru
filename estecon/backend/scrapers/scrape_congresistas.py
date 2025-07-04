import json
from pathlib import Path
from loguru import logger
from estecon.backend import URL, LegPeriod
from estecon.backend.scrapers.scrape_utils import parse_url, xpath2
from estecon.backend.scrapers.schema import Congresista, Party
import re
import httpx
from lxml.html import fromstring
import asyncio

PARTY_ID_MAP = {}
PARTY_COUNTER = 1

def get_or_create_party(party_name: str, leg_period: LegPeriod) -> Party:
    global PARTY_ID_MAP, PARTY_COUNTER
    if party_name not in PARTY_ID_MAP:
        party_id = PARTY_COUNTER
        PARTY_ID_MAP[party_name] = party_id
        PARTY_COUNTER += 1
        return Party(leg_period=leg_period, party_id=party_id, party_name=party_name)
    else:
        return None
    
def get_dict_periodos(url: str) -> dict:
    parse = parse_url(url)
    periodos = parse.xpath('//*[@name="idRegistroPadre"]/option')
    return {elem.text: elem.get('value') for elem in periodos}

def get_links_congres(url: str, params:dict) -> list:
    parse = parse_url(url, params)
    links = parse.xpath('//*[@class="congresistas"]//tr//td//*[@class="conginfo"]/@href')
    return [elem for elem in links]

semaphore = asyncio.Semaphore(10)
timeout = httpx.Timeout(20.0, connect=10.0)

# Async version can be implemented later if needed
async def get_cong_info2(client: httpx.AsyncClient, base_url: str, cong_link: str, leg_period: LegPeriod, retries: int = 3):
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
                new_party = get_or_create_party(party_name, leg_period)
                if new_party:
                    logger.info(f"New Party created: {new_party.party_name} with ID {new_party.party_id}")
                party_id = PARTY_ID_MAP[party_name]
                web_site = tree.xpath('//*[@class="web"]/span[2]/a/@href')

                congresista = Congresista(
                    id=id,
                    leg_period=leg_period,
                    nombre=xpath2('//*[@class="nombres"]/span[2]', tree),
                    party_id=party_id,
                    votes_in_election=int(xpath2('//*[@class="votacion"]/span[2]', tree).replace(",", "")),
                    dist_electoral=xpath2('//*[@class="representa"]/span[2]', tree),
                    condicion=xpath2('//*[@class="condicion"]/span[2]', tree),
                    website=web_site[0] if web_site else None
                )
                return congresista, new_party
        except httpx.ReadTimeout:
            if attempt < retries - 1:
                await asyncio.sleep(1)
                continue
            else:
                logger.error(f"❌ ReadTimeout: {url}")
        except Exception as e:
            logger.error(f"❌ Error al procesar {url}: {e}")
            break
    return None, None

async def get_cong_list2(base_url: str) -> tuple[dict, dict]:
    congresistas_dict = {}
    parties_dict = {}

    async with httpx.AsyncClient(verify=False) as client:
        periodos = get_dict_periodos(base_url)

        for periodo, valor in periodos.items():
            links = get_links_congres(base_url, {'idRegistroPadre': valor})
            logger.info(f"Scraping {len(links)} congresistas for the period: {periodo}")

            tasks = [get_cong_info2(client, base_url, link, periodo) for link in links]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            filtered_results = [
                r for r in results
                if isinstance(r, tuple) and r[0] is not None
            ]

            congresistas_dict[periodo] = [r[0] for r in filtered_results]
            unique_parties = {}
            for _, party in filtered_results:
                if party and party.party_id not in unique_parties:
                    unique_parties[party.party_id] = party

            parties_dict[periodo] = list(unique_parties.values())

    return congresistas_dict, parties_dict

if __name__ == '__main__':
    path = Path('./data/congresistas_2.json')
    if not path.exists():
        congresistas = asyncio.run(get_cong_list2(URL['congresistas']))
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(congresistas, f, ensure_ascii=False, indent=2)