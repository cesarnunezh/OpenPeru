# 📊 Congreso Data Model Tracker

This document tracks the status, update frequency, and source details for each entity in the OpenPeru data pipeline.

## 🔄 Summary

| Object            | Status - Raw    | Status - Clean  | Source/Notes |
|-------------------|-----------------|--------------|--------|
| Congresistas      | ✅ Finished    | 🔴 Not implemented | Official web page |
| Bancadas          | ✅ Finished    | 🔴 Not implemented | Official web page |
| Organization      | ✅ Finished    | 🔴 Not implemented | Official web page |
| Committee         | ✅ Finished    | 🔴 Not implemented | Official web page |
| Bill              | ✅ Finished    | 🔴 Not implemented | Official web page |
| BillDocuments     | ✅ Finished    | N/A                | Official web page |
| Motion            | ✅ Finished    | 🔴 Not implemented | Official web page |
| MotionDocuments   | ✅ Finished    | N/A                | Official web page |
| BillCongresista   | N/A            | 🔴 Not implemented | Official web page |
| BillCommittee     | N/A            | 🔴 Not implemented | Official web page |
| BillSteps         | N/A            | 🔴 Not implemented | Official web page |
| MotionCongresista | N/A            | 🔴 Not implemented | Official web page |
| MotionCommittee   | N/A            | 🔴 Not implemented | Official web page |
| MotionSteps       | N/A            | 🔴 Not implemented | Official web page |
| VoteEvent         | N/A            | 🔴 Not implemented | PDF |
| Vote              | N/A            | ⏳ In Progress | PDF |
| VoteCounts        | N/A            | 🔴 Not implemented | PDF |
| Membership        | N/A            | 🔴 Not implemented | Congressmen web page |
| BancadaMembership | N/A            | 🔴 Not implemented | Congressmen web page |
| Attendance        | N/A            | 🔴 Not implemented | PDF |
_Last updated: Nov 28th 2025_

---

## 🧑‍💼 Congresistas

- **File:** [`scrape_congresitas.py`](\scrapers\scrape_congresistas.py)
- **Status:** ✅ Finished
- **Update Frequency:** Yearly
- **Source Type:** Web
- **Source URL:** [https://www.congreso.gob.pe/pleno/congresistas/](https://www.congreso.gob.pe/pleno/congresistas/)


## 🏛️ Parties

- **File:** [`scrape_congresitas.py:get_or_create_party`](\scrapers\scrape_congresistas.py)
- **Status:** ✅ Finished
- **Update Frequency:** Yearly
- **Source Type:** Web
- **Source URL:** [https://www.congreso.gob.pe/pleno/congresistas/](https://www.congreso.gob.pe/pleno/congresistas/)

## 🏛️ Bancadas

- **File:** Pending
- **Status:** 🔴 Not implemented 
- **Update Frequency:** Monthly
- **Source Type:** Web
- **Source URL:** [https://www.congreso.gob.pe/gruposparlamentarios/reglamentos](https://www.congreso.gob.pe/gruposparlamentarios/reglamentos)
- **Notes:** Validate party acronyms to link with votes.

## 🧩 Organization (Committee)

- **File:** [`scrape_committees.py`](\scrapers\scrape_committees.py)
- **Status:** 🟡 Pending review
- **Update Frequency:** Yearly (Every July)
- **Source Type:** Web
- **Source URL:** [https://www.congreso.gob.pe/CuadrodeComisiones](https://www.congreso.gob.pe/CuadrodeComisiones)

## 📄 Bill (Proyecto de Ley)

- **File:** [`scrapers/scrape_project_bills.py`](\scrapers/scrape_project_bills.py)
- **Status:** ⏳ In progress
- **Update Frequency:** Weekly
- **Source Type:** Congress Web API
- **Source URL:** [https://wb2server.congreso.gob.pe/spley-portal/#/expediente/search](https://wb2server.congreso.gob.pe/spley-portal/#/expediente/search)
- Notes: Pending to update the code with the new data model (Pydantic schema).

## 👤 Bill_Congresista

- **File:** Pending to create file/function
- **Status:** 🔴 Not implemented 
- **Update Frequency:** Weekly
- **Source Type:** Congress Web API
- **Source URL:** [https://wb2server.congreso.gob.pe/spley-portal/#/expediente/search](https://wb2server.congreso.gob.pe/spley-portal/#/expediente/search)
- Notes: Pending to update to create the functions (Pydantic schema).

## 👥 Bill_Committee

- **File:** Pending to create file/function
- **Status:** 🔴 Not implemented
- **Update Frequency:** Weekly?
- **Source URL:** [https://wb2server.congreso.gob.pe/spley-portal/#/expediente/2021/1701](https://wb2server.congreso.gob.pe/spley-portal/#/expediente/2021/1701)
- **Notes:** Pending to update to create the functions (Pydantic schema).


## 🪜 Bill_Steps

- **File:** [`scrapers/scrape_project_bills.py`](\scrapers/scrape_project_bills.py)
- **Status:** 🔴 Not implemented
- **Update Frequency:** Weekly
- **Source Type:** Congress Web API
- **Source URL:** [https://wb2server.congreso.gob.pe/spley-portal/#/expediente/search](https://wb2server.congreso.gob.pe/spley-portal/#/expediente/search)
- Notes: Pending to update the code with the new data model (Pydantic schema).

## 🗳️ Vote_Event

- **File:** [`scrapers/extract_votes.py`](\scrapers/extract_votes.py)
- **Status:** 🔴 Not implemented
- **Update Frequency:** Weekly
- **Source Type:** PDFs
- **Source URL**: `scrape_project_bills.py` 
- **Notes:** Requires relation to Bill and/or BillSteps

## 🗳️ Vote

- **File:** [`scrapers/extract_votes.py`](\scrapers/extract_votes.py)
- **Status:** 🔴 Not implemented
- **Update Frequency:** Weekly
- **Source Type:** PDFs
- **Source URL**: `scrape_project_bills.py` 
- **Notes:** Requires relation to Vote_Event
---

## 🔢 Vote_Counts

- **File:** `scrapers/extract_votes.py`
- **Status:** ⏳ In progress
- **Update Frequency:** Weekly
- **Source Type:** PDFs
- **Source URL**: `scrape_project_bills.py` 
- **Notes:** Requires relation to Vote_Event

## 🧑‍💼 Membership

- **File:** [`scrapers/scrape_membership.py`](\scrapers\scrape_membership.py)
- **Status:** ⏳ In progress
- **Update Frequency:** Yearly
- **Source Type:** Web
- **Source URL:** Congressmen's web page
- **Notes:** Requires relation to Congresista

## 📆 Event

- **File:** Pending to create file/function
- **Status:** 🔴 Not implemented
- **Update Frequency:** Weekly
- **Source Type:** PDF
- **Source URL:** [Asistencia al Pleno](https://www.congreso.gob.pe/AsistenciasVotacionesPleno/asistencia-votacion-pleno), [Asistencia a Comisión Permanente](https://www.congreso.gob.pe/AsistenciasVotacionesPleno/asistencia-comisionpermanente), [Asistencia a Comisiones](https://www.congreso.gob.pe/actascomisiones/)

## 📆 Attendance

- **File:** Pending to create file/function
- **Status:** 🔴 Not implemented
- **Update Frequency:** Weekly
- **Source Type:** PDF
- **Source URL:** `scrape_project_bills.py` 
