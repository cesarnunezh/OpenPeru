"""
Backfill portrait images for all congresistas that don't yet have an S3 key.

Downloads `Congresista.photo_url`, uploads to S3 under
`documents/congresistas/<id>.<ext>`, and records the key + timestamp.

Usage:
    python scripts/backfill_congresista_photos.py [--dry-run] [--limit N] [--force]

Options:
    --dry-run   Don't upload or write to the DB; just log what would happen.
    --limit N   Process at most N congresistas (useful for spot-checks).
    --force     Re-fetch even when photo_s3_key is already set.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loguru import logger
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend.config import settings
from backend.database import models as db_models
from backend.scrapers.congresista_photos import sync_photo


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.25,
        help="Seconds to sleep between downloads (default: 0.25).",
    )
    args = parser.parse_args()

    engine = create_engine(settings.DB_URL)
    Session = sessionmaker(bind=engine)

    stmt = select(db_models.Congresista).order_by(db_models.Congresista.id)
    if not args.force:
        stmt = stmt.where(db_models.Congresista.photo_s3_key.is_(None))
    if args.limit:
        stmt = stmt.limit(args.limit)

    updated = 0
    skipped = 0
    failed = 0

    with Session() as db:
        rows = db.scalars(stmt).all()
        logger.info(f"Processing {len(rows)} congresista(s) (dry_run={args.dry_run})")

        for cong in rows:
            try:
                changed = sync_photo(db, cong, force=args.force, dry_run=args.dry_run)
            except Exception as exc:
                logger.exception(
                    f"Photo sync failed for {cong.id} ({cong.full_name}): {exc}"
                )
                failed += 1
                db.rollback()
                continue

            if changed:
                updated += 1
                if not args.dry_run:
                    db.commit()
            else:
                skipped += 1

            if args.sleep > 0:
                time.sleep(args.sleep)

    logger.info(
        f"Done. updated={updated} skipped={skipped} failed={failed} "
        f"(dry_run={args.dry_run})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
