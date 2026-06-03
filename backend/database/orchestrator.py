from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from loguru import logger
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

from backend import find_leg_period
from backend.config import settings
from backend.database import models as db_models
from backend.database.crud import (
    pipeline_bills as crud_bills,
    pipeline_core as crud_core,
    pipeline_motions as crud_motions,
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
)
from backend.documents.downloader import (
    DownloadStats,
    download_bill_documents,
    download_motion_documents,
)
from backend.process.bancadas import process_bancada
from backend.process.bills import (
    get_committees,
    process_bill,
    process_bill_document,
    process_bill_steps,
)
from backend.process.congresistas import process_memberships, process_profile_content
from backend.process.motions import (
    process_motion,
    process_motion_document,
    process_motion_steps,
)
from backend.process.organizations import (
    process_committee,
    process_org,
    process_org_membership,
)
from backend.process.leyes import process_leyes
from backend.scrapers.bancadas import RawBancadaScraper
from backend.scrapers.bills import RawBillScraper
from backend.scrapers.bills_documents import RawBillDocumentScraper
from backend.scrapers.committees import RawCommitteeScraper
from backend.scrapers.congresistas import RawCongresistasScraper
from backend.scrapers.leyes import RawLeyesScraper
from backend.scrapers.motions import RawMotionScraper
from backend.scrapers.motions_documents import RawMotionDocumentScraper
from backend.scrapers.organizations import RawOrganizationScraper


@dataclass
class StageStats:
    processed: int = 0
    skipped: int = 0
    errors: int = 0


