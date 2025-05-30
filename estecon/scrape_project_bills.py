import httpx
from lxml.html import fromstring
import polars as pl

def get_laws(url: str, params: dict) -> list:

    request = httpx.post(url, 
                         verify=False, 
                         json = params,
                         headers={
                             "accept": "application/json, text/plain, */*",
                             "content_type": "application/json",
                         })
    return request

def get_filters(url: str = "https://wb2server.congreso.gob.pe/spley-portal-service/periodo-parlamentario/2021/filtros") -> dict:
    """
    Returns the filters for the project laws
    """
    request = httpx.get(url, verify=False)
    if request.status_code == 200:
        return request.json()
    else:
        raise Exception(f"Error fetching filters: {request.status_code}")

def get_comisiones(filters: dict) -> list:
    """
    Returns the commissions from the filters
    """
    return filters['data'].get('comisiones', [])

def get_estados(filters: dict) -> list:
    """
    Returns the states from the filters
    """
    return filters['data'].get('estados', [])

def get_grupos_parlamentarios(filters: dict) -> list:
    """
    Returns the parliamentary groups from the filters
    """
    return filters['data'].get('gruposParlamentarios', [])

print("Fetching filters...")
filters = get_filters()
# print(filters)
print("Fetching commissions...")
comisiones = get_comisiones(filters)
df_comisiones = pl.DataFrame(comisiones)
print(df_comisiones.head())
print("Fetching states...")
estados = get_estados(filters)
print(estados)
print("Fetching parliamentary groups...")
grupos_parlamentarios = get_grupos_parlamentarios(filters)
print(grupos_parlamentarios)

# keys = ['comisiones', 'estados', 'periodosLegislativos', 'autores', 'gruposParlamentarios', 'proponentes', 'legislaturas']

# params = {
#         "perParId": 2021,
#         "perLegId": None,
#         "comisionId": None,
#         "estadoId": None,
#         "congresistaId": None,
#         "grupoParlamentarioId": None,
#         "proponenteId": None,
#         "legislaturaId": None,
#         "fecPresentacionDesde": None,
#         "fecPresentacionHasta": None,
#         "pleyNum": None,
#         "palabras": None,
#         "tipoFirmanteId": None,
#         "pageSize": 50,
#         "rowStart": 0,
#     }

# url = "https://wb2server.congreso.gob.pe/spley-portal-service/proyecto-ley/lista-con-filtro"
# r = get_laws(url,params).json()

# df = pl.DataFrame(r['data']['proyectos'])
# print(df.head())