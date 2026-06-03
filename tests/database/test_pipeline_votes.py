from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import (
    AttendanceStatus,
    LegPeriod,
    Proponents,
    RoleOrganization,
    TypeMotion,
    TypeOrganization,
    TypeRoleBill,
    VoteResult,
)
from backend.database.crud.pipeline_votes import refresh_congresista_metrics
from backend.database.models import (
    Attendance,
    Base,
    Bill,
    BillCongresistas,
    BillOrganization,
    ChamberMembership,
    Congresista,
    CongresistaMetric,
    Motion,
    MotionCongresistas,
    MotionOrganization,
    Organization,
    VoteEvent,
)


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


def test_refresh_congresista_metrics_rebuilds_without_committing(session):
    """`refresh_congresista_metrics` should rebuild derived metric rows from chamber memberships, attendance, authored bills, and authored motions without committing."""

    person = Congresista(
        id=1,
        full_name="Ana Torres",
        first_name="Ana",
        last_name="Torres",
        dni="12345678",
        photo_url="https://example.com/ana.jpg",
        website="https://example.com/ana",
    )
    chamber = Organization(
        org_id=1,
        org_name="Cámara de Diputados",
        org_type=TypeOrganization.CHAMBER,
    )
    bancada = Organization(
        org_id=2,
        org_name="Bancada Test",
        org_type=TypeOrganization.BANCADA,
        parent_org_id=1,
    )

    session.add_all([person, chamber, bancada])
    session.flush()

    session.add(
        ChamberMembership(
            person_id=1,
            org_id=1,
            leg_period=LegPeriod.PERIODO_2021_2026,
            org_type=TypeOrganization.CHAMBER,
            role=RoleOrganization.DIPUTADO,
            start_date=date(2021, 7, 27),
            end_date=date(2026, 7, 26),
            condicion="Activo",
            votes_in_election=10000,
            dist_electoral="Lima",
        )
    )

    session.add(
        Bill(
            id="B_2021_1",
            title="Ley de métricas",
            summary_congreso="Resumen",
            observations="",
            status="Aprobado",
            proponent=Proponents.CONGRESO,
            author_id=1,
            bill_approved=True,
            summary_oc="",
        )
    )
    session.add(
        BillCongresistas(
            bill_id="B_2021_1",
            person_id=1,
            bancada_id=2,
            role_type=TypeRoleBill.AUTHOR,
        )
    )
    session.add(
        BillOrganization(
            bill_id="B_2021_1",
            org_id=1,
            org_type=TypeOrganization.CHAMBER,
            presentation_date=date(2022, 1, 1),
        )
    )

    session.add(
        Motion(
            id="M_2021_1",
            motion_type=TypeMotion.SALUDO,
            summary_congreso="Resumen",
            observations="",
            status="Rechazado",
            author_id=1,
            motion_approved=False,
            summary_oc="",
        )
    )
    session.add(
        MotionCongresistas(
            motion_id="M_2021_1",
            person_id=1,
            bancada_id=2,
            role_type=TypeRoleBill.AUTHOR,
        )
    )
    session.add(
        MotionOrganization(
            motion_id="M_2021_1",
            org_id=1,
            org_type=TypeOrganization.CHAMBER,
            presentation_date=date(2022, 1, 2),
        )
    )

    session.add_all(
        [
            VoteEvent(
                vote_event_id="B_2021_1_1",
                org_id=1,
                bill_id="B_2021_1",
                event_date=date(2022, 1, 15),
                result=VoteResult.APROBADO,
                votes_in_favor=1,
                votes_against=0,
                votes_abstention=0,
            ),
            VoteEvent(
                vote_event_id="M_2021_1_1",
                org_id=1,
                motion_id="M_2021_1",
                event_date=date(2022, 1, 16),
                result=VoteResult.RECHAZADO,
                votes_in_favor=0,
                votes_against=1,
                votes_abstention=0,
            ),
        ]
    )

    session.add_all(
        [
            Attendance(
                event_id="B_2021_1_1",
                attendee_id=1,
                status=AttendanceStatus.PRESENTE,
            ),
            Attendance(
                event_id="M_2021_1_1",
                attendee_id=1,
                status=AttendanceStatus.AUSENTE,
            ),
        ]
    )

    session.flush()

    count = refresh_congresista_metrics(session)

    metric = session.get(
        CongresistaMetric,
        (1, LegPeriod.PERIODO_2021_2026),
    )

    assert count == 1
    assert metric is not None
    assert metric.avg_attendance == pytest.approx(0.5)
    assert metric.bills_auth == 1
    assert metric.bills_success_rate == pytest.approx(1.0)
    assert metric.motions_auth == 1
    assert metric.motions_success_rate == pytest.approx(0.0)
