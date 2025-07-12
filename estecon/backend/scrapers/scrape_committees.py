import os
from loguru import logger
from lxml.html import fromstring, HtmlElement
from difflib import get_close_matches
from selenium.webdriver.chrome.service import Service
from itertools import product
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from typing import List, Dict, Optional
from estecon.backend import LegislativeYear, LegPeriod, TypeOrganization
from estecon.backend.scrapers.schema import Organization
from estecon.backend.scrapers.scrape_utils import parse_url

ORG_ID_MAP = dict()
ORG_COUNTER = 1

def get_options(url: str, select_name: str) -> Dict[str,str]:
    """"""
    parse = parse_url(url)
    years = parse.xpath(f'//*[@name="{select_name}"]/option')
    return {elem.text : elem.get('value') for elem in years if elem.text is not None}

def get_html_with_selections(url: str, year_value: str, committee_value: str) -> Optional[HtmlElement]:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--log-level=3")

    service = Service(log_path=os.devnull)

    driver = webdriver.Chrome(service = service, options = options)
    driver.get(url)

    

    try:
        select_year = Select(driver.find_element(By.NAME, "idRegistroPadre"))
        select_year.select_by_value(year_value)

        select_committee = Select(driver.find_element(By.NAME, "fld_78_Comision"))
        select_committee.select_by_value(committee_value)    

        html = driver.page_source
        driver.quit()
        return fromstring(html)
    except NoSuchElementException as e:
        logger.error(f"Error found: {e}")
        driver.quit()
        return None
    
def get_or_create_org(org_name: str, legperiod: LegPeriod, legyear: LegislativeYear, org_url: str):
    global ORG_COUNTER, ORG_ID_MAP

    org_name_clean = org_name.strip().lower()
    close_name = next(iter(get_close_matches(org_name_clean, ORG_ID_MAP.keys(), 1, 0.9)), None)

    if org_name_clean not in ORG_ID_MAP and close_name is None:
        org_id = ORG_COUNTER
        ORG_ID_MAP[org_name_clean] = org_id
        ORG_COUNTER += 1
        logger.info(f"New Organization created: {org_name} with ID {org_id}")
        return Organization(
            leg_period=legperiod,
            leg_year=legyear,
            org_id=org_id,
            org_name=org_name_clean,
            org_type=TypeOrganization.COMMITTEE,
            org_url=org_url
        )
    matched_name = close_name or org_name_clean
    org_id = ORG_ID_MAP.get(matched_name)
    if close_name:
        logger.info(f"Close match used for organization name: {org_name_clean} → {close_name}")

    return Organization(
        leg_period=legperiod,
        leg_year=legyear,
        org_id=org_id,
        org_name=matched_name,
        org_type=TypeOrganization.COMMITTEE,
        org_url=org_url
    )

def get_committees(html: HtmlElement, legperiod: LegPeriod, legyear: LegislativeYear) -> List[Organization]:
    """"""
    lst_objects = html.xpath(f'//*[@class="congresistas"]/tbody/tr/td/a')
    lst_committees = []
    for obj in lst_objects:
        committee = get_or_create_org(
            org_name=obj.text,
            legperiod=legperiod,
            legyear=legyear,
            org_url=obj.attrib['href']
        )
        lst_committees.append(committee)
    return lst_committees

if __name__ == '__main__':

    # Use example:
    url = "https://www.congreso.gob.pe/CuadrodeComisiones"

    dict_years = get_options(url, 'idRegistroPadre')
    dict_types = get_options(url, 'fld_78_Comision')

    final_lst = []
    for year_key, type_key in product(dict_years.keys(), dict_types.keys()):
        if year_key == '2023':
            break

        logger.info(f'Creating committees for Año: {year_key} - Tipo: {type_key}')
        year = dict_years.get(year_key)
        types = dict_types.get(type_key)
        html = get_html_with_selections(url, year, types)
        if html is not None:
            lst_committees = get_committees(
                html, 
                LegPeriod.PERIODO_2021_2026,
                f'{year_key}-{int(year_key)+1}')
            final_lst.extend(lst_committees)

    logger.info(f'Total committees created: {len(final_lst)}')
        