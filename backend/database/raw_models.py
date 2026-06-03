from sqlalchemy import (
    Index,
    PrimaryKeyConstraint,
    ForeignKeyConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import expression
from sqlalchemy.inspection import inspect
from datetime import datetime
from backend.database.models import Base


class RawBase(Base):
    __abstract__ = True

    # Common columns for all the tables
    timestamp: Mapped[datetime] = mapped_column(nullable=False)
    last_update: Mapped[bool] = mapped_column(
        nullable=False, server_default=expression.false(), default=False
    )
    changed: Mapped[bool] = mapped_column(
        nullable=False, server_default=expression.false(), default=False
    )
    processed: Mapped[bool] = mapped_column(
        nullable=False, server_default=expression.false(), default=False
    )

    # Columns to ignore in ALL raw models
    _ignore_eq = {"id", "timestamp", "last_update", "changed", "processed"}

    def __eq__(self, other):
        """
        Compare two model instances for value-based equality.

        In this case, we are considering two objects equal when they are instances
        of the same class and all column values match, excluding any columns listed
        in `_ignore_eq`.

        This is useful when we want to determine whether two records represent
        the same underlying data and flag the changes accordingly in the raw ingestion.

        Args:
            other: Another object to compare against.

        Returns:
            bool: True if both objects are the same model type and all
            non-ignored column values are equal, otherwise False.
        """

        if not isinstance(other, self.__class__):
            return False

        mapper = inspect(self).mapper

        for col in mapper.columns:
            name = col.key
            if name in self._ignore_eq:
                continue
            if getattr(self, name) != getattr(other, name):
                return False

        return True

    __hash__ = None


class RawBancada(RawBase):
    """
    Represents a raw scraped of all bancadas in the peruvian parliament with its
    congressmembers that belongs to them.

    Attributes:
        id (str): Unique identifier for the bancada.
        leg_period (str): Legislative period
        raw_html (str): Html text
        timestamp (datetime): timestamp of the scraping task
        last_update (bool): Column that indicates if this tuple is the last update for the bill_id
        changed (bool): Column that indicates if the last update has any difference from the previous update
        processed (bool): Column that indicates if the last update with changes have been updated
    """

    __tablename__ = "raw_bancadas"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    legislative_period: Mapped[str] = mapped_column(nullable=False)
    raw_html: Mapped[str] = mapped_column(nullable=False)


class RawBill(RawBase):
    """
    Represents a raw scraped bill in the peruvian parliament.

    Attributes:
        id (str): Unique identifier for the bill.
        general (str): Main bill info
        committees (str) Information about committees
        congresistas (str) Information about authors and proponents
        steps (str) Information about bill steps
        api_url (str): Congress internal API to fetch.
        timestamp (datetime): timestamp of the scraping task
        last_update (bool): Column that indicates if this tuple is the last update for the bill_id
        changed (bool): Column that indicates if the last update has any difference from the previous update
        processed (bool): Column that indicates if the last update with changes have been updated
    """

    __tablename__ = "raw_bills"

    id: Mapped[str] = mapped_column(nullable=False)
    general: Mapped[str] = mapped_column(nullable=True)
    committees: Mapped[str] = mapped_column(nullable=True)
    congresistas: Mapped[str] = mapped_column(nullable=True)
    steps: Mapped[str] = mapped_column(nullable=True)
    api_url: Mapped[str | None] = mapped_column(nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint("id", "timestamp", name="pk_raw_bills"),
        Index(
            "ix_raw_bills_pipeline",
            "id",
            "last_update",
            "changed",
            "processed",
        ),
    )


class RawBillDocument(RawBase):
    """
    Raw documents url and text content extracted by scrape_raw_bills_documents.py

    Attributes:
        bill_id (str): Unique identifier for the bill.
        step_id (str): Event to which the document is related to.
        file_id (str): id related to the document
        step_date (datetime): date of the event related to the document
        url (str): complete document's url (congress website).
        s3_key (str): s3_key that maps the location of the document on the AWS S3 Bucket
        local_path (str): local path where the document is located.
        timestamp (datetime): timestamp of the scraping task
        last_update (bool): Column that indicates if this tuple is the last update for the bill_id
        changed (bool): Column that indicates if the last update has any difference from the previous update
        processed (bool): Column that indicates if the last update with changes have been updated
    """

    __tablename__ = "raw_bill_documents"

    bill_id: Mapped[str] = mapped_column(nullable=False)
    step_id: Mapped[str] = mapped_column(nullable=False)
    file_id: Mapped[str] = mapped_column(nullable=False)
    step_date: Mapped[datetime] = mapped_column(nullable=False)
    url: Mapped[str] = mapped_column(nullable=False)
    s3_key: Mapped[str] = mapped_column(nullable=True)
    local_path: Mapped[str] = mapped_column(nullable=True)

    __table_args__ = (
        Index(
            "ix_raw_bill_documents_pipeline",
            "bill_id",
            "step_id",
            "file_id",
            "last_update",
            "changed",
            "processed",
        ),
        PrimaryKeyConstraint(
            "bill_id", "step_id", "file_id", name="pk_raw_bills_documents"
        ),
    )


class RawBillPage(RawBase):
    __tablename__ = "raw_bill_pages"

    bill_id: Mapped[str] = mapped_column(nullable=False)
    step_id: Mapped[str] = mapped_column(nullable=False)
    file_id: Mapped[str] = mapped_column(nullable=False)
    page_num: Mapped[int] = mapped_column(nullable=False)
    text: Mapped[str] = mapped_column(nullable=False)
    ocr_model: Mapped[str] = mapped_column(nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint(
            "bill_id",
            "step_id",
            "file_id",
            "page_num",
            "ocr_model",
            name="pk_raw_bill_pages",
        ),
        ForeignKeyConstraint(
            ["bill_id", "step_id", "file_id"],
            [
                "raw_bill_documents.bill_id",
                "raw_bill_documents.step_id",
                "raw_bill_documents.file_id",
            ],
            name="fk_raw_bill_pages_document",
        ),
        Index(
            "ix_raw_bill_pages_pipeline",
            "bill_id",
            "step_id",
            "file_id",
            "page_num",
            "last_update",
            "changed",
            "processed",
        ),
    )


class RawCommittee(RawBase):
    """
    Represents a raw scraped committee in the peruvian parliament.

    Attributes:
        id (str): Unique identifier for raw committee.
        legislative_year (str): Legislative year
        committee_type (str): Type of committee in the parliament
        raw_html (str): Html text
        timestamp (datetime): timestamp of the scraping task
        last_update (bool): Column that indicates if this tuple is the last update for the bill_id
        changed (bool): Column that indicates if the last update has any difference from the previous update
        processed (bool): Column that indicates if the last update with changes have been updated
    """

    __tablename__ = "raw_committees"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    legislative_year: Mapped[str] = mapped_column(nullable=False)
    committee_type: Mapped[str] = mapped_column(nullable=False)
    raw_html: Mapped[str] = mapped_column(nullable=False)


class RawCongresista(RawBase):
    """
    Represents a raw scraped information of congresistas

    Attributes:
        id (str): Unique identifier for raw congresista.
        leg_period (str): Legislative period related to the congresista
        website (str): Congresista's website url
        profile_content (str): Html text from the website's profile tab
        memberships_content (str): API response to memberships of the congresista in json format
        timestamp: Time stamp of the scrape process
        last_update (bool): Column that indicates if this tuple is the last update for the bill_id
        changed (bool): Column that indicates if the last update has any difference from the previous update
        processed (bool): Column that indicates if the last update with changes have been updated
    """

    __tablename__ = "raw_congresistas"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    leg_period: Mapped[str] = mapped_column(nullable=False)
    website: Mapped[str] = mapped_column(nullable=False)
    profile_content: Mapped[str] = mapped_column(nullable=False)
    memberships_content: Mapped[str] = mapped_column(nullable=True)

    __table_args__ = (
        Index(
            "ix_raw_congresistas_pipeline",
            "id",
            "last_update",
            "changed",
            "processed",
        ),
    )


class RawLey(RawBase):
    """
    Represents a raw law extracted from the Peruvian congress web page.

    Attributes:
        id (str): Unique identifier for the organization.
        data (str): raw data xml information related to the law
        timestamp (datetime): timestamp of the scraping task
        last_update (bool): Column that indicates if this tuple is the last update for the bill_id
        changed (bool): Column that indicates if the last update has any difference from the previous update
        processed (bool): Column that indicates if the last update with changes have been updated
    """

    __tablename__ = "raw_leyes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    data: Mapped[str] = mapped_column(nullable=False)


class RawMotion(RawBase):
    """
    Represents a raw scraped motion in the peruvian parliament.

    Attributes:
        id (str): Unique identifier for the motion.
        general (str): Main motion info
        congresistas (str) Information about authors and proponents
        steps (str) Information about motion steps
        timestamp (datetime): timestamp of the scraping task
        last_update (bool): Column that indicates if this tuple is the last update for the bill_id
        changed (bool): Column that indicates if the last update has any difference from the previous update
        processed (bool): Column that indicates if the last update with changes have been updated
    """

    __tablename__ = "raw_motions"

    id: Mapped[str] = mapped_column(nullable=False)
    general: Mapped[str] = mapped_column(nullable=True)
    congresistas: Mapped[str] = mapped_column(nullable=True)
    steps: Mapped[str] = mapped_column(nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint("id", "timestamp", name="pk_raw_motions"),
        Index(
            "ix_raw_motions_pipeline",
            "id",
            "last_update",
            "changed",
            "processed",
        ),
    )


class RawMotionDocument(RawBase):
    """
    Raw documents url and text content extracted by scrape_raw_motions_documents.py

    Attributes:
        motion_id (str): Unique identifier for the motion.
        step_id (str): Event to which the document is related to.
        file_id (str): id related to the document
        step_date (datetime): date of the event related to the document
        url (str): complete document's url.
        s3_key (str): s3_key that maps the location of the document on the AWS S3 Bucket
        local_path (str): local path where the document is located.
        timestamp (datetime): timestamp of the scraping task
        last_update (bool): Column that indicates if this tuple is the last update for the bill_id
        changed (bool): Column that indicates if the last update has any difference from the previous update
        processed (bool): Column that indicates if the last update with changes have been updated
    """

    __tablename__ = "raw_motion_documents"

    motion_id: Mapped[str] = mapped_column(nullable=False)
    step_id: Mapped[str] = mapped_column(nullable=False)
    file_id: Mapped[str] = mapped_column(nullable=False)
    step_date: Mapped[datetime] = mapped_column(nullable=False)
    url: Mapped[str] = mapped_column(nullable=False)
    s3_key: Mapped[str] = mapped_column(nullable=True)
    local_path: Mapped[str] = mapped_column(nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint(
            "motion_id",
            "step_id",
            "file_id",
            name="pk_raw_motion_documents",
        ),
        Index(
            "ix_raw_motion_documents_pipeline",
            "motion_id",
            "step_id",
            "file_id",
            "last_update",
            "changed",
            "processed",
        ),
    )


class RawMotionPage(RawBase):
    __tablename__ = "raw_motion_pages"

    motion_id: Mapped[str] = mapped_column(nullable=False)
    step_id: Mapped[str] = mapped_column(nullable=False)
    file_id: Mapped[str] = mapped_column(nullable=False)
    page_num: Mapped[int] = mapped_column(nullable=False)
    text: Mapped[str] = mapped_column(nullable=False)
    ocr_model: Mapped[str] = mapped_column(nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint(
            "motion_id",
            "step_id",
            "file_id",
            "page_num",
            "ocr_model",
            name="pk_raw_motion_pages",
        ),
        ForeignKeyConstraint(
            ["motion_id", "step_id", "file_id"],
            [
                "raw_motion_documents.motion_id",
                "raw_motion_documents.step_id",
                "raw_motion_documents.file_id",
            ],
            name="fk_raw_motion_pages_document",
        ),
        Index(
            "ix_raw_motion_pages_pipeline",
            "motion_id",
            "step_id",
            "file_id",
            "page_num",
            "last_update",
            "changed",
            "processed",
        ),
    )


class RawOrganization(RawBase):
    """
    Represents a raw scraped organization in the peruvian parliament such as
    Junta de Portavoces, Consejo Directivo, Mesa Directiva y Comisión Permanente.

    Attributes:
        id (str): Unique identifier for the organization.
        legislative_year (str): Legislative year
        org_link (str): Organization's website
        raw_html (str): Html text
        timestamp (datetime): timestamp of the scraping task
        last_update (bool): Column that indicates if this tuple is the last update for the bill_id
        changed (bool): Column that indicates if the last update has any difference from the previous update
        processed (bool): Column that indicates if the last update with changes have been updated
    """

    __tablename__ = "raw_organizations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    legislative_year: Mapped[str] = mapped_column(nullable=False)
    type_org: Mapped[str] = mapped_column(nullable=False)
    org_link: Mapped[str] = mapped_column(nullable=True)
    raw_html: Mapped[str] = mapped_column(nullable=False)


class ScraperRun(Base):
    """
    Stores the metadata on the scrapers jobs for future analysis and future pipeline automations.

    Attributes:
        run_id (int): Unique identifier of the scraper run
        scraper_name (str): Name of the scraper file that ran
        start_time (datetime): Time when the scraper started running
        end_time (datetime): Time when the scraper stop running
        scraped_rows (int): Number of rows scraped within the run
    """

    __tablename__ = "scraper_runs"

    run_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    scraper_name: Mapped[str] = mapped_column(nullable=False)
    start_time: Mapped[datetime] = mapped_column(nullable=False)
    end_time: Mapped[datetime] = mapped_column(nullable=False)
    scraped_rows: Mapped[int] = mapped_column(nullable=False)
