from __future__ import annotations

import re
import unicodedata
from backend.core.constants import (
    BILL_ROLE_MAPS,
    LEG_PERIOD_ALIASES,
    LEGISLATURE_ALIASES,
)
from backend.core.enums import (
    BillStepType,
    LegPeriod,
    LegislativeYear,
    Legislature,
    MotionStepType,
    MotionType,
    Proponents,
    RoleOrganization,
    RoleTypeBill,
)


def _normalize_leg_period(value: str) -> str:
    # 1) Unicode normalize (handles odd forms)
    v = unicodedata.normalize("NFKC", value)

    # 2) Replace non-breaking spaces and other common weird spaces with normal space
    v = v.replace("\xa0", " ").replace("\u202f", " ").replace("\u2007", " ")

    v = v.strip()

    # 3) normalize different dash characters to "-"
    v = re.sub(r"[–—−]", "-", v)

    # 4) normalize spaces around dash
    v = re.sub(r"\s*-\s*", "-", v)

    # 5) collapse multiple spaces
    v = re.sub(r"\s+", " ", v)

    return v


LEG_PERIOD_RE = re.compile(r"(\d{4})-(\d{4})")


def parse_leg_period(value: str) -> LegPeriod:
    if value is None:
        raise ValueError("leg_period cannot be null")

    v = _normalize_leg_period(value)

    canon = LEG_PERIOD_ALIASES.get(v)
    if canon is None:
        m = LEG_PERIOD_RE.search(v)
        if m:
            canon = f"{m.group(1)}-{m.group(2)}"

    if canon is None:
        raise ValueError(f"Unknown leg period: {value!r} (normalized={v!r})")

    return LegPeriod(canon)


def _normalize_legislature(value: str) -> str:
    v = value.strip()
    v = re.sub(r"\s+", " ", v)  # collapse whitespace
    return v


def parse_legislature(value: str) -> Legislature:
    if value is None:
        raise ValueError("legislature cannot be null")

    v = _normalize_legislature(value)
    canon = LEGISLATURE_ALIASES.get(v)

    if canon is None:
        raise ValueError(f"Unknown legislature: {value!r}")

    return Legislature(canon)


def parse_role_bill(value: int) -> RoleTypeBill:
    if value is None:
        raise ValueError("role_bill cannot be null")

    canon = BILL_ROLE_MAPS.get(value)
    if canon is None:
        raise ValueError(f"Unknown role_bill: {value!r}")
    return RoleTypeBill(canon)


def parse_motion_type(value: str) -> MotionType:
    if value is None:
        raise ValueError("motion_type cannot be null")

    v = " ".join(value.strip().split())

    # Direct match for scalar enum values.
    for item in MotionType:
        if isinstance(item.value, str) and item.value == v:
            return item

    # Handle the multi-value case for COMISION_INVESTIGADORA.
    if v in MotionType.COMISION_INVESTIGADORA.value:
        return MotionType.COMISION_INVESTIGADORA

    raise ValueError(f"Unknown motion_type: {value!r}")


def parse_proponent(value: str) -> Proponents:
    if value is None:
        raise ValueError("proponent cannot be null")

    v = " ".join(value.strip().split())

    try:
        return Proponents(v)
    except ValueError:
        pass

    # Handle suffixes like "Congreso-Actualización"
    if "-" in v:
        head = v.split("-", 1)[0].strip()
        try:
            return Proponents(head)
        except ValueError:
            pass

    raise ValueError(f"Unknown proponent: {value!r}")


