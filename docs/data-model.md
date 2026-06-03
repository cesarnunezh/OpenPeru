# Data Model

This document describes the data entities, relationships, and storage layers in OpenPerú/CongresoAbierto. It serves as a reference for contributors working with the database models, processing pipelines, or API layer.

## Overview

CongresoAbierto maintains two separate database layers:

- **Raw layer**: stores data as close to the source as possible. Each record maps to a scraped page, downloaded PDF, or extracted table row. Raw data is append-only and never modified after ingestion, which make it possible to keep track to changes in contents.
- **Processed layer**: stores cleaned, validated, and normalized entities ready for analysis and consumption. This is the layer the API and frontend will query.

Both layers use SQLite and are modeled with SQLAlchemy ORM. Pydantic schemas enforce validation before records enter the processed layer.

## Data Sources

All data originates from publicly available information published by the Peruvian Congress (Congreso de la República):

| Source | Format | Content |
|--------|--------|---------|
| congreso.gob.pe | HTML / Internal API | Bills, Motions, Committees, Congressmembers, etc |
| Documents related to Bills/Motions | Scanned PDF | Attendance and votes, bills/motions content, letters |
| Live sessions streamings | Video / YouTube API | Plenary and Committee Sessions |


## Raw Tables (Raw Layer)

### Common Metadata Columns

Every raw table includes:

| Column | Type | Description |
|---|---|---|
| timestamp | DateTime | When the scraping task ran |
| last_update | Boolean | Whether this row is the most recent scrape for its entity |
| changed | Boolean | Whether this scrape differs from the previous one |
| processed | Boolean | Whether this row has been processed into the processed layer |

### raw_bills

Stores scraped bill (proyecto de ley) data from the Congress website.

| Column | Type | Key | Description |
|---|---|---|---|
| id | String | PK | Bill identifier (e.g., "00123/2024-CR") |
| timestamp | DateTime | PK | Scrape timestamp (composite PK with id) |
| general | String (nullable) | | Main bill info (HTML/text) |
| committees | String (nullable) | | Committee assignment info |
| congresistas | String (nullable) | | Author and proponent info |
| steps | String (nullable) | | Legislative step info |

### raw_bill_documents

Stores extracted text from PDF documents linked to bills.

| Column | Type | Key | Description |
|---|---|---|---|
| id | Integer | PK | Auto-increment |
| bill_id | String | IX | Reference to the bill |
| step_date | DateTime | | Date of the related event |
| seguimiento_id | String | | Event identifier |
| archivo_id | String | | Document file identifier |
| url | String | | Document URL |
| text | String | | Extracted text from PDF |

Indexed on `(bill_id, last_update)` and `(bill_id, processed)`.

### raw_motions

Stores scraped motion (moción) data. Same structure as `raw_bills` but without `committees`.

| Column | Type | Key | Description |
|---|---|---|---|
| id | String | PK | Motion identifier |
| timestamp | DateTime | PK | Scrape timestamp (composite PK) |
| general | String (nullable) | | Main motion info |
| congresistas | String (nullable) | | Author and proponent info |
| steps | String (nullable) | | Motion step info |

### raw_motion_documents

Same structure as `raw_bill_documents`, with `motion_id` instead of `bill_id`.

### raw_congresistas

Stores scraped congressperson profile and membership data.

| Column | Type | Key | Description |
|---|---|---|---|
| id | Integer | PK | Auto-increment |
| leg_period | String | | Legislative period |
| url | String | | Congressperson's website URL |
| profile_content | String | | HTML from the profile tab |
| memberships_content | String (nullable) | | API response for memberships (JSON) |

### raw_committees

Stores scraped committee information.

| Column | Type | Key | Description |
|---|---|---|---|
| id | Integer | PK | Auto-increment |
| legislative_year | Integer | | Legislative year |
| committee_type | String | | Type of committee |
| raw_html | String | | Full HTML content |

### raw_bancadas

Stores scraped bancada (parliamentary group) information.

| Column | Type | Key | Description |
|---|---|---|---|
| id | Integer | PK | Auto-increment |
| legislative_period | String | | Legislative period |
| raw_html | String | | Full HTML content |

### raw_organizations

Stores scraped organizational data for bodies such as Junta de Portavoces, Consejo Directivo, Mesa Directiva, and Comisión Permanente.

| Column | Type | Key | Description |
|---|---|---|---|
| id | Integer | PK | Auto-increment |
| legislative_year | Integer | | Legislative year |
| type_org | String | | Organization type |
| org_link | String | | Organization website URL |
| raw_html | String | | Full HTML content |

### raw_leyes

Stores raw law data extracted from the Congress website.

| Column | Type | Key | Description |
|---|---|---|---|
| id | Integer | PK | Auto-increment |
| data | String | | Raw XML data for the law |

## Core Entities (Processed Layer)

### Congresista

Represents a member of Congress. Uniqueness is enforced on `(nombre, leg_period)`.

