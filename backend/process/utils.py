import re
import json
import polars as pl

from backend import PARTY_ALIASES
from backend.config import directories
from sqlalchemy.orm import Session
from backend.database.raw_models import RawBill, RawMotion


def extract_text(text: str, initial: str = None, final: str = None) -> str:
    """
    Extracts the text between an specified initial and final texts. The initial
    or the final text could be optional, but not both

    Args:
        - text: original text
        - initial: initial part of the text to start
        - final: final part of the text to stop the extraction
    """
    assert initial or final, "Must specify either initial or final text"

    if initial and final:
        pattern = re.compile(f"{re.escape(initial)}(.*?){re.escape(final)}", re.DOTALL)
    elif initial and not final:
        pattern = re.compile(f"({re.escape(initial)})(.*)", re.DOTALL)
    else:
        pattern = re.compile(f"(.*?){re.escape(final)}", re.DOTALL)
    result = re.search(pattern, text)

    if not final:
        return result.group(2)
    else:
        return result.group(1)


def normalize_party_name(name: str) -> str:
    if name in PARTY_ALIASES.keys():
        canonical_name = PARTY_ALIASES[name]
        return canonical_name
    return name


def gen_congresistas_df(session: Session) -> None:
    bills_congresistas = session.query(RawBill.congresistas).distinct().all()
    motions_congresistas = session.query(RawMotion.congresistas).distinct().all()

    all_cong = []

    for (json_str,) in bills_congresistas + motions_congresistas:
        try:
            parsed = json.loads(json_str)
            if isinstance(parsed, list):
                all_cong.extend(parsed)
        except json.JSONDecodeError:
            continue

    unique_by_congresista = {
        d["congresistaId"]: d for d in all_cong if "congresistaId" in d
    }

    df = pl.DataFrame(list(unique_by_congresista.values()))

    df.write_json(directories.PROCESSED_DATA / "cong_info_2021_2026.json")

    return None


from datetime import datetime
from backend import LegislativeYear


def get_current_leg_year(timestamp: str) -> LegislativeYear:
    dt = datetime.fromisoformat(timestamp)
    year = dt.year

    cutoff = datetime(year, 7, 28)
    if dt < cutoff:
        # Before 28th July
        return LegislativeYear(str(year - 1))
    else:
        # After 28th July
        return LegislativeYear(str(year))
