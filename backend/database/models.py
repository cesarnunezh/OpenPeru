from sqlalchemy import (
    Column,
    Integer,
    String,
    Enum,
    Boolean,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    PrimaryKeyConstraint,
    Index,
)
from backend import (
    VoteOption,
    VoteResult,
    MajorityType,
    AttendanceStatus,
    BillStepType,
    RoleTypeBill,
    LegPeriod,
    Legislature,
    LegislativeYear,
    Proponents,
    RoleOrganization,
    TypeOrganization,
    TypeCommittee,
    MotionType,
    MotionStepType,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Vote(Base):
    """
    Represents a vote in a parliament session.

    Attributes:
        vote_event_id (str): Unique identifier for the vote event.
        voter_id (str): Unique identifier for the voter.
        option (str): The voter's choice, e.g., 'yes', 'no', 'abstain'.
        bancada_id (str): The political group of the voter.
    """

    __tablename__ = "votes"

    vote_event_id = Column(String, ForeignKey("vote_events.id"), primary_key=True)
    voter_id = Column(Integer, ForeignKey("congresistas.id"), nullable=False)
    option = Column(Enum(VoteOption, name="option"), nullable=False)
    bancada_id = Column(Integer, ForeignKey("bancadas.bancada_id"), nullable=False)

    __table_args__ = (
        UniqueConstraint("vote_event_id", "voter_id", name="uq_vote_event_voter"),
        Index("ix_vote_vote_event_id", "vote_event_id"),
        Index("ix_vote_voter_id", "voter_id"),
    )


class Attendance(Base):
    """
    Represents attendance of a congressperson at an event.

    Attributes:
        event_id (str): Unique identifier for the event.
        attendee_id (str): Unique identifier for the congressperson.
        status (str): Attendance status, e.g., 'present', 'absent'.
    """

    __tablename__ = "attendance"

    event_id = Column(Integer, ForeignKey("vote_events.id"), primary_key=True)
    attendee_id = Column(Integer, ForeignKey("congresistas.id"), nullable=False)
    status = Column(Enum(AttendanceStatus, name="attendance_status"), nullable=False)

    __table_args__ = (
        UniqueConstraint("event_id", "attendee_id", name="uq_attendance"),
        Index("ix_attendance_by_event", "event_id"),
        Index("ix_attendance_attendee_id", "attendee_id"),
    )


class VoteEvent(Base):
    """
    Represents a vote event in a parliament session.

    Attributes:
        leg_period (str): The legislative period during which the vote occurred.
        bill_id (str): Unique identifier for the bill associated with the vote.
        date (str): The date of the vote event.
    """

    __tablename__ = "vote_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    leg_period = Column(Enum(LegPeriod, name="leg_period"), nullable=False)
    bill_or_motion = Column(String, nullable=False)
    bill_motion_id = Column(String, nullable=False)
    date = Column(DateTime, nullable=False)
    result = Column(Enum(VoteResult, name="vote_result"), nullable=False)
    majority_type = Column(Enum(MajorityType, name="majority_type"), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "leg_period",
            "bill_or_motion",
            "bill_motion_id",
            "date",
            name="uq_vote_event",
        ),
        Index("ix_vote_event_bill_motion_id", "bill_motion_id"),
    )


class VoteCounts(Base):
    """
    Represents the counts of votes in a vote event.

    Attributes:
        vote_event_id (str): Unique identifier for the vote event.
        option (str): The voter's choice, e.g., 'yes', 'no', 'abstain'.
        bancada (str): The political group of the voter.
        count (int): Number of votes for the option.
    """

    __tablename__ = "vote_counts"

    vote_event_id = Column(String, ForeignKey("vote_events.id"), nullable=False)
    option = Column(Enum(VoteOption, name="option"), nullable=False)
    bancada_id = Column(Integer, ForeignKey("bancadas.bancada_id"), nullable=False)
    count = Column(Integer, nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint(
            "vote_event_id", "option", "bancada_id", name="pk_vote_counts"
        ),
        Index("ix_votecounts_vote_event_id", "vote_event_id"),
        Index("ix_votecounts_bancada_id", "bancada_id"),
    )


