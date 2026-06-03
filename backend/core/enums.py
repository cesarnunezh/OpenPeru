from enum import Enum


def enum_values(enum_cls: type[Enum]) -> list[str]:
    return [member.value for member in enum_cls]


def sql_value_list(enum_cls: type[Enum]) -> str:
    return ", ".join(f"'{str(member.value)}'" for member in enum_cls)


class TypeMajority(str, Enum):
    SIMPLE = "Simple"
    ABSOLUTA = "Absoluta"
    CALIFICADA = "Calificada"


class VoteResult(str, Enum):
    APROBADO = "Aprobado"
    RECHAZADO = "Rechazado"
    NO_QUORUM = "No hay quorum"


class VoteOption(str, Enum):
    SI = "Sí"
    NO = "No"
    ABSTENCION = "Abstención"
    SIN_RESPUESTA = "Sin respuesta"


class AttendanceStatus(str, Enum):
    PRESENTE = "Presente"
    AUSENTE = "Ausente"
    LICENCIA = "Con licencia"
    SUSPENDIDO = "Suspendido"


class TypeMotion(str, Enum):
    SALUDO = "Saludo"
    CENSURA_MESA = "Censura Mesa Directiva del Congreso"
    CENSURA_MINISTRO = "Censura al Consejo de Ministros"
    INTERES = "Interés Nacional"
    INTERPELACION = "Interpelación"
    INFORME_MINISTROS = "Invitación a Ministros para Informar"
    VACANCIA = "Vacancia"
    COMISION_INVESTIGADORA = "Comisiones Investigadoras"
    COMISION_ESPECIAL = "Comisiones Especiales"
    PESAR = "Pesar"
    OTRAS = "Otras"


class TypeMotionStep(str, Enum):
    PRESENTADO = "Presentado"
    ADMISION = "Admisión a debate"
    ETAPA_EN_COMISION = "En Comisión"
    ACUERDO_CD = "Acuerdo de Consejo Directivo"
    ACUERDO_JP = "Acuerdo de la Junta de Portavocez"
    AGENDA_CD = "En Agenda del Consejo Directivo"
    AGENDA_DEL_PLENO = "En Agenda del Pleno"
    ANUNCIO_O_DACION_DE_CUENTA = "Anunciado en el Pleno"
    FUNDAMENTACION = "Fundamentada la Moción"
    DEBATE = "En Debate"
    VOTACION_O_DECISION = "Votación"
    REVISION_DE_TEXTO = "Revisión o cambio de texto"
    COMUNICACION_OFICIAL = "Comunicación Oficial"
    ASISTENCIA_O_COMPARECENCIA = "Asistencia de Ministro"
    RECONSIDERACION = "Reconsideración"
    RETIRADO = "Retirado"
    ARCHIVADO = "Archivado"
    PUBLICADO = "Publicado"
    RENUNCIA = "Renuncia"
    CUESTION_DE_ORDEN = "Cuestión de orden"
    BLOQUEO_POR_REQUISITOS = "Incumplimiento de requisitos"
    CUARTO_INTERMEDIO = "Cuarto intermedio"
    FE_DE_ERRATAS_O_CORRECCION = "Fe de Erratas"
    SIN_CATEGORIA = "Sin categoría"


class TypeBillStep(str, Enum):
    PRESENTADO = "Presentado"
    EN_COMISION = "En Comisión"
    DICTAMEN_O_ACUERDO_DE_COMISION = "Dictamen o Acuerdo de Comisión"
    EXONERACION_DE_DICTAMEN = "Exoneración de Dictamen"
    AGENDA_DEL_CONSEJO_DIRECTIVO = "En Agenda del Consejo Directivo"
    AGENDA_DEL_PLENO = "En Agenda del Pleno"
    AGENDA_DE_LA_COMISION_PERMANENTE = "En Agenda de la Comisión Permanente"
    DEBATE_EN_EL_PLENO = "Debate en el Pleno"
    DEBATE_EN_LA_COMISION_PERMANENTE = "Debate en la Comisión Permanente"
    VOTACION = "Votación"
    TEXTO_SUSTITUTORIO_O_REVISION = "Revisión o cambio de texto"
    AUTOGRAFA = "Autógrafa"
    RECONSIDERACION = "Reconsideración"
    RETIRADO = "Retirado"
    ARCHIVADO = "Al Archivo"
    PROMULGADO = "Promulgado"
    PUBLICADO = "Publicado"
    CUARTO_INTERMEDIO = "Cuarto Intermedio"
    ACUMULADO = "Acumulado en Sala"
    ACLARACION = "Aclaración"
    RECHAZADO = "Rechazado"
    SIN_CATEGORIA = "Sin categoría"


class TypeRoleBill(str, Enum):
    AUTHOR = "Autor"
    COAUTHOR = "Coautor"
    ADHERENTE = "Adherente"


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


class RoleOrganization(str, Enum):
    # For Bancadas | Partidos
    VOCERO = "Vocero"
    MIEMBRO = "Miembro"

    # For Cámaras
    DIPUTADO = "Diputado"
    SENADOR = "Senador"

    # For Comisiones, Mesa Directiva, Junta de Portavoces
    PRESIDENTE = "Presidente"
    VICEPRESIDENTE = "Vicepresidente"
    SECRETARIO = "Secretario"
    TITULAR = "Titular"
    SUPLENTE = "Suplente"
    ACCESITARIO = "Accesitario"
    SEGUNDO_VICE = "Segundo Vicepresidente"
    TERCER_VICE = "Tercer Vicepresidente"


class TypeOrganization(str, Enum):
    COMMITTEE = "Comisión"
    CHAMBER = "Cámara"
    BANCADA = "Bancada"
    PARTY = "Partido"
    ADMINISTRATIVE = "Administrativo"


class TypeAdmin(str, Enum):
    JUNTA_DE_PORTAVOCES = "Junta de Portavoces"
    MESA_DIRECTIVA = "Mesa Directiva"
    COMISION_PERMANENTE = "Comisión Permanente"
    CONSEJO_DIRECTIVO = "Consejo Directivo"


class TypeCommittee(str, Enum):
    COM_INVESTIGADORA = "Comisiones Investigadoras"
    GRUPO_TRABAJO = "Grupo de Trabajo"
    SUBCOM_AC = "Subcomisión de Acusaciones Constitucionales"
    SUBCOM_CP = "Subcomisión de Control Político"
    COM_LEV_INMUN = "Comisión de Levantamiento de Inmunidad Parlamentaria"
    COM_ORD = "Comisión Ordinaria"
    SUBCOM_TLC = "Sub Comisión de Seguimiento del TLC"
    COM_ESP = "Comisiones Especiales"
    COM_ETICA = "Comisión de Ética Parlamentaria"


class EmbeddingModel(str, Enum):
    MULTILINGUAL_E5_BASE = "intfloat/multilingual-e5-base"


class OcrModel(str, Enum):
    """OCR engine used to extract text from a scanned document page.

    Bills are OCR'd with chandra2; attendance and votes with Tesseract.
    """

    CHANDRA = "chandra2"
    TESSERACT = "Tesseract"
