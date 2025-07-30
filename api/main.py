from datetime import date
from fastapi import FastAPI, HTTPException, Path, Query
from typing import Annotated


app = FastAPI()


#######################################
# Set up CORS and Security
#######################################
# TODO: When relevant
# from fastapi.middleware.cors import CORSMiddleware
#
# origins = [
#     "http://localhost",
#     "http://localhost:8080",
# ]
#
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=origins,
#     allow_credentials=False, # No log-in anticipatd, manually specify
#     allow_methods=["GET"], # Currently only allowing GET requests
#     allow_headers=[], # Disallow headers, as only serving static pages
# )

#######################################
# Request validation
#######################################
# TODO: Create Pydantic models for the request validation
# TODO: Import from models for the response validation - https://fastapi.tiangolo.com/tutorial/response-model/#response_model-parameter


#######################################
# API endpoint
#######################################
@app.get("/v1/bills", tags=["Bills"])
async def bills(
    status: Annotated[str | None, Query()] = None,
    proposed_by: Annotated[int | None, Query()] = None,
    last_action_date: Annotated[date | None, Query()] = None,
    step_type: Annotated[list[str] | None, Query()] = None,
    leg_period: Annotated[
        str | None,
        Query(min_length=9, max_length=9, pattern=r"([1-2]\d{3}\-[1-2]\d{3})"),
    ] = None,
):
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
            "last_action_date": "2025-02-21",
            "presentation_date": "2024-02-21",
        },
        {
            "bill_id": "2021_10301",
            "status": "EN COMISIÓN",
            "title": "LEY QUE FORTALECE Y OTORGA BENEFICIOS A LAS RONDAS CAMPESINAS",
            "summary": "PROPONE FORTALECER LA CAPACIDAD DE ACCIÓN DE LAS RONDAS CAMPESINAS A TRAVÉS DEL OTORGAMIENTO DE BENEFICIOS EN FAVOR DE SUS INTEGRANTES, EN EL MARCO DE LA LEY N°27908, LEY DE RONDAS CAMPESINAS",
            "author_id": 1047,
            "coauthors": [1158, 1115],
            "leg_period": "2021-2026",
            "last_action_date": "2025-02-24",
            "presentation_date": "2024-02-23",
        },
        {
            "bill_id": "2021_10307",
            "status": "DICTAMEN",
            "title": "LEY QUE DECLARA DE NECESIDAD PÚBLICA E INTERÉS NACIONAL LA CREACIÓN DE LA UNIVERSIDAD NACIONAL SOBERANA Y ETNOLINGÜÍSTICA DEL BAJO URUBAMBA - UNSELBU",
            "summary": "PROPONE DECLARAR DE NECESIDAD PÚBLICA E INTERÉS NACIONAL LA CREACIÓN DE LA UNIVERSIDAD NACIONAL SOBERANA Y ETNOLINGÜÍSTICA DEL BAJO URUBAMBA -  UNSELBU, CON SEDE CENTRAL EN EL DISTRITO DE SEPAHUA, DE LA PROVINCIA DE ATALAYA, DEL DEPARTAMENTO DE UCAYALI; CON LA FINALIDAD DE IMPULSAR EL ACCESO A LA EDUCACIÓN SUPERIOR UNIVERSITARIA, LA PROMOCIÓN DE LA INVESTIGACIÓN CIENTÍFICA TECNOLÓGICA, ASÍ COMO GARANTIZAR EN LA GENERACIÓN DE CONOCIMIENTOS Y DESARROLLO INTEGRAL EN LOS DIVERSOS CAMPOS CIENTÍFICOS Y HUMANIDADES, DE LA POBLACIÓN DE LA PROVINCIA DE ATALAYA Y PROVINCIAS ALEDAÑAS.",
            "author_id": 1109,
            "coauthors": [1099, 1115],
            "leg_period": "2021-2026",
            "last_action_date": "2024-09-24",
            "presentation_date": "2024-02-24",
        },
    ]
    return {"data": data}


@app.get("/v1/bills/{bill_id}", tags=["Bills"])
async def bills_detail(
    bill_id: Annotated[
        str, Path(min_length=10, max_length=10, pattern=r"(\d{4}\_\d{5})")
    ],
):
    """
    Returns detailed information on each bill.

    Requires bill_id parameter.
    """
    if bill_id != "2021_10300":
        raise HTTPException(
            status_code=404, detail="Test API requires bill_id == '2021_10300'"
        )
    data = {
        "bill_id": "2021_10300",
        "status": "EN COMISIÓN",
        "title": "LEY DE COMPROMISO ESTATAL Y SOCIAL CON LA NIÑEZ EN ORFANDAD Y LA ADOPCIÓN",
        "summary": "PROPONE GARANTIZAR LA ATENCIÓN PRIORITARIA DEL ESTADO Y PROMOVER EL COMPROMISO DE LA SOCIEDAD EN GENERAL CON LA INFANCIA EN SITUACIÓN DE ORFANDAD, ASÍ COMO FOMENTAR LA ADOPCIÓN",
        "author_id": 1099,
        "coauthors": [1039, 1062, 1129, 1126, 1032],
        "leg_period": "2021-2026",
        "last_action_date": "2025-02-21",
        "presentation_date": "2025-02-21",
        "complete_text": "Lorem ipsum",
        "bancada_id": 1,
        "bancada_name": "ALIANZA PARA EL PROGRESO",
        "bill_approved": False,
    }
    return {"data": data}


