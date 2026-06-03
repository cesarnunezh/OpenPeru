URL = {
    "congresistas": "https://www.congreso.gob.pe/pleno/congresistas/",
    "proyectos_ley": "https://wb2server.congreso.gob.pe/spley-portal/#/expediente/search",
    "dictamenes": "https://wb2server.congreso.gob.pe/spley-portal/#/dictamenes/periodos",
    "leyes": "https://www.leyes.congreso.gob.pe/",
    "asistencia_pleno": "https://www.congreso.gob.pe/AsistenciasVotacionesPleno/asistencia-votacion-pleno",
    "asistencia_comision_permanente": "https://www.congreso.gob.pe/AsistenciasVotacionesPleno/asistencia-comisionpermanente",
    "actas_comisiones": "https://www.congreso.gob.pe/actascomisiones/",
    "conformacion_comisiones": "https://www.congreso.gob.pe/CuadrodeComisiones/",
}

# Might need to review and make sure everyone is here
PARTIES = [
    " AP ",
    " AP-PIS ",
    " APP ",
    " BM ",
    " BDP ",
    " BOP ",
    " BS ",
    " BSS ",
    " E ",
    " FP ",
    " HYD ",
    " JP ",
    " IJPP-VP ",
    " JPP-VP ",
    " NA ",
    " NP ",
    " PL ",
    " PLG ",
    " PM ",
    " PP ",
    " SP ",
    " sP ",
    " RP ",
    " 8S ",
    " 8M ",
]

# Dictionary to avoid creation of duplicate parties objects
PARTY_ALIASES = {
    "Alianza para el Progreso": "Alianza para el Progreso del Perú",
    "Somos Perú": "Partido Democrático Somos Perú",
    "Frente Amplio": "Frente Amplio por Justicia, Vida y Libertad",
    "Frente Popular Agrícola del Perú": "Frente Popular Agrícola FIA del Perú",
    "No Agrupado": "Ninguno",
    "No ha acreditado": "Ninguno",
    "No registrado": "Ninguno",
    "Alianza Solidaridad Nacional": "Solidaridad Nacional",
    "Unión por el Perú": "Unión por el Perú - Social Democracia",
}

LEG_PERIOD_ALIASES = {
    "Parlamentario 2026 - 2031": "2026-2031",
    "Parlamentario 2021 - 2026": "2021-2026",
    "Parlamentario 2021-2026": "2021-2026",
    "2021 - 2026": "2021-2026",
    "2021–2026": "2021-2026",
    "2021-2026": "2021-2026",
    "Parlamentario 2016 - 2021": "2016-2021",
    "2016 - 2021": "2016-2021",
    "2016–2021": "2016-2021",
    "2016-2021": "2016-2021",
    "Parlamentario 2011 - 2016": "2011-2016",
    "2011 - 2016": "2011-2016",
    "2011–2016": "2011-2016",
    "2011-2016": "2011-2016",
    "Parlamentario 2006 - 2011": "2006-2011",
    "2006 - 2011": "2006-2011",
    "2006–2011": "2006-2011",
    "2006-2011": "2006-2011",
    "Parlamentario 2001 - 2006": "2001-2006",
    "2001 - 2006": "2001-2006",
    "2001–2006": "2001-2006",
    "2001-2006": "2001-2006",
    "Parlamentario 2000 - 2001": "2000-2001",
    "2000 - 2001": "2000-2001",
    "2000–2001": "2000-2001",
    "2000-2001": "2000-2001",
    "Parlamentario 1995 - 2000": "1995-2000",
    "1995 - 2000": "1995-2000",
    "1995–2000": "1995-2000",
    "1995-2000": "1995-2000",
    "CCD 1992 -1995": "1992-1995",
    "CCD 1992 - 1995": "1992-1995",
    "1992-1995": "1992-1995",
    "Parlamentario 1995-2000": "1995-2000",
    "CCD 1992-1995": "1992-1995",
}


LEGISLATURE_ALIASES = {
    # Congress wording → canonical legislature code
    # 2025
    "Primera Legislatura Ordinaria 2025": "2025-II",
    "Segunda Legislatura Ordinaria 2025": "2026-I",
    # 2024
    "Primera Legislatura Ordinaria 2024": "2024-II",
    "Segunda Legislatura Ordinaria 2024": "2025-I",
    # 2023
    "Primera Legislatura Ordinaria 2023": "2023-II",
    "Segunda Legislatura Ordinaria 2023": "2024-I",
    # 2022
    "Primera Legislatura Ordinaria 2022": "2022-II",
    "Segunda Legislatura Ordinaria 2022": "2023-I",
    # 2021
    "Primera Legislatura Ordinaria 2021": "2021-II",
    "Segunda Legislatura Ordinaria 2021": "2022-I",
    # 2020
    "Primera Legislatura Ordinaria 2020": "2020-II",
    "Segunda Legislatura Ordinaria 2020": "2021-I",
    # 2019
    "Primera Legislatura Ordinaria 2019": "2019-II",
    "Segunda Legislatura Ordinaria 2019": "2020-I",
    # 2018
    "Primera Legislatura Ordinaria 2018": "2018-II",
    "Segunda Legislatura Ordinaria 2018": "2019-I",
    # 2017
    "Primera Legislatura Ordinaria 2017": "2017-II",
    "Segunda Legislatura Ordinaria 2017": "2018-I",
}


BILL_ROLE_MAPS = {1: "author", 2: "coauthor", 3: "adherente"}
