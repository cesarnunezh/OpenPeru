from unittest.mock import patch

from backend.scrapers import congresista_photos as mod


# ---------- format sniffing ----------


def test_looks_like_image_accepts_jpeg():
    assert mod._looks_like_image(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00")


def test_looks_like_image_accepts_png():
    assert mod._looks_like_image(b"\x89PNG\r\n\x1a\n" + b"\x00" * 8)


def test_looks_like_image_rejects_other():
    assert not mod._looks_like_image(b"GIF89a...")
    assert not mod._looks_like_image(b"<!DOCTYPE html>")
    assert not mod._looks_like_image(b"")


# ---------- sync_photo ----------


class _StubCong:
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", 1)
        self.photo_url = kwargs.get("photo_url", "https://www.congreso.gob.pe/x.jpg")
        self.photo_bytes = kwargs.get("photo_bytes", None)


class _StubSession:
    def __init__(self):
        self.flushed = 0

    def flush(self):
        self.flushed += 1


class _StubResponse:
    def __init__(self, content: bytes):
        self.content = content


def test_sync_photo_skips_when_bytes_present():
    cong = _StubCong(photo_bytes=b"\xff\xd8\xff" + b"\x00" * 16)
    db = _StubSession()
    assert mod.sync_photo(db, cong) is False
    assert db.flushed == 0


def test_sync_photo_writes_bytes_on_success():
    jpeg = b"\xff\xd8\xff" + b"\x00" * 32
    cong = _StubCong()
    db = _StubSession()

    with patch.object(mod, "get_url", return_value=_StubResponse(jpeg)):
        assert mod.sync_photo(db, cong) is True

    assert cong.photo_bytes == jpeg
    assert db.flushed == 1


def test_sync_photo_returns_false_when_download_fails():
    cong = _StubCong()
    db = _StubSession()

    with patch.object(mod, "get_url", return_value=None):
        assert mod.sync_photo(db, cong) is False

    assert cong.photo_bytes is None
    assert db.flushed == 0


def test_sync_photo_rejects_non_image_response():
    cong = _StubCong()
    db = _StubSession()

    with patch.object(mod, "get_url", return_value=_StubResponse(b"<html>404</html>")):
        assert mod.sync_photo(db, cong) is False

    assert cong.photo_bytes is None
    assert db.flushed == 0