DES_ESTADO_TO_MOTION_STEP_TYPE: dict[str, MotionStepType] = {
    # Presented
    "Presentado": MotionStepType.PRESENTED,
    # Admitted / not admitted
    "Admitida la Moción": MotionStepType.ADMITTED,
    "NO ADMITIDA A DEBATE": MotionStepType.REJECTED,
    "RECHAZADA LA ADMISIÓN A DEBATE": MotionStepType.REJECTED,
    # Assigned / in committee
    "En Comisión": MotionStepType.ASSIGNED,
    "Integrantes de Comisión": MotionStepType.ASSIGNED,
    "Aprobado integrantes de Comisión": MotionStepType.ASSIGNED,
    # Agenda / internal routing (CD = Consejo Directivo)
    "En Agenda C.D": MotionStepType.AGENDA,
    "PARA SER VISTA POR EL CONSEJO DIRECTIVO": MotionStepType.INTERNAL_ROUTE,
    "Tramitada con conocimiento del CD": MotionStepType.INTERNAL_ROUTE,
    "TRAMITADA CON ACUERDO DE CD": MotionStepType.INTERNAL_ROUTE,
    "Por Acuerdo de CD.": MotionStepType.INTERNAL_ROUTE,
    "Acuerdo Junta de Portavoces": MotionStepType.INTERNAL_ROUTE,
    # Pleno routing / agenda
    "Para ser vista por el Pleno": MotionStepType.AGENDA,
    "En Agenda del Pleno": MotionStepType.AGENDA,
    "Orden del Día": MotionStepType.AGENDA,
    "Dado cuenta en el Pleno": MotionStepType.INTERNAL_ROUTE,
    "Por Acuerdo de Pleno": MotionStepType.INTERNAL_ROUTE,
    # Debate
    "En Debate": MotionStepType.DEBATE,
    "Leída en sesión": MotionStepType.DEBATE,
    # Vote-ish / outcomes
    "Aprobada": MotionStepType.APPROVED,
    "Aprobada la Moción": MotionStepType.APPROVED,
    "Rechazada": MotionStepType.REJECTED,
    # Reconsideration
    "Reconsideración": MotionStepType.RECONSIDERATION,
    "Rechazada Reconsideración": MotionStepType.RECONSIDERATION,  # still a reconsideration event
    # Text updates
    "Texto consensuado": MotionStepType.TEXT_UPDATE,
    "Texto Sustitutorio": MotionStepType.TEXT_UPDATE,
    "Retiro de Firma": MotionStepType.WITHDRAWN,
    "Adhesión": MotionStepType.TEXT_UPDATE,  # signature/support update
    # Official comms / documents
    "Oficio": MotionStepType.OFFICIAL_COMMUNICATION,
    # Publication
    "Publicado Diario Oficial  El Peruano": MotionStepType.PUBLISHED,
    # Appearances (minister, etc.)
    "Concurre Ministro": MotionStepType.APPEARANCE,
    "Asiste": MotionStepType.APPEARANCE,
    "Asistió el Ministro  para contestar el pliego.": MotionStepType.APPEARANCE,
    # Order / procedural
    "Cuestión de Orden": MotionStepType.DISCIPLINE_OR_ORDER,
    # Requirements / blocking status
    "INCUMPLE REQUISITOS PARA CONTINUAR SU TRÁMITE": MotionStepType.REQUIREMENTS_BLOCK,
    # Withdrawal
    "Solicita retiro de moción": MotionStepType.WITHDRAWN,
    "RETIRADA POR SU AUTOR": MotionStepType.WITHDRAWN,
    # Archive
    "Al archivo": MotionStepType.ARCHIVED,
    "En Archivo General": MotionStepType.ARCHIVED,
    # Resignation (if applicable in your domain)
    "Renuncia": MotionStepType.RESIGNATION,
    # External routing / referrals
    "En Fiscalía de la Nación": MotionStepType.INTERNAL_ROUTE,
}


def classify_motion_des_estado(des_estado: str | None) -> MotionStepType:
    if not des_estado:
        return MotionStepType.UNKNOWN

    key = " ".join(des_estado.strip().split())  # trim + collapse whitespace
    return (
        DES_ESTADO_TO_MOTION_STEP_TYPE.get(key)
        or DES_ESTADO_TO_MOTION_STEP_TYPE.get(key.upper())
        or DES_ESTADO_TO_MOTION_STEP_TYPE.get(key.title())
        or MotionStepType.UNKNOWN
    )


