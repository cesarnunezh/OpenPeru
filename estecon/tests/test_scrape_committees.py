import pytest
from lxml.html import fromstring, HtmlElement
from unittest.mock import patch, MagicMock
from estecon.backend import LegPeriod
from estecon.backend.scrapers.scrape_committees import (
    get_options,
    get_html_with_selections,
    get_or_create_org,
    get_committees,
    ORG_ID_MAP
)

# Sample HTML for select inputs
HTML_WITH_SELECT = '''
<html>
    <body>
        <select name="idRegistroPadre">
            <option value="1">2021</option>
            <option value="2">2022</option>
        </select>
        <select name="fld_78_Comision">
            <option value="10">Permanent</option>
        </select>
    </body>
</html>
'''

@pytest.fixture
def html_with_committees():
    html = '''
    <html>
        <table class="congresistas">
            <tbody>
                <tr><td><a href="https://example.com/com1">Comisión de Salud</a></td></tr>
                <tr><td><a href="https://example.com/com2">Comisión de Economía</a></td></tr>
            </tbody>
        </table>
    </html>
    '''
    return fromstring(html)

def test_get_options():
    with patch('estecon.backend.scrapers.scrape_committees.parse_url') as mock_parse:
        mock_parse.return_value = fromstring(HTML_WITH_SELECT)

        year_opts = get_options("dummy_url", "idRegistroPadre")
        assert year_opts == {"2021": "1", "2022": "2"}

        type_opts = get_options("dummy_url", "fld_78_Comision")
        assert type_opts == {"Permanent": "10"}

@patch('estecon.backend.scrapers.scrape_committees.webdriver.Chrome')
@patch('estecon.backend.scrapers.scrape_committees.Select')
def test_get_html_with_selections(mock_select, mock_webdriver):
    # Create dummy mocks for Select
    mock_select_instance = MagicMock()
    mock_select.return_value = mock_select_instance

    # Mock driver and its behavior
    mock_driver = MagicMock()
    mock_driver.page_source = HTML_WITH_SELECT
    mock_driver.find_element.side_effect = [MagicMock(tag_name='select'), MagicMock(tag_name='select')]
    mock_webdriver.return_value = mock_driver

    # Call function
    html = get_html_with_selections("dummy_url", "2021", "10")

    # Assertions
    assert isinstance(html, HtmlElement)
    assert html.cssselect("select[name='idRegistroPadre']")

    # Check Select usage
    mock_select.assert_called()
    mock_select_instance.select_by_value.assert_any_call("2021")
    mock_select_instance.select_by_value.assert_any_call("10")

def test_get_or_create_org_new():
    ORG_ID_MAP.clear()
    global ORG_COUNTER
    ORG_COUNTER = 1

    org = get_or_create_org(
        "Comisión de Transportes",
        LegPeriod.PERIODO_2021_2026,
        "2021-2022",
        "https://example.com"
    )
    assert org.org_id == 1
    assert org.org_name == "comisión de transportes"
    assert ORG_ID_MAP["comisión de transportes"] == 1

def test_get_or_create_org_existing():
    ORG_ID_MAP.clear()
    global ORG_COUNTER
    ORG_ID_MAP["comisión de justicia"] = 5
    ORG_COUNTER = 6

    org = get_or_create_org(
        "Comisión de Justicia",
        LegPeriod.PERIODO_2021_2026,
        "2022-2023",
        "https://example.com"
    )
    assert org.org_id == 5
    assert org.org_name == "comisión de justicia"

def test_get_committees(html_with_committees):
    ORG_ID_MAP.clear()
    global ORG_COUNTER
    ORG_COUNTER = 1

    committees = get_committees(html_with_committees, LegPeriod.PERIODO_2021_2026, "2021-2022")
    assert len(committees) == 2
    assert committees[0].org_name == "comisión de salud"
    assert committees[1].org_url == "https://example.com/com2"