from lxml.html import fromstring
from urllib.parse import urljoin

from backend import LegislativeYear, find_leg_period
from backend.database.raw_models import RawBancada
from backend.process.schema import Bancada, BancadaMembership

from backend.process.utils import get_current_leg_year

CONGRESO_BASE_URL = "https://www.congreso.gob.pe"
LEGACY_CONGRESO_BASE_URL = "https://www3.congreso.gob.pe"


def get_url_text(url: str, data: str | None = None) -> str | None:
    from backend.scrapers.utils import get_url_text as _get_url_text

    return _get_url_text(url, data)


def get_cong_website(profile_content: str) -> str | None:
    from backend.scrapers.utils import get_cong_website as _get_cong_website

    return _get_cong_website(profile_content)


def _build_profile_url(web_profile: str) -> str:
    """
    Normalize congresista profile links from both current path-style and legacy
    query-string style hrefs.
    """
    if web_profile.startswith(("http://", "https://")):
        return web_profile

    if web_profile.startswith(("/pagina/?", "pagina/?")):
        return urljoin(f"{LEGACY_CONGRESO_BASE_URL}/", web_profile.lstrip("/"))

    if "?" in web_profile:
        query = web_profile.split("?", 1)[1]
        return f"{LEGACY_CONGRESO_BASE_URL}/pagina/?{query}"

    return urljoin(CONGRESO_BASE_URL, web_profile)


def process_bancada(
    raw_bancada: RawBancada,
) -> tuple[list[Bancada], list[BancadaMembership]]:
    """
    Process a RawBancada instance into a Bancada instance and a list of BancadaMemberships
    that maps all the congresistas who belongs to the Bancada at a specific legislative year

    Args:
        raw_bancada (RawBancada): RawBancada instance that contains all the bancadas and membership for a specific period

    Returns:
        tuple[Bancada, list[BancadaMembership]]: Bancada instance and the list of BancadaMemberships
    """

    html = fromstring(raw_bancada.raw_html)

    rows = html.xpath('//*[@class="table-cng"]/tbody/tr')

    membership_list = []
    bancadas_lst = []
    for row in rows:
        childs = row.getchildren()
        if len(childs) == 1:
            # Bancada
            bancada = childs[0].xpath(".//h2")[0].text_content().title()
            leg_year = get_current_leg_year(str(raw_bancada.timestamp))
            current_leg_period = find_leg_period(leg_year)

            if raw_bancada.legislative_period != current_leg_period:
                # On past periods -> Use the last year from LegPeriod
                leg_year = LegislativeYear(
                    str(int(raw_bancada.legislative_period[-4:]) - 1)
                )

            bancadas_lst.append(Bancada(leg_year=leg_year, bancada_name=bancada))

        else:
            # Congresista
            name = row.xpath('.//*[@class="conginfo"]')[0].text
            web_profile = row.xpath('.//*[@class="conginfo"]/@href')[0]

            parsed_website = get_url_text(_build_profile_url(web_profile))
            website = get_cong_website(parsed_website)

            membership_list.append(
                BancadaMembership(
                    leg_year=leg_year,
                    cong_name=name,
                    website=website,
                    bancada_name=bancada,
                )
            )

    return bancadas_lst, membership_list
