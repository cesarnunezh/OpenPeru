import json
from datetime import datetime
from loguru import logger
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, select
from sqlalchemy.exc import SQLAlchemyError

from backend.config import settings
from backend.database.raw_models import RawBill
from backend.scrapers.utils import get_url_text

BASE_URL = "https://wb2server.congreso.gob.pe/spley-portal/#"
DB_PATH = settings.DB_URL


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
            self.engine = engine or create_engine(DB_PATH)
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

    def __get_existing_api_url(self, bill_id: str) -> str | None:
        with self.Session() as db:
            return db.scalar(
                select(RawBill.api_url)
                .where(
                    RawBill.id == bill_id,
                    RawBill.last_update.is_(True),
                    RawBill.api_url.is_not(None),
                )
                .limit(1)
            )

    def __search_api_url(self, bill_url: str) -> str:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            try:
                page.goto(
                    "https://wb2server.congreso.gob.pe/spley-portal/",
                    wait_until="domcontentloaded",
                )

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
        bill_id = f"{year}_{bill_number}"

        api_url = self.__get_existing_api_url(bill_id)

        if not api_url:
            api_url = self.__search_api_url(bill_url)

        if not api_url:
            logger.warning(f"No API URL found for Raw Bill {bill_id}")
            return

        response = get_url_text(api_url)

        if not response:
            logger.warning(f"No response found for Raw Bill {bill_id}")
            return

        try:
            resp = json.loads(response)
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON response for Raw Bill {bill_id}")
            return

        bill = self.create_raw_bill(year, bill_number, resp["data"], api_url)

        tracking_result = self.update_tracking(bill)

        if isinstance(tracking_result, list):
            self.raw_bills.extend(tracking_result)
        else:
            self.raw_bills.append(tracking_result)

        logger.success(f"Successfully scraped Raw Bill {bill_id}")

    def create_raw_bill(
        self, year: str, bill_number: str, data: dict, api_url: str
    ) -> RawBill:
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

        raw_bill.api_url = api_url
        return raw_bill

    def update_tracking(self, bill: RawBill) -> list[RawBill]:
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

            # First ever version of this: add tracking columns and return bill
            if last_bill is None:
                bill.changed = True
                bill.last_update = True
                bill.processed = False

                return [bill]

            # If has changed: add tracking columns properly and return bill and last bill
            if bill != last_bill:
                bill.changed = True
                bill.last_update = True
                bill.processed = False
                last_bill.last_update = False

                return [bill, last_bill]

            # No changes
            return []

        except SQLAlchemyError as e:
            logger.error(f"Failed to add update tracking to Raw Bills table: {e}")
            session.rollback()
            return []

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
