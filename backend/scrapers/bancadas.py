from loguru import logger
from typing import Literal
from datetime import datetime

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

from backend.config import settings
from backend.database.raw_models import RawBancada
from backend.scrapers.utils import parse_url


BASE_URL = "https://www3.congreso.gob.pe/pagina/grupos-parlamentarios"
DB_PATH = settings.DB_URL


class RawBancadaScraper:
    """
    Class to scrape Grupos Parlamentarios' raw data from the congress web page
    """

    def __init__(self):
        # Engine and session maker for DB
        self.engine = create_engine(DB_PATH)
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

        if parse is None:
            return {}

        options = parse.xpath(f'//*[@name="{select_name}"]/option')
        return {
            elem.text: elem.get("value") for elem in options if elem.text is not None
        }

    def get_html_with_selections(
        self, url: str, period_value: str, condition_value: str = ""
    ) -> str | None:
        browser = None
        page = None

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)

                try:
                    page = browser.new_page()
                    page.goto(url, wait_until="domcontentloaded")

                    page.wait_for_selector(
                        'select[name="idPeriodo[]"]', state="attached"
                    )
                    page.wait_for_selector(
                        'select[name="keyCondicion[]"]', state="attached"
                    )

                    js_set_select = """
                    ({ selector, value }) => {
                        const sel = document.querySelector(selector);
                        if (!sel) {
                            return false;
                        }

                        for (const opt of sel.options) {
                            opt.selected = (opt.value === value);
                        }

                        sel.dispatchEvent(new Event("change", { bubbles: true }));
                        return Array.from(sel.selectedOptions).map(opt => opt.value);
                    }
                    """

                    page.evaluate(
                        js_set_select,
                        {
                            "selector": 'select[name="idPeriodo[]"]',
                            "value": period_value,
                        },
                    )
                    page.wait_for_function(
                        """
                        ({ selector, value }) => {
                            const sel = document.querySelector(selector);
                            return !!sel && Array.from(sel.selectedOptions).some(
                                opt => opt.value === value
                            );
                        }
                        """,
                        arg={
                            "selector": 'select[name="idPeriodo[]"]',
                            "value": period_value,
                        },
                    )

                    page.evaluate(
                        js_set_select,
                        {
                            "selector": 'select[name="keyCondicion[]"]',
                            "value": condition_value,
                        },
                    )
                    page.wait_for_function(
                        """
                        ({ selector, value }) => {
                            const sel = document.querySelector(selector);
                            return !!sel && Array.from(sel.selectedOptions).some(
                                opt => opt.value === value
                            );
                        }
                        """,
                        arg={
                            "selector": 'select[name="keyCondicion[]"]',
                            "value": condition_value,
                        },
                    )

                    page.wait_for_selector(".table-cng", state="visible")
                    page.wait_for_timeout(1000)

                    return page.content()

                finally:
                    browser.close()

        except PlaywrightTimeoutError as e:
            logger.error(f"Error found: {e}")
            return None

    def get_raw_bancadas(self, only_current: bool = True) -> None:
        dict_periods = self.get_options(url=self.url, select_name="idPeriodo[]")
        dict_condicion = {"en Ejercicio": "eej"}

        if only_current:
            # Only scrape current period
            key, val = list(dict_periods.items())[0]
            dict_periods = {key: val}

        final_lst = []
        for period_key, period in dict_periods.items():
            cond_key, cond = next(iter(dict_condicion.items()))
            logger.info(
                f"Scraping bancada for period {period_key} and condition {cond_key}"
            )

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
                .filter(
                    RawBancada.legislative_period == bancada.legislative_period,
                    RawBancada.last_update.is_(True),
                )
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
                bancada.changed = self._snapshot_changed(bancada, last_bancada)
                bancada.last_update = True
                bancada.processed = not bancada.changed

                # Update the old version AFTER comparison
                last_bancada.last_update = False
                session.add(last_bancada)
                session.commit()

            return bancada

    @staticmethod
    def _snapshot_changed(current: RawBancada, previous: RawBancada) -> bool:
        return (
            current.legislative_period != previous.legislative_period
            or current.raw_html != previous.raw_html
        )

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