DES_ESTADO_TO_STEP_TYPE: dict[str, BillStepType] = {
    "------": BillStepType.UNKNOWN,
    # Presented
    "PRESENTADO": BillStepType.PRESENTED,
    # Assigned / committee routing
    "EN COMISIÓN": BillStepType.ASSIGNED,
    "PASA A COMISIÓN": BillStepType.ASSIGNED,
    "RETORNA A COMISIÓN": BillStepType.ASSIGNED,
    "Acumulado en Sala": BillStepType.INTERNAL_ROUTE,
    # Committee stage artifacts / decisions
    "DICTAMEN": BillStepType.COMMITTEE_STAGE,
    "ACUERDO DE COMISIÓN": BillStepType.COMMITTEE_STAGE,
    # Exemptions / procedural shortcuts
    "Dispensado de Dictamen": BillStepType.EXEMPTION,
    "EXONERADO DE DICTAMEN": BillStepType.EXEMPTION,
    "EXONERADO DE PLAZO DE PUBLICACIÓN": BillStepType.EXEMPTION,
    "Dispensado de Publicación en el Portal": BillStepType.EXEMPTION,
    # Agenda
    "Orden del Día": BillStepType.AGENDA,
    "EN AGENDA DEL PLENO": BillStepType.AGENDA,
    "EN AGENDA DE LA COMISIÓN PERMANENTE": BillStepType.AGENDA,
    # Debate
    "EN DEBATE - PLENO": BillStepType.DEBATE,
    "EN DEBATE - COMISIÓN PERMANENTE": BillStepType.DEBATE,
    "EN DEBATE DE LA COMISIÓN PERMANENTE": BillStepType.DEBATE,
    # Vote events
    "APROBADO 1ERA. VOTACIÓN": BillStepType.VOTE,
    "Pendiente 2da. votación": BillStepType.VOTE,
    "No alcanzó Nº de votos": BillStepType.VOTE,
    "NO APROBADO": BillStepType.VOTE,
    # Approval outcomes
    "APROBADO": BillStepType.APPROVED,
    "Aprobado Com.Permanente ": BillStepType.APPROVED,
    "ACUERDO DEL PLENO": BillStepType.APPROVED,
    # Text / autographs (post-approval drafting)
    "TEXTO SUSTITUTORIO": BillStepType.TEXT_UPDATE,
    "AUTÓGRAFA": BillStepType.TEXT_UPDATE,
    "AUTÓGRAFA OBSERVADA": BillStepType.TEXT_UPDATE,
    "Retiro de Firma": BillStepType.TEXT_UPDATE,  # could also be WITHDRAWN depending on how you interpret it
    # Reconsideration
    "EN RECONSIDERACIÓN": BillStepType.RECONSIDERATION,
    # Rejection
    "RECHAZADO": BillStepType.REJECTED,
    # Withdrawal
    "Retirado por su Autor": BillStepType.WITHDRAWN,
    "Solicita Retiro": BillStepType.WITHDRAWN,
    # Archive
    "Al Archivo": BillStepType.ARCHIVED,
    "DECRETO DE ARCHIVO": BillStepType.ARCHIVED,
    # Promulgation / publication
    "Promulgado/Presidente de la República": BillStepType.PROMULGATED,
    "Promulgado/Presidente del Congreso": BillStepType.PROMULGATED,
    "Publicada en el Diario Oficial El Peruano": BillStepType.PUBLISHED,
    # Clarification / internal routing
    "ACLARACIÓN": BillStepType.CLARIFICATION,
    "EN CUARTO INTERMEDIO": BillStepType.INTERNAL_ROUTE,
    "PARA CONSEJO DIRECTIVO": BillStepType.INTERNAL_ROUTE,
}


def classify_des_estado(des_estado: str | None) -> BillStepType:
    if not des_estado:
        return BillStepType.UNKNOWN

    key = " ".join(des_estado.strip().split())  # trim + collapse whitespace
    # keep original casing keys in mapping, but also try upper
    return DES_ESTADO_TO_STEP_TYPE.get(key) or DES_ESTADO_TO_STEP_TYPE.get(
        key.upper(), BillStepType.UNKNOWN
    )