class Bill(Base):
    """
    Represents a bill in the peruvian parliament.

    Attributes:
        id (str): Unique identifier for the bill.
        leg_period (str): Legislative period of the bill.
        legislature (str): Legislature where the bill was presented.
        presentation_date (datetime): Date when the bill was presented.
        title (str): Title of the bill.
        summary (str): Summary of the bill.
        observations (str): Observations on the bill.
        complete_text (str): Complete text of the bill.
        status (str): Current status of the bill.
        proponent (str): Type of proponent of the bill
        author_id (str): Unique identifier for the author of the bill.
        bancada_id (str): Unique identifier for the political group associated with the bill.
        bill_approved (bool): Boolean indicating if the bill has been published
    """

    __tablename__ = "bills"

    id = Column(String, primary_key=True)
    leg_period = Column(Enum(LegPeriod, name="leg_period"), nullable=False)
    legislature = Column(Enum(Legislature, name="legislature"), nullable=False)
    presentation_date = Column(DateTime, nullable=False)
    title = Column(String, nullable=False)
    summary = Column(String, nullable=False)
    observations = Column(String, nullable=False)
    complete_text = Column(String, nullable=False)
    status = Column(String, nullable=False)
    proponent = Column(Enum(Proponents, name="proponent"), nullable=False)
    author_id = Column(Integer, ForeignKey("congresistas.id"), nullable=True)
    bancada_id = Column(Integer, ForeignKey("bancadas.bancada_id"), nullable=True)
    bill_approved = Column(Boolean, nullable=False)

    __table_args__ = (
        UniqueConstraint("id", name="bill_unique"),
        Index("ix_bill_author_id", "author_id"),
        Index("ix_bill_bancada_id", "bancada_id"),
    )


class BillCongresistas(Base):
    """
    Represents a relation between a bill and parliament members based on their
    role during the presentation of the bill.

    Attributes:
        bill_id (str): A unique identifier for the bill.
        person_id (str): A unique identifier for the person.
        role_type (str): The type of role that the person has in the bill (e.g. author, coauthor, adherente, etc)
    """

    __tablename__ = "bills_congresistas"

    bill_id = Column(String, ForeignKey("bills.id"), nullable=False)
    person_id = Column(Integer, ForeignKey("congresistas.id"), nullable=False)
    role_type = Column(Enum(RoleTypeBill, name="role_type"), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("bill_id", "person_id"),
        Index("ix_billcongresistas_person_id", "person_id"),
    )


class BillCommittees(Base):
    """
    Represents the relation between bills and a committee

    Attributes:
        bill_id (str): The identifier of the bill.
        committee_id (str): The identifier of the committee.
    """

    __tablename__ = "bill_committees"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bill_id = Column(String, ForeignKey("bills.id"), nullable=False)
    committee_id = Column(Integer, ForeignKey("organizations.org_id"), nullable=False)

    __table_args__ = (
        UniqueConstraint("bill_id", "committee_id", name="bill_committee_uniq"),
        Index("ix_billcommittees_committee_id", "committee_id"),
    )


class BillStep(Base):
    """
    Represents a bill step record with details about the actions taken on a bill.

    Attributes:
        id (int): A unique identifier for each step record.
        bill_id (str): The identifier of the bill associated with this step.
        step_type (str): The type of step record (e.g. "Vote", "Assigned to Committee", "Presented", etc.)
        step_date (datetime): The date and time when the step occured.
        step_detail (str): The details on the step
    """

    __tablename__ = "bill_steps"

    id = Column(Integer, primary_key=True)
    bill_id = Column(String, ForeignKey("bills.id"), nullable=True)
    step_type = Column(Enum(BillStepType, name="type_step"), nullable=False)
    step_date = Column(DateTime, nullable=False)
    step_detail = Column(String, nullable=False)

    __table_args__ = (Index("ix_billstep_bill_id", "bill_id"),)


class BillDocument(Base):
    """
    Represents a bill document record.

    Attributes:
        bill_id (str): The identifier of the bill associated with this step.
        step_id (int): A unique identifier for each step record.
        archivo_id (int): A unique identifier for each file record.
        url (str): The url associated to the file
        text (str): Extracted text from the file
        vote_doc (bool): Records if the step is a vote or not.
    """

    __tablename__ = "bill_documents"

    bill_id = Column(String, ForeignKey("bills.id"), nullable=False)
    step_id = Column(Integer, ForeignKey("bill_steps.id"), nullable=False)
    archivo_id = Column(Integer, primary_key=True, nullable=False)
    url = Column(String, nullable=False)
    text = Column(String, nullable=False)
    vote_doc = Column(Boolean, nullable=False)

    __table_args__ = (
        Index("ix_billdocument_archivo_id", "archivo_id"),
        UniqueConstraint("bill_id", "step_id", "archivo_id", name="bill_document_uniq"),
    )


