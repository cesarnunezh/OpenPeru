import os
import time
from loguru import logger
from typing import Literal
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service

from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

from backend.config import (
    settings,
    directories,
    stop_logging_to_console,
    resume_logging_to_console,
)
from backend.database.raw_models import RawOrganization
from backend.scrapers.utils import parse_url


BASE_URLS = {
    "Junta de Portavoces": "https://www3.congreso.gob.pe/pagina/junta-de-portavoces",
    "Consejo Directivo": "https://www3.congreso.gob.pe/pagina/consejodirectivo",
    "Mesa Directiva": "https://www3.congreso.gob.pe/pagina/mesa-directiva",
    "Comisión Permanente": "https://www3.congreso.gob.pe/pagina/comision-permanente",
}

RAW_DB_PATH = settings.RAW_DB_URL


class RawOrganizationScraper:
    """
    Class to scrape Grupos Parlamentarios' raw data from the congress web page
    """

    def __init__(self):
        # Engine and session maker for DB
        self.engine = create_engine(RAW_DB_PATH)
        self.urls = BASE_URLS
        self.Session = sessionmaker(bind=self.engine)

    def get_options(
        self,
        url: str,
        select_name: Literal["idRegistroPadre"] = "idRegistroPadre",
    ) -> dict[str, str]:
        """
        Functions that fetchs all the possible options that are in the dropdown list in the html file

        Args:
            - url (str): link to the html
            - select_name (str): the name of the dropdown element
        """
        parse = parse_url(url)
        if parse is None:
            logger.warning(f"Failed to parse options page: {url}")
            return {}
        options = parse.xpath(f'//*[@name="{select_name}"]/option')
        return {
            elem.text: elem.get("value") for elem in options if elem.text is not None
        }

    def _build_driver(self) -> webdriver.Chrome:
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--log-level=3")
        options.add_experimental_option("excludeSwitches", ["enable-logging"])

        # Key: don't wait for every resource to load
        options.page_load_strategy = "eager"  # consider "none" if needed

        service = Service(log_path=os.devnull)
        driver = webdriver.Chrome(service=service, options=options)

        # Selenium side timeouts (independent of urllib3)
        driver.set_page_load_timeout(60)
        driver.set_script_timeout(30)
        driver.implicitly_wait(0)

        return driver

    def _safe_get(
        self,
        driver: webdriver.Chrome,
        url: str,
        *,
        retries: int = 2,
        sleep_s: float = 2.0,
    ) -> None:
        for attempt in range(retries + 1):
            try:
                driver.get(url)
                return
            except TimeoutException:
                # Often DOM is already usable. Stop further loading.
                try:
                    driver.execute_script("window.stop();")
                except Exception:
                    pass

                if attempt == retries:
                    raise
                time.sleep(sleep_s)

    def get_html_with_selections(self, url: str, period_value: str) -> str | None:
        driver = self._build_driver()

        try:
            self._safe_get(driver, url)
            wait = WebDriverWait(driver, 25)

            # Wait until the dropdown exists
            wait.until(EC.presence_of_element_located((By.NAME, "idRegistroPadre")))
            select_year = Select(driver.find_element(By.NAME, "idRegistroPadre"))

            # Select the period
            select_year.select_by_value(period_value)

            wait.until(
                lambda d: (
                    Select(
                        d.find_element(By.NAME, "idRegistroPadre")
                    ).first_selected_option.get_attribute("value")
                    == period_value
                )
            )

            # Strategy 2 (better if you know what changes): wait for a specific container/table to appear/update
            # wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.your-results-container")))

            return driver.page_source

        except TimeoutException as e:
            logger.warning(
                f"Selenium timeout loading {url} (period={period_value}): {e}"
            )
            return None
        except NoSuchElementException as e:
            logger.error(f"Element not found on {url} (period={period_value}): {e}")
            return None
        except WebDriverException as e:
            logger.error(f"WebDriver error on {url} (period={period_value}): {e}")
            return None
        finally:
            try:
                driver.quit()
            except Exception:
                pass

    def get_raw_organizations(self, only_current: bool = True) -> None:
        final_lst = []
        for type_org, url in self.urls.items():
            dict_periods = self.get_options(url=url, select_name="idRegistroPadre")

            if only_current:
                # Only scrape current period
                key, val = list(dict_periods.items())[0]
                dict_periods = {key: val}

            for year, value in dict_periods.items():
                logger.info(
                    f"Scraping organization for year {year} and type {type_org}"
                )

                html = self.get_html_with_selections(url, value)

                if html is not None:
                    new_org = RawOrganization(
                        timestamp=datetime.now(),
                        legislative_year=year,
                        type_org=type_org,
                        raw_html=html,
                        processed=False,
                        last_update=True,
                    )

                    final_lst.append(self.update_tracking(new_org))

        self.organizations_list = final_lst
        logger.success(
            f"Successfully extracted {len(self.organizations_list)} raw html organization"
        )

    def update_tracking(self, org: RawOrganization) -> RawOrganization:
        """Update the tracking columns of a RawOrganization object"""

        with self.Session() as session:
            last_org = (
                session.query(RawOrganization)
                .filter(
                    RawOrganization.type_org == org.type_org,
                    RawOrganization.legislative_year == org.legislative_year,
                    RawOrganization.last_update == True,
                )
                .order_by(RawOrganization.timestamp.desc())
                .first()
            )

            # First ever version of this org
            if last_org is None:
                org.changed = True
                org.last_update = True
                org.processed = False
            else:
                # Compare last vs new
                org.changed = org != last_org
                org.last_update = True
                org.processed = not org.changed

                # Update the old version AFTER comparison
                last_org.last_update = False
                session.add(last_org)
                session.commit()

            return org

    def add_organizations_to_db(self) -> bool:
        """
        Add the organizations to the database.
        Returns True on success, False on failure.
        """
        assert self.organizations_list, (
            "Organizations must be scraped before it can be saved"
        )

        session = self.Session()

        try:
            session.bulk_save_objects(self.organizations_list)
            session.commit()
            logger.success(
                f"Added {len(self.organizations_list)} organizations to Raw Organizations table"
            )
            return True
        except SQLAlchemyError as e:
            logger.error(f"Failed to add organizations: {e}")
            session.rollback()
            return False
        finally:
            # Close Session
            session.close()


if __name__ == "__main__":
    stop_logging_to_console(filename=directories.LOGS / "scrape_organizations.log")
    scraper = RawOrganizationScraper()
    scraper.get_raw_organizations(only_current=True)
    scraper.add_organizations_to_db()
    resume_logging_to_console()
