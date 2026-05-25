"""
Helpers for downloading congresista portrait images and uploading them to S3.

The source URLs come from `Congresista.photo_url`. The Peruvian congress site
sometimes returns 404 on the `www.congreso.gob.pe` host but serves the same
asset under `www3.congreso.gob.pe`, so a retry against the alternate host is
attempted before giving up.
"""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlparse, urlunparse

from loguru import logger
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import models as db_models
from backend.scrapers.bills_documents import RawBillDocumentScraper
from backend.scrapers.utils import get_url


# (magic-byte prefix, file extension, content-type)
_IMAGE_MAGIC: tuple[tuple[bytes, str, str], ...] = (
    (b"\xff\xd8\xff", "jpg", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "png", "image/png"),
)


def sniff_image_format(data: bytes) -> tuple[str, str] | None:
    """Return (extension, content_type) for jpeg/png bytes, or None if unsupported."""
    for prefix, ext, mime in _IMAGE_MAGIC:
        if data.startswith(prefix):
            return ext, mime
    return None


def _swap_to_www3(url: str) -> str | None:
    """Return the same URL with `www.congreso.gob.pe` swapped for `www3`, else None."""
    parsed = urlparse(url)
    if parsed.netloc != "www.congreso.gob.pe":
        return None
    return urlunparse(parsed._replace(netloc="www3.congreso.gob.pe"))


def download_portrait(url: str) -> bytes | None:
    """
    Download an image from `url`. If a `www.congreso.gob.pe` URL fails, retry
    against `www3.congreso.gob.pe`. Returns the raw bytes on success, None on
    failure.
    """
    response = get_url(url)
    if response is None:
        alt = _swap_to_www3(url)
        if alt is None:
            return None
        logger.info(f"Retrying portrait download against {alt}")
        response = get_url(alt)
        if response is None:
            return None
    return response.content


def build_portrait_s3_key(congresista_id: int, ext: str) -> str:
    """Compose the S3 key under documents/congresistas/<id>.<ext>."""
    parts: list[str] = []
    if settings.AWS_S3_PREFIX:
        parts.append(settings.AWS_S3_PREFIX.strip("/"))
    parts.extend(["documents", "congresistas", f"{congresista_id}.{ext}"])
    return "/".join(parts)


def sync_photo(
    db: Session,
    congresista: db_models.Congresista,
    *,
    force: bool = False,
    dry_run: bool = False,
) -> bool:
    """
    Download `congresista.photo_url`, upload to S3, persist key + timestamp.

    Skips if `photo_s3_key` is already set unless `force=True`. Returns True
    when the row was updated (or would be under dry-run), False otherwise.
    """
    if congresista.photo_s3_key and not force:
        return False
    if not congresista.photo_url:
        return False

    data = download_portrait(congresista.photo_url)
    if data is None:
        logger.warning(
            f"Could not download portrait for congresista {congresista.id}: "
            f"{congresista.photo_url}"
        )
        return False

    sniffed = sniff_image_format(data)
    if sniffed is None:
        logger.warning(
            f"Unsupported image format for congresista {congresista.id} "
            f"(first 8 bytes: {data[:8]!r})"
        )
        return False

    ext, content_type = sniffed
    key = build_portrait_s3_key(congresista.id, ext)

    if dry_run:
        logger.info(
            f"[dry-run] would upload {len(data)} bytes to "
            f"s3://{settings.AWS_S3_BUCKET_NAME}/{key} ({content_type})"
        )
        return True

    RawBillDocumentScraper.upload_bytes_to_s3(data, key, content_type=content_type)

    congresista.photo_s3_key = key
    congresista.photo_fetched_at = datetime.now(timezone.utc)
    db.flush()
    return True
