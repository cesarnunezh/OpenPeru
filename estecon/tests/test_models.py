import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timedelta
from estecon.backend.database.models import (
    Base, Vote, VoteEvent, VoteCounts, Attendance, Bill, BillCongresistas,
    BillCommittees, BillStep, Committee, Congresista, Organization, Membership,
    VoteOption, AttendanceStatus, BillStepType, RoleTypeBill, Proponents,
    LegPeriod, Legislature, LegislativeYear, TypeOrganization, RoleOrganization
)

@pytest.fixture(scope="module")
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)

def test_create_organization(session):
    org = Organization(
        leg_period=LegPeriod.PERIODO_2021_2026,
        leg_year=LegislativeYear.YEAR_2022,
        org_id=1,
        org_name="Congreso del Perú",
        org_type=TypeOrganization.COMMITTEE
    )
    session.add(org)
    session.commit()
    assert org.org_id == 1

def test_create_congresista(session):
    congresista = Congresista(
        id=1,
        leg_period=LegPeriod.PERIODO_2021_2026,
        nombre="Ana Torres",
        party_id=100,
        votes_in_election=25000,
        dist_electoral="Lima",
        condicion="Activo",
        website="https://example.com"
    )
    session.add(congresista)
    session.commit()
    assert congresista.nombre == "Ana Torres"

def test_create_bill(session):
    bill = Bill(
        id="B001",
        leg_period=LegPeriod.PERIODO_2021_2026,
        legislature=Legislature.LEGISLATURA_2021_1,
        presentation_date=datetime.now(),
        title="Ley de Transparencia",
        summary="Resumen de ley",
        observations="Observaciones aquí",
        complete_text="Texto completo",
        status="En trámite",
        proponent=Proponents.CONGRESO,
        author_id=1,
        bancada_id=10,
        bill_approved=False
    )
    session.add(bill)
    session.commit()
    assert bill.title == "Ley de Transparencia"

def test_create_vote_event_and_vote(session):
    vote_event = VoteEvent(
        id="VOT123",
        org_id=1,
        leg_period=LegPeriod.PERIODO_2021_2026,
        bill_id="B001",
        date=datetime.now()
    )
    session.add(vote_event)
    vote = Vote(
        vote_event_id="VOT123",
        voter_id=1,
        option=VoteOption.SI,
        bancada_id=10
    )
    session.add(vote)
    session.commit()
    assert vote.option == VoteOption.SI

def test_attendance(session):
    attendance = Attendance(
        org_id=1,
        event_id="VOT123",
        attendee_id=1,
        status=AttendanceStatus.PRESENTE
    )
    session.add(attendance)
    session.commit()
    assert attendance.status == AttendanceStatus.PRESENTE

def test_bill_step(session):
    step = BillStep(
        id=1,
        bill_id="B001",
        step_type=BillStepType.VOTE,
        step_date=datetime.now(),
        step_detail="Votación en pleno",
        step_url="http://example.com"
    )
    session.add(step)
    session.commit()
    assert step.step_type == BillStepType.VOTE

def test_membership_validation(session):
    membership = Membership(
        id=1,
        role=RoleOrganization.MIEMBRO,
        person_id=1,
        org_id=1,
        start_date=datetime.now() - timedelta(days=30),
        end_date=datetime.now()
    )
    session.add(membership)
    session.commit()
    assert membership.role == RoleOrganization.MIEMBRO

def test_unique_vote_constraint(session):
    vote = Vote(
        vote_event_id="VOT123",
        voter_id=1,
        option=VoteOption.NO,
        bancada_id=10
    )
    session.add(vote)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()

def test_bill_congresistas(session):
    relation = BillCongresistas(
        bill_id="B001",
        person_id=1,
        role_type=RoleTypeBill.COAUTHOR
    )
    session.add(relation)
    session.commit()
    assert relation.role_type == RoleTypeBill.COAUTHOR

def test_bill_committees(session):
    committee = Committee(
        leg_period=LegPeriod.PERIODO_2021_2026,
        leg_year=LegislativeYear.YEAR_2022,
        org_id=1,
        id=100,
        name="Comisión de Economía"
    )
    session.add(committee)
    session.commit()

    relation = BillCommittees(
        bill_id="B001",
        committee_id=100
    )
    session.add(relation)
    session.commit()
    assert relation.committee_id == 100

def test_vote_counts(session):
    vote_count = VoteCounts(
        org_id=1,
        vote_event_id="VOT123",
        option=VoteOption.SI,
        bancada_id=10,
        count=40
    )
    session.add(vote_count)
    session.commit()
    assert vote_count.count == 40