@app.get("/v1/events", tags=["Events"])
async def events(
    bill_id: Annotated[
        str, Query(min_length=10, max_length=10, pattern=r"(\d{4}\_\d{5})")
    ],
    congresistas_id: Annotated[int | None, Query()] = None,
    last_action_date: Annotated[str | None, Query()] = None,
    step_type: Annotated[list[str] | None, Query()] = None,
):
    """
    Provides information on each event. Can be filtered by bill_id or
    congresista_id, date, or event type.

    TODO: Determine if it should be limited by bill?
    """
    data = {
        "bill_id": "2021_10307",
        "steps": [
            {
                "step_id": 1,
                "step_type": "Introduced",
                "step_date": "2025-02-21",
                "step_details": "LEY QUE DECLARA DE NECESIDAD PÚBLICA E INTERÉS NACIONAL LA CREACIÓN DE LA UNIVERSIDAD NACIONAL SOBERANA Y ETNOLINGÜÍSTICA DEL BAJO URUBAMBA - UNSELBU",
                "vote_event_id": None,
                "vote_sum": None,  # TODO: Figure out if this is the right convention for optionality
                "votes": [],
            },
            {
                "step_id": 2,
                "step_type": "In committee",
                "step_date": "2025-02-24",
                "step_details": "Entre Presupuesto y Cuenta General de la República; Educación, Juventud y Deporte",
                "vote_event_id": None,
                "vote_sum": None,
                "votes": [],
            },
            {
                "step_id": 3,
                "step_type": "Vote",
                "step_date": "2025-02-21",
                "step_details": "Vote in resupuesto y Cuenta General de la República; Educación, Juventud y Deporte",
                "vote_event_id": "2021_10307_3",
                "vote_sum": {"yes": 1, "no": 1, "absent": 1},
                "votes": [
                    {"congresista_id": 1109, "option": "Yes"},
                    {"congresista_id": 1099, "option": "No"},
                    {"congresista_id": 1115, "option": "Absent"},
                ],
            },
        ],
    }
    return {"data": data}


@app.get("/v1/congresistas", tags=["Congresistas"])
async def congresistas(
    leg_period: Annotated[
        str,
        Query(min_length=9, max_length=9, pattern=r"([1-2]\d{3}\-[1-2]\d{3})"),
    ] = "2021-2026",
):
    """
    Provides a list of acting congresistas for each legislative year, linking
    formal names with IDs.
    """
    data = [
        {
            "id": "1109",
            "nombre": "María Grimaneza Acuña Peralta",
            "leg_period": "Parlamentario 2021 - 2026",
            "party_name": "Alianza para el Progreso",
            "bancada_name": "ALIANZA PARA EL PROGRESO",
            "dist_electoral": "Lambayeque",
            "condicion": "en Ejercicio",
        },
        {
            "id": "1099",
            "nombre": "Segundo Héctor Acuña Peralta",
            "leg_period": "Parlamentario 2021 - 2026",
            "party_name": "Alianza para el Progreso",
            "bancada_name": "HONOR Y DEMOCRACIA",
            "dist_electoral": "La libertad",
            "condicion": "en Ejercicio",
        },
        {
            "id": "1115",
            "nombre": "María Antonieta Agüero Gutiérrez",
            "leg_period": "Parlamentario 2021 - 2026",
            "party_name": "Partido Politico Nacional Perú Libre",
            "bancada_name": "PERÚ LIBRE",
            "dist_electoral": "Arequipa",
            "condicion": "en Ejercicio",
        },
        {
            "id": "1032",
            "nombre": "Alejandro Aurelio Aguinaga Recuenco",
            "leg_period": "Parlamentario 2021 - 2026",
            "party_name": "Fuerza Popular",
            "bancada_name": "FUERZA POPULAR",
            "dist_electoral": "Lambayeque",
            "condicion": "en Ejercicio",
        },
    ]
    return {"data": data}


# TODO: Add picture + multiple years
@app.get("/v1/congresistas/{congresista_id}", tags=["Congresistas"])
async def congresista_detail(congresista_id: Annotated[int, Path()]):
    """
    Returns detail on specific congresista
    """
    if congresista_id not in [1109]:
        raise HTTPException(
            status_code=404, detail="Test API requires congresista 1109"
        )
    data = {
        "id": "1109",
        "nombre": "María Grimaneza Acuña Peralta",
        "votation": "11,384",
        "leg_period": "Parlamentario 2021 - 2026",
        "party_name": "Alianza para el Progreso",
        "bancada_name": "ALIANZA PARA EL PROGRESO",
        "dist_electoral": "Lambayeque",
        "condicion": "en Ejercicio",
        "website": "https://www.congreso.gob.pe/congresistas2021/GrimanezaAcuna/",
    }
    return {"data": data}