| Column | Type | Key | Description |
|---|---|---|---|
| id | Integer | PK | Auto-increment |
| nombre | String | UQ | Full name |
| leg_period | Enum(LegPeriod) | UQ | Legislative period |
| party_name | String | | Political party name |
| current_bancada | String | | Current parliamentary group name |
| votes_in_election | Integer | | Votes received in election |
| dist_electoral | String (nullable) | | Electoral district |
| condicion | String | | Status (e.g., active, inactive) |
| website | String | | Official website URL |
| photo_url | String | | Official photo URL |

### Bancada

Represents a parliamentary group (grupo parlamentario).

| Column | Type | Key | Description |
|---|---|---|---|
| bancada_id | Integer | PK | Auto-increment |
| leg_year | Enum(LegislativeYear) | | Legislative year |
| bancada_name | String | | Group name |

### BancadaMembership

Tracks which congresista belongs to which bancada per legislative year.

| Column | Type | Key | Description |
|---|---|---|---|
| id | Integer | PK | Auto-increment |
| leg_year | Enum(LegislativeYear) | | Legislative year |
| person_id | Integer | FK → congresistas.id | |
| bancada_id | Integer | FK → bancadas.bancada_id | |

### Organization

Represents legislative organizations: committees, Junta de Portavoces, Consejo Directivo, Mesa Directiva, Comisión Permanente. Uniqueness on `(leg_period, leg_year, org_name, org_type)`.

| Column | Type | Key | Description |
|---|---|---|---|
| org_id | Integer | PK | Auto-increment |
| leg_period | Enum(LegPeriod) | UQ | Legislative period |
| leg_year | Enum(LegislativeYear) | UQ | Legislative year |
| org_name | String | UQ | Organization name |
| org_type | Enum(TypeOrganization) | UQ | Organization type |
| comm_type | Enum(TypeCommittee) (nullable) | | Committee subtype, if applicable |
| org_link | String | | Website URL |

### Membership

Tracks a person's role in an organization during a time period.

| Column | Type | Key | Description |
|---|---|---|---|
| id | Integer | PK | Auto-increment |
| role | Enum(RoleOrganization) | | Role (e.g., vocero, miembro, presidente) |
| person_id | Integer | FK → congresistas.id | |
| org_id | Integer | FK → organizations.org_id | |
| start_date | DateTime | | Start of membership |
| end_date | DateTime | | End of membership |

### Bill

Represents a bill (proyecto de ley).

| Column | Type | Key | Description |
|---|---|---|---|
| id | String | PK | Bill identifier (e.g., "00123/2024-CR") |
| leg_period | Enum(LegPeriod) | | Legislative period |
| legislature | Enum(Legislature) | | Legislature |
| presentation_date | DateTime | | Date filed |
| title | String | | Bill title |
| summary | String | | Bill summary |
| observations | String | | Observations |
| complete_text | String | | Full text |
| status | String | | Current status |
| proponent | Enum(Proponents) | | Proponent type |
| author_id | Integer (nullable) | FK → congresistas.id | Primary author |
| bancada_id | Integer (nullable) | FK → bancadas.bancada_id | Associated bancada |
| bill_approved | Boolean | | Whether the bill has been approved/published |

### BillCongresistas

Junction table linking bills to congresistas with their role. Composite PK on `(bill_id, person_id)`.

| Column | Type | Key | Description |
|---|---|---|---|
| bill_id | String | PK, FK → bills.id | |
| person_id | Integer | PK, FK → congresistas.id | |
| role_type | Enum(RoleTypeBill) | | Role: author, coauthor, adherente, etc. |

### BillCommittees

Junction table linking bills to committees. Unique on `(bill_id, committee_id)`.

| Column | Type | Key | Description |
|---|---|---|---|
| id | Integer | PK | Auto-increment |
| bill_id | String | FK → bills.id | |
| committee_id | Integer | FK → organizations.org_id | |

### BillStep

Tracks the procedural history of a bill.

| Column | Type | Key | Description |
|---|---|---|---|
| id | Integer | PK | |
| bill_id | String (nullable) | FK → bills.id, IX | |
| step_type | Enum(BillStepType) | | Step type (e.g., vote, assigned to committee, presented) |
| step_date | DateTime | | Date the step occurred |
| step_detail | String | | Details of the step |

### BillDocument

Stores extracted text from PDF documents linked to specific bill steps. Unique on `(bill_id, step_id, archivo_id)`.

| Column | Type | Key | Description |
|---|---|---|---|
| bill_id | String | FK → bills.id | |
| step_id | Integer | FK → bill_steps.id | |
| archivo_id | Integer | PK | File identifier |
| url | String | | Document URL |
| text | String | | Extracted text |
| vote_doc | Boolean | | Whether this document is a vote record |

### Motion

Represents a motion (moción).

| Column | Type | Key | Description |
|---|---|---|---|
| id | String | PK | Motion identifier |
| leg_period | Enum(LegPeriod) | | Legislative period |
| legislature | Enum(Legislature) | | Legislature |
| presentation_date | DateTime | | Date filed |
| motion_type | Enum(MotionType) | | Type of motion |
| summary | String | | Summary |
| observations | String | | Observations |
| complete_text | String | | Full text |
| status | String | | Current status |
| author_id | Integer (nullable) | FK → congresistas.id | Primary author |
| motion_approved | Boolean | | Whether the motion has been approved |

