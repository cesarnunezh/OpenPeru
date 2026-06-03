from sqlalchemy import (
    ForeignKey,
    UniqueConstraint,
    PrimaryKeyConstraint,
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    LargeBinary,
    Text,
    Enum,
    text,
)
from backend import (
    AttendanceStatus,
    VoteResult,
    VoteOption,
    TypeOrganization,
    TypeCommittee,
    TypeAdmin,
    Proponents,
    TypeBillStep,
    TypeMotion,
    TypeMotionStep,
    TypeRoleBill,
    EmbeddingModel,
    enum_values,
    sql_value_list,
)
from sqlalchemy.orm import declarative_base, Mapped, mapped_column
from datetime import datetime, date
from pgvector.sqlalchemy import Vector

DEFAULT_EMBEDDING_DIM = 768
SEMANTIC_BILLS_HNSW_INDEX = "ix_semantic_bills_embedding_hnsw"

Base = declarative_base()


org_type_enum = Enum(
    TypeOrganization,
    name="org_type",
    values_callable=enum_values,
    native_enum=True,
    validate_strings=True,
)

vote_option_enum = Enum(
    VoteOption,
    name="vote_option",
    values_callable=enum_values,
    native_enum=True,
    validate_strings=True,
)

type_role_bill_enum = Enum(
    TypeRoleBill,
    name="type_role_bill",
    values_callable=enum_values,
    native_enum=True,
    validate_strings=True,
)

embedding_model_name_enum = Enum(
    EmbeddingModel,
    name="embedding_model_name",
    values_callable=enum_values,
    native_enum=True,
    validate_strings=True,
)


class Vote(Base):
    """
    Represents a vote in a parliament session.

    Attributes:
        vote_event_id (str): Unique identifier for the vote event.
        voter_id (int): Unique identifier for the voter.
        option (str): The voter's choice, e.g., 'yes', 'no', 'abstain'.
        bancada_id (int): The political group of the voter.
    """

    __tablename__ = "votes"

    vote_event_id: Mapped[str] = mapped_column(
        ForeignKey("vote_events.vote_event_id"), nullable=False
    )
    voter_id: Mapped[int] = mapped_column(ForeignKey("congresistas.id"), nullable=False)
    option: Mapped[VoteOption] = mapped_column(vote_option_enum, nullable=False)
    bancada_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.org_id"), nullable=False
    )

    __table_args__ = (
        PrimaryKeyConstraint("vote_event_id", "voter_id", name="pk_vote_event_voter"),
        Index("ix_vote_vote_event_id", "vote_event_id"),
        Index("ix_vote_voter_id", "voter_id"),
        Index("ix_vote_bancada_id", "bancada_id"),
    )


class Attendance(Base):
    """
    Represents attendance of a congressperson at an event.

    Attributes:
        event_id (str): Unique identifier for the event.
        attendee_id (int): Unique identifier for the congressperson.
        status (str): Attendance status, e.g., 'present', 'absent'.
    """

    __tablename__ = "attendance"

    event_id: Mapped[str] = mapped_column(
        ForeignKey("vote_events.vote_event_id"), nullable=False
    )
    attendee_id: Mapped[int] = mapped_column(
        ForeignKey("congresistas.id"), nullable=False
    )
    status: Mapped[AttendanceStatus] = mapped_column(
        Enum(
            AttendanceStatus,
            name="attendance_status",
            values_callable=enum_values,
            native_enum=True,
            validate_strings=True,
        ),
        nullable=False,
    )

    __table_args__ = (
        PrimaryKeyConstraint("event_id", "attendee_id", name="pk_attendance"),
        Index("ix_attendance_by_event", "event_id"),
        Index("ix_attendance_attendee_id", "attendee_id"),
    )


