import pytest
from pydantic import ValidationError
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
    BillOrganization,
    Congresista,
    Organization,
    Membership,
    Motion,
    MotionStep,
)
from backend import (
    TypeRoleBill,
    TypeBillStep,
    TypeMotion,
    TypeMotionStep,
    Proponents,
    LegPeriod,
    TypeOrganization,
    RoleOrganization,
    VoteResult,
    TypeCommittee,
)


@pytest.fixture
def sample_votes():
    return [
        Vote(
            vote_event_id="B_2021_3_1",
            voter_full_name="Juan Perez",
            voter_website="www.congreso.gob.pe/JuanPerez",
            option=VoteOption.SI,
            bancada_name="Fuerza Popular",
        ),
        Vote(
            vote_event_id="B_2021_3_1",
            voter_full_name="Paolo Guerrero",
            voter_website="www.congreso.gob.pe/PaoloGuerrero",
            option=VoteOption.NO,
            bancada_name="Renovación Popular",
        ),
        Vote(
            vote_event_id="B_2021_3_1",
            voter_full_name="Patricia Chirinos",
            voter_website="www.congreso.gob.pe/PatriciaChirinos",
            option=VoteOption.SI,
            bancada_name="Juntos por el Perú",
        ),
    ]


@pytest.fixture
def sample_attendance():
    return [
        Attendance(
            event_id="B_2021_3_1",
            voter_full_name="Juan Perez",
            voter_website="www.congreso.gob.pe/JuanPerez",
            status=AttendanceStatus.PRESENTE,
        ),
        Attendance(
            event_id="B_2021_3_1",
            voter_full_name="Paolo Guerrero",
            voter_website="www.congreso.gob.pe/PaoloGuerrero",
            status=AttendanceStatus.AUSENTE,
        ),
        Attendance(
            event_id="B_2021_3_1",
            voter_full_name="Patricia Chirinos",
            voter_website="www.congreso.gob.pe/PatriciaChirinos",
            status=AttendanceStatus.PRESENTE,
        ),
    ]


@pytest.fixture
def sample_vote_event(sample_votes, sample_attendance):
    return VoteEvent(
        vote_event_id="B_2021_3_1",
        org_name="Cámara de Diputados",
        org_type="Cámara",
        bill_id="2021_3",
        motion_id=None,
        event_date=datetime.now().date(),
        result=VoteResult.APROBADO,
        votes=sample_votes,
        attendance=sample_attendance,
    )


@pytest.fixture
def sample_bill():
    return Bill(
        id="b001",
        title="Ley de Prueba",
        summary_congreso="Resumen",
        observations="Observaciones",
        status="En trámite",
        proponent=Proponents.PODER_EJECUTIVO,
        author_name=None,
        author_web=None,
        bancada_name="Bancada Test",
        bill_approved=True,
        summary_oc="Resumen OC",
    )


def test_vote_event_counts(sample_vote_event):
    vote_event = sample_vote_event
    counts = vote_event.get_counts()
    assert counts[VoteOption.SI] == 2
    assert counts[VoteOption.NO] == 1


def test_vote_event_counts_by_bancada(sample_vote_event):
    vote_event = sample_vote_event
    counts_by_bancada = vote_event.get_counts_by_bancada()
    assert counts_by_bancada[0].option == VoteOption.SI
    assert counts_by_bancada[0].bancada_name == "Fuerza Popular"
    assert counts_by_bancada[0].count == 1


def test_attendance_summary(sample_vote_event):
    vote_event = sample_vote_event
    summary = vote_event.get_attendance_summary()
    assert summary[AttendanceStatus.PRESENTE] == 2
    assert summary[AttendanceStatus.AUSENTE] == 1


def test_bill_creation(sample_bill):
    bill = sample_bill
    assert bill.author_name is None
    assert bill.proponent == Proponents.PODER_EJECUTIVO


def test_membership_date_validation():
    with pytest.raises(ValueError):
        Membership(
            cong_name="Jaime",
            org_name="Committee",
            org_type=TypeOrganization.COMMITTEE,
            leg_period=LegPeriod.PERIODO_2021_2026,
            role=RoleOrganization.MIEMBRO,
            time_stamp=datetime.now(),
            start_date=datetime.now(),
            end_date=datetime.now() - timedelta(days=1),
        )


