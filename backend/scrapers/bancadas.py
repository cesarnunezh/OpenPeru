import os
from loguru import logger
from typing import Literal
from itertools import product
from datetime import datetime

from lxml.html import HtmlElement
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service

from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

from backend.config import settings
from backend.database.raw_models import RawBancada
from backend.scrapers.utils import parse_url


BASE_URL = "https://www3.congreso.gob.pe/pagina/grupos-parlamentarios"
RAW_DB_PATH = settings.RAW_DB_URL


class RawBancadaScraper:
    """
    Class to scrape Grupos Parlamentarios' raw data from the congress web page
    """

    def __init__(self):
        # Engine and session maker for DB
        self.engine = create_engine(RAW_DB_PATH)
        self.url = BASE_URL
        self.Session = sessionmaker(bind=self.engine)

    def get_options(
        self,
        url: str,
        select_name: Literal["idPeriodo[]", "keyCondicion[]"] = "idPeriodo[]",
    ) -> dict[str, str]:
        """
        Functions that fetchs all the possible options that are in the dropdown list in the html file

        Args:
            - url (str): link to the html
            - select_name (str): the name of the dropdown element
        """
        parse = parse_url(url)
        options = parse.xpath(f'//*[@name="{select_name}"]/option')
        return {
            elem.text: elem.get("value") for elem in options if elem.text is not None
        }

    def get_html_with_selections(
        self, url: str, period_value: str, condition_value: str = ""
    ) -> HtmlElement | None:
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--log-level=3")
        options.add_experimental_option("excludeSwitches", ["enable-logging"])

        service = Service(log_path=os.devnull)

        driver = webdriver.Chrome(service=service, options=options)
        driver.get(url)

        wait = WebDriverWait(driver, 15)

        try:
            # Esperar a que existan los <select> ocultos
            wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, 'select[name="idPeriodo[]"]')
                )
            )
            wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, 'select[name="keyCondicion[]"]')
                )
            )

            # Helper JS para seleccionar opción en un <select multiple hidden>
            js_set_select = """
            const selector = arguments[0];
            const value = arguments[1];
            const sel = document.querySelector(selector);
            if (!sel) { return false; }

            for (const opt of sel.options) {
                opt.selected = (opt.value === value);
            }

            // Disparar change para que el plugin/servidor reaccionen
            const event = new Event('change', { bubbles: true });
            sel.dispatchEvent(event);
            return true;
            """

            # 1) Seleccionar periodo (idPeriodo[])
            driver.execute_script(
                js_set_select, 'select[name="idPeriodo[]"]', period_value
            )

            # Pequeña espera para que se actualice el filtro, por si hace algo server-side
            wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "button.ui-multiselect")
                )
            )

            # 2) Seleccionar condición (keyCondicion[])
            #   Para "Todas", condition_value debe ser "" (value="")
            driver.execute_script(
                js_set_select, 'select[name="keyCondicion[]"]', condition_value
            )

            # 3) Esperar a que la tabla de resultados esté presente
            #   (ajusta el selector si hace falta)
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".table-cng")))

            html = driver.page_source
            return html

        except NoSuchElementException as e:
            logger.error(f"Error found: {e}")
            driver.quit()
            return None

    def get_raw_bancadas(self, only_current: bool = True) -> None:
        dict_periods = self.get_options(url=self.url, select_name="idPeriodo[]")

        if only_current:
            dict_condicion = {"en Ejercicio": "eej"}
            
            # Only scrape current period
            key, val = list(dict_periods.items())[0]
            dict_periods = {key: val}
        else:
            dict_periods = self.get_options(url=self.url, select_name="idPeriodo[]")
            dict_condicion = self.get_options(
                url=self.url, select_name="keyCondicion[]"
            )

        final_lst = []
        for period_key, cond_key in product(dict_periods.keys(), dict_condicion.keys()):
            logger.info(
                f"Scraping bancada for period {period_key} and condition {cond_key}"
            )

            period = dict_periods.get(period_key)
            cond = dict_condicion.get(cond_key)

            html = self.get_html_with_selections(self.url, period, cond)

            if html is not None:
                new_bancada = RawBancada(
                    timestamp=datetime.now(),
                    legislative_period=period_key,
                    raw_html=html,
                    changed=False,
                    processed=False,
                    last_update=True,
                )
                final_lst.append(self.update_tracking(new_bancada))

        self.bancadas_list = final_lst
        logger.success(
            f"Successfully extracted {len(self.bancadas_list)} raw html bancadas"
        )

    def update_tracking(self, bancada: RawBancada) -> RawBancada:
        """Update the tracking columns of a RawBancada object"""

        with self.Session() as session:
            last_bancada = (
                session.query(RawBancada)
                .filter(RawBancada.id == bancada.id)
                .order_by(RawBancada.timestamp.desc())
                .first()
            )

            # First ever version of this bancada
            if last_bancada is None:
                bancada.changed = True
                bancada.last_update = True
                bancada.processed = False
            else:
                # Compare last vs new
                bancada.changed = bancada != last_bancada
                bancada.last_update = True
                bancada.processed = not bancada.changed

                # Update the old version AFTER comparison
                last_bancada.last_update = False
                session.add(last_bancada)
                session.commit()

            return bancada

    def add_bancadas_to_db(self) -> bool:
        """
        Add the bancadas to the database.
        Returns True on success, False on failure.
        """
        assert self.bancadas_list, "Bancadas must be scraped before it can be saved"

        session = self.Session()

        try:
            session.bulk_save_objects(self.bancadas_list)
            session.commit()
            logger.success(
                f"Added {len(self.bancadas_list)} bancadas to Raw Bancadas table"
            )
            return True
        except SQLAlchemyError as e:
            logger.error(f"Failed to add bancadas: {e}")
            session.rollback()
            return False
        finally:
            # Close Session
            session.close()


if __name__ == "__main__":
    scraper = RawBancadaScraper()
    scraper.get_raw_bancadas(only_current=False)
    scraper.add_bancadas_to_db()
