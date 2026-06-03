import pytest
from datetime import datetime, timedelta
from backend.process.schema import (
    Vote,
    VoteEvent,
    Attendance,
    VoteOption,
    AttendanceStatus,
    Bill,
    BillStep,
    BillCongresistas,
    BillCommittees,
    Congresista,
    Organization,
    Membership,
)
from backend import (
    RoleTypeBill,
    Proponents,
    Legislature,
    LegislativeYear,
    LegPeriod,
    TypeOrganization,
    RoleOrganization,
    VoteResult,
    MajorityType,
    TypeCommittee,
)


@pytest.fixture
def sample_votes():
    return [
        Vote(vote_event_id="ev1", voter_id=1, option=VoteOption.SI, bancada_id=10),
        Vote(vote_event_id="ev1", voter_id=2, option=VoteOption.NO, bancada_id=10),
        Vote(vote_event_id="ev1", voter_id=3, option=VoteOption.SI, bancada_id=20),
    ]


@pytest.fixture
def sample_attendance():
    return [
        Attendance(
            org_id=1, event_id="ev1", attendee_id=1, status=AttendanceStatus.PRESENTE
        ),
        Attendance(
            org_id=1, event_id="ev1", attendee_id=2, status=AttendanceStatus.AUSENTE
        ),
        Attendance(
            org_id=1, event_id="ev1", attendee_id=3, status=AttendanceStatus.PRESENTE
        ),
    ]


@pytest.fixture
def sample_vote_event(sample_votes, sample_attendance):
    return VoteEvent(
        leg_period=LegPeriod.PERIODO_2021_2026,
        bill_or_motion="Motion",
        bill_motion_id="123",
        date=datetime.now(),
        result=VoteResult.APPROVED,
        majority_type=MajorityType.SIMPLE,
        votes=sample_votes,
        attendance=sample_attendance,
    )


@pytest.fixture
def sample_bill():
    return Bill(
        id="b001",
        leg_period=LegPeriod.PERIODO_2021_2026,
        legislature=Legislature.LEGISLATURA_2026_1,
        presentation_date=datetime.now(),
        title="Ley de Prueba",
        summary="Resumen",
        observations="Observaciones",
        complete_text="Texto completo",
        status="En trámite",
        proponent=Proponents.PODER_EJECUTIVO,
        author_name=None,
        author_web=None,
        bill_approved=True,
    )


def test_vote_event_counts(sample_vote_event):
    vote_event = sample_vote_event
    counts = vote_event.get_counts()
    assert counts[VoteOption.SI] == 2
    assert counts[VoteOption.NO] == 1


def test_vote_event_counts_by_bancada(sample_vote_event):
    vote_event = sample_vote_event
    counts_by_bancada = vote_event.get_counts_by_bancada()
    assert counts_by_bancada[10][VoteOption.SI] == 1
    assert counts_by_bancada[10][VoteOption.NO] == 1
    assert counts_by_bancada[20][VoteOption.SI] == 1


def test_attendance_summary(sample_vote_event):
    vote_event = sample_vote_event
    summary = vote_event.get_attendance_summary()
    assert summary[AttendanceStatus.PRESENTE] == 2
    assert summary[AttendanceStatus.AUSENTE] == 1


def test_bill_creation(sample_bill):
    bill = sample_bill
    assert bill.author_name == None
    assert bill.proponent == Proponents.PODER_EJECUTIVO


def test_membership_date_validation():
    with pytest.raises(ValueError):
        Membership(
            role=RoleOrganization.MIEMBRO,
            nombre="Jaime",
            leg_period=LegPeriod.PERIODO_2021_2026,
            org_name="Committee",
            org_type="Comision",
            comm_type=TypeCommittee.COM_INVESTIGADORA,
            start_date=datetime.now(),
            end_date=datetime.now() - timedelta(days=1),
        )


def test_congresista_creation():
    congresista = Congresista(
        nombre="Juan Pérez",
        leg_period=LegPeriod.PERIODO_2021_2026,
        party_name="Partido X",
        current_bancada="Bancada X",
        votes_in_election=25000,
        dist_electoral="Lima",
        condicion="Activo",
        website="http://congreso.gob.pe/juanperez",
        photo_url="http://congreso.gob.pe/juanperez/foto",
    )
    assert congresista.nombre == "Juan Pérez"


def test_organization_creation():
    org = Organization(
        leg_period=LegPeriod.PERIODO_2021_2026,
        leg_year=LegislativeYear.YEAR_2025_2026,
        org_name="Comisión de Justicia",
        org_type=TypeOrganization.COMISON,
        comm_type=TypeCommittee.COM_INVESTIGADORA,
        org_link="http://congreso.gob.pe/comision_investigadora",
    )
    assert org.org_name == "Comisión de Justicia"


def test_bill_congresistas_creation():
    relation = BillCongresistas(
        bill_id="b001",
        nombre="Juan Perez",
        leg_period=LegPeriod.PERIODO_2021_2026,
        role_type=RoleTypeBill.ADHERENTE,
    )
    assert relation.role_type == RoleTypeBill.ADHERENTE


def test_bill_committees_creation():
    relation = BillCommittees(bill_id="b001", committee_name="Comision de Justicia")
    assert relation.committee_name == "Comision de Justicia"


def test_bill_step_creation():
    step = BillStep(
        id=123,
        bill_id="b001",
        vote_step=True,
        vote_id="b001_1",
        step_date=datetime.now(),
        step_detail="Se presentó el proyecto",
        step_files=[1, 2, 3, 4],
    )
    assert step.step_detail == "Se presentó el proyecto"
