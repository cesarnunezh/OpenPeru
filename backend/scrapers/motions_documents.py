import json
import base64
import time
from loguru import logger
from datetime import datetime

from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, select
from sqlalchemy.exc import SQLAlchemyError


from backend.config import settings, directories, stop_logging_to_console
from backend.scrapers.utils import render_pdf
from backend.database.raw_models import RawMotionDocument, RawMotion

BASE_URL = "https://api.congreso.gob.pe/smociones-portal-service"
RAW_DB_PATH = settings.RAW_DB_URL
PRIORITIES = set(
    [
        "Aprobada",
        "Aprobada la Moción",
        "Aprobado Proyecto de Resolución",
        "Publicado Diario Oficial El Peruano",
        "Rechazada",
    ]
)


class RawMotionDocumentScraper:
    """
    Class to scrape and store raw text extracted from motion's documents
    """

    def __init__(self):
        # Engine and session maker for DB
        self.engine = create_engine(RAW_DB_PATH, pool_pre_ping=True)
        self.Session = sessionmaker(bind=self.engine)

        self.documents = []

    def get_motions_pending_documents(self) -> list[str]:
        with self.Session() as session:
            stmt = (
                select(RawMotion.id)
                .outerjoin(
                    RawMotionDocument, RawMotion.id == RawMotionDocument.motion_id
                )
                .where(RawMotionDocument.motion_id.is_(None))
            )

            return session.scalars(stmt).all()

    def filter_steps(self, extracted_steps: list[dict], motion_id: str):
        """
        Filter steps that are already loaded in the DB
        """
        with self.Session() as session:
            n_steps_in_db = (
                session.query(RawMotionDocument)
                .filter(RawMotionDocument.motion_id == motion_id)
                .all()
            )

            seguimiento_ids = {int(step.seguimiento_id) for step in n_steps_in_db}

        filtered_steps = [
            step
            for step in extracted_steps
            if step["seguimientoId"] not in seguimiento_ids
        ]
        return filtered_steps

    def get_motion_documents(
        self, motion_id: str, update: bool = False, prioritize: bool = True
    ) -> list[RawMotionDocument]:
        """
        Extract the documents from a RawMotion's files and extract the text from each of them
        """

        with self.Session() as session:
            motion = (
                session.query(RawMotion)
                .filter(RawMotion.id == motion_id)
                .order_by(RawMotion.timestamp.desc())
                .first()
            )

            assert motion is not None, (
                f"Moition with id {motion_id} has not been scraped yet"
            )

            steps: list[dict] = json.loads(motion.steps)

        if not update:
            steps = self.filter_steps(steps, motion_id)

        if prioritize:
            logger.info(f"Total number of steps: {len(steps)}")
            steps = [
                step for step in steps if step.get("desEstadoMocion") in PRIORITIES
            ]

        if len(steps) == 0:
            logger.info(f"No steps found for motion {motion_id}")
            return None

        logger.info(f"Extracting files from {len(steps)} steps of motion {motion_id}")

        for ix, step in enumerate(steps):
            files = step.get("adjuntos")
            step_date = step.get("fecSeguimiento")

            if not files:
                continue

            for file in files:
                file_id = file["seguimientoAdjuntoId"]
                seguimiento_id = file["seguimientoId"]
                b64_id = base64.b64encode(str(file_id).encode()).decode()
                url = f"{BASE_URL}/seguimiento-adjunto/{b64_id}/pdf"

                logger.info(f"Extracting document {ix + 1}/{len(steps)} at url: {url}")
                extracted_text = render_pdf(url)
                logger.success(f"Successfully extracted text from {url}")

                new_doc = RawMotionDocument(
                    timestamp=datetime.now(),
                    motion_id=motion_id,
                    step_date=datetime.strptime(step_date, "%Y-%m-%dT%H:%M:%S.%f%z"),
                    seguimiento_id=seguimiento_id,
                    archivo_id=file_id,
                    url=url,
                    text=extracted_text,
                    processed=False,
                    last_update=True,
                )
                self.documents.append(self.update_tracking(new_doc))

    def update_tracking(self, document: RawMotionDocument) -> RawMotionDocument:
        """Update the tracking columns of a RawMotionDocument object"""

        with self.Session() as session:
            last_document = (
                session.query(RawMotionDocument)
                .filter(
                    RawMotionDocument.motion_id == document.motion_id,
                    RawMotionDocument.seguimiento_id == document.seguimiento_id,
                    RawMotionDocument.archivo_id == document.archivo_id,
                )
                .order_by(RawMotionDocument.timestamp.desc())
                .first()
            )

            # First ever version of this document
            if last_document is None:
                document.changed = True
                document.last_update = True
                document.processed = False
            else:
                # Compare last vs new
                document.changed = document != last_document
                document.last_update = True
                document.processed = not document.changed

                # Update the old version AFTER comparison
                last_document.last_update = False
                session.add(last_document)
                session.commit()

            return document

    def add_documents_to_db(self) -> bool:
        """
        Add the documents to the database.
        Returns True on success, False on failure.
        """

        assert self.documents, "Documents must be scraped before it can be saved"

        session = self.Session()

        try:
            session.bulk_save_objects(self.documents)
            session.commit()
            logger.success(
                f"Added {len(self.documents)} documents to Raw Motion Documents table"
            )
            return True
        except SQLAlchemyError as e:
            logger.error(
                f"Failed to add documents from motion {self.documents[0].motion_id}: {e}"
            )
            session.rollback()
            return False
        finally:
            # Close Session
            session.close()

    def load_raw_documents(self):
        if self.documents:
            self.add_documents_to_db()
            self.documents = []
        else:
            return None


if __name__ == "__main__":
    logger.info("Starting Scraper")
    scraper = RawMotionDocumentScraper()

    pending_motions = scraper.get_motions_pending_documents()

    stop_logging_to_console(filename=directories.LOGS / "scrape_motions_documents.log")

    for motion in pending_motions:
        try:
            scraper.get_motion_documents(
                motion_id=motion, update=False, prioritize=True
            )
            scraper.load_raw_documents()
        except TypeError as e:
            print(e)
            break
        except AttributeError as e:
            print(e)
            time.sleep(3)
            continue
        time.sleep(3)
