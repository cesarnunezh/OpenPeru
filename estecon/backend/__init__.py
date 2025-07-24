from enum import Enum
from datetime import datetime

URL = {'congresistas' : 'https://www.congreso.gob.pe/pleno/congresistas/',
       'proyectos_ley': 'https://wb2server.congreso.gob.pe/spley-portal/#/expediente/search',
       'dictamenes' : 'https://wb2server.congreso.gob.pe/spley-portal/#/dictamenes/periodos',
       'leyes' : 'https://www.leyes.congreso.gob.pe/',
       'asistencia_pleno' : "https://www.congreso.gob.pe/AsistenciasVotacionesPleno/asistencia-votacion-pleno",
       'asistencia_comision_permanente' : "https://www.congreso.gob.pe/AsistenciasVotacionesPleno/asistencia-comisionpermanente",
       'actas_comisiones' : "https://www.congreso.gob.pe/actascomisiones/",
       'conformacion_comisiones': "https://www.congreso.gob.pe/CuadrodeComisiones/"}

# Might need to review and make sure everyone is here
PARTIES = [" AP ", " AP-PIS ", " APP ", " BM ", " BDP ", " BOP ", " BS ", " BSS ",
            " E "," FP ", " HYD ", " JP ", " IJPP-VP "," JPP-VP ", " NA ", " NP ", 
            " PL ", " PLG ", " PM ", " PP ", " SP ", " sP ", " RP ", " 8S ", " 8M "] 

# Dictionary to avoid creation of duplicate parties objects
PARTY_ALIASES = {
    'Alianza para el Progreso': "Alianza para el Progreso del Perú",
    "Somos Perú": "Partido Democrático Somos Perú",
    'Frente Amplio' : 'Frente Amplio por Justicia, Vida y Libertad',
    'Frente Popular Agrícola del Perú' : "Frente Popular Agrícola FIA del Perú",
    'No Agrupado': "Ninguno",
    'No ha acreditado': "Ninguno",
    'No registrado' : "Ninguno",
    'Alianza Solidaridad Nacional' : 'Solidaridad Nacional',
    'Unión por el Perú' : 'Unión por el Perú - Social Democracia'
}

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

class BillStepType(str, Enum):
    VOTE = "presentado"
    ASSIGNED = "en comisión"
    DICTAMEN = "dictamen"
    ORDEN_DIA = "orden del día"
    EN_AGENDA = "en agenda del pleno"
    EN_DEBATE = "en debate - pleno"
    EN_CUARTO_INTERMEDIO = "en cuarto intermedio"
    APROBADO_VOT_1 = "aprobado 1era. votación"
    APROBADO_VOT_2 = "aprobado"
    AUTOGRAFA = "autógrafa"
    AUTOGRAFA_OBS = "autógrafa observada"
    EN_RECONSIDERACION = "en reconsideración"
    RETIRO_FIRMA = "retiro de firma"
    PROMULGADO_PDTE_CONG = "promulgado/presidente del congreso"
    PROMULGADO_PDTE_REP = "promulgado/presidente de la república"
    PUBLISHED = "publicada en el diario oficial el peruano"

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

class LegPeriod(str, Enum):
    PERIODO_2021_2026 = 'Parlamentario 2021 - 2026'
    PERIODO_2016_2021 = 'Parlamentario 2016 - 2021'
    PERIODO_2011_2016 = 'Parlamentario 2011 - 2016'
    PERIODO_2006_2011 = 'Parlamentario 2006 - 2011'
    PERIODO_2001_2006 = 'Parlamentario 2001 - 2006'
    PERIODO_2000_2001 = 'Parlamentario 2000 - 2001'
    PERIODO_1995_2000 = 'Parlamentario 1995 - 2000'
    PERIODO_1992_1995 = 'CCD 1992 -1995'

def make_legislature_enum():
    def label(period, year):
        return f"{'Primera' if period == 'I' else 'Segunda'} Legislatura Ordinaria {year}"

    legs_dict = {
        f"LEG_ORD_{year}_{per}": label(per, year)
        for year in range(1990, datetime.now().year + 1)
        for per in ["I", "II"]
    }

    return Enum("Legislature", legs_dict, type=str)

Legislature = make_legislature_enum()

class LegislativeYear(str, Enum):
    YEAR_2026 = "2025-2026"
    YEAR_2025 = "2024-2025"
    YEAR_2024 = "2023-2024"
    YEAR_2023 = "2022-2023"
    YEAR_2022 = "2021-2022"
    YEAR_2021 = "2020-2021"
    YEAR_2020 = "2019-2020"
    YEAR_2019 = "2018-2019"
    YEAR_2018 = "2017-2018"
    YEAR_2017 = "2016-2017"

class RoleOrganization(str, Enum):
    # For Bancadas | Partidos
    VOCERO = "vocero"
    MIEMBRO = "miembro"
    
    # For Comisiones, Mesa Directiva, Junta de Portavoces
    PRESIDENTE = "presidente"
    PRESIDENTA = "presidenta"
    VICEPRESIDENTE = "vicepresidente"
    VICEPRESIDENTA = "vicepresidenta"
    SECRETARIO = "secretario"
    SECRETARIA = "secretaria"
    TITULAR = "titular"
    SUPLENTE = "suplente"
    ACCESITARIO = "accesitario"
    

class TypeOrganization(str, Enum):
    BANCADA = "bancada"
    COMMITTEE = "committee"
    JUNTA_DE_PORTAVOCES = "junta de portavoces"
    MESA_DIRECTIVA = "mesa directiva"
    COMISION_PERMANENTE = "comision permanente"
