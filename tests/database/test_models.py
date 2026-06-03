import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timedelta
from backend.database.models import (
    Base,
    Vote,
    VoteEvent,
    VoteCounts,
    Attendance,
    Bill,
    BillCongresistas,
    BillOrganization,
    BillStep,
    CongresistaMetric,
    SemanticBill,
    Congresista,
    Organization,
    CommitteeMembership,
)
from backend import (
    TypeBillStep,
    RoleOrganization,
    VoteOption,
    AttendanceStatus,
    TypeRoleBill,
    Proponents,
    LegPeriod,
    VoteResult,
    TypeCommittee,
    TypeOrganization,
    EmbeddingModel,
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


def test_create_organization(session):
    org = Organization(
        org_name="Congreso del Perú",
        org_type=TypeOrganization.COMMITTEE.value,
        org_subtype=TypeCommittee.COM_ETICA.value,
        org_link="www.congreso.gob.pe/comision",
    )
    session.add(org)
    session.commit()
    assert org.org_link == "www.congreso.gob.pe/comision"


def test_create_congresista(session):
    congresista = Congresista(
        full_name="Ana Maria Torres Torres",
        first_name="Ana Maria",
        last_name="Torres Torres",
        dni="12345678",
        photo_url="https://example.com/photo",
        website="https://example.com",
    )
    session.add(congresista)
    session.commit()
    assert congresista.first_name == "Ana Maria"
    assert congresista.dni == "12345678"


def test_create_bill(session):
    org = Organization(
        org_name="Bancada Test",
        org_type=TypeOrganization.BANCADA.value,
    )
    session.add(org)
    session.flush()

    bill = Bill(
        id="B001",
        title="Ley de Transparencia",
        summary_congreso="Resumen de ley",
        observations="Observaciones aquí",
        status="En trámite",
        proponent=Proponents.CONGRESO.value,
        author_id=1,
        bill_approved=False,
        summary_oc="Resumen OC",
    )
    session.add(bill)
    session.commit()
    assert bill.title == "Ley de Transparencia"


def test_create_bill_vote_event_and_vote(session):
    vote_event = VoteEvent(
        vote_event_id="B_2021_4_1",
        org_id=1,
        bill_id="2021_4",
        event_date=datetime.now().date(),
        result=VoteResult.APROBADO.value,
        votes_in_favor=100,
        votes_against=10,
        votes_abstention=20,
    )
    session.add(vote_event)
    vote = Vote(
        vote_event_id="B_2021_4_1", voter_id=1, option=VoteOption.SI, bancada_id=10
    )
    session.add(vote)
    session.commit()
    assert vote.option == VoteOption.SI


def test_create_motion_vote_event_and_vote(session):
    vote_event = VoteEvent(
        vote_event_id="M_2021_4_1",
        org_id=1,
        motion_id="2021_4",
        event_date=datetime.now().date(),
        result=VoteResult.APROBADO.value,
        votes_in_favor=100,
        votes_against=10,
        votes_abstention=20,
    )
    session.add(vote_event)
    vote = Vote(
        vote_event_id="M_2021_4_1", voter_id=1, option=VoteOption.SI, bancada_id=10
    )
    session.add(vote)
    session.commit()
    assert vote.option == VoteOption.SI


def test_error_bill_and_motion_vote_event(session):
    with pytest.raises(IntegrityError):
        vote_event = VoteEvent(
            vote_event_id="M_2021_4_1",
            org_id=1,
            bill_id="2021_4",
            motion_id="2021_4",
            event_date=datetime.now().date(),
            result=VoteResult.APROBADO.value,
            votes_in_favor=100,
            votes_against=10,
            votes_abstention=20,
        )
        session.add(vote_event)
        session.commit()


def test_attendance(session):
    attendance = Attendance(
        event_id="B_2021_4_1", attendee_id=1, status=AttendanceStatus.PRESENTE
    )
    session.add(attendance)
    session.commit()
    assert attendance.status == AttendanceStatus.PRESENTE


def test_bill_step(session):
    step = BillStep(
        bill_id="B001",
        step_id=1,
        vote_step=True,
        vote_event_id=None,
        step_type=TypeBillStep.VOTACION.value,
        step_date=datetime.now(),
        step_detail="Votación en pleno",
    )
    session.add(step)
    session.commit()
    assert step.step_type == TypeBillStep.VOTACION


def test_membership_validation(session):
    membership = CommitteeMembership(
        id=1,
        person_id=1,
        org_id=1,
        leg_period=LegPeriod.PERIODO_2021_2026.value,
        org_type=TypeOrganization.COMMITTEE.value,
        role=RoleOrganization.MIEMBRO.value,
        start_date=datetime.now() - timedelta(days=30),
        end_date=datetime.now(),
    )
    session.add(membership)
    session.commit()
    assert membership.role == RoleOrganization.MIEMBRO


def test_unique_vote_constraint(session):
    v1 = Vote(vote_event_id="VOT123", voter_id="1", option=VoteOption.NO, bancada_id=10)
    v2 = Vote(
        vote_event_id="VOT123", voter_id="1", option=VoteOption.SI, bancada_id=10
    )  # same unique key

    session.add_all([v1, v2])

    with pytest.raises(IntegrityError):
        session.commit()

    session.rollback()


def test_bill_congresistas(session):
    relation = BillCongresistas(
        bill_id="B001",
        person_id=1,
        bancada_id=10,
        role_type=TypeRoleBill.COAUTHOR.value,
    )
    session.add(relation)
    session.commit()
    assert relation.role_type == TypeRoleBill.COAUTHOR


def test_bill_organization(session):
    committee = Organization(
        org_name="Congreso del Perú",
        org_type=TypeOrganization.COMMITTEE.value,
        org_subtype=TypeCommittee.COM_ETICA.value,
        org_link="www.congreso.gob.pe/comision",
    )
    session.add(committee)
    session.commit()

    relation = BillOrganization(
        bill_id="B001",
        org_id=committee.org_id,
        org_type=TypeOrganization.COMMITTEE.value,
        presentation_date=datetime.now().date(),
    )
    session.add(relation)
    session.commit()
    assert relation.org_id == 1


def test_vote_counts(session):
    vote_count = VoteCounts(
        vote_event_id="B_2021_4_1", option=VoteOption.SI, bancada_id=10, count=40
    )
    session.add(vote_count)
    session.commit()
    assert vote_count.count == 40


def test_create_congresista_metric(session):
    metric = CongresistaMetric(
        cong_id=1,
        leg_period=LegPeriod.PERIODO_2021_2026.value,
        avg_attendance=0.75,
        bills_auth=2,
        bills_success_rate=0.5,
        motions_auth=1,
        motions_success_rate=1.0,
    )

    session.add(metric)
    session.commit()

    saved = session.get(
        CongresistaMetric,
        (1, LegPeriod.PERIODO_2021_2026.value),
    )
    assert saved.avg_attendance == 0.75
    assert saved.bills_auth == 2
    assert saved.motions_success_rate == 1.0


def test_create_semantic_bill(session):
    bill = Bill(
        id="B002",
        title="Ley de Datos Abiertos",
        summary_congreso="Resumen",
        observations="",
        status="En trámite",
        proponent=Proponents.CONGRESO.value,
        author_id=None,
        bill_approved=False,
        summary_oc="Resumen OC",
    )
    semantic_bill = SemanticBill(
        bill_id="B002",
        chunk_index=0,
        text="Texto para búsqueda semántica",
        embedding=[0.0] * 768,
        embedding_model_name=EmbeddingModel.MULTILINGUAL_E5_BASE.value,
    )

    session.add(bill)
    session.add(semantic_bill)
    session.commit()

    saved = session.query(SemanticBill).filter_by(bill_id="B002").one()
    assert saved.chunk_index == 0
    assert saved.embedding_model_name == EmbeddingModel.MULTILINGUAL_E5_BASE
