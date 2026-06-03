# Endpoints Documentation

## Landing Page

| Property | Value |
|----------|-------|
| URL | `/home` |
| Method | `GET` |
| Parameters | None |
| Response | HTML landing page |

**Template Context Variables:** None required

## Bills Search Page

| Property | Value |
|----------|-------|
| URL | `/bills` |
| Method | `GET` |
| Parameters | `query` (keyword to search bills) or `bill_number` |
| Response | HTML page for bill search |

**Template Context Variables:**

```json

  "bills_id": 123,
  "bills_name": "Environmental Protection act",
  "bills_number": "N° 32014",
  "status": "Approved"

```

## Bills Detail Page

| Property | Value |
|----------|-------|
| URL | `/bills/<id>` |
| Method | `GET` |
| Parameters | `bill_id` |
| Response | HTML page showing bill detail and timeline |

**Template Context Variables:**

```json

  "bills_id": 123,
  "bills_number": "32014",
  "title": "Environmental Protection Act",
  "summary": "An act which establishes a comprehensive legal framework to protect the environment",
  "status": "Approved",
  "step_id": 1,
  "step_type": "committee_approvement",
  "step_date": "2025-03-01"

```

## Bills Difference Page

| Property | Value |
|----------|-------|
| URL | `/bills/<bill_id>/difference/<step_id>` |
| Method | `GET` |
| Parameters | `bill_id` (string), `step_id` (int) — the *new* step |
| Response | HTML page (200) or `304 Not Modified` (ETag match) |
| Caching | `ETag` + `Cache-Control: public, max-age=300, stale-while-revalidate=86400` |

Full frontend contract (HTML structure, CSS classes, stability promise,
sample fixtures, SPA integration notes): see
[`bill_difference_contract.md`](bill_difference_contract.md).


## Votes Page

| Property | Value |
|----------|-------|
| URL | `/bills/<id>/votes/<votes_id>` |
| Method | `GET` |
| Parameters | `bill_id` and `vote_event_id` |
| Response | HTML page showing voting results |

**Template Context Variables:**

```json

  "bill_id": 123,
  "bills_number": "N° 32014",
  "bill_name": "Environmental Protection Act",
  "summary": "An act which establishes a comprehensive legal framework to protect the environment",
  "vote_step": "second_voting",
  "vote_status": "approved",
  "in_favor": 74,
  "against": 36,
  "abst": 20,
  "congressman_name": "Juan Perez",
  "congressman_vote": "in_favor",
  "bancada_name": "bancada1",
  "bancada_in_favor": 20,
  "bancada_against": 5,
  "bancada_abst": 0,
  "vote_register_id": "document_id",
  "vote_register_url": "https://example.com/file.pdf",
  "session_video_id": "video_id",
  "session_video_url": "https://example_video.com"
```
## Congress Member Search

| Property | Value |
|----------|-------|
| URL | `/congresista` |
| Method | `GET` |
| Parameters | `query` (keyword to search congresista) |
| Response | HTML page for congress member search |

**Template Context Variables:**

```json

  "id_congresista": 29304,
  "nombre": "Juan Perez"

```

## Congress Member Detail

| Property | Value |
|----------|-------|
| URL | `/congresista/<id>` |
| Method | `GET` |
| Parameters | `congresista_id` |
| Response | HTML page showing details, metrics and last votes of the congress member |

**Template Context Variables:**

```json

  "congresista_id": 10345,
  "nombre": "Miguel Hernandez",
  "photo_url": "http://congreso.example/photo.jpg",
  "dist_electoral": "Lima",
  "party_name": "Fuerza Popular",
  "current_bancada": "Avanza Pais",
  "leg_period": "2021-2026",
  "condition": "Active",
  "attendance_rate": 0.54,
  "bills_authored_count": 45,
  "success_rate": 0.20,
  "org_id": 5647,
  "org_name": "Economy and Finance",
  "committee_role": "president",
  "committee_start_date": "2024-10-24",
  "committee_end_date": "2025-05-10",
  "vote_event_id": 75461,
  "bill_id": 123,
  "bill_title": "Sample Bill",
  "bill_result": "approved"

```


## Congress Member Bills

| Property | Value |
|----------|-------|
| URL | `/congresista/<id>/bills` |
| Method | `GET` |
| Parameters | `congresista_id` |
| Response | HTML page showing the bills authored by the congress member |

**Template Context Variables:**

```json

  "congresista_id": 45897,
  "nombre": "Martha Hildebrandt",
  "bill_id": 53790,
  "title": "Bill for making..."

```
## Information Pages

| Property | Value |
|----------|-------|
| URL | `/information` |
| Method | `GET` |
| Parameters | Various (see context variables) |
| Response | JSON, CSV, or XLSX format |

**Template Context Variables:**

```json

  "topic": "education",
  "date_from": "2024-01-01",
  "date_to": "2024-12-31",
  "sector_id": 3,
  "committee_id": 5647,
  "congressmember_id": 10345,
  "bill_id": "01234/2024-CR",
  "title": "Ley que modifica...",
  "presentation_date": "2024-05-14",
  "status": "En comisión",
  "total_results": 1,
  "date_proposed": "2024-05-14",
  "date_approved": null,
  "step_id": 901,
  "step_type": "assigned_to_committee",
  "step_date": "2024-05-20",
  "step_detail": "Sent to Economy and Finance Committee",
  "author_congresista_id": 10345,
  "author_nombre": "Miguel Hernandez",
  "committee_org_id": 5647,
  "committee_org_name": "Economy and Finance",
  "sector_name": "Education",
  "vote_event_id": 75461,
  "vote_date": "2024-06-10",
  "vote_result": "approved",
  "vote_option": "yes",
  "vote_count": 72

```
