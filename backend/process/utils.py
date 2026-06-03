import re
import json
import polars as pl
from datetime import datetime, timezone, date
from sqlalchemy.orm import Session
from operator import attrgetter

from backend import PARTY_ALIASES, LEGAL_TERMS
from backend.config import directories
from backend.database.raw_models import RawBill, RawMotion
from backend.process.schema import (
    BillStep,
    MotionStep,
    BillOrganization,
    MotionOrganization,
)


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


def to_datetime(value):
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        # API sometimes returns milliseconds.
        ts = value / 1000 if value > 10_000_000_000 else value
        return datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None)
    if isinstance(value, str) and value.isdigit():
        num = int(value)
        ts = num / 1000 if num > 10_000_000_000 else num
        return datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None)
    if isinstance(value, str):
        txt = value.strip().replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(txt).replace(tzinfo=None)
        except ValueError:
            return None
    return None


def gen_congresistas_df(session: Session, save: bool = False) -> None:
    """
    Extracts additional information from congresistas that are not in their
    profile page, but in the bills responses.

    Saves a JSON file at the processed directory.

    Args:
        session (Session): database Session
    """
    bills_congresistas = (
        session.query(RawBill.congresistas).filter(RawBill.last_update).distinct().all()
    )
    motions_congresistas = (
        session.query(RawMotion.congresistas)
        .filter(RawMotion.last_update)
        .distinct()
        .all()
    )
    all_cong = []

    for (json_str,) in bills_congresistas + motions_congresistas:
        try:
            parsed = json.loads(json_str)
            if isinstance(parsed, list):
                all_cong.extend(parsed)
        except json.JSONDecodeError:
            continue

    unique_by_congresista = {
        d["congresistaId"]: d
        for d in all_cong
        if ("congresistaId" in d) and ("dni" in d)
    }

    df = pl.DataFrame(list(unique_by_congresista.values()))

    if save:
        df.write_json(directories.PROCESSED_DATA / "cong_info_2021_2026.json")

    return df


def get_current_leg_year(value: str | date | datetime | None = None) -> int:
    """
    Return the congressional legislative year for a given date.

    The legislative year starts on July 27.
    For example:
        2025-07-26 -> 2024
        2025-07-27 -> 2025
        2026-05-06 -> 2025
    """

    if value is None:
        dt = date.today()

    elif isinstance(value, datetime):
        dt = value.date()

    elif isinstance(value, date):
        dt = value

    elif isinstance(value, str):
        dt = datetime.fromisoformat(value).date()

    else:
        raise TypeError(
            f"value must be str, date, datetime, or None. Got {type(value).__name__}"
        )

    cutoff = date(dt.year, 7, 27)

    if dt >= cutoff:
        return dt.year

    return dt.year - 1


def create_vote_ids(
    step_list: list[BillStep | MotionStep],
) -> list[BillStep | MotionStep]:
    """
    Generate deterministic vote event IDs for a bill.

    Vote steps are first sorted by date. Each vote event is then assigned an ID
    using the format `<bill_id>_<n>`, where `n` represents the vote event's
    position in the sorted sequence.

    Args:
        step_list (list[BillStep | MotionStep]): Steps associated with a bill
        or motion.

    Returns:
        list[BillStep | MotionStep]: Sorted steps, with vote event IDs assigned
        to vote steps.
    """
    # Sorting steps based on step date
    sorted_list = sorted(step_list, key=attrgetter("step_date"))

    final_list = []
    vote_step_counter = 0
    for step in sorted_list:
        # In case is a vote_step, then it creates their vote_event_id
        if step.vote_step:
            vote_step_counter += 1
            if isinstance(step, BillStep):
                vote_id = f"B_{step.bill_id}_{vote_step_counter}"
            elif isinstance(step, MotionStep):
                vote_id = f"M_{step.motion_id}_{vote_step_counter}"
            step.vote_event_id = vote_id

        final_list.append(step)

    return final_list


def split_and_sort_name(name: str) -> tuple[str, str, str]:
    try:
        last_name, first_name = [sub.strip() for sub in name.split(",")]
        full_name = f"{first_name} {last_name}"
        return full_name, first_name, last_name
    except ValueError:
        return name, None, None


def find_organization_schema(
    orgs: list[BillOrganization | MotionOrganization],
    *,
    org_name: str,
    org_type: str,
) -> BillOrganization | MotionOrganization | None:
    return next(
        (
            org
            for org in orgs
            if org.org_name == org_name
            and (org.org_type.value if hasattr(org.org_type, "value") else org.org_type)
            == org_type
        ),
        None,
    )


def as_date(value: date | datetime | None) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    return value


def replace_www(url: str | None) -> str:
    if not url:
        return ""

    return re.sub(
        r"^(https?://)?www\.",
        lambda m: (m.group(1) or "") + "www3.",
        url,
    )


def get_sentence_case(source: str) -> str:
    output = ""
    is_first_word = True

    for c in source:
        if is_first_word and not c.isspace():
            c = c.upper()
            is_first_word = False
        elif not is_first_word and c in ".!?":
            is_first_word = True
        else:
            c = c.lower()

        output += c

    # Fix legal terms that should keep title capitalization
    for pattern, replacement in LEGAL_TERMS.items():
        output = re.sub(pattern, replacement, output, flags=re.IGNORECASE)

    # Fix N° only when it appears before a number
    output = re.sub(
        r"(?<!\w)n\s*(?:°|º|\.º)?(?=\s*\d)",
        "N°",
        output,
        flags=re.IGNORECASE,
    )

    return output
