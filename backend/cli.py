import argparse
from loguru import logger

from backend.config import (
    directories,
    stop_logging_to_console,
    resume_logging_to_console,
)
from backend.database.orchestrator import (
    OpenPeruOrchestrator,
    StageStats,
    DownloadStats,
)


def _print_summary(summary: dict[str, StageStats]) -> None:
    total_processed = 0
    total_skipped = 0
    total_errors = 0
    for stage, stats in summary.items():
        logger.info(
            f"{stage}: processed={stats.processed}, skipped={stats.skipped}, errors={stats.errors}"
        )
        total_processed += stats.processed
        total_skipped += stats.skipped
        total_errors += stats.errors
    logger.info(
        f"total: processed={total_processed}, skipped={total_skipped}, errors={total_errors}"
    )


def _print_document_summary(summary: dict[str, DownloadStats]) -> None:
    total_scanned = 0
    total_downloaded = 0
    total_skipped = 0
    total_errors = 0
    total_uploaded = 0
    for stage, stats in summary.items():
        logger.info(
            f"{stage}: scanned={stats.scanned}, downloaded={stats.downloaded}, skipped={stats.skipped}, errors={stats.errors}, uploaded={stats.uploaded}"
        )
        total_scanned += stats.scanned
        total_downloaded += stats.downloaded
        total_skipped += stats.skipped
        total_errors += stats.errors
        total_uploaded += stats.uploaded
    logger.info(
        "documents_total: "
        f"scanned={total_scanned}, downloaded={total_downloaded}, "
        f"skipped={total_skipped}, errors={total_errors}, uploaded={total_uploaded}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="OpenPeru ETL Orchestrator")
    parser.add_argument(
        "--scrape",
        action="store_true",
        help="Run scrapers before processing",
    )
    parser.add_argument(
        "--skip-processing",
        action="store_true",
        help="Do not run raw->clean processing",
    )
    parser.add_argument(
        "--only-current",
        action="store_true",
        help="Scrape only current period where supported",
    )
    parser.add_argument(
        "--weekly-days",
        type=int,
        default=7,
        help="Refresh stale non-approved bills/motions older than this many days",
    )
    parser.add_argument(
        "--others-days",
        type=int,
        default=7,
        help="Skip congresistas/bancadas/committees/organizations scrape when latest raw scrape is within this many days",
    )
    target_group = parser.add_mutually_exclusive_group()
    target_group.add_argument(
        "--only-bills",
        action="store_true",
        help="Run only bills scraping/processing",
    )
    target_group.add_argument(
        "--only-motions",
        action="store_true",
        help="Run only motions scraping/processing",
    )
    target_group.add_argument(
        "--only-leyes",
        action="store_true",
        help="Run only leyes scraping/processing",
    )
    target_group.add_argument(
        "--only-others",
        action="store_true",
        help="Run only non-bill/non-motion entities (congresistas, bancadas, organizations)",
    )
    parser.add_argument("--bill-year", type=int)
    parser.add_argument("--bill-start", type=int)
    parser.add_argument("--bill-end", type=int)
    parser.add_argument("--motion-year", type=int)
    parser.add_argument("--motion-start", type=int)
    parser.add_argument("--motion-end", type=int)
    parser.add_argument("--ley-start", type=int)
    parser.add_argument("--ley-end", type=int)
    parser.add_argument(
        "--scrape-documents",
        action="store_true",
        help="Scrape pending bill/motion documents",
    )
    parser.add_argument(
        "--download-documents",
        action="store_true",
        help="Download PDF documents from RawDB links",
    )
    parser.add_argument(
        "--download-documents-limit",
        type=int,
        help="Limit the number of documents downloaded per type (bills/motions)",
    )
    parser.add_argument(
        "--update-documents",
        action="store_true",
        help="Re-download documents even if they already exist locally",
    )
    parser.add_argument(
        "--upload-documents-s3",
        action="store_true",
        help="Upload downloaded documents to the configured AWS S3 bucket",
    )
    parser.add_argument(
        "--no-documents",
        action="store_true",
        help="Skip loading documents in processing stage",
    )
    parser.add_argument(
        "--process-bills-limit",
        type=int,
        help="Limit the number of bill raw rows processed",
    )
    parser.add_argument(
        "--process-motions-limit",
        type=int,
        help="Limit the number of motion raw rows processed",
    )
    parser.add_argument(
        "--process-leyes-limit",
        type=int,
        help="Limit the number of leyes raw rows processed",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    orchestrator = OpenPeruOrchestrator()
    run_bills = True
    run_motions = True
    run_leyes = True
    run_others = True

    if args.only_bills:
        run_motions = False
        run_others = False
        run_leyes = False
    elif args.only_motions:
        run_bills = False
        run_others = False
        run_leyes = False
    elif args.only_leyes:
        run_motions = False
        run_bills = False
        run_others = False
    elif args.only_others:
        run_bills = False
        run_motions = False
        run_leyes = False

    if args.scrape:
        stop_logging_to_console(filename=directories.LOGS / "run_scrapers.log")
        orchestrator.run_scrapers(
            scrape_bills=run_bills,
            scrape_motions=run_motions,
            scrape_leyes=run_leyes,
            scrape_others=run_others,
            only_current=args.only_current,
            weekly_days=args.weekly_days,
            others_days=args.others_days,
            bill_year=args.bill_year,
            bill_start=args.bill_start,
            bill_end=args.bill_end,
            motion_year=args.motion_year,
            motion_start=args.motion_start,
            motion_end=args.motion_end,
            ley_start=args.ley_start,
            ley_end=args.ley_end,
            scrape_documents=args.scrape_documents,
        )
        resume_logging_to_console()

    if args.download_documents:
        stop_logging_to_console(
            filename=directories.LOGS / "run_document_downloads.log"
        )
        doc_summary = orchestrator.run_document_downloads(
            download_bills=run_bills,
            download_motions=run_motions,
            update=args.update_documents,
            upload_s3=args.upload_documents_s3,
            limit=args.download_documents_limit,
        )
        resume_logging_to_console()
        _print_document_summary(doc_summary)

    if not args.skip_processing:
        stop_logging_to_console(filename=directories.LOGS / "run_processing.log")
        summary = orchestrator.run_processing(
            process_bills=run_bills,
            process_motions=run_motions,
            process_leyes=run_leyes,
            process_others=run_others,
            include_documents=not args.no_documents,
            bills_limit=args.process_bills_limit,
            motions_limit=args.process_motions_limit,
            leyes_limit=args.process_leyes_limit,
        )
        resume_logging_to_console()
        _print_summary(summary)
