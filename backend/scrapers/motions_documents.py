import json
import base64
import boto3
from loguru import logger
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, select, Integer, cast, exists
from sqlalchemy.exc import SQLAlchemyError

from backend.config import settings, directories
from backend.scrapers.utils import get_url
from backend.database.raw_models import RawMotionDocument, RawMotion
from backend.database.models import MotionStep

BASE_URL = "https://api.congreso.gob.pe/smociones-portal-service"
DB_PATH = settings.DB_URL


class RawMotionDocumentScraper:
    """
    Class to scrape and store raw text extracted from motion's documents
    """

    def __init__(self):
        # Engine and session maker for DB
        self.engine = create_engine(DB_PATH, pool_pre_ping=True)
        self.Session = sessionmaker(bind=self.engine)

        self.documents: list[RawMotionDocument] = []

    def get_motions_pending_documents(self) -> list[str]:
        """
        Return motion IDs that have at least one step without a scraped document.

        A motion is considered pending when it has a record in `motion_steps` for a
        given step, but there is no matching record in `raw_motion_documents` for the
        same `motion_id` and `step_id`.

        Returns:
            list[str]: Distinct motion IDs with one or more missing raw documents.
        """
        with self.Session() as session:
            stmt = (
                select(RawMotion.id)
                .distinct()
                .where(
                    exists(
                        select(1).where(
                            MotionStep.motion_id == RawMotion.id,
                            ~exists(
                                select(1).where(
                                    RawMotionDocument.motion_id == MotionStep.motion_id,
                                    cast(RawMotionDocument.step_id, Integer)
                                    == MotionStep.step_id,
                                )
                            ),
                        )
                    )
                )
            )

            return list(session.scalars(stmt).all())

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

            steps_id = {int(step.step_id) for step in n_steps_in_db}

        return [
            step for step in extracted_steps if step["seguimientoId"] not in steps_id
        ]

    def get_motion_documents(
        self,
        motion_id: str,
        *,
        update: bool = False,
        download_local: bool = False,
        upload_s3: bool = False,
    ) -> None:
        """
        Extract the documents from a RawMotion's files and extract the text from each of its pages
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

        if len(steps) == 0:
            logger.info(f"No steps found for motion {motion_id}")
            return None

        logger.info(f"Extracting files from {len(steps)} steps of motion {motion_id}")

        for _, step in enumerate(steps):
            files = step.get("adjuntos")
            step_date = step.get("fecSeguimiento")

            if not files:
                continue

            for file in files:
                file_id = file["seguimientoAdjuntoId"]
                step_id = file["seguimientoId"]

                b64_id = base64.b64encode(str(file_id).encode()).decode()
                url = f"{BASE_URL}/seguimiento-adjunto/{b64_id}/pdf"

                file_name = self._build_filename(motion_id, step_id, file_id)
                dest_path = directories.MOTION_DOCUMENTS / file_name

                if download_local:
                    self._download_to_path(url, dest_path)

                s3_key = None
                if upload_s3:
                    s3_key = self._build_s3_key("motions", file_name)

                new_doc = RawMotionDocument(
                    motion_id=motion_id,
                    step_id=str(step_id),
                    file_id=str(file_id),
                    step_date=datetime.strptime(step_date, "%Y-%m-%dT%H:%M:%S.%f%z"),
                    url=url,
                    s3_key=s3_key,
                    local_path=str(dest_path) if dest_path is not None else None,
                    timestamp=datetime.now(),
                    processed=False,
                    last_update=True,
                )

                self.documents.append(new_doc)

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

    @staticmethod
    def _build_filename(motion_id: str, step_id: str, file_id: str) -> str:
        return f"{motion_id}-{step_id}-{file_id}.pdf"

    @staticmethod
    def _build_s3_key(kind: str, filename: str) -> str:
        parts = []
        if settings.AWS_S3_PREFIX:
            parts.append(settings.AWS_S3_PREFIX.strip("/"))
        parts.extend(["documents", kind, filename])
        return "/".join(parts)

    @staticmethod
    def _upload_file_to_s3(path: Path, key: str) -> None:
        bucket = settings.AWS_S3_BUCKET_NAME
        if not bucket:
            raise RuntimeError("AWS_S3_BUCKET_NAME is not configured.")

        if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
            session = boto3.session.Session(
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION,
            )
            client = session.client("s3")
        else:
            client = boto3.client("s3", region_name=settings.AWS_REGION)

        client.upload_file(path.as_posix(), bucket, key)

    @staticmethod
    def _download_to_path(url: str, dest: Path) -> bool:
        response = get_url(url)
        if response is None:
            logger.warning(f"Failed to fetch document: {url}")
            return False

        try:
            response.raise_for_status()
        except Exception as exc:
            logger.warning(f"Non-200 response fetching {url}: {exc}")
            return False

        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(response.content)
        return True
