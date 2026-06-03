from loguru import logger
from datetime import datetime
from typing import Literal

from playwright.sync_api import (
    Page,
    sync_playwright,
    TimeoutError as PlaywrightTimeoutError,
)

from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

from backend.config import settings
from backend.database.raw_models import RawCommittee
from backend.scrapers.utils import parse_url

BASE_URL = "https://www3.congreso.gob.pe/pagina/comisiones-ordinarias"
DB_PATH = settings.DB_URL

YEAR_SELECT = 'select[name="idRegistroPadre"]'
COMMITTEE_SELECT = 'select[name="fld_78_Comision"]'
TABLE_SELECTOR = "table.congresistas"
ROWS_SELECTOR = "table.congresistas tbody tr:has(td)"
LINKS_SELECTOR = "table.congresistas a[href]"


class RawCommitteeScraper:
    """
    Class to scrape committee raw data from the congress web page
    """

    def __init__(self):
        # Engine and session maker for DB
        self.engine = create_engine(DB_PATH)
        self.url = BASE_URL
        self.Session = sessionmaker(bind=self.engine)

    def get_options(
        self,
        url: str,
        select_name: Literal["idRegistroPadre", "fld_78_Comision"] = "idRegistroPadre",
    ) -> dict[str, str]:
        parse = parse_url(url)
        if parse is None:
            logger.warning(f"Failed to fetch options page: {url}")
            return {}

        options = parse.xpath(f'//*[@name="{select_name}"]/option')
        return {
            (elem.text or "").strip(): elem.get("value")
            for elem in options
            if (elem.text or "").strip() and elem.get("value")
        }

    @staticmethod
    def _set_select(page: Page, selector: str, value: str) -> None:
        page.evaluate(
            """
            ({ selector, value }) => {
                const sel = document.querySelector(selector);
                if (!sel) {
                    return false;
                }

                for (const opt of sel.options) {
                    opt.selected = (opt.value === value);
                }

                sel.dispatchEvent(new Event("input", { bubbles: true }));
                sel.dispatchEvent(new Event("change", { bubbles: true }));

                return Array.from(sel.selectedOptions).map(opt => opt.value);
            }
            """,
            {"selector": selector, "value": value},
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
            arg={"selector": selector, "value": value},
        )

    @staticmethod
    def _get_committee_options_current_page(page: Page) -> dict[str, str]:
        page.wait_for_selector(COMMITTEE_SELECT, state="attached")

        page.wait_for_function(
            """
            ({ selector }) => {
                const sel = document.querySelector(selector);
                if (!sel) {
                    return false;
                }

                return Array.from(sel.options).some(
                    opt => opt.value && opt.textContent.trim()
                );
            }
            """,
            arg={"selector": COMMITTEE_SELECT},
        )

        return page.eval_on_selector(
            COMMITTEE_SELECT,
            """
            sel => Object.fromEntries(
                Array.from(sel.options)
                    .map(opt => [opt.textContent.trim(), opt.value])
                    .filter(([text, value]) => text && value)
            )
            """,
        )

    def _select_year(self, page: Page, year_value: str) -> None:
        page.wait_for_selector(YEAR_SELECT, state="attached")
        self._set_select(page, YEAR_SELECT, year_value)

        page.wait_for_selector(COMMITTEE_SELECT, state="attached")

    def get_html_with_selections(
        self,
        page: Page,
        year_value: str,
        committee_value: str,
    ) -> str | None:
        try:
            self._select_year(page, year_value)

            page.wait_for_selector(TABLE_SELECTOR, state="attached")

            before_table = page.locator(TABLE_SELECTOR).inner_html()

            self._set_select(page, COMMITTEE_SELECT, committee_value)

            try:
                page.wait_for_function(
                    """
                    ({ selector, before }) => {
                        const table = document.querySelector(selector);
                        return !!table && table.innerHTML !== before;
                    }
                    """,
                    arg={
                        "selector": TABLE_SELECTOR,
                        "before": before_table,
                    },
                    timeout=5000,
                )
            except PlaywrightTimeoutError:
                logger.warning(
                    f"Table content did not visibly change "
                    f"(year={year_value}, committee={committee_value})"
                )

            rows_count = page.locator(ROWS_SELECTOR).count()
            links_count = page.locator(LINKS_SELECTOR).count()

            if rows_count == 0 or links_count == 0:
                logger.warning(
                    f"No committees found for type={committee_value} and year={year_value}"
                )
                return None

            return page.content()

        except PlaywrightTimeoutError as e:
            logger.warning(
                f"Playwright timeout "
                f"(year={year_value}, committee={committee_value}): {e}"
            )
            return None

    def get_raw_committees(self, only_current: bool = True) -> None:
        dict_years = self.get_options(url=self.url, select_name="idRegistroPadre")
        if not dict_years:
            logger.error("No year options found. Aborting.")
            self.committee_list = []
            return

        if only_current:
            first = next(iter(dict_years.items()), None)
            dict_years = dict([first]) if first else {}

        final_lst: list[RawCommittee] = []

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)

                try:
                    page = browser.new_page()
                    page.goto(self.url, wait_until="domcontentloaded")

                    for year_label, year_value in dict_years.items():
                        logger.info(f"Scraping committees for year {year_label}")

                        self._select_year(page, year_value)

                        committees_for_year = self._get_committee_options_current_page(
                            page
                        )
                        if not committees_for_year:
                            logger.warning(
                                f"No committee options found for year {year_label}"
                            )
                            continue

                        for (
                            committee_label,
                            committee_value,
                        ) in committees_for_year.items():
                            logger.info(
                                f"Scraping committee year={year_label}, "
                                f"type={committee_label}"
                            )

                            html = self.get_html_with_selections(
                                page=page,
                                year_value=year_value,
                                committee_value=committee_value,
                            )
                            if html is None:
                                continue

                            new_committee = RawCommittee(
                                timestamp=datetime.now(),
                                legislative_year=year_label,
                                committee_type=committee_label,
                                raw_html=html,
                                changed=False,
                                processed=False,
                                last_update=True,
                            )
                            final_lst.append(self.update_tracking(new_committee))

                finally:
                    browser.close()

        except PlaywrightTimeoutError as e:
            logger.error(f"Playwright error while scraping committees: {e}")

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
                    RawCommittee.last_update,
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
