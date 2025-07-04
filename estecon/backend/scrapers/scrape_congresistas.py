import json
from pathlib import Path
from estecon import URL
from loguru import logger
from .schema import Congresista
from .scrape_utils import parse_url, xpath2
import re
import httpx
from lxml.html import fromstring
import asyncio

def get_dict_periodos(url: str) -> dict:
    parse = parse_url(url)
    periodos = parse.xpath('//*[@name="idRegistroPadre"]/option')
    return {elem.text: elem.get('value') for elem in periodos}

def get_links_congres(url: str, params:dict) -> list:
    parse = parse_url(url, params)
    links = parse.xpath('//*[@class="congresistas"]//tr//td//*[@class="conginfo"]/@href')
    return [elem for elem in links]

# Async version can be implemented later if needed
async def get_cong_info2(client: httpx.AsyncClient, base_url: str, cong_link: str, leg_period: str) -> dict:
    async with asyncio.Semaphore(10):
        r = await client.get(base_url + cong_link)
        tree = fromstring(r.text)
        search = re.search(r"(?<=id=)\d+", cong_link)
        id = search.group() if search else None
        return vars(Congresista(
            id=id,
            nombre=xpath2('//*[@class="nombres"]/span[2]', tree),
            votation=xpath2('//*[@class="votacion"]/span[2]', tree),
            leg_period=leg_period,
            party_name=xpath2('//*[@class="grupo"]/span[2]', tree),
            bancada_name=xpath2('//*[@class="bancada"]/span[2]', tree),
            dist_electoral=xpath2('//*[@class="representa"]/span[2]', tree),
            condicion=xpath2('//*[@class="condicion"]/span[2]', tree),
            website=tree.xpath('//*[@class="web"]/span[2]/a/@href')[0] if tree.xpath('//*[@class="web"]/span[2]/a/@href') else None
        ))

async def get_cong_list2(base_url: str) -> list[dict]:
    final_dict = {}
    async with httpx.AsyncClient(verify=False) as client:
        periodos = get_dict_periodos(base_url)
        for periodo, valor in periodos.items():
            links = get_links_congres(base_url, {'idRegistroPadre': valor})
            logger.info(f"Scraping {len(links)} congresistas for the period: {periodo}")
            tasks = [get_cong_info2(client, base_url, link, periodo) for link in links]
            results = await asyncio.gather(*tasks)
            final_dict[periodo] = results
    return final_dict

if __name__ == '__main__':
    path = Path('./data/congresistas.json')
    if not path.exists():
        congresistas = asyncio.run(get_cong_list2(URL['congresistas']))
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(congresistas, f, ensure_ascii=False, indent=2)