def test_congresista_creation():
    congresista = Congresista(
        full_name="Ana Maria Torres Torres",
        first_name="Ana Maria",
        last_name="Torres Torres",
        dni="12345678",
        photo_url="https://example.com/photo",
        website="https://example.com",
    )
    assert congresista.full_name == "Ana Maria Torres Torres"


def test_organization_creation():
    org = Organization(
        org_name="Comisión de Justicia",
        org_type=TypeOrganization.COMMITTEE,
        org_subtype=TypeCommittee.COM_INVESTIGADORA,
        org_link="http://congreso.gob.pe/comision_investigadora",
    )
    assert org.org_name == "Comisión de Justicia"


def test_bill_congresistas_creation():
    relation = BillCongresistas(
        bill_id="b001",
        nombre="Juan Perez",
        role_type=TypeRoleBill.ADHERENTE,
    )
    assert relation.role_type == TypeRoleBill.ADHERENTE


def test_bill_organization_creation():
    relation = BillOrganization(
        bill_id="b001",
        org_name="Comisión de Justicia",
        org_type=TypeOrganization.COMMITTEE,
        presentation_date=datetime.now().date(),
    )
    assert relation.org_name == "Comisión de Justicia"


def test_bill_step_creation():
    step = BillStep(
        bill_id="b001",
        step_id=123,
        step_type=TypeBillStep.VOTACION,
        vote_step=True,
        vote_event_id=None,
        step_date=datetime.now().date(),
        step_detail="Se presentó el proyecto",
        step_committees=[],
    )
    assert step.step_detail == "Se presentó el proyecto"


@pytest.mark.parametrize(
    ("schema_cls", "payload"),
    [
        (
            Vote,
            {
                "vote_event_id": "B_2021_3_1",
                "voter_full_name": "Juan Perez",
                "voter_website": None,
                "option": VoteOption.SI,
                "bancada_name": "Fuerza Popular",
                "unexpected": "stale scraper value",
            },
        ),
        (
            Bill,
            {
                "id": "b001",
                "title": "Ley de Prueba",
                "summary_congreso": "Resumen",
                "observations": None,
                "status": "En trámite",
                "proponent": Proponents.CONGRESO,
                "author_name": None,
                "author_web": None,
                "bancada_name": "Bancada Test",
                "bill_approved": False,
                "summary_oc": "Resumen OC",
                "legacy_field": "stale processor value",
            },
        ),
        (
            Motion,
            {
                "id": "m001",
                "motion_type": TypeMotion.SALUDO,
                "summary_congreso": "Resumen",
                "observations": None,
                "status": "En trámite",
                "author_name": None,
                "author_web": None,
                "motion_approved": False,
                "summary_opencongress": "Resumen OC",
                "legacy_field": "stale processor value",
            },
        ),
    ],
)
def test_process_schemas_reject_extra_fields(schema_cls, payload):
    """Process schemas should reject unknown fields so stale scraper or processor payloads fail loudly instead of being silently dropped."""
    with pytest.raises(ValidationError):
        schema_cls(**payload)


@pytest.mark.parametrize(
    ("schema_cls", "payload"),
    [
        (
            Attendance,
            {
                "event_id": "B_2021_3_1",
                "voter_full_name": "Juan Perez",
                "status": AttendanceStatus.PRESENTE,
            },
        ),
        (
            BillStep,
            {
                "bill_id": "b001",
                "step_id": 123,
                "step_type": TypeBillStep.VOTACION,
                "vote_step": True,
                "step_date": datetime.now().date(),
                "step_committees": [],
            },
        ),
        (
            MotionStep,
            {
                "motion_id": "m001",
                "step_id": 123,
                "step_type": TypeMotionStep.PRESENTADO,
                "vote_step": False,
                "step_date": datetime.now(),
            },
        ),
    ],
)
def test_process_schemas_reject_removed_required_fields(schema_cls, payload):
    with pytest.raises(ValidationError):
        schema_cls(**payload)
