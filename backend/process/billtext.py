from __future__ import annotations
import re
# Mirrors data/raw/billtext.sqlite3-query: uppercase-only search on both
# accented and unaccented heading forms; body cut before the earliest trailing
# marker; slice returned from the original raw text.

_FORMAT_CHARS = str.maketrans(
    {
        "*": " ",
        "_": " ",
        "#": " ",
        "`": " ",
        "“": '"',
        "”": '"',
    }
)

_START_AFTER_RE = (
    "CON EL SIGUIENTE TEXTO SUSTITUTORIO",
    "PRESENTA EL SIGUIENTE PROYECTO DE LEY",
    "PROPONE PARA SU APROBACIÓN EL SIGUIENTE PROYECTO DE LEY",
    "PROPONE PARA SU APROBACION EL SIGUIENTE PROYECTO DE LEY",
)

_HEADINGS_RE: tuple[re.Pattern[str], ...] = (
    # Autógrafa / final legal formula
    re.compile(
        r"EL\s+CONGRESO\s+DE\s+LA\s+REP[ÚU]BLIC[AА][,;]?\s+"
        r"HA\s+DADO\s+LA\s+LEY\s+SIGUIENTE:?\s*"
    ),
    re.compile(
        r"EL\s+CONGRESO\s+DE\s+LA\s+REP[ÚU]BLIC[AА][,;]?\s+"
        r"HA\s+DADO\s+LA\s+SIGUIENTE\s+LEY:?\s*"
    ),
    re.compile(
        r"EL\s+CONGRESO\s+DE\s+LA\s+REP[ÚU]BLIC[AА][,;]?\s+"
        r"HA\s+DADO\s+LA\s+RESOLUCI[ÓO]N\s+LEGISLATIVA\s+DEL\s+CONGRESO\s+"
        r"SIGUIENTE:?\s*"
    ),
    re.compile(
        r"EL\s+CONGRESO\s+DE\s+LA\s+REP[ÚU]BLIC[AА][,;]?\s+"
        r"HA\s+DADO\s+LA\s+RESOLUCI[ÓO]N\s+LEGISLATIVA\s+SIGUIENTE:?\s*"
    ),
    re.compile(
        r"EL\s+CONGRESO\s+DE\s+LA\s+REP[ÚU]BLIC[AА][,;]?\s+"
        r"HA\s+DADO\s+LA\s+SIGUIENTE\s+RESOLUCI[ÓO]N\s+LEGISLATIVA:?\s*"
    ),
    # Dictamen bill text
    re.compile(r"TEXTO\s+SUSTITUTORIO:?\s*"),
    re.compile(r"TEXTO\s+SUSTITUTORIO\s+SIGUIENTE[.:]?\s*"),
    # Dictamen conclusion before the substitute text
    re.compile(r"CON\s+EL\s+SIGUIENTE\s+TEXTO\s+SUSTITUTORIO:?\s*"),
    # Original proposals: "presenta/propone el siguiente proyecto de ley"
    re.compile(r"PRESENTA\s+EL\s+SIGUIENTE\s+PROYECTO\s+DE\s+LEY:?\s*"),
    re.compile(r"PRESENTA\s+LA\s+SIGUIENTE\s+INICIATIVA\s+LEGISLATIVA[.:]?\s*"),
    re.compile(
        r"PROPONE\s+PARA\s+SU\s+APROBACI[ÓO]N\s+EL\s+SIGUIENTE\s+"
        r"PROYECTO\s+DE\s+LEY(?:\s+MULTIPARTIDARIO)?[.:]?\s*"
    ),
    # You already had these
    re.compile(r"F[ÓO]RMULA\s+LEGAL:?\s*"),
    re.compile(r"PROYECTO\s+DE\s+RESOLUCI[ÓO]N\s+LEGISLATIVA:?\s*"),
)

_MONTHS_RE = (
    r"(?:ENERO|FEBRERO|MARZO|ABRIL|MAYO|JUNIO|JULIO|AGOSTO|"
    r"SETIEMBRE|SEPTIEMBRE|OCTUBRE|NOVIEMBRE|DICIEMBRE)"
)

_SPANISH_WORDS_RE = r"[A-ZÁÉÍÓÚÜÑ]+(?:\s+[A-ZÁÉÍÓÚÜÑ]+){0,8}"

_YEAR_RE = rf"(?:\d{{4}}|{_SPANISH_WORDS_RE})"

_LIMA_DATE_RE = re.compile(
    rf"(?:EN\s+)?LIMA,?\s*"
    rf"(?:"
    # Example: En Lima, a los dieciséis días del mes de diciembre de dos mil veinticinco
    rf"(?:A\s+LOS?\s+)?"
    rf"(?:\d{{1,2}}|{_SPANISH_WORDS_RE})\s+"
    rf"(?:D[IÍ]AS?\s+)?"
    rf"(?:DEL\s+MES\s+)?"
    rf"DE\s+{_MONTHS_RE}\s+"
    rf"DE\s+{_YEAR_RE}"
    rf"|"
    # Example: Lima, enero del 2025 / Lima, enero de 2025
    rf"(?:A\s+)?"
    rf"{_MONTHS_RE}\s+"
    rf"(?:DE|DEL)\s+"
    rf"{_YEAR_RE}"
    rf")"
    rf"\.?"
)

_END_MARKERS_RE: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"COMUN[IÍ]QUESE\s+AL\s+SEÑOR\s+PRESIDENTE\s+DE\s+LA\s+REP[ÚU]BLICA\s+"
        r"PARA\s+SU\s+PROMULGACI[ÓO]N\.?\s*"
    ),
    _LIMA_DATE_RE,
    re.compile(r"EXPOSICI[ÓO]N\s+DE\s+MOTIVOS"),
)


def _should_start_after(match_text: str) -> bool:
    text = match_text.upper()
    return any(marker in text for marker in _START_AFTER_RE)


def normalize_bill_text(s: str) -> str:
    """
    Uppercase search form.

    Replaces Markdown formatting chars with spaces so indices still match raw_text.
    """
    return s.upper().translate(_FORMAT_CHARS)


def _earliest_match(
    haystack: str,
    patterns: tuple[re.Pattern[str], ...],
    min_pos: int = 0,
) -> re.Match[str] | None:
    """Return the earliest regex match found in haystack."""
    matches = [
        match
        for pattern in patterns
        if (match := pattern.search(haystack, pos=min_pos)) is not None
    ]

    if not matches:
        return None

    return min(matches, key=lambda match: match.start())


def extract_bill_body(raw_text: str) -> str | None:
    """Return the raw-text slice from the first heading, trimmed before any end marker."""
    if not (raw_text or "").strip():
        return None

    norm = normalize_bill_text(raw_text)

    start_match = _earliest_match(norm, _HEADINGS_RE)
    if start_match is None:
        return None

    if "SIGUIENTE" in start_match.group():
        start = (
            start_match.end()
            if _should_start_after(start_match.group())
            else start_match.start()
        )
    else:
        start = start_match.start()

    # min_pos=1: ignore an end marker that appears exactly at the heading start.
    end_match = _earliest_match(norm[start:], _END_MARKERS_RE, min_pos=1)

    if end_match is None:
        return raw_text[start:].strip()

    return raw_text[start : start + end_match.start()].strip()
