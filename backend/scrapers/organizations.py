from loguru import logger
from typing import Literal
from datetime import datetime

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

from backend.config import settings
from backend.database.raw_models import RawOrganization
from backend.scrapers.utils import parse_url


BASE_URLS = {
    "Junta de Portavoces": "https://www3.congreso.gob.pe/pagina/junta-de-portavoces",
    "Consejo Directivo": "https://www3.congreso.gob.pe/pagina/consejodirectivo",
    "Mesa Directiva": "https://www3.congreso.gob.pe/pagina/mesa-directiva",
    "Comisión Permanente": "https://www3.congreso.gob.pe/pagina/comision-permanente",
}

DB_PATH = settings.DB_URL


class RawOrganizationScraper:
    """
    Class to scrape Grupos Parlamentarios' raw data from the congress web page
    """

    def __init__(self):
        # Engine and session maker for DB
        self.engine = create_engine(DB_PATH)
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

    def get_html_with_selections(self, url: str, period_value: str) -> str | None:
        browser = None
        page = None

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)

                try:
                    page = browser.new_page()
                    page.goto(url, wait_until="domcontentloaded")

                    page.wait_for_selector(
                        'select[name="idRegistroPadre"]', state="attached"
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
                            "selector": 'select[name="idRegistroPadre"]',
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
                            "selector": 'select[name="idRegistroPadre"]',
                            "value": period_value,
                        },
                    )

                    page.wait_for_selector("table.congresistas", state="visible")
                    page.wait_for_timeout(1000)

                    return page.content()

                finally:
                    browser.close()

        except PlaywrightTimeoutError as e:
            logger.error(f"Error found: {e}")
            return None

    def get_raw_organizations(self, only_current: bool = True) -> None:
        final_lst = []
        for type_org, url in self.urls.items():
            dict_periods = self.get_options(url=url, select_name="idRegistroPadre")

            if not dict_periods:
                logger.warning(f"No years found for type={type_org}")
                continue

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
                        org_link=url,
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

    @staticmethod
    def _snapshot_changed(current: RawOrganization, previous: RawOrganization) -> bool:
        return (
            current.legislative_year != previous.legislative_year
            or current.type_org != previous.type_org
            or current.raw_html != previous.raw_html
        )

    def update_tracking(self, org: RawOrganization) -> RawOrganization:
        """Update the tracking columns of a RawOrganization object"""

        with self.Session() as session:
            last_org = (
                session.query(RawOrganization)
                .filter(
                    RawOrganization.type_org == org.type_org,
                    RawOrganization.legislative_year == org.legislative_year,
                    RawOrganization.last_update,
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
                org.changed = self._snapshot_changed(org, last_org)
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
