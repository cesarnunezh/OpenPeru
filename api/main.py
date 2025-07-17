from fastapi import FastAPI

app = FastAPI()


#######################################
# API endpoint
#######################################
@app.get("/v1/bills")
async def bills():
    """
    Retrieves a list of bills from the bills table with ids and summary
    information sorted by most recent actions. Paginated.
    """
    data = [
        {
            "bill_id": "2021_10300",
            "status": "EN COMISIÓN",
            "title": "LEY DE COMPROMISO ESTATAL Y SOCIAL CON LA NIÑEZ EN ORFANDAD Y LA ADOPCIÓN",
            "summary": "PROPONE GARANTIZAR LA ATENCIÓN PRIORITARIA DEL ESTADO Y PROMOVER EL COMPROMISO DE LA SOCIEDAD EN GENERAL CON LA INFANCIA EN SITUACIÓN DE ORFANDAD, ASÍ COMO FOMENTAR LA ADOPCIÓN",
            "author_id": 1099,
            "coauthors": [1039, 1062, 1129, 1126, 1032],
            "leg_period": "2021-2026",
            "last_action_date": "2025-02-21T00:00:00.000-0500",
        },
        {
            "bill_id": "2021_10301",
            "status": "EN COMISIÓN",
            "title": "LEY QUE FORTALECE Y OTORGA BENEFICIOS A LAS RONDAS CAMPESINAS",
            "summary": "PROPONE FORTALECER LA CAPACIDAD DE ACCIÓN DE LAS RONDAS CAMPESINAS A TRAVÉS DEL OTORGAMIENTO DE BENEFICIOS EN FAVOR DE SUS INTEGRANTES, EN EL MARCO DE LA LEY N°27908, LEY DE RONDAS CAMPESINAS",
            "author_id": 1047,
            "coauthors": [1158, 1115],
            "leg_period": "2021-2026",
            "last_action_date": "2025-02-24T12:42:36.000-0500",
        },
        {
            "bill_id": "2021_10307",
            "status": "DICTAMEN",
            "title": "LEY QUE DECLARA DE NECESIDAD PÚBLICA E INTERÉS NACIONAL LA CREACIÓN DE LA UNIVERSIDAD NACIONAL SOBERANA Y ETNOLINGÜÍSTICA DEL BAJO URUBAMBA - UNSELBU",
            "summary": "PROPONE DECLARAR DE NECESIDAD PÚBLICA E INTERÉS NACIONAL LA CREACIÓN DE LA UNIVERSIDAD NACIONAL SOBERANA Y ETNOLINGÜÍSTICA DEL BAJO URUBAMBA -  UNSELBU, CON SEDE CENTRAL EN EL DISTRITO DE SEPAHUA, DE LA PROVINCIA DE ATALAYA, DEL DEPARTAMENTO DE UCAYALI; CON LA FINALIDAD DE IMPULSAR EL ACCESO A LA EDUCACIÓN SUPERIOR UNIVERSITARIA, LA PROMOCIÓN DE LA INVESTIGACIÓN CIENTÍFICA TECNOLÓGICA, ASÍ COMO GARANTIZAR EN LA GENERACIÓN DE CONOCIMIENTOS Y DESARROLLO INTEGRAL EN LOS DIVERSOS CAMPOS CIENTÍFICOS Y HUMANIDADES, DE LA POBLACIÓN DE LA PROVINCIA DE ATALAYA Y PROVINCIAS ALEDAÑAS.",
            "author_id": 1109,
            "coauthors": [1099, 1115],
            "leg_period": "2021-2026",
            "last_action_date": "2024-09-24T12:42:36.000-0500",
        },
    ]
    return {"data": data}
