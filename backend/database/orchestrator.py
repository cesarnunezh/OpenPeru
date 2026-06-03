from __future__ import annotations

import json
import time
from datetime import date, datetime, timedelta
from typing import Type, Callable

from tqdm import tqdm
from loguru import logger
from sqlalchemy import create_engine, func, select, or_, update
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

from backend.config import (
    settings,
    directories,
    log_manager,
)
from backend.database import models as db_models
from backend.database.build_db import drop_step_vote_event_fks
from backend.database.models import Bill, Motion
from backend.database.crud import (
    pipeline_bills as crud_bills,
    pipeline_core as crud_core,
    pipeline_motions as crud_motions,
)
from backend.database.crud.pipeline_core import (
    ProcessStats,
    ScraperStats,
    upsert_scraper_run,
)
from backend.database.raw_models import (
    RawBase,
    RawBancada,
    RawBill,
    RawCommittee,
    RawCongresista,
    RawLey,
    RawMotion,
    RawOrganization,
    RawBillDocument,
)
from backend.process.bancadas import process_bancada
from backend.process.bills import (
    process_bill,
    process_bill_organizations,
    process_bill_text,
)
from backend.process.diff import compute_bill_difference
from backend.process.congresistas import (
    process_cong_memberships,
    process_profile_content,
    get_cong_data,
)
from backend.process.motions import (
    process_motion,
    process_motion_organizations,
    process_motion_text,
)
from backend.process.organizations import (
    process_chambers,
    process_committee,
    process_admin_org,
)
from backend.process.leyes import process_leyes
from backend.process.schema import Membership, Organization
from backend.process.summarization import summarize_bill_from_db
from backend.process.utils import (
    get_current_leg_year,
    find_organization_schema,
    split_and_sort_name,
    replace_www,
)
from backend.scrapers.utils import get_last_id
from backend.scrapers.congresista_photos import sync_photo as sync_congresista_photo


