import re
from loguru import logger
from datetime import datetime

from lxml.html import HtmlElement
from urllib.parse import urljoin

from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

from backend.config import settings
from backend.database.raw_models import RawCongresista
from backend.scrapers.utils import (
    parse_url,
    get_url_text,
    normalize_text,
    get_cong_website,
)

BASE_URL = "https://www3.congreso.gob.pe/pagina/congresistas"
API_MEMBERSHIP = "https://wb2server.congreso.gob.pe/vll/cargos/api/"
RAW_DB_PATH = settings.RAW_DB_URL


class RawCongresistasScraper:
    """
    Class to scrape congresistas raw data from the congress web page
    """

    def __init__(self):
        # Engine and session maker for DB
        self.engine = create_engine(RAW_DB_PATH)
        self.url = BASE_URL
        self.Session = sessionmaker(bind=self.engine)

        self.periods = {}
        self.raw_congresistas: list[RawCongresista] = []

    def get_dict_periodos(self):
        parse = parse_url(self.url)
        periodos = parse.xpath('//*[@name="idRegistroPadre"]/option')
        self.periods = {elem.text: elem.get("value") for elem in periodos}

    def extract_table(self, period) -> HtmlElement:
        parse = parse_url(self.url, {"idRegistroPadre": period})
        table = parse.xpath('//*[@class="congresistas"]')
        return table[0]

    def get_urls_from_table(self, period) -> list[str]:
        html = self.extract_table(period)
        cong_links = html.xpath(
            '//*[@class="congresistas"]//tr//td//*[@class="conginfo"]/@href'
        )
        return cong_links

    def get_profile_content(self, cong_link: str) -> str:
        full_url = self.url + cong_link
        return get_url_text(full_url)

    def _is_cargos_label(self, txt: str) -> bool:
        """
        Helper function to assert if the labels inside the webpage is related to cargos.
        We care about labels like: 'Cargos', 'Cargos del congresista', 'Cargos de la congresista', etc.
        """
        if "cargo" not in txt:
            return False
        # soft preference for congresista/parlamentario but we don't force it
        return True

    def _score_link_text(self, txt: str) -> int:
        """
        Higher score means that is more like what we want from the cargos url.
        """
        score = 0
        if "cargo" in txt:
            score += 2
        if "congres" in txt or "parlament" in txt:
            score += 2
        if "cargos del" in txt or "cargos de la" in txt:
            score += 1
        return score

    def get_best_cargos_link(self, doc: HtmlElement, base_url: str) -> str | None:
        """
        Method
        """
        # collect all <a> and <button> (just in case)
        candidates = doc.xpath("//a | //button")

        best_href = None
        best_score = -1

        for node in candidates:
            raw_text = node.text_content()
            txt = normalize_text(raw_text)

            if not self._is_cargos_label(txt):
                continue

            # try common URL carriers
            href = node.get("href") or node.get("data-href") or node.get("onclick")
            if not href:
                continue

            s = self._score_link_text(txt)
            if s > best_score:
                best_score = s
                best_href = href

        if best_href:
            return urljoin(base_url, best_href)

        # fallback: None found
        return None

    def create_raw_congresista(
        self, period: str, cong_link: str
    ) -> RawCongresista | None:
        profile_content = self.get_profile_content(cong_link)
        website = get_cong_website(profile_content)

        if period in [
            "Parlamentario 2001 - 2006",
            "Parlamentario 2000 - 2001",
            "Parlamentario 1995 - 2000",
            "CCD 1992 -1995",
        ]:
            return RawCongresista(
                timestamp=datetime.now(),
                leg_period=period,
                url=website,
                profile_content=profile_content,
                memberships_content=None,
            )
        else:
            html_cong = parse_url(website)
            cargos_url = self.get_best_cargos_link(html_cong, website)
            if not cargos_url:
                return RawCongresista(
                    timestamp=datetime.now(),
                    leg_period=period,
                    url=website,
                    profile_content=profile_content,
                    memberships_content=None,
                )
        try:
            cargos = parse_url(cargos_url)

            iframe = cargos.xpath('//*[@id="objContents"]/div[2]/p/iframe')
            if not iframe:
                raise IndexError("No iframe found in cargos page")
            api_call = iframe[0].get("src")
            match = re.search(r"(listar/)(.*)", api_call)
            if not match:
                raise ValueError(f"Invalid iframe src pattern: {api_call}")
            api_id = match.group(2)
        except (IndexError, ValueError, AttributeError, TypeError) as e:
            logger.warning(f"Failed to extract API ID for {cong_link}: {e}")
            logger.warning(f"Congresista partially extracted from {website}")
            return RawCongresista(
                timestamp=datetime.now(),
                leg_period=period,
                url=website,
                profile_content=profile_content,
                memberships_content=None,
            )

        memberships_content = get_url_text(API_MEMBERSHIP + api_id)

        raw_congresista = RawCongresista(
            timestamp=datetime.now(),
            leg_period=period,
            url=website,
            profile_content=profile_content,
            memberships_content=memberships_content,
        )
        logger.success(f"Congresista successfully extracted from {website}")
        return raw_congresista

    def extract_cong_from_period(
        self, period_key: str, period_value: str
    ) -> list[RawCongresista]:
        congresistas = []

        links = self.get_urls_from_table(period_value)
        for cong_link in links:
            new_cong = self.create_raw_congresista(period_key, cong_link)
            congresistas.append(self.update_tracking(new_cong))

        return congresistas

    def update_tracking(self, congresista: RawCongresista) -> RawCongresista:
        """Update the tracking columns of a RawCongresista object"""

        with self.Session() as session:
            last_congresista = (
                session.query(RawCongresista)
                .filter(RawCongresista.id == congresista.id)
                .order_by(RawCongresista.timestamp.desc())
                .first()
            )

            # First ever version of this congresista
            if last_congresista is None:
                congresista.changed = True
                congresista.last_update = True
                congresista.processed = False
            else:
                # Compare last vs new
                congresista.changed = congresista != last_congresista
                congresista.last_update = True
                congresista.processed = not congresista.changed

                # Update the old version AFTER comparison
                last_congresista.last_update = False
                session.add(last_congresista)
                session.commit()

            return congresista

    def extract_and_load_all(self, only_current: bool = False) -> list[RawCongresista]:
        assert self.periods, (
            "You need to extract all the available periods before extracting the tables"
        )

        periods = self.periods
        if only_current:
            first = next(iter(self.periods.items()), None)
            periods = dict([first]) if first else {}

        for period, value in periods.items():
            self.raw_congresistas = self.extract_cong_from_period(period, value)
            self.add_congresistas_to_db()

        return self.raw_congresistas

    def add_congresistas_to_db(self) -> bool:
        """
        Add the raw congresistas to the database.
        Returns True on success, False on failure
        """

        assert self.raw_congresistas, (
            "Congresistas must be scraped before it can be saved"
        )

        session = self.Session()

        try:
            session.bulk_save_objects(self.raw_congresistas)
            session.commit()
            logger.success(
                f"Added {len(self.raw_congresistas)} congresistas to Raw Congresistas table"
            )
            return True
        except SQLAlchemyError as e:
            logger.error(f"Failed to add committees: {str(e)}")
            session.rollback()
            return False
        finally:
            # Close Session
            session.close()


if __name__ == "__main__":
    scraper = RawCongresistasScraper()
    scraper.get_dict_periodos()
    scraper.extract_and_load_all()
