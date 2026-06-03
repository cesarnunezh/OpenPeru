"""Tests for the ``bill_difference`` Flask route.

Covers the request-time behaviour added by the diff feature:

  * 404 paths for unknown bill / mismatched step
  * ``ETag`` + ``Cache-Control`` headers on a 200
  * ``304`` short-circuit when ``If-None-Match`` matches
  * Structured payload renders into the page
  * Malformed JSON in ``difference_content`` falls through cleanly (no 500)
  * Renderer exception falls through cleanly (no 500)

The route depends on ``app.routes.bills.SessionProcessed`` for DB access;
the ``client`` fixture monkey-patches that name onto an in-memory SQLite
sessionmaker so each test starts from a clean schema.
"""

from __future__ import annotations

import json
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.core.enums import Proponents, TypeBillStep
from backend.database.models import (
    Base,
    Bill,
    BillDifference,
    BillStep,
)


@pytest.fixture()
def session_factory(tmp_path):
    db_path = tmp_path / "processed_test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    yield Session
    engine.dispose()


@pytest.fixture()
def client(monkeypatch, session_factory):
    import app.routes.bills as bills_module
    from app.app import create_app

    monkeypatch.setattr(bills_module, "SessionProcessed", session_factory)
    flask_app = create_app()
    flask_app.testing = True
    return flask_app.test_client()


def _seed_bill(session_factory, *, bill_id="2021_1234"):
    with session_factory() as db:
        db.add(
            Bill(
                id=bill_id,
                title="Test bill",
                summary_congreso="",
                observations="",
                status="presentado",
                proponent=Proponents.CONGRESO,
                bill_approved=False,
                summary_oc="",
            )
        )
        db.commit()


def _seed_step(session_factory, *, step_id=1, bill_id="2021_1234"):
    with session_factory() as db:
        db.add(
            BillStep(
                bill_id=bill_id,
                step_id=step_id,
                vote_step=False,
                step_date=date(2022, 2, 1),
                step_type=TypeBillStep.DICTAMEN_O_ACUERDO_DE_COMISION,
                step_detail="",
            )
        )
        db.commit()


def _seed_difference(
    session_factory,
    *,
    step_id=1,
    bill_id="2021_1234",
    difference_type="modified",
    difference_content: object = None,
):
    payload_json = (
        json.dumps(difference_content) if difference_content is not None else None
    )
    with session_factory() as db:
        db.add(
            BillDifference(
                bill_id=bill_id,
                step_id=step_id,
                prev_step_id=None,
                difference_type=difference_type,
                difference_content=payload_json,
            )
        )
        db.commit()


def _modified_payload():
    return {
        "parser_version": 1,
        "summary": {
            "nodes_total": 1,
            "nodes_changed": 1,
            "nodes_inserted": 0,
            "nodes_deleted": 0,
            "nodes_renamed": 0,
        },
        "nodes": [
            {
                "node_id": "articulo_1",
                "kind": "articulo",
                "status": "matched",
                "match_strategy": "id",
                "a_label": "Artículo 1.-",
                "b_label": "Artículo 1.-",
                "hunks": [
                    {
                        "op": "replace",
                        "a_start": 0,
                        "a_end": 1,
                        "b_start": 0,
                        "b_end": 1,
                        "a_text": "viejo",
                        "b_text": "nuevo",
                        "word_diff": [
                            {
                                "op": "replace",
                                "a_tokens": ["viejo"],
                                "b_tokens": ["nuevo"],
                            }
                        ],
                    }
                ],
            }
        ],
    }


# ── 404 paths ───────────────────────────────────────────────────────────────


def test_returns_404_when_bill_missing(client):
    resp = client.get("/bills/does_not_exist/difference/1")
    assert resp.status_code == 404


def test_returns_404_when_step_missing(client, session_factory):
    _seed_bill(session_factory)
    resp = client.get("/bills/2021_1234/difference/999")
    assert resp.status_code == 404


def test_returns_404_when_step_belongs_to_another_bill(client, session_factory):
    _seed_bill(session_factory, bill_id="2021_1234")
    _seed_bill(session_factory, bill_id="2021_9999")
    _seed_step(session_factory, step_id=42, bill_id="2021_9999")
    resp = client.get("/bills/2021_1234/difference/42")
    assert resp.status_code == 404


# ── ETag + Cache-Control ────────────────────────────────────────────────────


