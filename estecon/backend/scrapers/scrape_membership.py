import re
import httpx
import asyncio
import json
from loguru import logger
from datetime import datetime
from lxml.html import fromstring
from typing import List, Dict, Tuple, Optional
from estecon.backend import URL, RoleOrganization, LegPeriod, TypeOrganization
from estecon.backend.scrapers.schema import Congresista, Membership, Organization
from estecon.backend.scrapers.scrape_utils import parse_url, xpath2

semaphore = asyncio.Semaphore(10)
timeout = httpx.Timeout(20)

def gen_cargos_url(url: str) -> str:
    """
    Transform the web of the congresista into the url where all the memberships are
    
    Args:
        url (str): URL of the congresista profile page
    """
    parse = parse_url(url + "sobrecongresista/cargos/")
    cargos_url = parse.xpath('//*[@id="objContents"]//iframe')[0].get('src')
    return cargos_url.replace('/#/listar','/api')

def get_membership(cargos_dict: Dict, cong_id: int, org_id: int) -> Membership:
    """
    Extract a Membership object from a dictionary
    """
    role = cargos_dict['desCargo'].lower()
    start_date = datetime.fromtimestamp(cargos_dict['fechaInicio']/1000)
    end_date = datetime.fromtimestamp(cargos_dict['fechaFin']/1000)
    return Membership(
        role = role,
        person_id = cong_id,
        org_id = org_id,
        start_date = start_date,
        end_date = end_date
    )

async def get_dict_cargos(client: httpx.AsyncClient, cong_url: str, retries: int = 3) -> Optional[Dict]:
    """
    Get a dictionary of all the cargos that a congresista have occupied in the parliament
    """
    cargos_url = gen_cargos_url(cong_url)
    for attempt in range(retries):
        try:
            async with semaphore:
                response = await client.get(cargos_url, timeout=timeout)
                json_dict = response.content.decode("utf-8")
                data = json.loads(json_dict)
                return data['data']
        except httpx.ReadTimeout:
            if attempt < retries - 1:
                await asyncio.sleep(1)
                continue
            else:
                logger.error(f"ReadTimeout: {cong_url}")
                break
    return None

async def main(url: str):
    async with httpx.AsyncClient(verify=False) as client:
        response = await get_dict_cargos(client, url)
        member = get_membership(response[0], 1, 1)
        print(member)
        return member

if __name__ == "__main__":
    # Example of use
    url = "https://www.congreso.gob.pe/congresistas2021/EduardoSalhuana/"
    asyncio.run(main(url))