import pytest
from datetime import datetime, timedelta
from estecon.backend.scrapers.schema import (
    Vote,
    VoteEvent,
    Attendance,
    VoteOption,
    AttendanceStatus,
    Bill,
    BillStep,
    BillCongresistas,
    BillCommittees,
    Committee,
    Congresista,
    Organization,
    Membership,
)
from estecon.backend import (
    RoleTypeBill,
    Proponents,
    Legislature,
    LegislativeYear,
    LegPeriod,
    TypeOrganization,
    RoleOrganization,
    BillStepType,
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


def test_vote_event_counts(sample_votes):
    vote_event = VoteEvent(
        id="ev1",
        org_id=1,
        leg_period=LegPeriod.PERIODO_2021_2026,
        bill_id="123",
        date=datetime.now(),
        votes=sample_votes,
    )
    counts = vote_event.get_counts()
    assert counts[VoteOption.SI] == 2
    assert counts[VoteOption.NO] == 1


def test_vote_event_counts_by_bancada(sample_votes):
    vote_event = VoteEvent(
        id="ev1",
        org_id=1,
        leg_period=LegPeriod.PERIODO_2021_2026,
        bill_id="123",
        date=datetime.now(),
        votes=sample_votes,
    )
    counts_by_bancada = vote_event.get_counts_by_bancada()
    assert counts_by_bancada[10][VoteOption.SI] == 1
    assert counts_by_bancada[10][VoteOption.NO] == 1
    assert counts_by_bancada[20][VoteOption.SI] == 1


def test_attendance_summary(sample_attendance):
    vote_event = VoteEvent(
        id="ev1",
        org_id=1,
        leg_period=LegPeriod.PERIODO_2021_2026,
        bill_id="123",
        date=datetime.now(),
        attendance=sample_attendance,
    )
    summary = vote_event.get_attendance_summary()
    assert summary[AttendanceStatus.PRESENTE] == 2
    assert summary[AttendanceStatus.AUSENTE] == 1


def test_bill_creation_and_json(tmp_path):
    bill = Bill(
        id="b001",
        org_id=1,
        leg_period=LegPeriod.PERIODO_2021_2026,
        legislature=Legislature.LEGISLATURA_2026_1,
        presentation_date=datetime.now(),
        title="Ley de Prueba",
        summary="Resumen",
        observations="Observaciones",
        complete_text="Texto completo",
        status="En trámite",
        proponent=Proponents.PODER_EJECUTIVO,
        author_id=123,
        bancada_id=10,
        bill_approved=True,
    )
    json_path = tmp_path / "bill.json"
    bill.save_to_json(json_path)
    assert json_path.exists()


def test_membership_date_validation():
    with pytest.raises(ValueError):
        Membership(
            id=1,
            role=RoleOrganization.MIEMBRO,
            person_id=101,
            org_id=200,
            start_date=datetime.now(),
            end_date=datetime.now() - timedelta(days=1),
        )


def test_congresista_creation():
    congresista = Congresista(
        id=1,
        leg_period=LegPeriod.PERIODO_2021_2026,
        nombre="Juan Pérez",
        party_id=5,
        votes_in_election=25000,
        dist_electoral="Lima",
        condicion="Activo",
        website="http://congreso.gob.pe/juanperez",
    )
    assert congresista.nombre == "Juan Pérez"


def test_organization_creation():
    org = Organization(
        leg_period=LegPeriod.PERIODO_2021_2026,
        leg_year=LegislativeYear.YEAR_2025,
        org_id=1,
        org_name="Comisión de Justicia",
        org_type=TypeOrganization.COMMITTEE,
    )
    assert org.org_name == "Comisión de Justicia"


def test_committee_creation():
    committee = Committee(
        leg_period=LegPeriod.PERIODO_2021_2026,
        leg_year=LegislativeYear.YEAR_2025,
        org_id=1,
        id="cj01",
        name="Comisión de Justicia",
    )
    assert committee.name == "Comisión de Justicia"


def test_bill_congresistas_creation():
    relation = BillCongresistas(
        bill_id="b001", person_id="1", role_type=RoleTypeBill.ADHERENTE
    )
    assert relation.role_type == RoleTypeBill.ADHERENTE


def test_bill_committees_creation():
    relation = BillCommittees(bill_id="b001", committee_id=1)
    assert relation.committee_id == 1


def test_bill_step_creation():
    step = BillStep(
        id=1,
        bill_id="b001",
        step_type=BillStepType.ASSIGNED,
        step_date=datetime.now(),
        step_detail="Se presentó el proyecto",
        step_url="http://congreso.gob.pe/proyecto/b001",
    )
    assert step.step_type == BillStepType.ASSIGNED