def find_leg_period(leg_year: LegislativeYear):
    int_year = int(leg_year)

    if int_year in range(2026, 2031):
        return parse_leg_period("Parlamentario 2026 - 2031")
    if int_year in range(2021, 2026):
        return parse_leg_period("Parlamentario 2021 - 2026")
    if int_year in range(2016, 2021):
        return parse_leg_period("Parlamentario 2016 - 2021")
    if int_year in range(2011, 2016):
        return parse_leg_period("Parlamentario 2011 - 2016")
    if int_year in range(2006, 2011):
        return parse_leg_period("Parlamentario 2006 - 2011")
    if int_year in range(2001, 2006):
        return parse_leg_period("Parlamentario 2001 - 2006")
    if int_year in range(2000, 2001):
        return parse_leg_period("Parlamentario 2000 - 2001")
    if int_year in range(1995, 2000):
        return parse_leg_period("Parlamentario 1995 - 2000")
    return parse_leg_period("CCD 1992 -1995")


def normalize_membership_role(raw: str) -> str:
    if not raw:
        raise ValueError("Empty membership role")

    role = raw.strip().lower()

    role_map = {
        "presidenta": "presidente",
        "presidente": "presidente",
        "vicepresidenta": "vicepresidente",
        "vicepresidente": "vicepresidente",
        "secretaria": "secretario",
        "secretario": "secretario",
        "vocera": "vocero",
        "vocero": "vocero",
        "miembro": "miembro",
        "titular": "titular",
        "suplente": "suplente",
        "accesitaria": "accesitario",
        "accesitario": "accesitario",
    }

    canon = role_map.get(role)

    if canon is None:
        raise ValueError(f"Unknown role: {role!r}")

    return RoleOrganization(canon)


def _norm_text(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    s = s.replace("\xa0", " ").replace("\u202f", " ").replace("\u2007", " ")
    s = s.strip()
    s = re.sub(r"\s+", " ", s)
    return s


# Canonical outputs must exactly match your enum values
_COMM_TYPE_RULES: list[tuple[re.Pattern[str], str]] = [
    # Most specific first
    (
        re.compile(r"^sub\s*comisi[oó]n\s+de\s+acusaciones\s+constitucionales", re.I),
        "Subcomisión de Acusaciones Constitucionales",
    ),
    (
        re.compile(r"^sub\s*comisi[oó]n\s+de\s+control\s+pol[ií]tico", re.I),
        "Subcomisión de Control Político",
    ),
    (
        re.compile(
            r"^comisi[oó]n\s+de\s+levantamiento\s+de\s+inmunidad\s+parlamentaria", re.I
        ),
        "Comisión de Levantamiento de Inmunidad Parlamentaria",
    ),
    (
        re.compile(r"^comisi[oó]n\s+de\s+[eé]tica\s+parlamentaria", re.I),
        "Comisión de Ética Parlamentaria",
    ),
    (
        re.compile(r"^sub\s*comisi[oó]n\s+de\s+seguimiento\s+del\s+tlc", re.I),
        "Sub Comisión de Seguimiento del TLC",
    ),
    # Common noisy cases
    (re.compile(r"^comisi[oó]n\s+ordinaria\b", re.I), "Comisión Ordinaria"),
    (
        re.compile(r"^comisiones?\s+investigadoras?\b", re.I),
        "Comisiones Investigadoras",
    ),
    (re.compile(r"^comisiones?\s+especiales?\b", re.I), "Comisiones Especiales"),
    (re.compile(r"^grupo\s+de\s+trabajo\b", re.I), "Grupo de Trabajo"),
]


def parse_comm_type(value: str) -> str:
    raw = value
    v = _norm_text(value)

    # normalize dash variants (optional, but consistent with your style)
    v = re.sub(r"[–—−]", "-", v)

    for pat, canon in _COMM_TYPE_RULES:
        if pat.search(v):
            return canon

    raise ValueError(f"Unknown comm_type: {raw!r} (normalized={v!r})")
