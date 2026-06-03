import sys
import types
from types import SimpleNamespace

import pytest


def mock_chandra2_vllm(url: str):
    print(f"Mock OCR used for source: {url}")
    return [{"page_num": 1, "text": "[mock] OCR output"}]


class _DummyBatchInputItem:
    def __init__(self, image, prompt_type):
        self.image = image
        self.prompt_type = prompt_type


def _install_chandra_schema_stub(monkeypatch):
    schema_module = types.ModuleType("chandra.model.schema")
    schema_module.BatchInputItem = _DummyBatchInputItem
    model_module = types.ModuleType("chandra.model")
    model_module.schema = schema_module
    chandra_module = types.ModuleType("chandra")
    chandra_module.model = model_module

    monkeypatch.setitem(sys.modules, "chandra", chandra_module)
    monkeypatch.setitem(sys.modules, "chandra.model", model_module)
    monkeypatch.setitem(sys.modules, "chandra.model.schema", schema_module)


def test_mock_chandra2_vllm_returns_single_page():
    pages = mock_chandra2_vllm("https://example.com/doc.pdf")

    assert pages == [{"page_num": 1, "text": "[mock] OCR output"}]


def test_normalize_congreso_url_rewrites_api():
    from backend.process import chandra2 as mod

    url = "https://wb2server.congreso.gob.pe/path/to/doc.pdf"

    assert (
        mod._normalize_congreso_url(url)
        == "https://api.congreso.gob.pe/path/to/doc.pdf"
    )


def test_chandra2_vllm_invalid_url_raises(monkeypatch):
    from backend.process import chandra2 as mod

    _install_chandra_schema_stub(monkeypatch)

    with pytest.raises(ValueError, match="Expected an HTTP"):
        mod.chandra2_vllm("ftp://example.com/doc.pdf")


def test_chandra2_vllm_download_fail_raises(monkeypatch):
    from backend.process import chandra2 as mod

    _install_chandra_schema_stub(monkeypatch)
    monkeypatch.setattr(mod, "get_url", lambda _url: None)

    with pytest.raises(RuntimeError, match="Failed to download PDF"):
        mod.chandra2_vllm("https://example.com/doc.pdf")


class _DummySession:
    def __init__(self):
        self.added = []
        self.committed = False
        self.scalar_calls = 0
        self.get_calls = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def scalar(self, *args, **kwargs):
        self.scalar_calls += 1
        return None

    def add(self, obj):
        self.added.append(obj)

    def get(self, *args, **kwargs):
        self.get_calls += 1
        return None

    def commit(self):
        self.committed = True


class _DummySessionFactory:
    def __init__(self, session):
        self._session = session

    def __call__(self):
        return self._session


def test_write_raw_bill_pages_uses_mock_ocr(monkeypatch):
    from backend.process import chandra2 as mod

    dummy_session = _DummySession()
    monkeypatch.setattr(mod, "chandra2_vllm", mock_chandra2_vllm)

    doc = SimpleNamespace(
        bill_id="PL_1",
        step_id="1",
        file_id="1",
        url="https://example.com/doc.pdf",
    )

    created = mod.write_raw_bill_pages(
        _DummySessionFactory(dummy_session),
        [doc],
        ocr_model="chandra2",
    )

    assert created == 1
    assert dummy_session.committed is True
    assert len(dummy_session.added) == 1
    assert dummy_session.added[0].text == "[mock] OCR output"
