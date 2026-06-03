from enum import Enum


class MajorityType(str, Enum):
    SIMPLE = "simple"
    ABSOLUTE = "absolute"
    QUALIFIED = "qualified"


class VoteResult(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    TIED = "tied"
    NO_QUORUM = "no_quorum"
    SUSPENDED = "suspended"  # cuarto intermedio
    RETURNED_TO_COMMITTEE = "returned_to_committee"
    FILED = "filed"
    WITHDRAWN = "withdrawn"


class VoteOption(str, Enum):
    SI = "si"
    NO = "no"
    ABSTENCION = "abstencion"
    SIN_RESPUESTA = "sin respuesta"


class AttendanceStatus(str, Enum):
    PRESENTE = "presente"
    AUSENTE = "ausente"
    LICENCIA = "con licencia"
    SUSPENDIDO = "suspendido"


class MotionType(str, Enum):
    SALUDO = "Saludo"
    CENSURA_MESA = "Censura Mesa Directiva del Congreso"
    CENSURA_MINISTRO = "Censura al Consejo de Ministros"
    INTERES = "Interés Nacional"
    INTERPELACION = "Interpelación"
    INFORME_MINISTROS = "Invitación a Ministros para Informar"
    VACANCIA = "Vacancia"
    COMISION_INVESTIGADORA = [
        "Otorgar Facultades de Comisión Investigadora",
        "Comisiones Investigadoras",
    ]
    COMISION_ESPECIAL = "Comisiones Especiales"
    PESAR = "Pesar"
    OTRAS = "Otras"


class MotionStepType(str, Enum):
    UNKNOWN = "unknown"

    # Intake / start
    PRESENTED = "presented"
    ADMITTED = "admitted to debate"

    # Routing / admin handling
    ASSIGNED = "assigned"
    INTERNAL_ROUTE = "internal routing"
    AGENDA = "agenda"

    # Deliberation
    DEBATE = "debate"
    VOTE = "vote"
    APPROVED = "approved"
    REJECTED = "rejected"

    # Reconsideration
    RECONSIDERATION = "reconsideration"

    # Text / documents
    TEXT_UPDATE = "text update"
    OFFICIAL_COMMUNICATION = "official communication"

    # Attendance / appearances (minister, etc.)
    APPEARANCE = "appearance"

    # Other outcomes
    WITHDRAWN = "withdrawn"
    ARCHIVED = "archived"
    PUBLISHED = "published"
    RESIGNATION = "resignation"
    DISCIPLINE_OR_ORDER = "question of order"
    REQUIREMENTS_BLOCK = "requirements not met"


class BillStepType(str, Enum):
    UNKNOWN = "unknown"
    PRESENTED = "presented"
    ASSIGNED = "assigned to committee"
    COMMITTEE_STAGE = "committee stage"
    AGENDA = "agenda"
    DEBATE = "debate"
    VOTE = "vote"
    RECONSIDERATION = "reconsideration"
    APPROVED = "approved"
    REJECTED = "rejected"
    TEXT_UPDATE = "text update"
    WITHDRAWN = "withdrawn"
    ARCHIVED = "archived"
    PROMULGATED = "promulgated"
    PUBLISHED = "published"
    CLARIFICATION = "clarification"
    INTERNAL_ROUTE = "internal routing"
    EXEMPTION = "exemption"


class RoleTypeBill(str, Enum):
    AUTHOR = "author"
    COAUTHOR = "coauthor"
    ADHERENTE = "adherente"


class Proponents(str, Enum):
    CONGRESO = "Congreso"
    PODER_EJECUTIVO = "Poder Ejecutivo"
    MINISTERIO_PUBLICO = "Ministerio Público"
    DEFENSORIA = "Defensoría del Pueblo"
    JNE = "Jurado Nacional de Elecciones"
    CONTRALORIA = "Contraloría General de la República"
    TRIBUNAL_CONSTITUCIONAL = "Tribunal Constitucional"
    BANCO_CENTRAL = "Banco Central de Reserva"
    SBS = "Superintendencia de Banca y Seguros"
    COLEGIOS_PROF = "Colegios Profesionales"
    INI_CIUDADANA = "Iniciativas Ciudadanas"
    PODER_JUDICIAL = "Poder Judicial"
    GORES = "Gobiernos Regionales"
    GOLOS = "Gobiernos Locales"
    JNJ = "Junta Nacional de Justicia"


class LegPeriod(str, Enum):
    PERIODO_2026_2031 = "2026-2031"
    PERIODO_2021_2026 = "2021-2026"
    PERIODO_2016_2021 = "2016-2021"
    PERIODO_2011_2016 = "2011-2016"
    PERIODO_2006_2011 = "2006-2011"
    PERIODO_2001_2006 = "2001-2006"
    PERIODO_2000_2001 = "2000-2001"
    PERIODO_1995_2000 = "1995-2000"
    PERIODO_1992_1995 = "1992-1995"


class Legislature(str, Enum):
    LEGISLATURA_2026_1 = "2026-I"
    LEGISLATURA_2025_2 = "2025-II"
    LEGISLATURA_2025_1 = "2025-I"
    LEGISLATURA_2024_2 = "2024-II"
    LEGISLATURA_2024_1 = "2024-I"
    LEGISLATURA_2023_2 = "2023-II"
    LEGISLATURA_2023_1 = "2023-I"
    LEGISLATURA_2022_2 = "2022-II"
    LEGISLATURA_2022_1 = "2022-I"
    LEGISLATURA_2021_2 = "2021-II"
    LEGISLATURA_2021_1 = "2021-I"
    LEGISLATURA_2020_2 = "2020-II"
    LEGISLATURA_2020_1 = "2020-I"
    LEGISLATURA_2019_2 = "2019-II"
    LEGISLATURA_2019_1 = "2019-I"
    LEGISLATURA_2018_2 = "2018-II"
    LEGISLATURA_2018_1 = "2018-I"
    LEGISLATURA_2017_2 = "2017-II"
    LEGISLATURA_2017_1 = "2017-I"
    LEGISLATURA_2016_2 = "2016-II"


class LegislativeYear(str, Enum):
    YEAR_2026_2027 = "2026"
    YEAR_2025_2026 = "2025"
    YEAR_2024_2025 = "2024"
    YEAR_2023_2024 = "2023"
    YEAR_2022_2023 = "2022"
    YEAR_2021_2022 = "2021"
    YEAR_2020_2021 = "2020"
    YEAR_2019_2020 = "2019"
    YEAR_2018_2019 = "2018"
    YEAR_2017_2018 = "2017"
    YEAR_2016_2017 = "2016"


class RoleOrganization(str, Enum):
    # For Bancadas | Partidos
    VOCERO = "vocero"
    MIEMBRO = "miembro"

    # For Comisiones, Mesa Directiva, Junta de Portavoces
    PRESIDENTE = "presidente"
    VICEPRESIDENTE = "vicepresidente"
    SECRETARIO = "secretario"
    TITULAR = "titular"
    SUPLENTE = "suplente"
    ACCESITARIO = "accesitario"


class TypeOrganization(str, Enum):
    COMISON = "Comisión"
    JUNTA_DE_PORTAVOCES = "Junta de Portavoces"
    MESA_DIRECTIVA = "Mesa Directiva"
    COMISION_PERMANENTE = "Comisión Permanente"
    CONSEJO_DIRECTIVO = "Consejo Directivo"
    SUBCOM_ACUSACIONES = "Subcomisión de Acusaciones Constitucionales"


class TypeCommittee(str, Enum):
    # For Committees
    COM_INVESTIGADORA = "Comisiones Investigadoras"
    GRUPO_TRABAJO = "Grupo de Trabajo"
    SUBCOM_AC = "Subcomisión de Acusaciones Constitucionales"
    SUBCOM_CP = "Subcomisión de Control Político"
    COM_LEV_INMUN = "Comisión de Levantamiento de Inmunidad Parlamentaria"
    COM_ORD = "Comisión Ordinaria"
    SUBCOM_TLC = "Sub Comisión de Seguimiento del TLC"
    COM_ESP = "Comisiones Especiales"
    COM_ETICA = "Comisión de Ética Parlamentaria"