class Congresista(Base):
    """
    Represents a member of the peruvian parliament

    Attributes:
        id (str): Unique identifier for the person.
        nombre (str): Name of the person.
        leg_period (str): Legislative period.
        party_name (str): Name of the party.
        current_bancada (str): Name of the bancada.
        votes_in_election (int): Number of votes obtain in elections
        dist_electoral (str): Electoral district.
        condicion (str): Condition of the congressperson, e.g., 'active', 'inactive'.
        website (str): Official website of the congressperson.
        photo_url (str): Official photo url of the congressperson.
    """

    __tablename__ = "congresistas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String, nullable=False)
    leg_period = Column(Enum(LegPeriod, name="leg_period"), nullable=False)
    party_name = Column(String, nullable=False)
    current_bancada = Column(String, nullable=False)
    votes_in_election = Column(Integer, nullable=False)
    dist_electoral = Column(String, nullable=True)
    condicion = Column(String, nullable=False)
    website = Column(String, nullable=False)
    photo_url = Column(String, nullable=False)

    __table_args__ = (
        UniqueConstraint("nombre", "leg_period", name="congresista_uniq"),
    )


class Bancada(Base):
    """
    Represent a Bancada (Grupo Parlamentario) in the peruvian parliament

    Attributes:
        leg_year (str): Year period of the bancada
        bancada_id (int): Unique identifier for the bancada
        bancada_name (str): Name of the bancada
    """

    __tablename__ = "bancadas"

    bancada_id = Column(Integer, primary_key=True, autoincrement=True)
    leg_year = Column(Enum(LegislativeYear, name="leg_period"), nullable=False)
    bancada_name = Column(String, nullable=False)


class Organization(Base):
    """
    Represents a legislative organization, such as a parliament or congress.

    Attributes:
        org_id (int): Unique identifier for the organization.
        leg_period (str): Legislative period.
        leg_year (str): Legislative year.
        org_name (str): Name of the organization.
        org_type (str): Type of organization (e.g. bancada, partido, committee, etc)
        comm_type (str): Type of committee (e.g. ordinaria, especial, etc)
        org_link (str): Url of the organization's website.

    """

    __tablename__ = "organizations"

    org_id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    leg_period = Column(Enum(LegPeriod, name="leg_period"), nullable=False)
    leg_year = Column(Enum(LegislativeYear, name="leg_year"), nullable=False)
    org_name = Column(String, nullable=False)
    org_type = Column(Enum(TypeOrganization, name="type_organization"), nullable=False)
    comm_type = Column(Enum(TypeCommittee, name="type_committee"), nullable=True)
    org_link = Column(String, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "leg_period", "leg_year", "org_name", "org_type", name="org_uniq"
        ),
    )


class Membership(Base):
    """
    Represents a person's role in an organization during a specific time period.

    Attributes:
        id (int): Unique identifier for the membership relationship.
        role (str): Role of the person in the organization (e.g. vocero, miembro, presidente, etc)
        person_id (int): Identifier for the person
        org_id (int): Identifier for the organization
        start_date (datetime): Date of the beginning of the membership
        end_date (datetime): Date of the end of the membership
    """

    __tablename__ = "memberships"

    id = Column(Integer, primary_key=True, autoincrement=True)
    role = Column(Enum(RoleOrganization, name="role"), nullable=False)
    person_id = Column(Integer, ForeignKey("congresistas.id"), nullable=False)
    org_id = Column(Integer, ForeignKey("organizations.org_id"), nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)

    __table_args__ = (UniqueConstraint("id", name="membership"),)


class BancadaMembership(Base):
    """
    Represents a person's membership in a bancada during a specific time period.

    Attributes:
        id (int): Unique identifier for the membership relationship.
        leg_year (str): Year period of the membership
        person_id (int): Identifier for the person
        bancada_id (int): Identifier for the bancada
    """

    __tablename__ = "bancada_memberships"

    id = Column(Integer, primary_key=True, autoincrement=True)
    leg_year = Column(Enum(LegislativeYear, name="leg_year"), nullable=False)
    person_id = Column(Integer, ForeignKey("congresistas.id"), nullable=False)
    bancada_id = Column(Integer, ForeignKey("bancadas.bancada_id"), nullable=False)