def test_200_sets_etag_and_cache_control(client, session_factory):
    _seed_bill(session_factory)
    _seed_step(session_factory)
    _seed_difference(session_factory, difference_content=_modified_payload())

    resp = client.get("/bills/2021_1234/difference/1")
    assert resp.status_code == 200
    assert resp.headers.get("ETag")
    assert "max-age=300" in resp.headers.get("Cache-Control", "")
    assert "stale-while-revalidate" in resp.headers.get("Cache-Control", "")


def test_if_none_match_returns_304(client, session_factory):
    _seed_bill(session_factory)
    _seed_step(session_factory)
    _seed_difference(session_factory, difference_content=_modified_payload())

    first = client.get("/bills/2021_1234/difference/1")
    etag = first.headers["ETag"]

    second = client.get(
        "/bills/2021_1234/difference/1", headers={"If-None-Match": etag}
    )
    assert second.status_code == 304
    assert second.data == b""


def test_if_none_match_changes_when_language_changes(client, session_factory):
    _seed_bill(session_factory)
    _seed_step(session_factory)
    _seed_difference(session_factory, difference_content=_modified_payload())

    first = client.get("/bills/2021_1234/difference/1")

    with client.session_transaction() as sess:
        sess["lang"] = "es"

    second = client.get(
        "/bills/2021_1234/difference/1",
        headers={"If-None-Match": first.headers["ETag"]},
    )

    assert second.status_code == 200
    assert "Paso" in second.get_data(as_text=True)


def test_etag_changes_when_content_changes(client, session_factory):
    _seed_bill(session_factory)
    _seed_step(session_factory)
    _seed_difference(session_factory, difference_content=_modified_payload())

    etag_v1 = client.get("/bills/2021_1234/difference/1").headers["ETag"]

    with session_factory() as db:
        row = db.get(BillDifference, ("2021_1234", 1))
        row.difference_content = json.dumps(
            {**_modified_payload(), "parser_version": 2}
        )
        db.commit()

    etag_v2 = client.get("/bills/2021_1234/difference/1").headers["ETag"]
    assert etag_v1 != etag_v2


# ── Rendered body ───────────────────────────────────────────────────────────


def test_structured_payload_renders_into_page(client, session_factory):
    _seed_bill(session_factory)
    _seed_step(session_factory)
    _seed_difference(session_factory, difference_content=_modified_payload())

    resp = client.get("/bills/2021_1234/difference/1")
    body = resp.get_data(as_text=True)
    assert 'data-renderer-version="1"' in body
    assert "diff-tok-delete" in body
    assert "diff-tok-insert" in body
    assert "viejo" in body
    assert "nuevo" in body


def test_no_change_path_does_not_render_diff(client, session_factory):
    _seed_bill(session_factory)
    _seed_step(session_factory)
    _seed_difference(
        session_factory,
        difference_type="no_change",
        difference_content=None,
    )

    resp = client.get("/bills/2021_1234/difference/1")
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "No changes between versions." in body


def test_unavailable_path_renders_status_message(client, session_factory):
    # Regression: when a later step has no extracted text, the diff used
    # to render the prior text as fully deleted. It now stores 'unavailable';
    # the template must show the explanatory status instead of a deletion.
    _seed_bill(session_factory)
    _seed_step(session_factory)
    _seed_difference(
        session_factory,
        difference_type="unavailable",
        difference_content=None,
    )

    resp = client.get("/bills/2021_1234/difference/1")
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "Text could not be extracted for comparison." in body
    assert "diff-tok-delete" not in body


# ── Failure-mode fallbacks ──────────────────────────────────────────────────


def test_malformed_json_falls_through_cleanly(client, session_factory):
    _seed_bill(session_factory)
    _seed_step(session_factory)
    with session_factory() as db:
        db.add(
            BillDifference(
                bill_id="2021_1234",
                step_id=1,
                prev_step_id=None,
                difference_type="modified",
                difference_content='{"nodes": [',  # truncated
            )
        )
        db.commit()

    resp = client.get("/bills/2021_1234/difference/1")
    assert resp.status_code == 200
    assert "No difference data available." in resp.get_data(as_text=True)


def test_renderer_exception_falls_through_cleanly(client, session_factory, monkeypatch):
    _seed_bill(session_factory)
    _seed_step(session_factory)
    _seed_difference(session_factory, difference_content=_modified_payload())

    import app.routes.bills as bills_module

    def _boom(_payload):
        raise RuntimeError("renderer is angry")

    monkeypatch.setattr(bills_module, "render_payload_html", _boom)

    resp = client.get("/bills/2021_1234/difference/1")
    assert resp.status_code == 200
    assert "No difference data available." in resp.get_data(as_text=True)
