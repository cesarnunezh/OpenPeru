import argparse

from backend.database.orchestrator import OpenPeruOrchestrator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="OpenPeru ETL Orchestrator")
    parser.add_argument(
        "--scrape",
        action="store_true",
        help="Run scrapers before processing for rows with last scrape older than 1 day",
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
    target_group.add_argument(
        "--scrape-documents",
        action="store_true",
        help="Scrape pending bill/motion documents",
    )
    parser.add_argument(
        "--process-documents",
        action="store_true",
        help="Enable document processing stage",
    )
    parser.add_argument(
        "--first-summary",
        action="store_true",
        help="Computes the first processing of summaries for bills",
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
    run_documents = True

    if args.only_bills:
        run_motions = False
        run_others = False
        run_leyes = False
        run_documents = False
    elif args.only_motions:
        run_bills = False
        run_others = False
        run_leyes = False
        run_documents = False
    elif args.only_leyes:
        run_motions = False
        run_bills = False
        run_others = False
        run_documents = False
    elif args.only_others:
        run_bills = False
        run_motions = False
        run_leyes = False
        run_documents = False
    elif args.scrape_documents:
        run_bills = False
        run_motions = False
        run_leyes = False
        run_others = False

    if args.scrape:
        orchestrator.run_scrapers(
            scrape_bills=run_bills,
            scrape_motions=run_motions,
            scrape_leyes=run_leyes,
            scrape_others=run_others,
            only_current=args.only_current,
            scrape_documents=run_documents,
        )

    if not args.skip_processing:
        orchestrator.run_processing(
            process_bills=run_bills,
            process_motions=run_motions,
            process_leyes=run_leyes,
            process_others=run_others,
            process_documents=args.process_documents,
            first_load=args.first_summary,
        )
