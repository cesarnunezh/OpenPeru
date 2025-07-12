from loguru import logger
from lxml.html import fromstring, HtmlElement
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from typing import List, Dict, Optional
from estecon.backend import LegislativeYear, LegPeriod, TypeOrganization
from estecon.backend.scrapers.schema import Organization
from estecon.backend.scrapers.scrape_utils import parse_url

# 'idRegistroPadre'
# 'fld_78_Comision'

def get_options(url: str, select_name: str) -> List[Dict[str,str]]:
    """"""
    parse = parse_url(url)
    years = parse.xpath(f'//*[@name="{select_name}"]/option')
    return {elem.text : elem.get('value') for elem in years if elem.text is not None}

def get_html_with_selections(url: str, year_value: str, committee_value: str) -> Optional[HtmlElement]:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--log-level=3")

    driver = webdriver.Chrome(options=options)
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
    
def get_committees(html: HtmlElement, legperiod: LegPeriod, legyear: LegislativeYear) -> List[Organization]:
    """"""
    lst_objects = html.xpath('//*[@class="congresistas"]/tbody/tr/td/a')
    lst_committees = []
    for obj in lst_objects:
        committee = Organization(
            leg_period = legperiod,
            leg_year = legyear,
            org_id = 1,
            org_name = obj.text,
            org_type = TypeOrganization.COMMITTEE,
            org_url = obj.attrib['href']
        )
        lst_committees.append(committee)
    return lst_committees