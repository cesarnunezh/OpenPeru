import json
import base64
import time
from loguru import logger
from datetime import datetime

from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, tuple_, select

from sqlalchemy.exc import SQLAlchemyError

from backend.config import settings, directories, stop_logging_to_console
from backend.scrapers.utils import render_pdf
from backend.database.raw_models import RawBillDocument, RawBill

BASE_URL = "https://wb2server.congreso.gob.pe/spley-portal-service/"
RAW_DB_PATH = settings.RAW_DB_URL
PRIORITIES = set(
    [
        "Publicada en el Diario Oficial El Peruano",
        "AUT\u00d3GRAFA",
        "APROBADO",
        "EN DEBATE - PLENO",
        "APROBADO 1ERA. VOTACI\u00d3N",
    ]
)


class RawBillDocumentScraper:
    """
    Class to scrape and store raw text extracted from bill's documents
    """

    def __init__(self):
        # Engine and session maker for DB
        self.engine = create_engine(RAW_DB_PATH)
        self.Session = sessionmaker(bind=self.engine)

        self.documents = []

    def get_bills_pending_documents(self) -> list[str]:
        with self.Session() as session:
            stmt = (
                select(RawBill.id)
                .outerjoin(RawBillDocument, RawBill.id == RawBillDocument.bill_id)
                .where(RawBillDocument.bill_id.is_(None))
            )

            return session.scalars(stmt).all()

    def filter_steps(self, extracted_steps: list[dict], bill_id: str):
        """
        Filter steps that are already loaded in the DB
        """
        with self.Session() as session:
            n_steps_in_db = (
                session.query(RawBillDocument)
                .filter(RawBillDocument.bill_id == bill_id)
                .all()
            )

            seguimiento_ids = {int(step.seguimiento_id) for step in n_steps_in_db}

        return [
            step
            for step in extracted_steps
            if step["seguimientoPleyId"] not in seguimiento_ids
        ]

    def get_bill_documents(
        self, bill_id: str, update: bool = False, prioritize: bool = True
    ) -> list[RawBillDocument]:
        """
        Extract the urls from a RawBill's files and extract the text from each of them
        """
        with self.Session() as session:
            bill = (
                session.query(RawBill)
                .filter(RawBill.id == bill_id)
                .order_by(RawBill.timestamp.desc())
                .first()
            )

            assert bill is not None, f"Bill with id {bill_id} has not been scraped yet"

            steps: list[dict] = json.loads(bill.steps)

        if not update:
            steps = self.filter_steps(steps, bill_id)

        if prioritize:
            logger.info(f"Total number of steps: {len(steps)}")
            steps = [step for step in steps if step.get("desEstado") in PRIORITIES]

        if len(steps) == 0:
            logger.info(f"No steps found for bill {bill_id}")
            return None

        logger.info(f"Extracting files from {len(steps)} steps of bill {bill_id}")

        for ix, step in enumerate(steps):
            files = step.get("archivos")
            step_date = step.get("fecha")

            if not files:
                continue

            for file in files:
                file_id = file["proyectoArchivoId"]
                seguimiento_id = file["seguimientoPleyId"]

                b64_id = base64.b64encode(str(file_id).encode()).decode()
                url = f"{BASE_URL}/archivo/{b64_id}/pdf"
                logger.info(f"Extracting document {ix + 1}/{len(steps)} at url: {url}")
                extracted_text = render_pdf(url)
                logger.success(f"Successfully extracted text from {url}")

                new_doc = RawBillDocument(
                    timestamp=datetime.now(),
                    bill_id=bill_id,
                    step_date=datetime.strptime(step_date, "%Y-%m-%dT%H:%M:%S.%f%z"),
                    seguimiento_id=seguimiento_id,
                    archivo_id=file_id,
                    url=url,
                    text=extracted_text,
                    processed=False,
                    last_update=True,
                )
                self.documents.append(new_doc)

    def _track_documents(self, session, documents: list[RawBillDocument]) -> None:
        """
        For each new doc:
          - mark it as last_update=True
          - set changed based on comparison with latest existing doc for same natural key
          - set previous latest doc's last_update=False
        Runs in one DB session, no commits here (caller commits).
        """

        if not documents:
            return None

        # Natural key for "same document across versions"
        def key(d: RawBillDocument):
            return (d.bill_id, d.archivo_id, d.seguimiento_id)

        keys = list({(d.bill_id, d.archivo_id, d.seguimiento_id) for d in documents})

        # Fetch current latest versions (we assume last_update=True means latest)
        existing_latest = (
            session.query(RawBillDocument)
            .filter(
                RawBillDocument.last_update.is_(True),
                tuple_(
                    RawBillDocument.bill_id,
                    RawBillDocument.archivo_id,
                    RawBillDocument.seguimiento_id,
                ).in_(keys),
            )
            .all()
        )

        latest_by_key = {key(d): d for d in existing_latest}

        # Define what "changed" means (avoid relying on __eq__/__ne__)
        def is_changed(new: RawBillDocument, old: RawBillDocument) -> bool:
            return (
                new.url != old.url
                or new.step_date != old.step_date
                or new.text != old.text
            )

        for new_doc in documents:
            new_doc.last_update = True
            prev = latest_by_key.get(key(new_doc))

            if prev is None:
                new_doc.changed = True
                new_doc.processed = False
            else:
                new_doc.changed = is_changed(new_doc, prev)
                new_doc.processed = not new_doc.changed
                prev.last_update = False
                session.add(prev)  # stage update of old latest

    def add_documents_to_db(self) -> bool:
        """
        Add the documents to the database.
        Returns True on success, False on failure.
        """

        assert self.documents, "Documents must be scraped before it can be saved"

        with self.Session() as session:
            try:
                # tracking + mark previous last_update=False in same transaction
                self._track_documents(session, self.documents)

                # Use add_all (safer than bulk_save_objects when you update other rows too)
                session.add_all(self.documents)

                session.commit()
                logger.success(
                    f"Added {len(self.documents)} documents to Raw Bill Documents table"
                )
                return True

            except SQLAlchemyError as e:
                logger.error(
                    f"Failed to add documents from bill {self.documents[0].bill_id}: {e}"
                )
                session.rollback()
                return False

    def load_raw_documents(self):
        if self.documents:
            self.add_documents_to_db()
            self.documents = []
        else:
            return None


if __name__ == "__main__":
    logger.info("Starting Scraper")
    scraper = RawBillDocumentScraper()

    pending_bills = scraper.get_bills_pending_documents()

    # bill = 5779
    # year = 2021

    stop_logging_to_console(filename=directories.LOGS / "scrape_bills_documents.log")
    for bill in pending_bills:
        try:
            scraper.get_bill_documents(bill_id=bill, update=False, prioritize=True)
            scraper.load_raw_documents()
        except TypeError as e:
            print(e)
            break
        except AttributeError as e:
            print(e)
            time.sleep(3)
            continue
        time.sleep(3)
