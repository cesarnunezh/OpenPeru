import json
import time
from datetime import datetime, timedelta
from loguru import logger
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

from backend.config import settings
from backend.database.raw_models import RawBill

BASE_URL = "https://wb2server.congreso.gob.pe/spley-portal/#"
RAW_DB_PATH = settings.RAW_DB_URL


def get_url_text(url: str, data: str | None = None) -> str | None:
    from backend.scrapers.utils import get_url_text as _get_url_text

    return _get_url_text(url, data)


class RawBillScraper:
    """
    Class to scrape and store raw bill information
    """

    def __init__(self, session=None, engine=None):
        # Engine and session maker for DB
        if session is not None:
            self.session = session
            self.engine = session.get_bind()
            self.Session = sessionmaker(bind=self.engine)  # safe default
        else:
            self.engine = engine or create_engine(RAW_DB_PATH)
            self.Session = sessionmaker(bind=self.engine)
            self.session = None

        # Mapping raw section name to RawBill attribute name
        self.section_mapping = {
            "general": "general",
            "firmantes": "congresistas",
            "comisiones": "committees",
            "seguimientos": "steps",
        }

        # List of raw bills objects
        self.raw_bills = []

    def __search_api_url(self, bill_url: str) -> str:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            try:
                page.goto("https://wb2server.congreso.gob.pe/spley-portal/", wait_until="domcontentloaded")

                with page.expect_response(
                    lambda r: (
                        "spley-portal-service/expediente/" in r.url
                        and r.request.method == "GET"
                        and r.status == 200
                    ),
                    timeout=10000,
                ) as response_info:
                    page.evaluate("url => { window.location.href = url; }", bill_url)

                return response_info.value.url

            except PlaywrightTimeoutError:
                return None

            finally:
                browser.close()

    def scrape_bill(self, year: str, bill_number: str) -> None:
        """
        Scrape key sections: general, congresistas, committees, steps

        Returns tuple with result of scrape, error message if relevant
        """

        bill_url = f"{BASE_URL}/expediente/{year}/{bill_number}"
        api_url = self.__search_api_url(bill_url)
        response = get_url_text(api_url)

        if response:
            resp = json.loads(response)

            # Successfully built the raw bill!
            bill = self.create_raw_bill(year, bill_number, resp["data"])
            self.raw_bills.append(self.update_tracking(bill))
            logger.success(f"Successfully scraped Raw Bill {year}_{bill_number}")

        else:
            return None

    def create_raw_bill(self, year: str, bill_number: str, data: dict) -> RawBill:
        # Initialize raw bill with id and timestamp
        raw_bill = RawBill(
            id=f"{year}_{bill_number}", timestamp=datetime.now(), processed=False
        )

        # Add sections
        for raw_name, attribute_name in self.section_mapping.items():
            # Grab expected section, use English value to signal no section
            # (since sections can be empty lists themselves)
            attribute_value = data.get(raw_name, "Not Found")
            if attribute_value == "Not Found":
                logger.warning(
                    f"{raw_bill.id} - Missing Attribute: {raw_name} ({attribute_name})"
                )
            else:
                setattr(raw_bill, attribute_name, json.dumps(attribute_value))

        return raw_bill

    def update_tracking(self, bill: RawBill) -> RawBill:
        """Update the tracking columns of a RawBill object"""

        # Create a new session
        session = self.session or self.Session()
        try:
            last_bill = (
                session.query(RawBill)
                .filter(RawBill.id == bill.id)
                .order_by(RawBill.timestamp.desc())
                .first()
            )

            # First ever version of this bill
            if last_bill is None:
                bill.changed = True
                bill.last_update = True
                bill.processed = False
            else:
                # Compare last vs new
                bill.changed = bill != last_bill
                bill.last_update = True
                bill.processed = not bill.changed

                # Update the old version AFTER comparison
                last_bill.last_update = False
                session.add(last_bill)
                session.commit()

            return bill
        except SQLAlchemyError as e:
            logger.error(f"Failed to add update tracking to Raw Bills table: {e}")
            session.rollback()
            return False

        finally:
            # Close Session
            if self.session is None:
                session.close()

    def add_bills_to_db(self) -> bool:
        """
        Add a single bill to the database.
        Returns True on success, False on failure.
        """
        assert len(self.raw_bills) != 0, (
            "There are no Raw Bills scraped. Nothing to load to DB."
        )

        # Create a new session
        session = self.session or self.Session()
        try:
            # Add and commit raw bill
            session.bulk_save_objects(self.raw_bills)
            session.commit()
            logger.success(f"Added {len(self.raw_bills)} Raw Bills to table.")
            return True

        except SQLAlchemyError as e:
            logger.error(f"Failed to add bills to Raw Bills table: {e}")
            session.rollback()
            return False

        finally:
            # Close Session
            if self.session is None:
                session.close()

    def load_raw_bills(self):
        self.add_bills_to_db()
        self.raw_bills = []

    @staticmethod
    def _is_approved_from_general(general_raw: str | None) -> bool:
        if not general_raw:
            return False

        try:
            general = json.loads(general_raw)
        except (TypeError, json.JSONDecodeError):
            return False

        status = (general.get("desEstado") or "").strip().lower()
        return status == "publicada en el diario oficial el peruano"

    def get_ids_pending_weekly_refresh(self, max_age_days: int = 7) -> list[str]:
        """
        Return ids that should be refreshed this week:
          - latest snapshot is older than `max_age_days`
          - latest snapshot is not approved
        """
        cutoff = datetime.now() - timedelta(days=max_age_days)
        session = self.session or self.Session()

        try:
            latest_rows = (
                session.query(RawBill).filter(RawBill.last_update == True).all()
            )
            pending_ids: list[str] = []

            for row in latest_rows:
                if row.timestamp > cutoff:
                    continue
                if self._is_approved_from_general(row.general):
                    continue
                pending_ids.append(row.id)

            return pending_ids
        finally:
            if self.session is None:
                session.close()

    def scrape_pending_weekly(
        self, max_age_days: int = 7, flush_every: int = 100
    ) -> list[str]:
        """
        Re-scrape pending, non-approved bill ids that are stale.
        """
        pending_ids = self.get_ids_pending_weekly_refresh(max_age_days=max_age_days)

        for idx, bill_id in enumerate(pending_ids, start=1):
            year, number = bill_id.split("_", 1)
            self.scrape_bill(year, number)

            if len(self.raw_bills) >= flush_every:
                self.load_raw_bills()

            if idx % 10 == 0:
                time.sleep(2)

        if self.raw_bills:
            self.load_raw_bills()

        logger.info(f"Weekly bill refresh processed {len(pending_ids)} ids")
        return pending_ids


def main():
    scraper = RawBillScraper()
    scraper.scrape_pending_weekly(max_age_days=7, flush_every=100)


if __name__ == "__main__":
    main()