class VoteEvent(Base):
    """
    Represents a vote event in a parliament session.

    Attributes:
        vote_event_id (str): Unique identifier for the vote event
        org_id (int): Unique identifier for the organization where the vote event occur
        bill_id (str): Unique identifier for the bill associated with the vote.
        motion_id (str): Unique identifier for the motion associated with the vote.
        event_date (date): The date of the vote event.
        result (str): Final result of the vote event
        votes_in_favor (int): Number of votes in favor
        votes_against (int): Number of votes against
        votes_abstention (int): Number of votes in abstention
    """

    __tablename__ = "vote_events"

    vote_event_id: Mapped[str] = mapped_column(primary_key=True, nullable=False)
    org_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.org_id"), nullable=False
    )
    bill_id: Mapped[str | None] = mapped_column(ForeignKey("bills.id"), nullable=True)
    motion_id: Mapped[str | None] = mapped_column(
        ForeignKey("motions.id"), nullable=True
    )
    event_date: Mapped[date] = mapped_column(nullable=False)
    result: Mapped[VoteResult] = mapped_column(
        Enum(
            VoteResult,
            name="vote_result",
            values_callable=enum_values,
            native_enum=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    votes_in_favor: Mapped[int] = mapped_column(nullable=False)
    votes_against: Mapped[int] = mapped_column(nullable=False)
    votes_abstention: Mapped[int] = mapped_column(nullable=False)

    __table_args__ = (
        CheckConstraint(
            """
            (bill_id IS NOT NULL AND motion_id IS NULL)
            OR
            (bill_id IS NULL AND motion_id IS NOT NULL)
            """,
            name="ck_vote_event_exactly_one_target",
        ),
        Index(
            "uq_vote_event_org_bill_date",
            "org_id",
            "bill_id",
            "event_date",
            unique=True,
            postgresql_where=text("bill_id IS NOT NULL"),
        ),
        Index(
            "uq_vote_event_org_motion_date",
            "org_id",
            "motion_id",
            "event_date",
            unique=True,
            postgresql_where=text("motion_id IS NOT NULL"),
        ),
        CheckConstraint(
            "votes_in_favor >= 0", name="ck_vote_event_votes_in_favor_nonnegative"
        ),
        CheckConstraint(
            "votes_against >= 0", name="ck_vote_event_votes_against_nonnegative"
        ),
        CheckConstraint(
            "votes_abstention >= 0", name="ck_vote_event_votes_abstention_nonnegative"
        ),
        Index("ix_vote_event_bill_id", "bill_id"),
        Index("ix_vote_event_motion_id", "motion_id"),
        Index("ix_vote_event_org_id", "org_id"),
    )


class VoteCounts(Base):
    """
    Represents the counts of votes in a vote event.

    Attributes:
        vote_event_id (str): Unique identifier for the vote event.
        option (str): The voter's choice, e.g., 'yes', 'no', 'abstain'.
        bancada_id (int): The political group of the voter.
        count (int): Number of votes for the option.
    """

    __tablename__ = "vote_counts"

    vote_event_id: Mapped[str] = mapped_column(
        ForeignKey("vote_events.vote_event_id"), nullable=False
    )
    option: Mapped[VoteOption] = mapped_column(vote_option_enum, nullable=False)
    bancada_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.org_id"), nullable=False
    )
    count: Mapped[int] = mapped_column(nullable=False)

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
        title (str): Title of the bill.
        summary_congreso (str): Summary of the bill.
        observations (str): Observations on the bill.
        status (str): Current status of the bill.
        proponent (str): Type of proponent of the bill
        author_id (int): Unique identifier for the author of the bill.
        bill_approved (bool): Boolean indicating if the bill has been published
        summary_oc (str): Summary generated by OpenCongress
    """

    __tablename__ = "bills"

    id: Mapped[str] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(nullable=False)
    summary_congreso: Mapped[str] = mapped_column(Text, nullable=False)
    observations: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(nullable=False)
    proponent: Mapped[Proponents] = mapped_column(
        Enum(
            Proponents,
            name="proponents",
            values_callable=enum_values,
            native_enum=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    author_id: Mapped[int] = mapped_column(ForeignKey("congresistas.id"), nullable=True)
    bill_approved: Mapped[bool] = mapped_column(nullable=False)
    summary_oc: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (Index("ix_bill_author_id", "author_id"),)


class BillCongresistas(Base):
    """
    Represents a relation between a bill and parliament members based on their
    role during the presentation of the bill.

    Attributes:
        bill_id (str): A unique identifier for the bill.
        person_id (int): A unique identifier for the person.
        bancada_id (int): Unique identifier for the political group associated with the bill at the moment of presentation.
        role_type (str): The type of role that the person has in the bill (e.g. author, coauthor, adherente, etc)
    """

    __tablename__ = "bills_congresistas"

    bill_id: Mapped[str] = mapped_column(ForeignKey("bills.id"), nullable=False)
    person_id: Mapped[int] = mapped_column(
        ForeignKey("congresistas.id"), nullable=False
    )
    bancada_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.org_id"), nullable=True
    )
    role_type: Mapped[TypeRoleBill] = mapped_column(type_role_bill_enum, nullable=False)
    __table_args__ = (
        PrimaryKeyConstraint("bill_id", "person_id"),
        Index("ix_billcongresistas_person_id", "person_id"),
        Index("ix_billcongresistas_bancada_id", "bancada_id"),
    )


class BillOrganization(Base):
    """
    Represents the relation between bills and a organization

    Attributes:
        bill_id (str): The identifier of the bill.
        org_id (int): The identifier of the organization.
        org_type (str): Type of the organization.
        presentation_date (date): Date of presentation of the motion in the organization.
        decision_date (date): Date of the final decision of the motion in the organization.
    """

    __tablename__ = "bill_organizations"

    bill_id: Mapped[str] = mapped_column(ForeignKey("bills.id"), nullable=False)
    org_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.org_id"), nullable=False
    )
    org_type: Mapped[TypeOrganization] = mapped_column(
        Enum(
            TypeOrganization,
            name="type_organization",
            values_callable=enum_values,
            native_enum=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    presentation_date: Mapped[date] = mapped_column(nullable=False)
    decision_date: Mapped[date | None] = mapped_column(nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint("bill_id", "org_id", name="bill_org_uniq"),
        Index("ix_billcommittees_org_id", "org_id"),
        Index("ix_billcommittees_bill_id", "bill_id"),
    )


class BillStep(Base):
    """
    Represents a bill step record with details about the actions taken on a bill.

    Attributes:
        bill_id (str): The identifier of the bill associated with this step.
        step_id (int): A unique identifier for each step record.
        step_type (str): Type of the step related to the bill
        vote_step (bool): Records if the step is a vote or not.
        vote_event_id (str): Id of the vote.
        step_date (date): The date and time when the step occured.
        step_detail (str): The details on the step
    """

    __tablename__ = "bill_steps"

    bill_id: Mapped[str] = mapped_column(ForeignKey("bills.id"), nullable=False)
    step_id: Mapped[int] = mapped_column(nullable=False)
    step_type: Mapped[TypeBillStep] = mapped_column(
        Enum(
            TypeBillStep,
            name="type_bill_steps",
            values_callable=enum_values,
            native_enum=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    vote_step: Mapped[bool] = mapped_column(nullable=False)
    vote_event_id: Mapped[str] = mapped_column(
        nullable=True
    )  # ForeignKey("vote_events.vote_event_id")
    step_date: Mapped[date] = mapped_column(nullable=False)
    step_detail: Mapped[str] = mapped_column(nullable=False)

    __table_args__ = (
        Index("ix_billstep_bill_id", "bill_id"),
        Index("ix_billstep_vote_event_id", "vote_event_id"),
        PrimaryKeyConstraint("bill_id", "step_id", name="pk_bill_steps"),
    )


class BillText(Base):
    """
    Extracted normative body text from a bill PDF (anchor-based slice of OCR text).
    One row per bill document.
    """

    __tablename__ = "bill_texts"

    bill_id: Mapped[str] = mapped_column(nullable=False)
    step_id: Mapped[int] = mapped_column(nullable=False)
    file_id: Mapped[int] = mapped_column(nullable=False)
    version_id: Mapped[int] = mapped_column(nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint(
            "bill_id", "step_id", "file_id", "version_id", name="pk_bill_texts"
        ),
        ForeignKeyConstraint(
            ["bill_id", "step_id"],
            ["bill_steps.bill_id", "bill_steps.step_id"],
            name="fk_bill_texts_bill_steps",
        ),
    )


class BillDifference(Base):
    """
    Precomputed text diff between a bill step and the most recent
    text-bearing predecessor step.

    One row per ``(bill_id, step_id)``. ``prev_step_id`` is the step_id
    (within the same bill) whose text was used as the "old" side; ``None``
    when this is the first text-bearing step.

    ``difference_content`` is a JSON-serialized hybrid payload
    (parser_version, summary, nodes) — see ``backend/process/diff/``.
    """

    __tablename__ = "bill_differences"

    bill_id: Mapped[str] = mapped_column(nullable=False)
    step_id: Mapped[int] = mapped_column(nullable=False)
    prev_step_id: Mapped[int] = mapped_column(nullable=True)
    difference_type: Mapped[str] = mapped_column(nullable=False)
    difference_content: Mapped[str] = mapped_column(Text, nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint("bill_id", "step_id", name="pk_bill_differences"),
        ForeignKeyConstraint(
            ["bill_id", "step_id"],
            ["bill_steps.bill_id", "bill_steps.step_id"],
            name="fk_bill_differences_bill_steps",
        ),
        Index("ix_billdifference_bill_id", "bill_id"),
    )


class Congresista(Base):
    """
    Represents a member of the peruvian parliament

    Attributes:
        id (int): Unique identifier for the person.
        full_name (str): Full name of the person.
        first_name (str): First name of the person.
        last_name (str): Last name of the person.
        dni (str): DNI (Documento Nacional de Identidad) of the person.
        gender (str): Male or Female.
        photo_url (str): Official photo url of the congressperson.
        photo_bytes (bytes | None): Downloaded portrait image bytes, when fetched.
        website (str): Official website of the congressperson.
    """

    __tablename__ = "congresistas"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(nullable=False)
    first_name: Mapped[str] = mapped_column(nullable=True)
    last_name: Mapped[str] = mapped_column(nullable=True)
    dni: Mapped[str] = mapped_column(nullable=True)
    gender: Mapped[str] = mapped_column(nullable=True)
    photo_url: Mapped[str] = mapped_column(nullable=False)
    photo_bytes: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    website: Mapped[str] = mapped_column(nullable=False)

    __table_args__ = (UniqueConstraint("full_name", "dni", name="uq_congresista_id"),)


class Organization(Base):
    """
    Represents a legislative organization, such as a chamber, political group (bancada),
    party, committee or administrative organization.

    Attributes:
        org_id (int): Unique identification of the organization.
        org_name (str): Name of the organization.
        org_type (str): Type of organization (e.g. bancada, partido, committee, etc)
        org_subtype (str): Subtype of organization (e.g. ordinaria, especial, etc)
        org_link (str): Url of the organization's website.
        parent_org_id (int): Unique identification of the organization's parent
        date_founding (date): Date of establishment of the organization
        date_dissolution (date): Date of dissolution of the organization
    """

    __tablename__ = "organizations"

    org_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    org_name: Mapped[str] = mapped_column(nullable=False)

    org_type: Mapped[TypeOrganization] = mapped_column(
        org_type_enum,
        nullable=False,
    )
    org_subtype: Mapped[str | None] = mapped_column(nullable=True)
    org_link: Mapped[str | None] = mapped_column(nullable=True)

    parent_org_id: Mapped[int | None] = mapped_column(
        ForeignKey("organizations.org_id"), nullable=True
    )
    date_founding: Mapped[datetime | None] = mapped_column(nullable=True)
    date_dissolution: Mapped[datetime | None] = mapped_column(nullable=True)

    __table_args__ = (
        UniqueConstraint("org_name", "org_type", "parent_org_id", name="org_uniq"),
        CheckConstraint(
            f"""
            (
                org_type = '{TypeOrganization.COMMITTEE.value}'
                AND org_subtype IN ({sql_value_list(TypeCommittee)})
            )
            OR
            (
                org_type = '{TypeOrganization.ADMINISTRATIVE.value}'
                AND org_subtype IN ({sql_value_list(TypeAdmin)})
            )
            OR
            (
                org_type NOT IN (
                    '{TypeOrganization.COMMITTEE.value}',
                    '{TypeOrganization.ADMINISTRATIVE.value}'
                )
                AND org_subtype IS NULL
            )
            """,
            name="ck_organization_subtype_matches_type",
        ),
    )


class Membership(Base):
    """
    Represents a person's role in an organization during a specific time period.

    Attributes:
        id (int): Unique identifier for the Membership
        person_id (int): Identifier for the person
        org_id (int): Identifier for the organization
        leg_period (str): Legislative period.
        org_type (str): Type of membership (e.g. bancada, partido, committee, etc)
        role (str): Role of the person in the organization (e.g. vocero, miembro, presidente, etc)
        start_date (date): Date of the beginning of the membership
        end_date (date): Date of the end of the membership
    """

    __tablename__ = "memberships"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    person_id: Mapped[int] = mapped_column(
        ForeignKey("congresistas.id"), nullable=False
    )
    org_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.org_id"), nullable=False
    )
    leg_period: Mapped[str] = mapped_column(nullable=False)

    org_type: Mapped[TypeOrganization] = mapped_column(
        org_type_enum,
        nullable=False,
    )
    role: Mapped[str] = mapped_column(nullable=False)

    start_date: Mapped[date] = mapped_column(nullable=False)
    end_date: Mapped[date] = mapped_column(nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "person_id",
            "org_id",
            "leg_period",
            "org_type",
            "role",
            "start_date",
            "end_date",
            name="uq_membership_person_org_period_role_dates",
        ),
    )

    __mapper_args__ = {
        "polymorphic_on": "org_type",
        "polymorphic_identity": "membership",
    }


class ChamberMembership(Membership):
    """
    Represents a person's membership in a chamber during a specific time period.

    Attributes:
        id (int): Unique identifier for the Membership
        person_id (int): Identifier for the person
        org_id (int): Identifier for the organization
        leg_period (str): Legislative period.
        org_type (str): Type of organization (e.g. bancada, partido, committee, etc)
        role (str): Role of the person in the organization (e.g. vocero, miembro, presidente, etc)
        start_date (datetime): Date of the beginning of the membership
        end_date (datetime): Date of the end of the membership
        condicion (str): Current status of their membership into the chamber
        votes_in_election (int): Votes obtained in the election
        dist_electoral (str): Electoral district
    """

    __tablename__ = "chamber_memberships"

    id: Mapped[int] = mapped_column(
        ForeignKey("memberships.id"),
        primary_key=True,
    )
    condicion: Mapped[str | None] = mapped_column(nullable=True)
    votes_in_election: Mapped[int | None] = mapped_column(nullable=True)
    dist_electoral: Mapped[str | None] = mapped_column(nullable=True)

    __mapper_args__ = {
        "polymorphic_identity": TypeOrganization.CHAMBER.value,
    }


class PartyMembership(Membership):
    """
    Represents a person's membership in a party during a specific time period.

    Attributes:
        id (int): Unique identifier for the Membership
        person_id (int): Identifier for the person
        org_id (int): Identifier for the organization
        leg_period (str): Legislative period.
        org_type (str): Type of organization (e.g. bancada, partido, committee, etc)
        role (str): Role of the person in the organization (e.g. vocero, miembro, presidente, etc)
        start_date (datetime): Date of the beginning of the membership
        end_date (datetime): Date of the end of the membership
    """

    __tablename__ = "party_memberships"

    id: Mapped[int] = mapped_column(
        ForeignKey("memberships.id"),
        primary_key=True,
    )

    __mapper_args__ = {
        "polymorphic_identity": TypeOrganization.PARTY.value,
    }


class BancadaMembership(Membership):
    """
    Represents a person's membership in a party during a specific time period.

    Attributes:
        id (int): Unique identifier for the Membership
        person_id (int): Identifier for the person
        org_id (int): Identifier for the organization
        leg_period (str): Legislative period.
        org_type (str): Type of organization (e.g. bancada, partido, committee, etc)
        role (str): Role of the person in the organization (e.g. vocero, miembro, presidente, etc)
        start_date (datetime): Date of the beginning of the membership
        end_date (datetime): Date of the end of the membership
    """

    __tablename__ = "bancada_memberships"

    id: Mapped[int] = mapped_column(
        ForeignKey("memberships.id"),
        primary_key=True,
    )

    __mapper_args__ = {
        "polymorphic_identity": TypeOrganization.BANCADA.value,
    }


class CommitteeMembership(Membership):
    """
    Represents a person's membership in a party during a specific time period.

    Attributes:
        id (int): Unique identifier for the Membership
        person_id (int): Identifier for the person
        org_id (int): Identifier for the organization
        leg_period (str): Legislative period.
        org_type (str): Type of organization (e.g. bancada, partido, committee, etc)
        role (str): Role of the person in the organization (e.g. vocero, miembro, presidente, etc)
        start_date (datetime): Date of the beginning of the membership
        end_date (datetime): Date of the end of the membership
    """

    __tablename__ = "committee_memberships"

    id: Mapped[int] = mapped_column(
        ForeignKey("memberships.id"),
        primary_key=True,
    )

    __mapper_args__ = {
        "polymorphic_identity": TypeOrganization.COMMITTEE.value,
    }


class AdminMembership(Membership):
    """
    Represents a person's membership in a party during a specific time period.

    Attributes:
        id (int): Unique identifier for the Membership
        person_id (int): Identifier for the person
        org_id (int): Identifier for the organization
        leg_period (str): Legislative period.
        org_type (str): Type of organization (e.g. bancada, partido, committee, etc)
        role (str): Role of the person in the organization (e.g. vocero, miembro, presidente, etc)
        start_date (datetime): Date of the beginning of the membership
        end_date (datetime): Date of the end of the membership
    """

    __tablename__ = "admin_memberships"

    id: Mapped[int] = mapped_column(
        ForeignKey("memberships.id"),
        primary_key=True,
    )

    __mapper_args__ = {
        "polymorphic_identity": TypeOrganization.ADMINISTRATIVE.value,
    }


class Motion(Base):
    """
    Represents a motion in the peruvian parliament.

    Attributes:
        id (str): Unique identifier for the motion.
        motion_type (str): Type of the motion.
        summary_congreso (str): Summary of the motion.
        observations (str): Observations on the motion.
        status (str): Current status of the motion.
        author_id (str): Unique identifier for the author of the motion.
        motion_approved (bool): Boolean indicating if the motion has been published
        summary_oc (str): Summary generated by OpenCongress
    """

    __tablename__ = "motions"

    id: Mapped[str] = mapped_column(primary_key=True)
    motion_type: Mapped[TypeMotion] = mapped_column(
        Enum(
            TypeMotion,
            name="type_motion",
            values_callable=enum_values,
            native_enum=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    summary_congreso: Mapped[str] = mapped_column(Text, nullable=False)
    observations: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(nullable=False)
    author_id: Mapped[int] = mapped_column(ForeignKey("congresistas.id"), nullable=True)
    motion_approved: Mapped[bool] = mapped_column(nullable=False, default=False)
    summary_oc: Mapped[str] = mapped_column(Text, nullable=False)


class MotionCongresistas(Base):
    """
    Represents a relation between a motion and parliament members based on their
    role during the presentation of the motion.

    Attributes:
        motion_id (str): A unique identifier for the motion.
        nombre (str): Name of the person.
        role_type (str): The type of role that the person has in the motion (e.g. author, coauthor, adherente, etc)
        bancada_id (int): Unique identifier for the political group associated with the motion at the moment of presentation.
    """

    __tablename__ = "motions_congresistas"

    motion_id: Mapped[str] = mapped_column(ForeignKey("motions.id"), nullable=False)
    person_id: Mapped[int] = mapped_column(
        ForeignKey("congresistas.id"), nullable=False
    )
    role_type: Mapped[TypeRoleBill] = mapped_column(type_role_bill_enum, nullable=False)
    bancada_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.org_id"), nullable=True
    )

    __table_args__ = (
        PrimaryKeyConstraint("motion_id", "person_id"),
        Index("ix_motioncongresistas_person_id", "person_id"),
        Index("ix_motioncongresistas_bancada_id", "bancada_id"),
    )


class MotionOrganization(Base):
    """
    Represents the relation between motions and an organization such as the 'Cámara
    de Diputados' or 'Cámara de Senadores'

    Attributes:
        motion_id (str): The identifier of the motion.
        org_name (str): The identifier of the organization.
        org_type (str): Type of the organization.
        presentation_date (date): Date of presentation of the motion in the organization.
        decision_date (date): Date of the final decision of the motion in the organization.
    """

    __tablename__ = "motion_organizations"

    motion_id: Mapped[str] = mapped_column(ForeignKey("motions.id"), nullable=False)
    org_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.org_id"), nullable=False
    )
    org_type: Mapped[TypeOrganization] = mapped_column(org_type_enum, nullable=False)
    presentation_date: Mapped[date] = mapped_column(nullable=False)
    decision_date: Mapped[date | None] = mapped_column(nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint("motion_id", "org_id"),
        Index("ix_motion_org_org_id", "org_id"),
        Index("ix_motion_org_motion_id", "motion_id"),
    )


class MotionStep(Base):
    """
    Represents a motion step record with details about the actions taken on a motion.

    Attributes:
        motion_id (str): The identifier of the motion associated with this step.
        step_id (int): A unique identifier for each step record.
        step_type (MotionStepType): Type of the step related to the motion
        vote_step (bool): Records if the step is a vote or not.
        vote_event_id (str): Id of the vote.
        step_date (datetime): The date and time when the step occured.
        step_detail (str): The details on the step
    """

    __tablename__ = "motion_steps"

    motion_id: Mapped[str] = mapped_column(ForeignKey("motions.id"), nullable=False)
    step_id: Mapped[int] = mapped_column(nullable=False)
    step_type: Mapped[TypeMotionStep] = mapped_column(
        Enum(
            TypeMotionStep,
            name="type_motion_step",
            values_callable=enum_values,
            native_enum=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    vote_step: Mapped[bool] = mapped_column(nullable=False)
    vote_event_id: Mapped[str] = mapped_column(nullable=True)
    step_date: Mapped[date] = mapped_column(nullable=False)
    step_detail: Mapped[str] = mapped_column(nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("motion_id", "step_id", name="pk_motion_steps"),
    )


class MotionText(Base):
    """
    Represents the content of a Motion at during a MotionStep

    Attributes:
        motion_id (str): The identifier of the motion associated with this step.
        step_id (int): A unique identifier for each step record.
        file_id (int): A unique identifier for each file record.
        version_id (int): The version of the motion's content
        text (str): Extracted text from the file
    """

    __tablename__ = "motion_texts"

    motion_id: Mapped[str] = mapped_column(nullable=False)
    step_id: Mapped[int] = mapped_column(nullable=False)
    file_id: Mapped[int] = mapped_column(nullable=False)
    version_id: Mapped[int] = mapped_column(nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint(
            "motion_id", "step_id", "file_id", "version_id", name="pk_motion_texts"
        ),
        ForeignKeyConstraint(
            ["motion_id", "step_id"],
            ["motion_steps.motion_id", "motion_steps.step_id"],
            "fk_motion_steps_texts",
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

    id: Mapped[str] = mapped_column(primary_key=True, nullable=False)
    title: Mapped[str] = mapped_column(nullable=False)
    bill_id: Mapped[str] = mapped_column(ForeignKey("bills.id"), nullable=False)


class CongresistaMetric(Base):
    """
    Stores precomputed metrics for each congresista by legislative period.
    """

    __tablename__ = "congresista_metrics"

    cong_id: Mapped[int] = mapped_column(
        ForeignKey("congresistas.id"),
        nullable=False,
    )
    leg_period: Mapped[str] = mapped_column(nullable=False)

    avg_attendance: Mapped[float | None] = mapped_column(nullable=True)

    bills_auth: Mapped[int] = mapped_column(nullable=False, default=0)
    bills_success_rate: Mapped[float | None] = mapped_column(nullable=True)

    motions_auth: Mapped[int] = mapped_column(nullable=False, default=0)
    motions_success_rate: Mapped[float | None] = mapped_column(nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint("cong_id", "leg_period"),
        Index("ix_congresista_metrics_period", "leg_period"),
    )


class SemanticBill(Base):
    """
    Stores semantic-search chunks and embeddings for bills.

    Each row represents one chunk of text extracted from a bill. The chunk is
    converted into an embedding vector and used by PostgreSQL/pgvector to perform
    semantic similarity search.

    This table is a derived search index, not the source of truth for bill data.
    The source bill metadata remains in the `bills` table.

    Attributes:
        id (int): Primary key for the semantic bill chunk.
        bill_id (str): ID of the bill associated with this chunk.
        chunk_index (int): Position of the chunk within the full bill text.
        text (str): Text content used to generate the embedding.
        embedding (list[float]): Vector representation of the chunk text.
        embedding_model_name (str): Name of the model used to generate the embedding.
    """

    __tablename__ = "semantic_bills"

    id: Mapped[int] = mapped_column(primary_key=True)

    bill_id: Mapped[str] = mapped_column(
        ForeignKey("bills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(nullable=False)

    text: Mapped[str] = mapped_column(Text, nullable=False)

    embedding: Mapped[list[float]] = mapped_column(
        Vector(DEFAULT_EMBEDDING_DIM), nullable=False
    )
    embedding_model_name: Mapped[EmbeddingModel] = mapped_column(
        embedding_model_name_enum,
        nullable=False,
    )
    __table_args__ = (
        CheckConstraint(
            f"embedding_model_name = '{EmbeddingModel.MULTILINGUAL_E5_BASE.value}'",
            name="ck_semantic_bills_embedding_model_name_supported",
        ),
        UniqueConstraint(
            "bill_id",
            "chunk_index",
            "embedding_model_name",
            name="uq_semantic_bills_bill_chunk_model",
        ),
    )