class OpenPeruOrchestrator:
    """
    End-to-end ETL orchestrator:
      1) scrape raw tables
      2) process raw rows into Pydantic DTOs
      3) load SQLAlchemy models into the clean DB
    """

    def __init__(self, db_url: str = settings.DB_URL, engine=None):
        """Bind to ``db_url`` (or reuse ``engine``), ensure tables exist, and drop step/vote FKs."""
        self.db_engine = engine or create_engine(db_url, pool_pre_ping=True)
        self.DBSession = sessionmaker(
            bind=self.db_engine, autocommit=False, autoflush=False
        )

        # Ensure schemas exist before the pipeline runs.
        db_models.Base.metadata.create_all(self.db_engine)
        drop_step_vote_event_fks(self.db_engine)

    # -----------------------------
    # Public API
    # -----------------------------
    def _recent_raw_exists(self, raw_model: RawBase, days: int = 1) -> bool:
        """
        Query to check recent changes in a period of time in any RawDB table (default 1 day)
        """
        cutoff = datetime.now() - timedelta(days=days)
        with self.DBSession() as raw_db:
            last_ts = raw_db.query(func.max(raw_model.timestamp)).scalar()
            return bool(last_ts and last_ts >= cutoff)

    def _get_approved_ids(self, model: Type[Bill] | Type[Motion]) -> list[str]:
        """Return ids of Bills/Motions whose ``*_approved`` flag is True (never re-scrape these)."""
        with self.DBSession() as db:
            approved_col = (
                model.bill_approved if model is Bill else model.motion_approved
            )
            ids = [
                row[0]
                for row in db.query(model.id).filter(approved_col.is_(True)).all()
            ]
        return ids

    def _get_ids_to_update(
        self,
        raw_model: Type[RawBill] | Type[RawMotion],
        model: Type[Bill] | Type[Motion],
        days: int = 1,
    ) -> list[str] | None:
        """
        Return ids that should be refreshed this day:
          - latest snapshot is older than `max_age_days`
          - latest snapshot is not approved
        """
        cutoff = datetime.now() - timedelta(days=days)

        with self.DBSession() as raw_db:
            latest_rows = raw_db.query(raw_model).filter(raw_model.last_update).all()
            pending_ids: list[str] = []

            approved_ids = self._get_approved_ids(model)

            for row in latest_rows:
                if row.timestamp > cutoff:
                    continue
                if row.id in approved_ids:
                    continue
                pending_ids.append(row.id)

            return pending_ids

    def _get_last_id_scraped(
        self,
        raw_model: Type[RawBill] | Type[RawMotion] | Type[RawLey],
    ) -> int:
        """Return the highest numeric id present in ``raw_model`` (0 if empty)."""
        with self.DBSession() as db:
            ids = db.scalars(select(raw_model.id).distinct()).all()

        if not ids:
            return 0

        if raw_model is RawLey:
            return max(int(item) for item in ids)

        return max(int(item.split("_", 1)[1]) for item in ids)

    def _load_scraper_results(self, scraper_name: str) -> None:
        """Persist a ScraperStats row for ``scraper_name`` and log a one-line summary."""
        stats = self.scraper_results[scraper_name]
        with self.DBSession() as db:
            upsert_scraper_run(db, scraper_name, stats)
        log_manager.console_logger().info(
            f"Results for scraper/{scraper_name}: Time: {(stats.end_time - stats.start_time).seconds}s | Rows scraped: {stats.scrapped}"
        )

    def _log_stage_summary(self, stage: str, stats: ProcessStats) -> None:
        """Log processed/skipped/errors counts for a processing stage."""
        log_manager.console_logger().info(
            f"{stage}: processed={stats.processed}, skipped={stats.skipped}, errors={stats.errors}"
        )

    def run_scrapers(
        self,
        *,
        scrape_bills: bool = True,
        scrape_motions: bool = True,
        scrape_leyes: bool = True,
        scrape_others: bool = True,
        only_current: bool = True,
        scrape_documents: bool = False,
    ) -> None:
        """
        Run raw scrapers. Bills/motions scraping requires explicit ranges.
        """
        console = log_manager.console_logger()
        console.info("Starting scraper pipeline")
        self.scraper_results: dict[str, ScraperStats] = dict()

        if scrape_others:
            from backend.scrapers.bancadas import RawBancadaScraper
            from backend.scrapers.committees import RawCommitteeScraper
            from backend.scrapers.congresistas import RawCongresistasScraper
            from backend.scrapers.organizations import RawOrganizationScraper

            console.info(
                "Running reference scrapers (congresistas, bancadas, committees, organizations)"
            )

            with log_manager.stage("scraper", "congresistas") as stage_logger:
                if self._recent_raw_exists(RawCongresista, days=1):
                    console.info(
                        "Skipping congresistas scrape: latest raw scrape is within 1 day"
                    )
                    stage_logger.info("Skipped congresistas scraper")
                else:
                    console.info("Starting congresistas scraper")
                    stage_logger.info("Starting congresistas scraper")
                    cong = RawCongresistasScraper()
                    start_time = datetime.now()
                    cong.get_dict_periodos()
                    scraped_congs = cong.extract_and_load_all(only_current=only_current)
                    end_time = datetime.now()
                    self.scraper_results["congresistas.py"] = ScraperStats(
                        start_time, end_time, len(scraped_congs)
                    )
                    self._load_scraper_results("congresistas.py")

            with log_manager.stage("scraper", "bancadas") as stage_logger:
                if self._recent_raw_exists(RawBancada, days=1):
                    console.info(
                        "Skipping bancadas scrape: latest raw scrape is within 1 day"
                    )
                    stage_logger.info("Skipped bancadas scraper")
                else:
                    console.info("Starting bancadas scraper")
                    stage_logger.info("Starting bancadas scraper")
                    banc = RawBancadaScraper()
                    start_time = datetime.now()
                    banc.get_raw_bancadas(only_current=only_current)
                    scraped_banc = banc.add_bancadas_to_db()
                    end_time = datetime.now()
                    self.scraper_results["bancadas.py"] = ScraperStats(
                        start_time, end_time, int(scraped_banc)
                    )
                    self._load_scraper_results("bancadas.py")

            with log_manager.stage("scraper", "committees") as stage_logger:
                if self._recent_raw_exists(RawCommittee, days=1):
                    console.info(
                        "Skipping committees scrape: latest raw scrape is within 1 day"
                    )
                    stage_logger.info("Skipped committees scraper")
                else:
                    console.info("Starting committees scraper")
                    stage_logger.info("Starting committees scraper")
                    comm = RawCommitteeScraper()
                    start_time = datetime.now()
                    comm.get_raw_committees(only_current=only_current)
                    comm.add_committees_to_db()
                    scraped_comm = len(comm.committee_list)
                    end_time = datetime.now()
                    self.scraper_results["committees.py"] = ScraperStats(
                        start_time, end_time, scraped_comm
                    )
                    self._load_scraper_results("committees.py")

            with log_manager.stage("scraper", "organizations") as stage_logger:
                if self._recent_raw_exists(RawOrganization, days=1):
                    console.info(
                        "Skipping organizations scrape: latest raw scrape is within 1 day"
                    )
                    stage_logger.info("Skipped organizations scraper")
                else:
                    console.info("Starting organizations scraper")
                    stage_logger.info("Starting organizations scraper")
                    org = RawOrganizationScraper()
                    start_time = datetime.now()
                    org.get_raw_organizations(only_current=only_current)
                    scraped_orgs = len(org.organizations_list)
                    org.add_organizations_to_db()
                    end_time = datetime.now()
                    self.scraper_results["organizations.py"] = ScraperStats(
                        start_time, end_time, scraped_orgs
                    )
                    self._load_scraper_results("organizations.py")

        if scrape_bills:
            from backend.scrapers.bills import RawBillScraper

            with log_manager.stage("scraper", "bills") as stage_logger:
                console.info("Starting bills scraper")
                stage_logger.info("Starting bills scraper")
                scraper = RawBillScraper()
                new_results = self._scrape_range(
                    scraper=scraper,
                    raw_model=RawBill,
                    scrape_fn=scraper.scrape_bill,
                    buffer_attr="raw_bills",
                    load_fn=scraper.load_raw_bills,
                    flush_every=100,
                    entity_name="Bills",
                )
                pending_results = self._scrape_pending_daily(
                    raw_model=RawBill,
                    model=Bill,
                    scraper=scraper,
                    scrape_fn=scraper.scrape_bill,
                    buffer_attr="raw_bills",
                    load_fn=scraper.load_raw_bills,
                    max_age_days=1,
                    flush_every=100,
                    entity_name="Bills",
                )
                self.scraper_results["bills.py"] = ScraperStats(
                    new_results.start_time,
                    pending_results.end_time,
                    new_results.scrapped + pending_results.scrapped,
                )
                self._load_scraper_results("bills.py")

        if scrape_motions:
            from backend.scrapers.motions import RawMotionScraper

            with log_manager.stage("scraper", "motions") as stage_logger:
                console.info("Starting motions scraper")
                stage_logger.info("Starting motions scraper")
                scraper = RawMotionScraper()
                new_results = self._scrape_range(
                    scraper=scraper,
                    raw_model=RawMotion,
                    scrape_fn=scraper.scrape_motion,
                    buffer_attr="raw_motions",
                    load_fn=scraper.load_raw_motions,
                    flush_every=100,
                    entity_name="Motions",
                )
                pending_results = self._scrape_pending_daily(
                    raw_model=RawMotion,
                    model=Motion,
                    scraper=scraper,
                    scrape_fn=scraper.scrape_motion,
                    buffer_attr="raw_motions",
                    load_fn=scraper.load_raw_motions,
                    max_age_days=1,
                    flush_every=100,
                    entity_name="Motions",
                )
                self.scraper_results["motions.py"] = ScraperStats(
                    new_results.start_time,
                    pending_results.end_time,
                    new_results.scrapped + pending_results.scrapped,
                )
                self._load_scraper_results("motions.py")

        if scrape_documents:
            with log_manager.stage("scraper", "documents") as stage_logger:
                console.info("Starting document scraper")
                stage_logger.info("Starting document scraper")
                doc_bill_run, doc_motion_run = self._scrape_pending_documents()
                self.scraper_results["bills_documents.py"] = doc_bill_run
                self.scraper_results["motions_documents.py"] = doc_motion_run
                self._load_scraper_results("bills_documents.py")
                self._load_scraper_results("motions_documents.py")

        if scrape_leyes:
            from backend.scrapers.leyes import RawLeyesScraper

            with log_manager.stage("scraper", "leyes") as stage_logger:
                console.info("Starting leyes scraper")
                stage_logger.info("Starting leyes scraper")
                scraper = RawLeyesScraper()
                self.scraper_results["leyes.py"] = self._scrape_range(
                    scraper=scraper,
                    raw_model=RawLey,
                    scrape_fn=scraper.scrape_ley,
                    buffer_attr="raw_leyes",
                    load_fn=scraper.load_raw_leyes,
                    flush_every=100,
                    entity_name="Leyes",
                )
                self._load_scraper_results("leyes.py")

    def run_processing(
        self,
        *,
        process_bills: bool = True,
        process_motions: bool = True,
        process_leyes: bool = True,
        process_others: bool = True,
        process_documents: bool = True,
        bills_limit: int | None = None,
        leyes_limit: int | None = None,
        motions_limit: int | None = None,
        first_load: bool = False,
    ) -> dict[str, ProcessStats]:
        """
        Process raw -> clean tables.
        """
        console = log_manager.console_logger()
        console.info("Starting processing pipeline")
        summary: dict[str, ProcessStats] = {}

        if process_others:
            with log_manager.stage("process", "organizations"):
                console.info("Starting organizations processing")
                summary["organizations"] = self._process_organization_definitions()
                summary["bancadas"] = self._process_bancada_definitions()
                self._log_stage_summary("organizations", summary["organizations"])
                self._log_stage_summary("bancadas", summary["bancadas"])

            with log_manager.stage("process", "congresistas"):
                console.info("Starting congresistas processing")
                summary["congresistas"] = self._process_congresistas()
                self._log_stage_summary("congresistas", summary["congresistas"])

            with log_manager.stage("process", "memberships"):
                console.info("Starting memberships processing")
                summary["admin_memberships"] = self._process_admin_memberships()
                summary["bancada_memberships"] = self._process_bancada_memberships()
                self._log_stage_summary(
                    "admin_memberships", summary["admin_memberships"]
                )
                self._log_stage_summary(
                    "bancada_memberships", summary["bancada_memberships"]
                )

        if process_bills:
            with log_manager.stage("process", "bills"):
                console.info("Starting bills processing")
                summary["bills"] = self._process_bills(
                    limit=bills_limit,
                )
                self._log_stage_summary("bills", summary["bills"])

            with log_manager.stage("process", "bills"):
                console.info("Starting populating bill summaries")
                summary["bill_summary"] = self._process_bills_summaries(
                    first_load=first_load
                )
                self._log_stage_summary("bill_summary", summary["bill_summary"])

            if process_documents:
                with log_manager.stage("process", "bill_text"):
                    console.info("Starting bill text processing")
                    summary["bill_text"] = self._process_bill_text(limit=bills_limit)
                    self._log_stage_summary("bill_text", summary["bill_text"])

                with log_manager.stage("process", "bill_differences"):
                    console.info("Starting bill differences processing")
                    summary["bill_differences"] = self._process_bill_differences(
                        limit=bills_limit,
                    )
                    self._log_stage_summary(
                        "bill_differences", summary["bill_differences"]
                    )

        if process_motions:
            with log_manager.stage("process", "motions"):
                console.info("Starting motions processing")
                summary["motions"] = self._process_motions(
                    include_documents=False,
                    limit=motions_limit,
                )
                self._log_stage_summary("motions", summary["motions"])

        if process_leyes:
            with log_manager.stage("process", "leyes"):
                console.info("Starting leyes processing")
                summary["leyes"] = self._process_leyes(limit=leyes_limit)
                self._log_stage_summary("leyes", summary["leyes"])

        return summary

    # -----------------------------
    # Scraping internals
    # -----------------------------
    def _scrape_range(
        self,
        scraper,
        raw_model: Type[RawBill] | Type[RawMotion] | Type[RawLey],
        scrape_fn: Callable[[str, str], None],
        buffer_attr: str,
        load_fn: Callable[[], None],
        flush_every: int = 100,
        entity_name: str = "items",
    ) -> ScraperStats:
        """Scrape ids from (last_scraped+1) up to the remote max, flushing every ``flush_every`` rows."""
        start = self._get_last_id_scraped(raw_model) + 1
        end = get_last_id(entity_name)
        # TODO: update this for next congreso
        year = 2021

        logger.info(f"Scraping {entity_name} in range {year}_{start}..{year}_{end}")

        start_time = datetime.now()
        count = 0

        for number in tqdm(range(start, end + 1), desc=entity_name):
            if entity_name == "Leyes":
                scrape_fn(number)
            else:
                scrape_fn(str(year), str(number))

            current_length = len(getattr(scraper, buffer_attr))

            if current_length >= flush_every:
                count += current_length
                load_fn()

        remaining = len(getattr(scraper, buffer_attr))

        if remaining:
            count += remaining
            load_fn()

        end_time = datetime.now()
        return ScraperStats(start_time, end_time, count)

    def _scrape_pending_daily(
        self,
        raw_model: Type[RawBill] | Type[RawMotion],
        model: Type[Bill] | Type[Motion],
        scraper,
        scrape_fn: Callable[[str, str], None],
        buffer_attr: str,
        load_fn: Callable[[], None],
        max_age_days: int = 1,
        flush_every: int = 100,
        entity_name: str = "items",
    ) -> ScraperStats:
        """Re-scrape rows older than ``max_age_days`` and not yet approved, sleeping briefly every 10 ids."""
        pending_ids = self._get_ids_to_update(raw_model, model, max_age_days)
        start_time = datetime.now()
        count = 0

        for idx, item_id in enumerate(
            tqdm(pending_ids, desc=f"Pending {entity_name}"), start=1
        ):
            year, number = item_id.split("_", 1)

            scrape_fn(str(year), str(number))

            current_length = len(getattr(scraper, buffer_attr))

            if current_length >= flush_every:
                count += current_length
                load_fn()

            if idx % 10 == 0:
                time.sleep(2)

        remaining = len(getattr(scraper, buffer_attr))

        if remaining:
            count += remaining
            load_fn()

        end_time = datetime.now()
        return ScraperStats(start_time, end_time, count)

    def _scrape_pending_documents(self) -> tuple[ScraperStats, ScraperStats]:
        """Fetch documents for bills and motions still missing them; returns (bill_stats, motion_stats)."""
        from backend.scrapers.bills_documents import RawBillDocumentScraper
        from backend.scrapers.motions_documents import RawMotionDocumentScraper

        logger.info("Scraping pending bill and motion documents")

        bill_docs = RawBillDocumentScraper()
        start_time = datetime.now()
        count = 0
        bill_ids = bill_docs.get_bills_pending_documents()
        for bill_id in tqdm(bill_ids, desc="Bill documents"):
            bill_docs.get_bill_documents(
                bill_id=bill_id,
                update=False,
                download_local=False,
                upload_s3=False,
            )
            count += len(bill_docs.documents)
            bill_docs.load_raw_documents()
        end_time = datetime.now()
        doc_bill_run = ScraperStats(start_time, end_time, count)

        motion_docs = RawMotionDocumentScraper()
        start_time = datetime.now()
        count = 0
        motion_ids = motion_docs.get_motions_pending_documents()
        for motion_id in tqdm(motion_ids, desc="Motion documents"):
            motion_docs.get_motion_documents(
                motion_id=motion_id,
                update=False,
                download_local=False,
                upload_s3=False,
            )
            count += len(motion_docs.documents)
            motion_docs.load_raw_documents()
        end_time = datetime.now()
        doc_motion_run = ScraperStats(start_time, end_time, count)

        return doc_bill_run, doc_motion_run

    # -----------------------------
    # Processing internals
    # -----------------------------
    def _membership_dates(self, membership: Membership) -> tuple[date, date]:
        """Resolve a membership's start/end, falling back to the legislative-year window (Jul 28 → Jul 28)."""
        seed = membership.start_date or membership.time_stamp
        leg_year = get_current_leg_year(seed)
        derived_start = date(leg_year, 7, 28)
        derived_end = date(leg_year + 1, 7, 28)

        start = membership.start_date or derived_start
        if isinstance(start, datetime):
            start = start.date()

        end = membership.end_date
        if isinstance(end, datetime):
            end = end.date()
        if end is None or end < start:
            end = derived_end

        return start, end

    def _upsert_organization_with_count(
        self, db, org_schema: Organization
    ) -> tuple[db_models.Organization, bool]:
        """Upsert an organization; second return is True if this was a new insert."""
        pre = crud_core.find_organization(
            db,
            org_name=org_schema.org_name,
            org_type=org_schema.org_type,
        )
        org = crud_core.upsert_organization(db, org_schema)
        return org, pre is None

    def _upsert_membership_schema(
        self,
        db,
        *,
        cong: db_models.Congresista,
        org: db_models.Organization,
        membership: Membership,
    ) -> db_models.Membership:
        """Upsert a Membership row linking ``cong`` to ``org`` with derived dates and non-null extras."""
        start_date, end_date = self._membership_dates(membership)
        extra_fields = {
            "condicion": membership.condicion,
            "votes_in_election": membership.votes_in_election,
            "dist_electoral": membership.dist_electoral,
        }
        extra_fields = {k: v for k, v in extra_fields.items() if v is not None}
        return crud_core.upsert_membership(
            db=db,
            person_id=cong.id,
            org_id=org.org_id,
            leg_period=membership.leg_period,
            org_type=org.org_type,
            role=membership.role,
            start_date=start_date,
            end_date=end_date,
            extra_fields=extra_fields,
        )

    def _process_congresistas(self) -> ProcessStats:
        """Process unprocessed RawCongresista rows into Congresista + Organization + Membership records."""
        stats = ProcessStats()
        clean_inserted = 0
        clean_updated = 0

        CONG_JSON = directories.PROCESSED_DATA / "cong_info_2021_2026.json"

        dict_cong_data = get_cong_data(CONG_JSON)
        with self.DBSession() as db:
            rows = (
                db.query(RawCongresista)
                .filter(
                    RawCongresista.last_update.is_(True),
                    RawCongresista.processed.is_(False),
                )
                .all()
            )
            for raw_cong in tqdm(rows, desc="Process congresistas"):
                try:
                    # TODO: Remove this range to process all years
                    if raw_cong.leg_period not in [
                        "Parlamentario 2021 - 2026",
                        "Parlamentario 2016 - 2021",
                    ]:
                        raw_cong.processed = False
                        stats.skipped += 1
                        continue
                    cong_schema, org_schemas, profile_memberships = (
                        process_profile_content(raw_cong, dict_cong_data)
                    )
                    pre = crud_core.find_congresista(
                        db,
                        name=cong_schema.full_name,
                        website=cong_schema.website,
                    )
                    cong = crud_core.upsert_congresista(db, cong_schema)
                    if pre is None:
                        clean_inserted += 1
                        try:
                            sync_congresista_photo(db, cong)
                        except Exception as photo_exc:
                            logger.warning(
                                f"Photo sync failed for congresista {cong.id}: {photo_exc}"
                            )
                    else:
                        clean_updated += 1

                    for org_schema in org_schemas:
                        self._upsert_organization_with_count(db, org_schema)

                    memberships = profile_memberships
                    if raw_cong.memberships_content:
                        memberships.extend(
                            process_cong_memberships(raw_cong, cong_schema)
                        )
                    for ms in memberships:
                        # TODO: We need to implement a fuzzy match for finding organization
                        org = crud_core.find_organization(
                            db=db,
                            org_name=ms.org_name,
                            org_type=ms.org_type,
                        )
                        if org is None:
                            logger.warning(
                                f"Skipping Membership org_name={ms.org_name} for org_type={ms.org_type} and Congresista={cong.full_name}"
                            )
                            stats.skipped += 1
                            continue
                        self._upsert_membership_schema(
                            db,
                            cong=cong,
                            org=org,
                            membership=ms,
                        )

                    raw_cong.processed = True
                    stats.processed += 1
                except Exception as exc:
                    logger.exception(
                        f"Error processing RawCongresista id={raw_cong.id}: {exc}"
                    )
                    db.rollback()
                    stats.errors += 1
            db.commit()
        logger.info(
            f"[congresistas] raw_total={len(rows)} processed={stats.processed} skipped={stats.skipped} errors={stats.errors} clean_inserted={clean_inserted} clean_updated={clean_updated}"
        )
        return stats

    def _process_organization_definitions(self) -> ProcessStats:
        """Load chambers, committees, and admin organizations into the clean Organization table."""
        stats = ProcessStats()
        clean_inserted = 0
        clean_updated = 0
        with self.DBSession() as db:
            for org_schema in process_chambers():
                _, inserted = self._upsert_organization_with_count(db, org_schema)
                if inserted:
                    clean_inserted += 1
                else:
                    clean_updated += 1

            # Committees
            committees = (
                db.query(RawCommittee)
                .filter(
                    RawCommittee.last_update.is_(True),
                    RawCommittee.processed.is_(False),
                )
                .all()
            )

            for raw_comm in tqdm(committees, desc="Process committees"):
                try:
                    # TODO: Remove this range to process all years
                    if int(raw_comm.legislative_year) not in range(2016, 2027):
                        raw_comm.processed = False
                        stats.skipped += 1
                        continue
                    for org_schema in process_committee(raw_comm):
                        _, inserted = self._upsert_organization_with_count(
                            db, org_schema
                        )
                        if inserted:
                            clean_inserted += 1
                        else:
                            clean_updated += 1
                    raw_comm.processed = True
                    stats.processed += 1
                except Exception as exc:
                    logger.exception(
                        f"Error processing RawCommittee id={raw_comm.id}: {exc}"
                    )
                    db.rollback()
                    stats.errors += 1

            # Administrative organization definitions. RawOrganization is marked
            # processed only after its memberships are loaded.
            organizations = (
                db.query(RawOrganization)
                .filter(
                    RawOrganization.last_update.is_(True),
                    RawOrganization.processed.is_(False),
                )
                .all()
            )
            for raw_org in tqdm(organizations, desc="Process organizations"):
                try:
                    # TODO: Remove this range to process all years
                    if int(raw_org.legislative_year) not in range(2016, 2027):
                        raw_org.processed = False
                        stats.skipped += 1
                        continue
                    org_schema, _ = process_admin_org(raw_org)
                    _, inserted = self._upsert_organization_with_count(db, org_schema)
                    if inserted:
                        clean_inserted += 1
                    else:
                        clean_updated += 1
                    stats.processed += 1
                except Exception as exc:
                    logger.exception(
                        f"Error processing RawOrganization id={raw_org.id}: {exc}"
                    )
                    db.rollback()
                    stats.errors += 1

            db.commit()
        logger.info(
            f"[organization_definitions] raw_committees={len(committees)} raw_orgs={len(organizations)} processed={stats.processed} skipped={stats.skipped} errors={stats.errors} clean_inserted={clean_inserted} clean_updated={clean_updated}"
        )
        return stats

    def _process_admin_memberships(self) -> ProcessStats:
        """Link congresistas to admin organizations; marks RawOrganization processed only if all members resolved."""
        stats = ProcessStats()
        with self.DBSession() as db:
            organizations = (
                db.query(RawOrganization)
                .filter(
                    RawOrganization.last_update.is_(True),
                    RawOrganization.processed.is_(False),
                )
                .all()
            )
            for raw_org in tqdm(organizations, desc="Process admin memberships"):
                try:
                    if int(raw_org.legislative_year) not in range(2016, 2027):
                        raw_org.processed = False
                        stats.skipped += 1
                        continue
                    org_schema, membership_list = process_admin_org(raw_org)
                    org, _ = self._upsert_organization_with_count(db, org_schema)
                    missing = False
                    for ms in membership_list:
                        cong = crud_core.find_congresista(
                            db,
                            name=ms.cong_name,
                            website=ms.website,
                        )
                        if cong is None:
                            missing = True
                            stats.skipped += 1
                            continue
                        self._upsert_membership_schema(
                            db,
                            cong=cong,
                            org=org,
                            membership=ms,
                        )
                    raw_org.processed = not missing
                    stats.processed += 1
                except Exception as exc:
                    logger.exception(
                        f"Error processing RawOrganization memberships id={raw_org.id}: {exc}"
                    )
                    db.rollback()
                    stats.errors += 1

            db.commit()
        logger.info(
            f"[admin_memberships] raw_orgs={len(organizations)} processed={stats.processed} skipped={stats.skipped} errors={stats.errors}"
        )
        return stats

    def _process_bancada_definitions(self) -> ProcessStats:
        """Upsert Organization rows for each bancada in the 2021-2026 legislative period."""
        stats = ProcessStats()
        clean_inserted = 0
        clean_updated = 0
        with self.DBSession() as db:
            rows = (
                db.query(RawBancada)
                .filter(
                    RawBancada.last_update.is_(True), RawBancada.processed.is_(False)
                )
                .all()
            )
            for raw_bancada in tqdm(rows, desc="Process bancada definitions"):
                try:
                    if raw_bancada.legislative_period not in [
                        "Parlamentario 2021 - 2026"
                    ]:
                        raw_bancada.processed = False
                        stats.skipped += 1
                        continue
                    bancadas, _ = process_bancada(raw_bancada)
                    missing = False
                    for bancada in bancadas:
                        org, inserted = self._upsert_organization_with_count(
                            db, bancada
                        )
                        if inserted:
                            clean_inserted += 1
                        else:
                            clean_updated += 1
                    stats.processed += 1
                    raw_bancada.processed = not missing
                except Exception as exc:
                    logger.exception(
                        f"Error processing RawBancada definitions id={raw_bancada.id}: {exc}"
                    )
                    db.rollback()
                    stats.errors += 1

            db.commit()
        logger.info(
            f"[bancada_definitions] raw_total={len(rows)} processed={stats.processed} skipped={stats.skipped} errors={stats.errors} clean_inserted={clean_inserted} clean_updated={clean_updated}"
        )
        return stats

    def _process_bancada_memberships(self) -> ProcessStats:
        """Link congresistas to bancada organizations; only marks raw processed when every member resolves."""
        stats = ProcessStats()
        with self.DBSession() as db:
            rows = (
                db.query(RawBancada)
                .filter(
                    RawBancada.last_update.is_(True), RawBancada.processed.is_(False)
                )
                .all()
            )
            for raw_bancada in tqdm(rows, desc="Process bancada memberships"):
                try:
                    if raw_bancada.legislative_period not in [
                        "Parlamentario 2021 - 2026"
                    ]:
                        raw_bancada.processed = False
                        stats.skipped += 1
                        continue
                    _, memberships = process_bancada(raw_bancada)

                    missing = False
                    for ms in memberships:
                        cong = crud_core.find_congresista(
                            db,
                            name=ms.cong_name,
                            website=ms.website,
                        )
                        org = crud_core.find_organization(
                            db,
                            org_name=ms.org_name,
                            org_type=ms.org_type,
                        )
                        if cong is None or org is None:
                            logger.warning(
                                f"Skipping BancadaMembership raw_id={raw_bancada.id}, cong={ms.cong_name}, website={ms.website}, org={ms.org_name}, org_type={ms.org_type}: reference not found"
                            )
                            missing = True
                            stats.skipped += 1
                            continue
                        self._upsert_membership_schema(
                            db,
                            cong=cong,
                            org=org,
                            membership=ms,
                        )

                    raw_bancada.processed = not missing
                    stats.processed += 1
                except Exception as exc:
                    logger.exception(
                        f"Error processing RawBancada memberships id={raw_bancada.id}: {exc}"
                    )
                    db.rollback()
                    stats.errors += 1

            db.commit()
        logger.info(
            f"[bancada_memberships] raw_total={len(rows)} processed={stats.processed} skipped={stats.skipped} errors={stats.errors}"
        )
        return stats

    def _process_bills(self, *, limit: int | None) -> ProcessStats:
        """Process unprocessed RawBill rows into Bill + steps + org/cong relations + (optionally) text and diffs."""
        stats = ProcessStats()
        clean_inserted = 0
        clean_updated = 0
        with self.DBSession() as db:
            query = db.query(RawBill).filter(
                RawBill.last_update.is_(True), RawBill.processed.is_(False)
            )
            if limit is not None:
                query = query.limit(limit)
            rows = query.all()

            for raw_bill in tqdm(rows, desc="Process bills"):
                try:
                    bill_schema, bill_congs, bill_steps = process_bill(raw_bill)

                    bill_orgs = process_bill_organizations(raw_bill, bill_steps)
                    chamber_schema = find_organization_schema(
                        bill_orgs,
                        org_name="Cámara de Diputados",
                        org_type="Cámara",
                    )

                    if chamber_schema is None:
                        logger.warning(
                            f"Skipping RawBill id={raw_bill.id}: chamber relation not generated"
                        )
                        stats.skipped += 1
                        continue
                    chamber = crud_core.find_organization(
                        db,
                        org_name="Cámara de Diputados",
                        org_type="Cámara",
                    )
                    if chamber is None:
                        logger.warning(
                            f"Skipping RawBill id={raw_bill.id}: Cámara de Diputados organization not found"
                        )
                        stats.skipped += 1
                        continue

                    pre = db.get(db_models.Bill, bill_schema.id)
                    bill = crud_bills.upsert_bill(db, bill_schema)
                    if pre is None:
                        clean_inserted += 1
                    else:
                        clean_updated += 1

                    for step_schema in bill_steps:
                        crud_bills.upsert_bill_step(db, step_schema)

                    for org_schema in bill_orgs:
                        org = crud_core.find_organization(
                            db=db,
                            org_name=org_schema.org_name,
                            org_type=org_schema.org_type,
                        )
                        if org is None:
                            logger.warning(
                                f"Skipping BillOrganization bill_id={bill.id}, org={org_schema.org_name}, org_type={org_schema.org_type}: organization not found"
                            )
                            stats.skipped += 1
                            continue
                        crud_bills.upsert_bill_organization(
                            db, bill.id, org.org_id, org_schema
                        )

                    for cong_rel in bill_congs:
                        cong = crud_core.find_congresista(
                            db,
                            name=split_and_sort_name(cong_rel.nombre)[0],
                            website=replace_www(cong_rel.web_page),
                        )
                        if cong is None:
                            logger.warning(
                                f"Skipping BillCongresista bill_id={bill.id}, name={cong_rel.nombre}, website={cong_rel.web_page}: congresista not found"
                            )
                            stats.skipped += 1
                            continue

                        crud_bills.upsert_bill_congresista(
                            db,
                            bill.id,
                            cong.id,
                            cong_rel.role_type.value
                            if hasattr(cong_rel.role_type, "value")
                            else cong_rel.role_type,
                        )

                    raw_bill.processed = True
                    stats.processed += 1
                except Exception as exc:
                    logger.exception(
                        f"Error processing RawBill id={raw_bill.id}: {exc}"
                    )
                    db.rollback()
                    stats.errors += 1

            db.commit()
        logger.info(
            f"[bills] raw_total={len(rows)} processed={stats.processed} skipped={stats.skipped} errors={stats.errors} clean_inserted={clean_inserted} clean_updated={clean_updated}"
        )
        return stats

    def _process_bills_summaries(
        self,
        *,
        first_load: bool = False,
    ) -> ProcessStats:
        stats = ProcessStats()
        clean_inserted = 0
        clean_updated = 0

        with self.DBSession() as db:
            if first_load:
                stmt = select(Bill.id).where(
                    or_(
                        Bill.summary_oc.is_(None),
                        func.trim(Bill.summary_oc) == "",
                    )
                )
            else:
                stmt = (
                    select(Bill.id)
                    .join(RawBill, Bill.id == RawBill.id)
                    .where(
                        RawBill.last_update.is_(True),
                        RawBill.changed.is_(True),
                    )
                )

            pending_bill_ids = list(db.scalars(stmt).all())

        if first_load:
            clean_inserted = len(pending_bill_ids)
        else:
            clean_updated = len(pending_bill_ids)

        for bill_id in tqdm(pending_bill_ids, desc="Processing summaries"):
            try:
                result = summarize_bill_from_db(bill_id)

                with self.DBSession() as db:
                    db.execute(
                        update(Bill)
                        .where(Bill.id == bill_id)
                        .values(summary_oc=result["summary"])
                    )
                    db.commit()

                stats.processed += 1

            except KeyError as e:
                stats.errors += 1
                logger.error(
                    f"[bill_summary] Missing expected key {e} for bill_id={bill_id}"
                )
                continue

            except SQLAlchemyError as e:
                stats.errors += 1
                logger.exception(
                    f"[bill_summary] Database error while processing bill_id={bill_id}: {e}"
                )
                continue

        logger.info(
            "[bill_summary] "
            f"pending_summaries={len(pending_bill_ids)} "
            f"processed={stats.processed} "
            f"skipped={stats.skipped} "
            f"errors={stats.errors} "
            f"clean_inserted={clean_inserted} "
            f"clean_updated={clean_updated}"
        )

        return stats

    def _process_bill_text(self, *, limit: int | None) -> ProcessStats:
        stats = ProcessStats()

        with self.DBSession() as db:
            bill_pages = crud_bills.find_bills_with_pending_pages(db)

            for idx, ((bill_id, step_id, file_id), pending_pages) in enumerate(
                bill_pages.items()
            ):
                if limit is not None and idx >= limit:
                    break

                next_version = crud_bills.get_next_bill_text_version(db, bill_id)
                try:
                    text_schema = process_bill_text(pending_pages, next_version)
                except ValueError as exc:
                    stats.errors += 1
                    logger.error(
                        f"Error extracting Bill Text for bill_id {bill_id}, "
                        f"step_id: {step_id}, file_id: {file_id}: {exc}"
                    )
                    continue

                try:
                    crud_bills.upsert_bill_text(
                        db,
                        bill_id=text_schema.bill_id,
                        step_id=text_schema.step_id,
                        file_id=text_schema.file_id,
                        version_id=text_schema.version_id,
                        text=text_schema.text,
                    )

                    raw_doc = db.get(RawBillDocument, (bill_id, step_id, file_id))

                    if raw_doc is None:
                        stats.errors += 1
                        logger.error(
                            f"RawBillDocument not found for bill_id {bill_id}, "
                            f"step_id: {step_id}, file_id: {file_id}"
                        )
                        db.rollback()
                        continue

                    for page in pending_pages:
                        page.processed = True

                    raw_doc.processed = True

                    db.commit()

                    stats.processed += len(pending_pages)

                except SQLAlchemyError as exc:
                    stats.errors += 1
                    logger.error(
                        f"Error loading Bill Text for bill_id {bill_id}, "
                        f"step_id: {step_id}, file_id: {file_id}: {exc}"
                    )
                    db.rollback()
                    continue

        logger.info(
            f"[bill_text] n_bills={len(bill_pages)} processed={stats.processed} skipped={stats.skipped} errors={stats.errors}"
        )
        return stats

    def _process_bill_differences(self, *, limit: int | None) -> ProcessStats:
        """Recompute diffs for every bill that has at least one ``bill_texts`` row.

        Driven off ``bill_texts`` rather than ``RawBill`` so this stage is
        independent of raw bill processing — it can be re-run on its own
        after a ``PARSER_VERSION`` bump or a fix to the diff package without
        having to mark raw bills unprocessed.
        """
        stats = ProcessStats()
        with self.DBSession() as db:
            query = (
                select(db_models.BillText.bill_id)
                .distinct()
                .order_by(db_models.BillText.bill_id)
            )
            if limit is not None:
                query = query.limit(limit)
            bill_ids = db.execute(query).scalars().all()

            for bill_id in tqdm(bill_ids, desc="Bill differences"):
                # Commit per bill: each bill is its own atomic unit, so a
                # failure on one doesn't roll back diffs already written for
                # earlier bills in the same batch.
                try:
                    self._compute_bill_differences(db, bill_id)
                    db.commit()
                    stats.processed += 1
                except Exception as exc:
                    logger.exception(
                        f"Error computing bill differences for bill_id={bill_id}: {exc}"
                    )
                    db.rollback()
                    stats.errors += 1
        logger.info(
            f"[bill_differences] bills_total={len(bill_ids)} processed={stats.processed} errors={stats.errors}"
        )
        return stats

    def _compute_bill_differences(self, db, bill_id: str) -> None:
        """Compute and store text diffs for every step of a bill against the
        most recent text-bearing predecessor.

        Step ordering is ``(step_date ASC, step_id ASC)`` so same-date steps
        pair deterministically across pipeline runs. Steps with no BillText
        are skipped as predecessors — we walk back through text-less steps
        so the next text-bearing step doesn't get stored as ``first_version``
        when an earlier version exists.
        """
        steps = (
            db.execute(
                select(db_models.BillStep)
                .where(db_models.BillStep.bill_id == bill_id)
                .order_by(
                    db_models.BillStep.step_date.asc(),
                    db_models.BillStep.step_id.asc(),
                )
            )
            .scalars()
            .all()
        )

        billtexts: list[db_models.BillText | None] = [
            crud_bills.get_billtext_for_step(db, bill_id, s.step_id) for s in steps
        ]

        prev_step: db_models.BillStep | None = None
        prev_bt: db_models.BillText | None = None
        for step, new_bt in zip(steps, billtexts):
            result = compute_bill_difference(
                prev_bt.text if prev_bt else None,
                new_bt.text if new_bt else None,
            )

            crud_bills.upsert_bill_difference(
                db,
                bill_id=bill_id,
                step_id=step.step_id,
                prev_step_id=prev_step.step_id if prev_step else None,
                difference_type=result["type"],
                difference_content=json.dumps(result["content"])
                if result["content"]
                else None,
            )

            if new_bt is not None:
                prev_step = step
                prev_bt = new_bt

    def _process_motions(
        self, *, include_documents: bool, limit: int | None
    ) -> ProcessStats:
        """Process unprocessed RawMotion rows into Motion + steps + org/cong relations + (optionally) text."""
        stats = ProcessStats()
        clean_inserted = 0
        clean_updated = 0
        with self.DBSession() as db:
            query = db.query(RawMotion).filter(
                RawMotion.last_update.is_(True), RawMotion.processed.is_(False)
            )
            if limit is not None:
                query = query.limit(limit)
            rows = query.all()

            for raw_motion in tqdm(rows, desc="Process motions"):
                try:
                    motion_schema, motion_congs, motion_steps = process_motion(
                        raw_motion
                    )

                    motion_orgs = process_motion_organizations(raw_motion, motion_steps)
                    chamber_schema = find_organization_schema(
                        motion_orgs,
                        org_name="Cámara de Diputados",
                        org_type="Cámara",
                    )
                    if chamber_schema is None:
                        logger.warning(
                            f"Skipping RawMotion id={raw_motion.id}: chamber relation not generated"
                        )
                        stats.skipped += 1
                        continue

                    chamber = crud_core.find_organization(
                        db,
                        org_name="Cámara de Diputados",
                        org_type="Cámara",
                    )
                    if chamber is None:
                        logger.warning(
                            f"Skipping RawMotion id={raw_motion.id}: Cámara de Diputados organization not found"
                        )
                        stats.skipped += 1
                        continue

                    pre = db.get(db_models.Motion, motion_schema.id)
                    motion = crud_motions.upsert_motion(db, motion_schema)
                    if pre is None:
                        clean_inserted += 1
                    else:
                        clean_updated += 1

                    for step_schema in motion_steps:
                        crud_motions.upsert_motion_step(db, step_schema)

                    for org_schema in motion_orgs:
                        org = crud_core.find_organization(
                            db=db,
                            org_name=org_schema.org_name,
                            org_type=org_schema.org_type,
                        )
                        if org is None:
                            logger.warning(
                                f"Skipping MotionOrganization motion_id={motion.id}, org={org_schema.org_name}: organization not found"
                            )
                            stats.skipped += 1
                            continue
                        crud_motions.upsert_motion_organization(
                            db, motion.id, org.org_id, org_schema
                        )

                    for cong_rel in motion_congs:
                        cong = crud_core.find_congresista(
                            db,
                            name=split_and_sort_name(cong_rel.nombre)[0],
                            website=replace_www(cong_rel.web_page),
                        )
                        if cong is None:
                            logger.warning(
                                f"Skipping MotionCongresista motion_id={motion.id}, name={cong_rel.nombre}, website={cong_rel.web_page}: congresista not found"
                            )
                            stats.skipped += 1
                            continue
                        crud_motions.upsert_motion_congresista(
                            db,
                            motion.id,
                            cong.id,
                            cong_rel.role_type.value
                            if hasattr(cong_rel.role_type, "value")
                            else cong_rel.role_type,
                        )

                    if include_documents:
                        for raw_doc in crud_motions.find_raw_motion_documents(
                            db, motion.id
                        ):
                            pages = crud_motions.find_raw_motion_pages(
                                db, motion.id, raw_doc.step_id, raw_doc.file_id
                            )
                            if not pages:
                                stats.skipped += 1
                                continue
                            try:
                                text_schema = process_motion_text(pages)
                            except ValueError:
                                stats.skipped += 1
                                continue
                            crud_motions.upsert_motion_text(
                                db,
                                motion_id=text_schema.motion_id,
                                step_id=text_schema.step_id,
                                file_id=text_schema.file_id,
                                version_id=text_schema.version_id,
                                text=text_schema.text,
                            )
                            raw_doc.processed = True

                    raw_motion.processed = True
                    stats.processed += 1
                except Exception as exc:
                    logger.exception(
                        f"Error processing RawMotion id={raw_motion.id}: {exc}"
                    )
                    db.rollback()
                    stats.errors += 1

            db.commit()
        logger.info(
            f"[motions] raw_total={len(rows)} processed={stats.processed} skipped={stats.skipped} errors={stats.errors} clean_inserted={clean_inserted} clean_updated={clean_updated}"
        )
        return stats

    def _process_leyes(self, *, limit: int | None) -> ProcessStats:
        """Process unprocessed RawLey rows into Ley records, skipping any whose referenced Bill is missing."""
        stats = ProcessStats()
        clean_inserted = 0
        clean_updated = 0
        with self.DBSession() as db:
            query = db.query(RawLey).filter(
                RawLey.last_update.is_(True), RawLey.processed.is_(False)
            )
            if limit is not None:
                query = query.limit(limit)
            rows = query.all()

            for raw_ley in tqdm(rows, desc="Process leyes"):
                try:
                    ley_schema = process_leyes(raw_ley)
                    if ley_schema is None:
                        logger.warning(
                            f"Skipping RawLey id={raw_ley.id}: unable to parse bill link"
                        )
                        raw_ley.processed = True
                        stats.skipped += 1
                        continue
                    if db.get(db_models.Bill, ley_schema.bill_id) is None:
                        logger.warning(
                            f"Skipping RawLey id={raw_ley.id}: referenced bill_id={ley_schema.bill_id} not found"
                        )
                        raw_ley.processed = False
                        stats.skipped += 1
                        continue
                    pre = db.get(db_models.Ley, ley_schema.id)
                    crud_core.upsert_ley(db, ley_schema)
                    if pre is None:
                        clean_inserted += 1
                    else:
                        clean_updated += 1

                    raw_ley.processed = True
                    stats.processed += 1
                except Exception as exc:
                    logger.exception(f"Error processing RawLey id={raw_ley.id}: {exc}")
                    db.rollback()
                    stats.errors += 1

            db.commit()
        logger.info(
            f"[leyes] raw_total={len(rows)} processed={stats.processed} skipped={stats.skipped} errors={stats.errors} clean_inserted={clean_inserted} clean_updated={clean_updated}"
        )
        return stats
