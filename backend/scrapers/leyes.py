from datetime import datetime, UTC
from loguru import logger

from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

from backend.config import settings
from backend.scrapers.utils import get_url_text
from backend.database.raw_models import RawLey

BASE_URL = "https://api.congreso.gob.pe/adlp-visor-service/expediente/ley?numley="
DB_PATH = settings.DB_URL


class RawLeyesScraper:
    """
    Class to scrape and store raw ley information
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

        # List of raw leyes objects
        self.raw_leyes = []
        # Track previous versions that were marked as not last_update.
        self._tracking_updates = []

    def scrape_ley(self, ley_number: int) -> None:
        """
        Scrape data from ley api request
        """

        ley_url = f"{BASE_URL}{ley_number}"
        response = get_url_text(ley_url)

        if response:
            # Successfully built the raw ley!
            ley = self.create_raw_ley(ley_number, response)
            tracked = self.update_tracking(ley)
            if tracked:
                self.raw_leyes.append(tracked)
                logger.success(f"Successfully scraped Raw Ley {ley_number}")
            else:
                logger.warning(
                    f"Skipping Raw Ley {ley_number} due to tracking update failure."
                )

        else:
            return None

    def create_raw_ley(self, ley_number: int, data: str) -> RawLey:
        # Initialize raw ley with id and timestamp
        raw_ley = RawLey(
            id=ley_number, timestamp=datetime.now(UTC), data=data, processed=False
        )

        return raw_ley

    def update_tracking(self, ley: RawLey) -> RawLey:
        """Update the tracking columns of a RawLey object"""

        # Create a new session
        session = self.session or self.Session()
        try:
            last_ley = (
                session.query(RawLey)
                .filter(RawLey.id == ley.id)
                .order_by(RawLey.timestamp.desc())
                .first()
            )

            # First ever version of this ley
            if last_ley is None:
                ley.changed = True
                ley.last_update = True
            else:
                # Compare last vs new
                ley.changed = ley.data != last_ley.data
                ley.last_update = True

                # Update the old version AFTER comparison
                last_ley.last_update = False
                session.add(last_ley)
                session.commit()
                self._tracking_updates.append(last_ley.id)

            return ley
        except SQLAlchemyError as e:
            logger.error(f"Failed to add update tracking to Raw Leyes table: {e}")
            session.rollback()
            return None

        finally:
            # Close Session
            if self.session is None:
                session.close()

    def add_leyes_to_db(self) -> bool:
        """
        Add a single ley to the database.
        Returns True on success, False on failure.
        """
        if len(self.raw_leyes) == 0:
            logger.info("There are no Raw Leyes scraped. Nothing to load to DB.")
            return False

        # Create a new session
        session = self.session or self.Session()
        try:
            # Add and commit raw ley
            session.bulk_save_objects(self.raw_leyes)
            session.commit()
            logger.success(f"Added {len(self.raw_leyes)} Raw Leyes to table.")
            self._tracking_updates = []
            return True

        except SQLAlchemyError as e:
            logger.error(f"Failed to add leyes to Raw Leyes table: {e}")
            session.rollback()
            self._restore_tracking_updates()
            return False

        finally:
            # Close Session
            if self.session is None:
                session.close()

    def _restore_tracking_updates(self) -> None:
        if not self._tracking_updates:
            return

        session = self.session or self.Session()
        try:
            (
                session.query(RawLey)
                .filter(RawLey.id.in_(self._tracking_updates))
                .update({RawLey.last_update: True}, synchronize_session=False)
            )
            session.commit()
        except SQLAlchemyError as e:
            logger.error(f"Failed to restore tracking updates for Raw Leyes: {e}")
            session.rollback()
        finally:
            if self.session is None:
                session.close()
            self._tracking_updates = []

    def load_raw_leyes(self):
        if self.add_leyes_to_db():
            self.raw_leyes = []
