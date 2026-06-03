import json
import time
from datetime import datetime, timedelta
from loguru import logger

from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

from backend.config import settings
from backend.database.raw_models import RawMotion
from backend.scrapers.utils import get_url_text

BASE_URL = "https://api.congreso.gob.pe/smociones-portal-service"
RAW_DB_PATH = settings.RAW_DB_URL


class RawMotionScraper:
    """
    Class to scrape and store raw bill information
    """

    def __init__(self, session=None, engine=None):
        # Engine and session maker for DB
        if session is not None:
            self.session = session
            self.engine = session.get_bind()
            self.Session = sessionmaker(bind=self.engine)
        else:
            self.engine = engine or create_engine(RAW_DB_PATH)
            self.session = None
            self.Session = sessionmaker(bind=self.engine)

        # Mapping raw section name to RawMotion attribute name
        self.section_mapping = {
            "firmantes": "congresistas",
            "seguimientos": "steps",
        }

        # List of raw bills objects
        self.raw_motions = []

    def scrape_motion(self, year: str, motion_number: str) -> None:
        """
        Scrape key sections: general, congresistas, steps

        Returns tuple with result of scrape, error message if relevant
        """

        motion_url = f"{BASE_URL}/mocion/{year}/{motion_number}"
        response = get_url_text(motion_url)

        if response:
            resp = json.loads(response)

            # Successfully built the raw bill!
            new_motion = self.create_raw_motion(year, motion_number, resp["data"])
            self.raw_motions.append(self.update_tracking(new_motion))
            logger.success(f"Successfully scraped Raw Motion {year}_{motion_number}")

        else:
            return None

    def create_raw_motion(self, year: str, motion_number: str, data: dict) -> RawMotion:
        # Initialize raw bill with id and timestamp
        raw_motion = RawMotion(
            id=f"{year}_{motion_number}",
            timestamp=datetime.now(),
            processed=False,
            last_update=True,
        )

        # Add sections
        for raw_name, attribute_name in self.section_mapping.items():
            # Grab expected section, use English value to signal no section
            # (since sections can be empty lists themselves)
            attribute_value = data.pop(raw_name, "Not Found")
            if attribute_value == "Not Found":
                logger.warning(
                    f"{raw_motion.id} - Missing Attribute: {raw_name} ({attribute_name})"
                )
            else:
                setattr(raw_motion, attribute_name, json.dumps(attribute_value))

        raw_motion.general = json.dumps(data)

        return raw_motion

    def update_tracking(self, motion: RawMotion) -> RawMotion:
        """Update the tracking columns of a RawMotion object"""
        session = self.session or self.Session()
        try:
            last_motion = (
                session.query(RawMotion)
                .filter(RawMotion.id == motion.id)
                .order_by(RawMotion.timestamp.desc())
                .first()
            )

            # First ever version of this motion
            if last_motion is None:
                motion.changed = True
                motion.last_update = True
                motion.processed = False
            else:
                # Compare last vs new
                motion.changed = motion != last_motion
                motion.last_update = True
                motion.processed = not motion.changed

                # Update the old version AFTER comparison
                last_motion.last_update = False
                session.add(last_motion)
                session.commit()

            return motion
        finally:
            if self.session is None:
                session.close()

    def add_motions_to_db(self) -> bool:
        """
        Add a single motion to the database.
        Returns True on success, False on failure.
        """
        assert len(self.raw_motions) != 0, (
            "There are no Raw Motions scraped. Nothing to load to DB."
        )

        # Create a new session
        session = self.session or self.Session()
        try:
            # Add and commit raw motion
            session.bulk_save_objects(self.raw_motions)
            session.commit()
            logger.success(f"Added {len(self.raw_motions)} Raw Motions to table.")
            return True

        except SQLAlchemyError as e:
            logger.error(f"Failed to add motions to Raw Motions table: {e}")
            session.rollback()
            return False

        finally:
            # Close Session
            if self.session is None:
                session.close()

    def load_raw_motions(self):
        self.add_motions_to_db()
        self.raw_motions = []

    @staticmethod
    def _is_approved_from_general(general_raw: str | None) -> bool:
        if not general_raw:
            return False

        try:
            general = json.loads(general_raw)
        except (TypeError, json.JSONDecodeError):
            return False

        status = " ".join((general.get("desEstadoMocion") or "").split()).lower()
        return status == "publicado diario oficial el peruano"

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
                session.query(RawMotion).filter(RawMotion.last_update == True).all()
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
        Re-scrape pending, non-approved motion ids that are stale.
        """
        pending_ids = self.get_ids_pending_weekly_refresh(max_age_days=max_age_days)

        for idx, motion_id in enumerate(pending_ids, start=1):
            year, number = motion_id.split("_", 1)
            self.scrape_motion(year, number)

            if len(self.raw_motions) >= flush_every:
                self.load_raw_motions()

            if idx % 10 == 0:
                time.sleep(2)

        if self.raw_motions:
            self.load_raw_motions()

        logger.info(f"Weekly motion refresh processed {len(pending_ids)} ids")
        return pending_ids


if __name__ == "__main__":
    scraper = RawMotionScraper()
    scraper.scrape_pending_weekly(max_age_days=7, flush_every=100)