class OpenPeruOrchestrator:
    """
    End-to-end ETL orchestrator:
      1) scrape raw tables
      2) process raw rows into Pydantic DTOs
      3) load SQLAlchemy models into the clean DB
    """

    def __init__(
        self, raw_db_url: str = settings.RAW_DB_URL, db_url: str = settings.DB_URL
    ):
        self.raw_engine = create_engine(raw_db_url, pool_pre_ping=True)
        self.db_engine = create_engine(db_url, pool_pre_ping=True)
        self.RawSession = sessionmaker(
            bind=self.raw_engine, autocommit=False, autoflush=False
        )
        self.DBSession = sessionmaker(
            bind=self.db_engine, autocommit=False, autoflush=False
        )

        # Ensure schemas exist before the pipeline runs.
        RawBase.metadata.create_all(self.raw_engine)
        db_models.Base.metadata.create_all(self.db_engine)

    # -----------------------------
    # Public API
    # -----------------------------
    def _recent_raw_exists(self, raw_model: RawBase, days: int = 7) -> bool:
        """
        Query to check recent changes in a period of time in any RawDB table (default 7 days / 1 week)
        """
        cutoff = datetime.now() - timedelta(days=days)
        with self.RawSession() as raw_db:
            last_ts = raw_db.query(func.max(raw_model.timestamp)).scalar()
            return bool(last_ts and last_ts >= cutoff)

    def run_scrapers(
        self,
        *,
        scrape_bills: bool = True,
        scrape_motions: bool = True,
        scrape_leyes: bool = True,
        scrape_others: bool = True,
        only_current: bool = True,
        weekly_days: int = 7,
        others_days: int = 7,
        bill_year: int | None = None,
        bill_start: int | None = None,
        bill_end: int | None = None,
        ley_start: int | None = None,
        ley_end: int | None = None,
        motion_year: int | None = None,
        motion_start: int | None = None,
        motion_end: int | None = None,
        scrape_documents: bool = False,
    ) -> None:
        """
        Run raw scrapers. Bills/motions scraping requires explicit ranges.
        """
        logger.info("Starting processing pipeline")

        if scrape_others:
            logger.info(
                "Running reference scrapers (congresistas, bancadas, committees, organizations)"
            )

            if self._recent_raw_exists(RawCongresista, days=others_days):
                logger.info(
                    f"Skipping congresistas scrape: latest raw scrape is within {others_days} days"
                )
            else:
                cong = RawCongresistasScraper()
                cong.get_dict_periodos()
                cong.extract_and_load_all(only_current=only_current)

            if self._recent_raw_exists(RawBancada, days=others_days):
                logger.info(
                    f"Skipping bancadas scrape: latest raw scrape is within {others_days} days"
                )
            else:
                banc = RawBancadaScraper()
                banc.get_raw_bancadas(only_current=only_current)
                banc.add_bancadas_to_db()

            if self._recent_raw_exists(RawCommittee, days=others_days):
                logger.info(
                    f"Skipping committees scrape: latest raw scrape is within {others_days} days"
                )
            else:
                comm = RawCommitteeScraper()
                comm.get_raw_committees(only_current=only_current)
                comm.add_committees_to_db()

            if self._recent_raw_exists(RawOrganization, days=others_days):
                logger.info(
                    f"Skipping organizations scrape: latest raw scrape is within {others_days} days"
                )
            else:
                org = RawOrganizationScraper()
                org.get_raw_organizations(only_current=only_current)
                org.add_organizations_to_db()

        if scrape_bills:
            if all(v is not None for v in [bill_year, bill_start, bill_end]):
                self._scrape_bill_range(int(bill_year), int(bill_start), int(bill_end))
            else:
                RawBillScraper().scrape_pending_weekly(
                    max_age_days=weekly_days, flush_every=100
                )

        if scrape_motions:
            if all(v is not None for v in [motion_year, motion_start, motion_end]):
                self._scrape_motion_range(
                    int(motion_year), int(motion_start), int(motion_end)
                )
            else:
                RawMotionScraper().scrape_pending_weekly(
                    max_age_days=weekly_days, flush_every=100
                )

        if scrape_documents and (scrape_bills or scrape_motions):
            self._scrape_pending_documents()

        if scrape_leyes:
            if all(v is not None for v in [ley_start, ley_end]):
                self._scrape_leyes_range(int(ley_start), int(ley_end))
            else:
                RawLeyesScraper().scrape_pending_weekly(
                    max_age_days=weekly_days, flush_every=100
                )

    def run_processing(
        self,
        *,
        process_bills: bool = True,
        process_motions: bool = True,
        process_leyes: bool = True,
        process_others: bool = True,
        include_documents: bool = True,
        bills_limit: int | None = None,
        leyes_limit: int | None = None,
        motions_limit: int | None = None,
    ) -> dict[str, StageStats]:
        """
        Process raw -> clean tables.
        """
        logger.info("Starting processing pipeline")
        summary: dict[str, StageStats] = {}

        if process_others:
            summary["organizations"] = self._process_organizations()
            summary["congresistas"] = self._process_congresistas()
            summary["bancadas"] = self._process_bancadas()
        if process_bills:
            summary["bills"] = self._process_bills(
                include_documents=include_documents,
                limit=bills_limit,
            )
        if process_motions:
            summary["motions"] = self._process_motions(
                include_documents=include_documents,
                limit=motions_limit,
            )
        if process_leyes:
            summary["leyes"] = self._process_leyes(limit=leyes_limit)

        return summary

    def run_document_downloads(
        self,
        *,
        download_bills: bool = True,
        download_motions: bool = True,
        update: bool = False,
        upload_s3: bool = False,
        limit: int | None = None,
    ) -> dict[str, DownloadStats]:
        summary: dict[str, DownloadStats] = {}
        with self.RawSession() as raw_db:
            if download_bills:
                summary["bill_documents"] = download_bill_documents(
                    raw_db, update=update, upload_s3=upload_s3, limit=limit
                )
            if download_motions:
                summary["motion_documents"] = download_motion_documents(
                    raw_db, update=update, upload_s3=upload_s3, limit=limit
                )
        return summary

    # -----------------------------
    # Scraping internals
    # -----------------------------
    def _scrape_bill_range(
        self, year: int, start: int, end: int, flush_every: int = 100
    ) -> None:
        logger.info(f"Scraping bills in range {year}_{start}..{year}_{end}")
        scraper = RawBillScraper()
        for bill_number in range(start, end + 1):
            scraper.scrape_bill(str(year), str(bill_number))
            if len(scraper.raw_bills) >= flush_every:
                scraper.load_raw_bills()
        if scraper.raw_bills:
            scraper.load_raw_bills()

    def _scrape_motion_range(
        self, year: int, start: int, end: int, flush_every: int = 100
    ) -> None:
        logger.info(f"Scraping motions in range {year}_{start}..{year}_{end}")
        scraper = RawMotionScraper()
        for motion_number in range(start, end + 1):
            scraper.scrape_motion(str(year), str(motion_number))
            if len(scraper.raw_motions) >= flush_every:
                scraper.load_raw_motions()
        if scraper.raw_motions:
            scraper.load_raw_motions()

    def _scrape_pending_documents(self) -> None:
        logger.info("Scraping pending bill and motion documents")

        bill_docs = RawBillDocumentScraper()
        for bill_id in bill_docs.get_bills_pending_documents():
            bill_docs.get_bill_documents(bill_id=bill_id, update=False, prioritize=True)
            bill_docs.load_raw_documents()

        motion_docs = RawMotionDocumentScraper()
        for motion_id in motion_docs.get_motions_pending_documents():
            motion_docs.get_motion_documents(
                motion_id=motion_id, update=False, prioritize=True
            )
            motion_docs.load_raw_documents()

    def _scrape_leyes_range(self, ley_start: int, ley_end: int, flush_every: int = 100):
        logger.info(f"Scraping leyes in range {ley_start}..{ley_end}")
        scraper = RawLeyesScraper()
        for ley_number in range(ley_start, ley_end + 1):
            scraper.scrape_ley(ley_number)
            if len(scraper.raw_leyes) >= flush_every:
                scraper.load_raw_leyes()
        if scraper.raw_leyes:
            scraper.load_raw_leyes()

    # -----------------------------
    # Processing internals
    # -----------------------------
    def _process_congresistas(self) -> StageStats:
        stats = StageStats()
        clean_inserted = 0
        clean_updated = 0
        with self.RawSession() as raw_db, self.DBSession() as db:
            rows = (
                raw_db.query(RawCongresista)
                .filter(
                    RawCongresista.last_update.is_(True),
                    RawCongresista.processed.is_(False),
                )
                .all()
            )
            for raw_cong in rows:
                try:
                    # TODO: Remove this range to process all years
                    if raw_cong.leg_period not in [
                        "Parlamentario 2021 - 2026",
                        "Parlamentario 2016 - 2021",
                    ]:
                        raw_cong.processed = False
                        stats.skipped += 1
                        continue
                    cong_schema = process_profile_content(raw_cong)
                    pre = crud_core.find_congresista(
                        db,
                        name=cong_schema.nombre,
                        leg_period=cong_schema.leg_period,
                        website=cong_schema.website,
                    )
                    cong = crud_core.upsert_congresista(db, cong_schema)
                    if pre is None:
                        clean_inserted += 1
                    else:
                        clean_updated += 1

                    if raw_cong.memberships_content:
                        memberships = process_memberships(raw_cong, cong_schema)
                        for ms in memberships:
                            org = crud_core.find_organization(
                                db=db,
                                org_name=ms.org_name,
                                leg_period=ms.leg_period,
                                leg_year=ms.start_date.year,
                            )
                            if org is None:
                                stats.skipped += 1
                                continue
                            crud_core.upsert_membership(
                                db=db,
                                person_id=cong.id,
                                org_id=org.org_id,
                                role=ms.role,
                                start_date=ms.start_date,
                                end_date=ms.end_date,
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
            raw_db.commit()
        logger.info(
            f"[congresistas] raw_total={len(rows)} processed={stats.processed} skipped={stats.skipped} errors={stats.errors} clean_inserted={clean_inserted} clean_updated={clean_updated}"
        )
        return stats

    def _process_organizations(self) -> StageStats:
        stats = StageStats()
        clean_inserted = 0
        clean_updated = 0
        with self.RawSession() as raw_db, self.DBSession() as db:
            committees = (
                raw_db.query(RawCommittee)
                .filter(
                    RawCommittee.last_update.is_(True),
                    RawCommittee.processed.is_(False),
                )
                .all()
            )

            for raw_comm in committees:
                try:
                    # TODO: Remove this range to process all years
                    if raw_comm.legislative_year not in range(2016, 2027):
                        raw_comm.processed = False
                        stats.skipped += 1
                        continue
                    for org_schema in process_committee(raw_comm):
                        pre = (
                            db.query(db_models.Organization)
                            .filter(
                                db_models.Organization.leg_period
                                == org_schema.leg_period,
                                db_models.Organization.leg_year == org_schema.leg_year,
                                db_models.Organization.org_name == org_schema.org_name,
                                db_models.Organization.org_type == org_schema.org_type,
                            )
                            .first()
                        )
                        org = crud_core.upsert_organization(db, org_schema)
                        if pre is None:
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

            organizations = (
                raw_db.query(RawOrganization)
                .filter(
                    RawOrganization.last_update.is_(True),
                    RawOrganization.processed.is_(False),
                )
                .all()
            )
            for raw_org in organizations:
                try:
                    # TODO: Remove this range to process all years
                    if raw_org.legislative_year not in range(2016, 2027):
                        raw_org.processed = False
                        stats.skipped += 1
                        continue
                    org_schema = process_org(raw_org)
                    pre = (
                        db.query(db_models.Organization)
                        .filter(
                            db_models.Organization.leg_period == org_schema.leg_period,
                            db_models.Organization.leg_year == org_schema.leg_year,
                            db_models.Organization.org_name == org_schema.org_name,
                            db_models.Organization.org_type == org_schema.org_type,
                        )
                        .first()
                    )
                    org = crud_core.upsert_organization(db, org_schema)
                    if pre is None:
                        clean_inserted += 1
                    else:
                        clean_updated += 1
                    for ms in process_org_membership(raw_org, org_schema):
                        cong = crud_core.find_congresista(
                            db,
                            name=ms.nombre,
                            leg_period=ms.leg_period,
                            website=ms.web_page,
                        )
                        if cong is None:
                            stats.skipped += 1
                            continue
                        crud_core.upsert_membership(
                            db=db,
                            person_id=cong.id,
                            org_id=org.org_id,
                            role=ms.role,
                            start_date=ms.start_date,
                            end_date=ms.end_date,
                        )
                    raw_org.processed = True
                    stats.processed += 1
                except Exception as exc:
                    logger.exception(
                        f"Error processing RawOrganization id={raw_org.id}: {exc}"
                    )
                    db.rollback()
                    stats.errors += 1

            db.commit()
            raw_db.commit()
        logger.info(
            f"[organizations] raw_committees={len(committees)} raw_orgs={len(organizations)} processed={stats.processed} skipped={stats.skipped} errors={stats.errors} clean_inserted={clean_inserted} clean_updated={clean_updated}"
        )
        return stats

    def _process_bancadas(self) -> StageStats:
        stats = StageStats()
        clean_inserted = 0
        clean_updated = 0
        with self.RawSession() as raw_db, self.DBSession() as db:
            rows = (
                raw_db.query(RawBancada)
                .filter(
                    RawBancada.last_update.is_(True), RawBancada.processed.is_(False)
                )
                .all()
            )
            for raw_bancada in rows:
                try:
                    if raw_bancada.legislative_period not in [
                        "Parlamentario 2021 - 2026"
                    ]:
                        raw_bancada.processed = False
                        stats.skipped += 1
                        continue
                    bancadas, memberships = process_bancada(raw_bancada)
                    bancada_rows = [
                        (bancada.leg_year, bancada.bancada_name) for bancada in bancadas
                    ]
                    bancadas_index, inserted_count, existing_count = (
                        crud_core.upsert_bancadas_bulk(db, bancada_rows)
                    )
                    clean_inserted += inserted_count
                    clean_updated += existing_count

                    membership_rows: list[tuple[str, int, int]] = []
                    for ms in memberships:
                        leg_year_value = (
                            ms.leg_year.value
                            if hasattr(ms.leg_year, "value")
                            else ms.leg_year
                        )
                        cong = crud_core.find_congresista(
                            db,
                            name=ms.cong_name,
                            leg_period=find_leg_period(str(leg_year_value)),
                            website=ms.website,
                        )
                        bancada = bancadas_index.get(
                            (str(leg_year_value), ms.bancada_name.lower())
                        )
                        if cong is None or bancada is None:
                            stats.skipped += 1
                            continue
                        membership_rows.append(
                            (str(leg_year_value), cong.id, bancada.bancada_id)
                        )
                    crud_core.upsert_bancada_memberships_bulk(db, membership_rows)

                    raw_bancada.processed = True
                    stats.processed += 1
                except Exception as exc:
                    logger.exception(
                        f"Error processing RawBancada id={raw_bancada.id}: {exc}"
                    )
                    db.rollback()
                    stats.errors += 1

            db.commit()
            raw_db.commit()
        logger.info(
            f"[bancadas] raw_total={len(rows)} processed={stats.processed} skipped={stats.skipped} errors={stats.errors} clean_inserted={clean_inserted} clean_updated={clean_updated}"
        )
        return stats

    def _process_bills(
        self, *, include_documents: bool, limit: int | None
    ) -> StageStats:
        stats = StageStats()
        clean_inserted = 0
        clean_updated = 0
        with self.RawSession() as raw_db, self.DBSession() as db:
            query = raw_db.query(RawBill).filter(
                RawBill.last_update.is_(True), RawBill.processed.is_(False)
            )
            if limit is not None:
                query = query.limit(limit)
            rows = query.all()

            for raw_bill in rows:
                try:
                    bill_schema, bill_congs = process_bill(raw_bill)
                    pre = db.get(db_models.Bill, bill_schema.id)
                    bill = crud_bills.upsert_bill(db, bill_schema)
                    if pre is None:
                        clean_inserted += 1
                    else:
                        clean_updated += 1

                    for cong_rel in bill_congs:
                        cong = crud_core.find_congresista(
                            db,
                            name=cong_rel.nombre,
                            leg_period=cong_rel.leg_period,
                            website=cong_rel.web_page,
                        )
                        if cong is None:
                            stats.skipped += 1
                            continue
                        crud_bills.upsert_bill_congresista(
                            db, bill.id, cong.id, cong_rel.role_type
                        )

                    for comm in get_committees(raw_bill) or []:
                        org = crud_core.find_organization(
                            db=db,
                            org_name=comm.committee_name,
                            leg_period=bill_schema.leg_period,
                            leg_year=bill_schema.presentation_date.year,
                        )
                        if org is None:
                            stats.skipped += 1
                            continue
                        crud_bills.upsert_bill_committee(db, bill.id, org.org_id)

                    for step_schema in process_bill_steps(raw_bill) or []:
                        crud_bills.upsert_bill_step(
                            db,
                            step_schema.id,
                            bill.id,
                            step_schema.step_date,
                            step_schema.step_detail,
                            step_schema.step_status,
                        )

                    if include_documents:
                        for raw_doc in crud_bills.find_raw_bill_documents(
                            raw_db, bill.id
                        ):
                            doc = process_bill_document(raw_doc)
                            crud_bills.upsert_bill_document(
                                db,
                                doc.bill_id,
                                doc.step_id,
                                doc.archivo_id,
                                doc.url,
                                doc.text,
                                doc.vote_doc,
                            )
                            raw_doc.processed = True

                    raw_bill.processed = True
                    stats.processed += 1
                except Exception as exc:
                    logger.exception(
                        f"Error processing RawBill id={raw_bill.id}: {exc}"
                    )
                    db.rollback()
                    stats.errors += 1

            db.commit()
            raw_db.commit()
        logger.info(
            f"[bills] raw_total={len(rows)} processed={stats.processed} skipped={stats.skipped} errors={stats.errors} clean_inserted={clean_inserted} clean_updated={clean_updated}"
        )
        return stats

    def _process_motions(
        self, *, include_documents: bool, limit: int | None
    ) -> StageStats:
        stats = StageStats()
        clean_inserted = 0
        clean_updated = 0
        with self.RawSession() as raw_db, self.DBSession() as db:
            query = raw_db.query(RawMotion).filter(
                RawMotion.last_update.is_(True), RawMotion.processed.is_(False)
            )
            if limit is not None:
                query = query.limit(limit)
            rows = query.all()

            for raw_motion in rows:
                try:
                    motion_schema, motion_congs = process_motion(raw_motion)
                    pre = db.get(db_models.Motion, motion_schema.id)
                    motion = crud_motions.upsert_motion(db, motion_schema)
                    if pre is None:
                        clean_inserted += 1
                    else:
                        clean_updated += 1

                    for cong_rel in motion_congs:
                        cong = crud_core.find_congresista(
                            db,
                            name=cong_rel.nombre,
                            leg_period=cong_rel.leg_period,
                            website=cong_rel.web_page,
                        )
                        if cong is None:
                            stats.skipped += 1
                            continue
                        crud_motions.upsert_motion_congresista(
                            db, motion.id, cong.id, cong_rel.role_type
                        )

                    for step_schema in process_motion_steps(raw_motion) or []:
                        crud_motions.upsert_motion_step(
                            db,
                            step_id=step_schema.id,
                            motion_id=motion.id,
                            step_date=step_schema.step_date,
                            step_detail=step_schema.step_detail,
                            step_status=step_schema.step_status,
                        )

                    if include_documents:
                        for raw_doc in crud_motions.find_raw_motion_documents(
                            raw_db, motion.id
                        ):
                            doc = process_motion_document(raw_doc)
                            crud_motions.upsert_motion_document(
                                db,
                                motion_id=doc.motion_id,
                                step_id=doc.step_id,
                                archivo_id=doc.archivo_id,
                                url=doc.url,
                                text=doc.text,
                                vote_doc=doc.vote_doc,
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
            raw_db.commit()
        logger.info(
            f"[motions] raw_total={len(rows)} processed={stats.processed} skipped={stats.skipped} errors={stats.errors} clean_inserted={clean_inserted} clean_updated={clean_updated}"
        )
        return stats

    def _process_leyes(self, *, limit: int | None) -> StageStats:
        stats = StageStats()
        clean_inserted = 0
        clean_updated = 0
        with self.RawSession() as raw_db, self.DBSession() as db:
            query = raw_db.query(RawLey).filter(
                RawLey.last_update.is_(True), RawLey.processed.is_(False)
            )
            if limit is not None:
                query = query.limit(limit)
            rows = query.all()

            for raw_ley in rows:
                try:
                    ley_schema = process_leyes(raw_ley)
                    if ley_schema is None:
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
            raw_db.commit()
        logger.info(
            f"[leyes] raw_total={len(rows)} processed={stats.processed} skipped={stats.skipped} errors={stats.errors} clean_inserted={clean_inserted} clean_updated={clean_updated}"
        )
        return stats
