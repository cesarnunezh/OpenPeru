import pytest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from estecon.backend.scrapers.scrape_project_bills import (
    get_authors_and_adherents,
    get_steps,
    get_committees,
    is_vote_file,
    cached_get_file_text,
    scrape_bill
)
from estecon.backend.scrapers.schema import BillStep, Bill

# --- Sample Fixtures ---

@pytest.fixture
def sample_data():
    path = Path(__file__).parent / "sample_bill_data.json"
    return json.loads(path.read_text(encoding="utf-8"))

@pytest.fixture
def fake_pdf_text_vote():
    return "SESIÓN DE PLENO\nSI ++\nNO --\nRESULTADO"

@pytest.fixture
def fake_pdf_text_nonvote():
    return "Sesión ordinaria del Pleno. Informe presentado..."

# --- Unit Tests ---

def test_get_authors_and_adherents(sample_data):
    lead, coauthors, adherents = get_authors_and_adherents(sample_data["data"])
    assert lead["name"]
    assert isinstance(coauthors, list)
    assert isinstance(adherents, list)

def test_get_steps(sample_data, fake_pdf_text_vote):
    with patch("estecon.backend.scrapers.scrape_project_bills.cached_get_file_text", return_value=fake_pdf_text_vote):
        steps = get_steps(sample_data, 2021, "1234")
        assert isinstance(steps, list)
        for step in steps:
            assert isinstance(step, BillStep)

def test_get_committees(sample_data):
    committees = get_committees(sample_data, "Primera Legislatura Ordinaria 2024")
    assert isinstance(committees, list)
    for c in committees:
        assert "name" in c and "id" in c and "leg_year" in c

def test_is_vote_file(fake_pdf_text_vote, fake_pdf_text_nonvote):
    assert is_vote_file(fake_pdf_text_vote) is True
    assert is_vote_file(fake_pdf_text_nonvote) is False

def test_cached_get_file_text(tmp_path):
    fake_url = "https://example.com/fake.pdf"
    fake_path = tmp_path / "ocr_cache" / "fake.txt"
    fake_path.parent.mkdir(parents=True, exist_ok=True)
    fake_path.write_text("Cached Text")

    with patch("estecon.backend.scrapers.scrape_project_bills.url_to_cache_file", return_value=fake_path), \
         patch("estecon.backend.scrapers.scrape_project_bills.render_pdf", return_value="New Rendered Text"), \
         patch("estecon.backend.scrapers.scrape_project_bills.save_ocr_txt_to_cache") as mock_save:

        # Should use cache
        text = cached_get_file_text(fake_url)
        assert text == "Cached Text"
        assert not mock_save.called

        # Delete cache and test fallback
        fake_path.unlink()
        text = cached_get_file_text(fake_url)
        assert text == "New Rendered Text"
        assert mock_save.called

@patch("estecon.backend.scrapers.scrape_project_bills.httpx.get")
@patch("estecon.backend.scrapers.scrape_project_bills.cached_get_file_text", return_value="Texto completo de la ley")
def test_scrape_bill(mock_cache_text, mock_httpx_get, sample_data):
    mock_httpx_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"data": sample_data["data"]}
    )
    result = scrape_bill("2021", "1234")
    assert isinstance(result[0], Bill)
    assert isinstance(result[1], tuple)
    assert isinstance(result[2], list)
    assert isinstance(result[3], list)