### MotionCongresistas

Junction table linking motions to congresistas. Composite PK on `(motion_id, person_id)`.

| Column | Type | Key | Description |
|---|---|---|---|
| motion_id | String | PK, FK → motions.id | |
| person_id | Integer | PK, FK → congresistas.id | |
| role_type | Enum(RoleTypeBill) | | Role: author, coauthor, adherente, etc. |

### MotionStep

Tracks the procedural history of a motion.

| Column | Type | Key | Description |
|---|---|---|---|
| id | Integer | PK | |
| motion_id | String (nullable) | FK → motions.id, IX | |
| step_type | Enum(MotionStepType) | | Step type |
| step_date | DateTime | | Date the step occurred |
| step_detail | String | | Details of the step |

### MotionDocument

Stores extracted text from PDF documents linked to specific motion steps. Unique on `(motion_id, step_id, archivo_id)`.

| Column | Type | Key | Description |
|---|---|---|---|
| motion_id | String | FK → motions.id | |
| step_id | Integer | FK → motion_steps.id | |
| archivo_id | Integer | PK | File identifier |
| url | String | | Document URL |
| text | String | | Extracted text |
| vote_doc | Boolean | | Whether this document is a vote record |

### VoteEvent

Represents a vote event in a plenary session. Unique on `(leg_period, bill_or_motion, bill_motion_id, date)`.

| Column | Type | Key | Description |
|---|---|---|---|
| id | Integer | PK | Auto-increment |
| leg_period | Enum(LegPeriod) | UQ | Legislative period |
| bill_or_motion | String | UQ | Whether this vote is on a bill or motion |
| bill_motion_id | String | UQ, IX | Identifier for the bill or motion voted on |
| date | DateTime | UQ | Date of the vote |
| result | Enum(VoteResult) | | Outcome: aprobado, rechazado, etc. |
| majority_type | Enum(MajorityType) (nullable) | | Type of majority required |

### Vote

Records how each congresista voted. Unique on `(vote_event_id, voter_id)`.

| Column | Type | Key | Description |
|---|---|---|---|
| vote_event_id | String | PK, FK → vote_events.id, IX | |
| voter_id | Integer | FK → congresistas.id, IX | |
| option | Enum(VoteOption) | | Vote cast: yes, no, abstain |
| bancada_id | Integer | FK → bancadas.bancada_id | Voter's bancada at time of vote |

### VoteCounts

Pre-aggregated vote counts by bancada. Composite PK on `(vote_event_id, option, bancada_id)`.

| Column | Type | Key | Description |
|---|---|---|---|
| vote_event_id | String | PK, FK → vote_events.id, IX | |
| option | Enum(VoteOption) | PK | Vote option |
| bancada_id | Integer | PK, FK → bancadas.bancada_id, IX | |
| count | Integer | | Number of votes |

### Attendance

Records attendance at vote events. Unique on `(event_id, attendee_id)`.

| Column | Type | Key | Description |
|---|---|---|---|
| event_id | Integer | PK, FK → vote_events.id, IX | |
| attendee_id | Integer | FK → congresistas.id, IX | |
| status | Enum(AttendanceStatus) | | Present, absent, licencia |

### Ley

Represents an enacted law (ley).

| Column | Type | Key | Description |
|---|---|---|---|
| id | String | PK | Law identifier |
| title | String | | Law title |
| bill_id | String | | Bill that originated this law |


## Raw Layer

The raw layer mirrors the source structure rather than the domain model. Typical raw tables include:

- **raw_scraped_pages**: HTML content, URL, scrape timestamp, scraper identifier
- **raw_table_rows**: individual rows extracted from HTML tables, with the source page reference
- **raw_pdf_metadata**: PDF file path, source URL, download timestamp, page count
- **raw_ocr_output**: extracted text per PDF page, confidence scores, processing metadata

Raw records include a `source_url`, `scraped_at` timestamp, and `scraper_version` for traceability.

## Planned Extensions

| Extension | Impact on Data Model |
|---|---|
| LLM bill summaries | New table: `resumen_proyecto_ley` linked to `proyecto_ley`, storing generated summaries, model version, and generation timestamp |
| Edition tracking | New table: `edicion_proyecto_ley` tracking text diffs between bill versions |
| Semantic search on debates | New table: `debate_fragmento` storing debate text chunks with speaker attribution; vector embeddings stored in a separate vector store (not SQLite) |
| Public API | No schema changes; read-only access to processed layer |

## Conventions

- All table and column names use **snake_case** in Spanish to match the domain language.
- Primary keys are auto-incrementing integers named `id`.
- Foreign keys follow the pattern `{entity}_id`.
- Timestamps use ISO 8601 format.
- Nullable fields are explicitly marked; non-nullable fields must always be populated.
- The `periodo_legislativo` field (e.g., "2021-2026") appears across multiple tables to partition data by legislative period.
