import os
import time
from loguru import logger
from datetime import datetime
from typing import Literal

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

from backend.config import settings
from backend.database.raw_models import RawCommittee
from backend.scrapers.utils import parse_url

BASE_URL = "https://www3.congreso.gob.pe/pagina/comisiones-ordinarias"
RAW_DB_PATH = settings.RAW_DB_URL


class RawCommitteeScraper:
    """
    Class to scrape committee raw data from the congress web page
    """

    def __init__(self):
        # Engine and session maker for DB
        self.engine = create_engine(RAW_DB_PATH)
        self.url = BASE_URL
        self.Session = sessionmaker(bind=self.engine)

    def _select_year(
        self, driver: webdriver.Chrome, wait: WebDriverWait, year_value: str
    ) -> None:
        wait.until(EC.presence_of_element_located((By.NAME, "idRegistroPadre")))
        Select(driver.find_element(By.NAME, "idRegistroPadre")).select_by_value(
            year_value
        )
        wait.until(
            lambda d: (
                Select(
                    d.find_element(By.NAME, "idRegistroPadre")
                ).first_selected_option.get_attribute("value")
                == year_value
            )
        )

    def _get_committee_options_current_page(
        self, driver: webdriver.Chrome, wait: WebDriverWait
    ) -> dict[str, str]:
        wait.until(EC.presence_of_element_located((By.NAME, "fld_78_Comision")))
        opts = driver.find_elements(
            By.CSS_SELECTOR, 'select[name="fld_78_Comision"] option'
        )

        out: dict[str, str] = {}
        for opt in opts:
            txt = (opt.text or "").strip()
            val = opt.get_attribute("value")
            if txt and val:
                out[txt] = val
        return out

    def get_options(
        self,
        url: str,
        select_name: Literal["idRegistroPadre", "fld_78_Comision"] = "idRegistroPadre",
    ) -> dict[str, str]:
        """
        Functions that fetchs all the possible options that are in the dropdown list in the html file

        Args:
            - url (str): link to the html
            - select_name (str): the name of the dropdown element
        """
        parse = parse_url(url)
        if parse is None:
            logger.warning(f"Failed to fetch options page: {url}")
            return {}
        years = parse.xpath(f'//*[@name="{select_name}"]/option')
        return {
            (elem.text or "").strip(): elem.get("value")
            for elem in years
            if (elem.text or "").strip() and elem.get("value")
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

    def get_html_with_selections(
        self,
        driver: webdriver.Chrome,
        wait: WebDriverWait,
        year_value: str,
        committee_value: str,
    ) -> str | None:
        try:
            self._select_year(driver, wait, year_value)

            # capture something that should change after committee selection (best-effort)
            before = driver.page_source

            wait.until(EC.presence_of_element_located((By.NAME, "fld_78_Comision")))
            Select(driver.find_element(By.NAME, "fld_78_Comision")).select_by_value(
                committee_value
            )

            wait.until(
                lambda d: (
                    Select(
                        d.find_element(By.NAME, "fld_78_Comision")
                    ).first_selected_option.get_attribute("value")
                    == committee_value
                )
            )

            # best-effort: wait for page_source to change
            wait.until(lambda d: d.page_source != before)

            return driver.page_source

        except TimeoutException as e:
            logger.warning(
                f"Selenium timeout (year={year_value}, committee={committee_value}): {e}"
            )
            return None
        except NoSuchElementException as e:
            logger.error(
                f"Element not found (year={year_value}, committee={committee_value}): {e}"
            )
            return None
        except WebDriverException as e:
            logger.error(
                f"WebDriver error (year={year_value}, committee={committee_value}): {e}"
            )
            return None

    def get_raw_committees(self, only_current: bool = False) -> None:
        dict_years = self.get_options(url=self.url, select_name="idRegistroPadre")
        if not dict_years:
            logger.error("No year options found. Aborting.")
            self.committee_list = []
            return

        if only_current:
            first = next(iter(dict_years.items()), None)
            dict_years = dict([first]) if first else {}

        final_lst: list[RawCommittee] = []

        for year_label, year_value in dict_years.items():
            logger.info(f"Scraping committees for year {year_label}")

            driver = self._build_driver()
            try:
                self._safe_get(driver, self.url)
                wait = WebDriverWait(driver, 25)

                # select year once
                self._select_year(driver, wait, year_value)

                # committee options depend on year, so read them now
                committees_for_year = self._get_committee_options_current_page(
                    driver, wait
                )
                if not committees_for_year:
                    logger.warning(f"No committee options found for year {year_label}")
                    continue

                for committee_label, committee_value in committees_for_year.items():
                    logger.info(
                        f"Scraping committee year={year_label}, type={committee_label}"
                    )

                    html = self.get_html_with_selections(
                        driver=driver,
                        wait=wait,
                        year_value=year_value,
                        committee_value=committee_value,
                    )
                    if html is None:
                        continue

                    new_committee = RawCommittee(
                        timestamp=datetime.now(),
                        legislative_year=int(year_label),
                        committee_type=committee_label,
                        raw_html=html,
                        processed=False,
                        last_update=True,
                    )
                    final_lst.append(self.update_tracking(new_committee))

            finally:
                try:
                    driver.quit()
                except Exception:
                    pass

        self.committee_list = final_lst
        logger.success(
            f"Successfully extracted {len(self.committee_list)} raw html committees"
        )

    def update_tracking(self, committee: RawCommittee) -> RawCommittee:
        """Update the tracking columns of a RawCommittee object"""

        with self.Session() as session:
            last_committee = (
                session.query(RawCommittee)
                .filter(
                    RawCommittee.legislative_year == committee.legislative_year,
                    RawCommittee.committee_type == committee.committee_type,
                    RawCommittee.last_update == True,
                )
                .order_by(RawCommittee.timestamp.desc())
                .first()
            )

            # First ever version of this committee
            if last_committee is None:
                committee.changed = True
                committee.last_update = True
                committee.processed = False
            else:
                # Compare last vs new
                committee.changed = committee != last_committee
                committee.last_update = True
                committee.processed = not committee.changed

                # Update the old version AFTER comparison
                last_committee.last_update = False
                session.add(last_committee)
                session.commit()

            return committee

    def add_committees_to_db(self) -> bool:
        """
        Add the committees to the database.
        Returns True on success, False on failure.
        """
        assert self.committee_list, "Committees must be scraped before it can be saved"

        session = self.Session()

        try:
            session.bulk_save_objects(self.committee_list)
            session.commit()
            logger.success(
                f"Added {len(self.committee_list)} committees to Raw Committees table"
            )
            return True
        except SQLAlchemyError as e:
            logger.error(f"Failed to add committees: {e}")
            session.rollback()
            return False
        finally:
            # Close Session
            session.close()


if __name__ == "__main__":
    scraper = RawCommitteeScraper()
    scraper.get_raw_committees()
    scraper.add_committees_to_db()
