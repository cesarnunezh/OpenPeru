"""
Download congresista portrait images from `Congresista.photo_url` and store
them as bytes on the row's `photo_bytes` column.
"""

from __future__ import annotations

from loguru import logger
from sqlalchemy.orm import Session

from backend.database import models as db_models
from backend.scrapers.utils import get_url


_IMAGE_MAGIC: tuple[bytes, ...] = (
    b"\xff\xd8\xff",  # JPEG
    b"\x89PNG\r\n\x1a\n",  # PNG
)


def _looks_like_image(data: bytes) -> bool:
    return any(data.startswith(prefix) for prefix in _IMAGE_MAGIC)


def sync_photo(db: Session, congresista: db_models.Congresista) -> bool:
    """Download `photo_url` into `photo_bytes`. Skips if already populated."""
    if congresista.photo_bytes is not None:
        return False

    response = get_url(congresista.photo_url)
    if response is None:
        logger.warning(
            f"Could not download portrait for congresista {congresista.id}: {congresista.photo_url}"
        )
        return False

    data = response.content
    if not _looks_like_image(data):
        logger.warning(
            f"Response for congresista {congresista.id} doesn't look like an image (first 8 bytes: {data[:8]!r})"
        )
        return False

    congresista.photo_bytes = data
    db.flush()
    return True
