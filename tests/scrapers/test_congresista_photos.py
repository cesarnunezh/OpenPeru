from unittest.mock import patch


from backend.scrapers import congresista_photos as mod


# ---------- magic-byte sniffing ----------


def test_sniff_image_format_jpeg():
    data = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00"
    assert mod.sniff_image_format(data) == ("jpg", "image/jpeg")


def test_sniff_image_format_png():
    data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
    assert mod.sniff_image_format(data) == ("png", "image/png")


def test_sniff_image_format_unsupported():
    assert mod.sniff_image_format(b"GIF89a...") is None
    assert mod.sniff_image_format(b"<!DOCTYPE html>") is None
    assert mod.sniff_image_format(b"") is None


# ---------- S3 key construction ----------


def test_build_portrait_s3_key_without_prefix():
    with patch.object(mod.settings, "AWS_S3_PREFIX", None):
        assert mod.build_portrait_s3_key(42, "jpg") == "documents/congresistas/42.jpg"


def test_build_portrait_s3_key_with_prefix():
    with patch.object(mod.settings, "AWS_S3_PREFIX", "/staging/"):
        assert (
            mod.build_portrait_s3_key(7, "png")
            == "staging/documents/congresistas/7.png"
        )


# ---------- host swap fallback ----------


def test_swap_to_www3_matches_only_www_host():
    assert (
        mod._swap_to_www3("https://www.congreso.gob.pe/foo/bar.jpg")
        == "https://www3.congreso.gob.pe/foo/bar.jpg"
    )
    assert mod._swap_to_www3("https://www3.congreso.gob.pe/foo.jpg") is None
    assert mod._swap_to_www3("https://other.example.com/foo.jpg") is None


def test_download_portrait_falls_back_to_www3():
    primary = "https://www.congreso.gob.pe/foo.jpg"
    fallback = "https://www3.congreso.gob.pe/foo.jpg"

    class _Resp:
        content = b"image-bytes"

    def fake_get_url(url):
        if url == primary:
            return None
        if url == fallback:
            return _Resp()
        raise AssertionError(f"unexpected url: {url}")

    with patch.object(mod, "get_url", side_effect=fake_get_url):
        assert mod.download_portrait(primary) == b"image-bytes"


def test_download_portrait_returns_none_when_both_fail():
    with patch.object(mod, "get_url", return_value=None):
        assert mod.download_portrait("https://www.congreso.gob.pe/foo.jpg") is None


def test_download_portrait_no_fallback_for_other_hosts():
    calls = []

    def fake_get_url(url):
        calls.append(url)
        return None

    with patch.object(mod, "get_url", side_effect=fake_get_url):
        result = mod.download_portrait("https://other.example.com/foo.jpg")

    assert result is None
    assert calls == ["https://other.example.com/foo.jpg"]


# ---------- sync_photo end-to-end (with mocked S3) ----------


class _StubCong:
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", 1)
        self.full_name = kwargs.get("full_name", "Test Person")
        self.photo_url = kwargs.get("photo_url", "https://www3.congreso.gob.pe/x.jpg")
        self.photo_s3_key = kwargs.get("photo_s3_key", None)
        self.photo_fetched_at = kwargs.get("photo_fetched_at", None)


class _StubSession:
    def __init__(self):
        self.flushed = 0

    def flush(self):
        self.flushed += 1


def test_sync_photo_skips_when_key_present():
    cong = _StubCong(photo_s3_key="documents/congresistas/1.jpg")
    db = _StubSession()
    assert mod.sync_photo(db, cong) is False
    assert db.flushed == 0


def test_sync_photo_uploads_and_sets_fields():
    cong = _StubCong(id=99)
    db = _StubSession()
    jpeg_bytes = b"\xff\xd8\xff" + b"\x00" * 32

    with (
        patch.object(mod, "download_portrait", return_value=jpeg_bytes),
        patch.object(mod.RawBillDocumentScraper, "upload_bytes_to_s3") as mock_upload,
        patch.object(mod.settings, "AWS_S3_PREFIX", None),
    ):
        assert mod.sync_photo(db, cong) is True

    mock_upload.assert_called_once()
    _, kwargs = mock_upload.call_args
    args, _ = mock_upload.call_args
    assert args[0] == jpeg_bytes
    assert args[1] == "documents/congresistas/99.jpg"
    assert kwargs["content_type"] == "image/jpeg"

    assert cong.photo_s3_key == "documents/congresistas/99.jpg"
    assert cong.photo_fetched_at is not None
    assert db.flushed == 1


def test_sync_photo_dry_run_does_not_upload_or_persist():
    cong = _StubCong(id=5)
    db = _StubSession()
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32

    with (
        patch.object(mod, "download_portrait", return_value=png_bytes),
        patch.object(mod.RawBillDocumentScraper, "upload_bytes_to_s3") as mock_upload,
    ):
        assert mod.sync_photo(db, cong, dry_run=True) is True

    mock_upload.assert_not_called()
    assert cong.photo_s3_key is None
    assert cong.photo_fetched_at is None
    assert db.flushed == 0


def test_sync_photo_rejects_unsupported_format():
    cong = _StubCong()
    db = _StubSession()

    with (
        patch.object(mod, "download_portrait", return_value=b"GIF89a..."),
        patch.object(mod.RawBillDocumentScraper, "upload_bytes_to_s3") as mock_upload,
    ):
        assert mod.sync_photo(db, cong) is False

    mock_upload.assert_not_called()
    assert cong.photo_s3_key is None


def test_sync_photo_returns_false_when_download_fails():
    cong = _StubCong()
    db = _StubSession()

    with patch.object(mod, "download_portrait", return_value=None):
        assert mod.sync_photo(db, cong) is False
    assert cong.photo_s3_key is None
