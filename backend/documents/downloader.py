from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from loguru import logger
from sqlalchemy.orm import Session

from backend.config import directories, settings
from backend.database.raw_models import RawBillDocument, RawMotionDocument
from backend.scrapers.utils import get_url


@dataclass
class DownloadStats:
    scanned: int = 0
    downloaded: int = 0
    skipped: int = 0
    errors: int = 0
    uploaded: int = 0


def _sanitize(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value)).strip("_")


def build_filename(parent_id: str, seguimiento_id: str, archivo_id: str) -> str:
    base = f"{_sanitize(parent_id)}-{_sanitize(seguimiento_id)}-{_sanitize(archivo_id)}"
    return f"{base}.pdf"


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


def _build_s3_key(kind: str, filename: str) -> str:
    parts = []
    if settings.AWS_S3_PREFIX:
        parts.append(settings.AWS_S3_PREFIX.strip("/"))
    parts.extend(["documents", kind, filename])
    return "/".join(parts)


def _upload_file_to_s3(path: Path, key: str) -> None:
    bucket = settings.AWS_S3_BUCKET_NAME
    if not bucket:
        raise RuntimeError("AWS_S3_BUCKET_NAME is not configured.")

    try:
        import boto3  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "boto3 is required for S3 uploads. Install it in the environment."
        ) from exc

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


def download_bill_documents(
    raw_db: Session,
    *,
    update: bool = False,
    upload_s3: bool = False,
    limit: int | None = None,
) -> DownloadStats:
    stats = DownloadStats()
    query = raw_db.query(RawBillDocument).filter(RawBillDocument.last_update.is_(True))
    if limit is not None:
        query = query.limit(limit)

    for doc in query.yield_per(200):
        stats.scanned += 1
        filename = build_filename(doc.bill_id, doc.seguimiento_id, doc.archivo_id)
        dest = directories.BILL_DOCUMENTS / filename

        if not dest.exists() or update:
            if _download_to_path(doc.url, dest):
                stats.downloaded += 1
            else:
                stats.errors += 1
                continue
        else:
            stats.skipped += 1

        if upload_s3 and dest.exists():
            key = _build_s3_key("bills", filename)
            _upload_file_to_s3(dest, key)
            stats.uploaded += 1

    return stats


def download_motion_documents(
    raw_db: Session,
    *,
    update: bool = False,
    upload_s3: bool = False,
    limit: int | None = None,
) -> DownloadStats:
    stats = DownloadStats()
    query = raw_db.query(RawMotionDocument).filter(
        RawMotionDocument.last_update.is_(True)
    )
    if limit is not None:
        query = query.limit(limit)

    for doc in query.yield_per(200):
        stats.scanned += 1
        filename = build_filename(doc.motion_id, doc.seguimiento_id, doc.archivo_id)
        dest = directories.MOTION_DOCUMENTS / filename

        if not dest.exists() or update:
            if _download_to_path(doc.url, dest):
                stats.downloaded += 1
            else:
                stats.errors += 1
                continue
        else:
            stats.skipped += 1

        if upload_s3 and dest.exists():
            key = _build_s3_key("motions", filename)
            _upload_file_to_s3(dest, key)
            stats.uploaded += 1

    return stats