class Motion(Base):
    """
    Represents a motion in the peruvian parliament.

    Attributes:
        id (str): Unique identifier for the motion.
        leg_period (str): Legislative period of the motion.
        legislature (str): Legislature where the motion was presented.
        presentation_date (datetime): Date when the motion was presented.
        motion_type (str): Type of the motion.
        summary (str): Summary of the motion.
        observations (str): Observations on the motion.
        complete_text (str): Complete text of the motion.
        status (str): Current status of the motion.
        author_id (str): Unique identifier for the author of the motion.
        motion_approved (bool): Boolean indicating if the motion has been published
    """

    __tablename__ = "motions"

    id = Column(String, primary_key=True)
    leg_period = Column(Enum(LegPeriod, name="leg_period"), nullable=False)
    legislature = Column(Enum(Legislature, name="legislature"), nullable=False)
    presentation_date = Column(DateTime, nullable=False)
    motion_type = Column(Enum(MotionType, name="motion_type"), nullable=False)
    summary = Column(String, nullable=False)
    observations = Column(String, nullable=False)
    complete_text = Column(String, nullable=False)
    status = Column(String, nullable=False)
    author_id = Column(Integer, ForeignKey("congresistas.id"), nullable=True)
    motion_approved = Column(Boolean, nullable=False, default=False)


class MotionCongresistas(Base):
    """
    Represents a relation between a motion and parliament members based on their
    role during the presentation of the motion.

    Attributes:
        motion_id (str): A unique identifier for the motion.
        nombre (str): Name of the person.
        leg_period (str): Legislative period.
        role_type (str): The type of role that the person has in the motion (e.g. author, coauthor, adherente, etc)
    """

    __tablename__ = "motions_congresistas"

    motion_id = Column(String, ForeignKey("motions.id"), nullable=False)
    person_id = Column(Integer, ForeignKey("congresistas.id"), nullable=False)
    role_type = Column(Enum(RoleTypeBill, name="role_type_motion"), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("motion_id", "person_id"),
        Index("ix_motioncongresistas_person_id", "person_id"),
    )


class MotionStep(Base):
    """
    Represents a motion step record with details about the actions taken on a motion.

    Attributes:
        id (int): A unique identifier for each step record.
        motion_id (str): The identifier of the motion associated with this step.
        vote_step (bool): Records if the step is a vote or not.
        step_date (datetime): The date and time when the step occured.
        step_detail (str): The details on the step
        step_url (str): The url associated to the step
    """

    __tablename__ = "motion_steps"

    id = Column(Integer, primary_key=True)
    motion_id = Column(String, ForeignKey("motions.id"), nullable=True)
    step_type = Column(Enum(MotionStepType, name="type_step"), nullable=False)
    step_date = Column(DateTime, nullable=False)
    step_detail = Column(String, nullable=False)

    __table_args__ = (Index("ix_motionstep_motion_id", "motion_id"),)


class MotionDocument(Base):
    """
    Represents a document object related to a Motion and to a specific MotionStep

    Attributes:
        motion_id (str): The identifier of the motion associated with this step.
        step_id (int): A unique identifier for each step record.
        archivo_id (int): A unique identifier for each file record.
        url (str): The url associated to the file
        text (str): Extracted text from the file
        vote_doc (bool): Records if the step is a vote or not.
    """

    __tablename__ = "motion_documents"

    motion_id = Column(String, ForeignKey("motions.id"), nullable=False)
    step_id = Column(Integer, ForeignKey("motion_steps.id"), nullable=False)
    archivo_id = Column(Integer, primary_key=True, nullable=False)
    url = Column(String, nullable=False)
    text = Column(String, nullable=False)
    vote_doc = Column(Boolean, nullable=False)

    __table_args__ = (
        Index("ix_motiondocument_archivo_id", "archivo_id"),
        UniqueConstraint(
            "motion_id", "step_id", "archivo_id", name="motion_document_uniq"
        ),
    )


class Ley(Base):
    """
    Represents a law (ley) in the peruvian parliament.

    Attributes:
        id (str): Unique identifier for the motion.
        title (str): Law title.
        bill_id (str): Bill id related to this law (Proyecto de Ley)
    """

    __tablename__ = "leyes"

    id = Column(String, primary_key=True, nullable=False)
    title = Column(String, nullable=False)
    bill_id = Column(String, nullable=False)
