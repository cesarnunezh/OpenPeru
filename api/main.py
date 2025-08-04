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
# API endpoints
#######################################
@app.get("/")
async def home():
    return {"data": "Hello world"}


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
            "id": "2021_10300",
            "org_id": 1,
            "leg_period": "Parlamentario 2021 - 2026",
            "legislature": "2021-II",
            "presentation_date": "2025-02-21",
            "title": "LEY DE COMPROMISO ESTATAL Y SOCIAL CON LA NIÑEZ EN ORFANDAD Y LA ADOPCIÓN",
            "summary": "PROPONE GARANTIZAR LA ATENCIÓN PRIORITARIA DEL ESTADO Y PROMOVER EL COMPROMISO DE LA SOCIEDAD EN GENERAL CON LA INFANCIA EN SITUACIÓN DE ORFANDAD, ASÍ COMO FOMENTAR LA ADOPCIÓN",
            "observations": "No idea",
            "complete_text": "Lorem ipsum",
            "status": "EN COMISIÓN",
            "proponent": "Congreso",
            "author_id": 1099,
            "bancada_id": 1,
            "bill_approved": False,
            "coauthors": [1039, 1062, 1129, 1126, 1032],
        },
        {
            "id": "2021_10301",
            "org_id": 1,
            "leg_period": "Parlamentario 2021 - 2026",
            "legislature": "2021-II",
            "presentation_date": "2025-02-23",
            "title": "LEY QUE FORTALECE Y OTORGA BENEFICIOS A LAS RONDAS CAMPESINAS",
            "summary": "PROPONE GARANTIZAR LA ATENCIÓN PRIORITARIA DEL ESTADO Y PROMOVER EL COMPROMISO DE LA SOCIEDAD EN GENERAL CON LA INFANCIA EN SITUACIÓN DE ORFANDAD, ASÍ COMO FOMENTAR LA ADOPCIÓN",
            "observations": "No idea",
            "complete_text": "Lorem ipsum",
            "status": "EN COMISIÓN",
            "proponent": "Congreso",
            "author_id": 1047,
            "bancada_id": 1,
            "bill_approved": False,
            "coauthors": [1158, 1115],
        },
        {
            "id": "2021_10307",
            "org_id": 1,
            "leg_period": "Parlamentario 2021 - 2026",
            "legislature": "2021-II",
            "presentation_date": "2025-02-24",
            "title": "LEY QUE DECLARA DE NECESIDAD PÚBLICA E INTERÉS NACIONAL LA CREACIÓN DE LA UNIVERSIDAD NACIONAL SOBERANA Y ETNOLINGÜÍSTICA DEL BAJO URUBAMBA - UNSELBU",
            "summary": "PROPONE DECLARAR DE NECESIDAD PÚBLICA E INTERÉS NACIONAL LA CREACIÓN DE LA UNIVERSIDAD NACIONAL SOBERANA Y ETNOLINGÜÍSTICA DEL BAJO URUBAMBA -  UNSELBU, CON SEDE CENTRAL EN EL DISTRITO DE SEPAHUA, DE LA PROVINCIA DE ATALAYA, DEL DEPARTAMENTO DE UCAYALI; CON LA FINALIDAD DE IMPULSAR EL ACCESO A LA EDUCACIÓN SUPERIOR UNIVERSITARIA, LA PROMOCIÓN DE LA INVESTIGACIÓN CIENTÍFICA TECNOLÓGICA, ASÍ COMO GARANTIZAR EN LA GENERACIÓN DE CONOCIMIENTOS Y DESARROLLO INTEGRAL EN LOS DIVERSOS CAMPOS CIENTÍFICOS Y HUMANIDADES, DE LA POBLACIÓN DE LA PROVINCIA DE ATALAYA Y PROVINCIAS ALEDAÑAS.",
            "observations": "No idea",
            "complete_text": "Lorem ipsum",
            "status": "DICTAMEN",
            "proponent": "Congreso",
            "author_id": 1109,
            "bancada_id": 1,
            "bill_approved": False,
            "coauthors": [1099, 1115],
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
        "id": "2021_10300",
        "org_id": 1,
        "leg_period": "Parlamentario 2021 - 2026",
        "legislature": "2021-II",
        "presentation_date": "2025-02-21",
        "title": "LEY DE COMPROMISO ESTATAL Y SOCIAL CON LA NIÑEZ EN ORFANDAD Y LA ADOPCIÓN",
        "summary": "PROPONE GARANTIZAR LA ATENCIÓN PRIORITARIA DEL ESTADO Y PROMOVER EL COMPROMISO DE LA SOCIEDAD EN GENERAL CON LA INFANCIA EN SITUACIÓN DE ORFANDAD, ASÍ COMO FOMENTAR LA ADOPCIÓN",
        "observations": "No idea",
        "complete_text": "Lorem ipsum",
        "status": "EN COMISIÓN",
        "proponent": "Congreso",
        "author_id": 1099,
        "bancada_id": 1,
        "bill_approved": False,
        "coauthors": [1039, 1062, 1129, 1126, 1032],
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
        "bill_id": "2021_10300",
        "steps": [
            {
                "step_id": 1,
                "step_type": "Introduced",
                "step_date": "2025-02-21",
                "step_detail": "LEY QUE DECLARA DE NECESIDAD PÚBLICA E INTERÉS NACIONAL LA CREACIÓN DE LA UNIVERSIDAD NACIONAL SOBERANA Y ETNOLINGÜÍSTICA DEL BAJO URUBAMBA - UNSELBU",
                "vote_event_id": None,
                "vote_count": None,  # TODO: Figure out if this is the right convention for optionality
                "votes": [],
            },
            {
                "step_id": 2,
                "step_type": "In committee",
                "step_date": "2025-02-24",
                "step_detail": "Entre Presupuesto y Cuenta General de la República; Educación, Juventud y Deporte",
                "vote_event_id": None,
                "vote_count": None,
                "votes": [],
            },
            {
                "step_id": 3,
                "step_type": "Vote",
                "step_date": "2025-02-21",
                "step_detail": "Vote in resupuesto y Cuenta General de la República; Educación, Juventud y Deporte",
                "vote_event_id": "2021_10307_3",
                "vote_count": [
                    {
                        "org_id": 1,
                        "vote_event_id": "2025-02-21",
                        "option": "si",
                        "count": 1,
                        "bancada_id": 1,
                    },
                    {
                        "org_id": 1,
                        "vote_event_id": "2025-02-21",
                        "option": "no",
                        "count": 1,
                        "bancada_id": 1,
                    },
                    {
                        "org_id": 1,
                        "vote_event_id": "2025-02-21",
                        "option": "abstencion",
                        "count": 1,
                        "bancada_id": 1,
                    },
                    {
                        "org_id": 1,
                        "vote_event_id": "2025-02-21",
                        "option": "sin respuesta",
                        "count": 1,
                        "bancada_id": 1,
                    },
                ],
                "votes": [
                    {
                        "vote_event_id": "2025-02-21",
                        "voter_id": 1109,
                        "option": "si",
                        "bancada_id": 1,
                    },
                    {
                        "vote_event_id": "2025-02-21",
                        "voter_id": 1099,
                        "option": "no",
                        "bancada_id": 1,
                    },
                    {
                        "vote_event_id": "2025-02-21",
                        "voter_id": 1115,
                        "option": "abstencion",
                        "bancada_id": 1,
                    },
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
            "id": 1109,
            "nombre": "María Grimaneza Acuña Peralta",
            "leg_period": "Parlamentario 2021 - 2026",
            "party_name": "Alianza para el Progreso",
            "party_id": 1,
            "dist_electoral": "Lambayeque",
            "condicion": "en Ejercicio",
            "website": "fill",
            "votes_in_election": 1,
        },
        {
            "id": 1099,
            "nombre": "Segundo Héctor Acuña Peralta",
            "leg_period": "Parlamentario 2021 - 2026",
            "party_name": "Alianza para el Progreso",
            "party_id": 1,
            "dist_electoral": "La libertad",
            "condicion": "en Ejercicio",
            "website": "fill",
            "votes_in_election": 1,
        },
        {
            "id": 1115,
            "nombre": "María Antonieta Agüero Gutiérrez",
            "leg_period": "Parlamentario 2021 - 2026",
            "party_name": "Partido Politico Nacional Perú Libre",
            "party_id": 2,
            "dist_electoral": "Arequipa",
            "condicion": "en Ejercicio",
            "website": "fill",
            "votes_in_election": 1,
        },
        {
            "id": 1032,
            "nombre": "Alejandro Aurelio Aguinaga Recuenco",
            "leg_period": "Parlamentario 2021 - 2026",
            "party_name": "Fuerza Popular",
            "party_id": 3,
            "dist_electoral": "Lambayeque",
            "condicion": "en Ejercicio",
            "website": "fill",
            "votes_in_election": 1,
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
        "id": 1109,
        "nombre": "María Grimaneza Acuña Peralta",
        "votes_in_election": 11384,
        "leg_period": "Parlamentario 2021 - 2026",
        "party_name": "Alianza para el Progreso",
        "party_id": 1,
        "dist_electoral": "Lambayeque",
        "condicion": "en Ejercicio",
        "website": "https://www.congreso.gob.pe/congresistas2021/GrimanezaAcuna/",
        "image": "https://www.congreso.gob.pe/Storage/tbl_congresistas/fld_47_Fotografia_file/1112-v2Kz5Cm4Di9Bc1L.jpg",
    }
    return {"data": data}
