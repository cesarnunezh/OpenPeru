from typing_extensions import Self
from pydantic import BaseModel, field_validator, ConfigDict, model_validator
from backend import (
    VoteOption,
    VoteResult,
    AttendanceStatus,
    TypeRoleBill,
    TypeBillStep,
    LegPeriod,
    TypeMotionStep,
    Proponents,
    TypeOrganization,
    RoleOrganization,
    TypeCommittee,
    TypeAdmin,
    TypeMotion,
    parse_leg_period,
    parse_role_bill,
    parse_proponent,
    parse_motion_type,
)
from datetime import datetime, date


class PrintableModel(BaseModel):
    def __str__(self):
        return "\n".join(f"{key}: {value}" for key, value in self.model_dump().items())


class Vote(PrintableModel):
    """
    Pydantic model representing a vote.

    Attributes:
        vote_event_id (str):
        voter_full_name (str):
        voter_website (str):
        option (str):
        bancada_name (str):
    """

    # Attributes that fit in in Popolo structure
    vote_event_id: str
    voter_full_name: str
    voter_website: str | None
    option: VoteOption
    bancada_name: str

    model_config = ConfigDict(extra="forbid", use_enum_values=False)


class Attendance(PrintableModel):
    """
    Represents attendance of a congressperson at an event.

    Attributes:
        event_id (str): Unique identifier for the event.
        attendee_id (str): Unique identifier for the congressperson.
        status (str): Attendance status, e.g., 'present', 'absent'.
    """

    event_id: str
    voter_full_name: str
    voter_website: str | None
    status: AttendanceStatus

    model_config = ConfigDict(extra="forbid", use_enum_values=False)


class VoteCount(PrintableModel):
    """
    Represents the counts of votes in a vote event.

    Attributes:
        vote_event_id (str): Unique identifier for the vote event.
        option (str): The voter's choice, e.g., 'yes', 'no', 'abstain'.
        bancada (str): The political group of the voter.
        count (int): Number of votes for the option.
    """

    vote_event_id: str
    option: VoteOption
    bancada_name: str
    count: int

    model_config = ConfigDict(extra="forbid", use_enum_values=False)


class VoteEvent(PrintableModel):
    """
    Represents a vote event in a parliament session.
    Attributes:
        vote_event_id (str): Unique identifier for the vote event
        org_name (str): Name of the organization where the vote occur
        org_type (str): Type of organization
        bill_id (str): Unique identifier for the bill associated with the vote.
        motion_id (str): Unique identifier for the motion associated with the vote.
        event_date (date): The date of the vote event.
        result (str): Final result of the vote event
        votes (list[Vote]): List of Vote objects in this event
        attendance (list[Attendance]): List of Attendance objects in this event
    """

    # Attributes that fit in in Popolo structure
    vote_event_id: str
    org_name: str
    org_type: str
    bill_id: str | None
    motion_id: str | None
    event_date: date
    result: VoteResult
    votes: list[Vote]
    attendance: list[Attendance]

    model_config = ConfigDict(extra="forbid", use_enum_values=False)

    def get_counts(self) -> dict[VoteOption, int]:
        """
        Counts the number of votes per option.
        """
        if not self.votes:
            return {}
        return {
            option: sum(1 for vote in self.votes if vote.option == option)
            for option in set(vote.option for vote in self.votes)
        }

    def get_counts_by_bancada(self) -> list[VoteCount]:
        """
        Returns vote counts grouped by bancada and option.
        """
        if not self.votes:
            return []

        counts: dict[tuple[str, VoteOption], int] = {}

        for vote in self.votes:
            key = (vote.bancada_name, vote.option)
            counts[key] = counts.get(key, 0) + 1

        return [
            VoteCount(
                vote_event_id=self.vote_event_id,
                bancada_name=bancada_name,
                option=option,
                count=count,
            )
            for (bancada_name, option), count in sorted(
                counts.items(),
                key=lambda item: (item[0][0], item[0][1].value),
            )
        ]

    def get_attendance_summary(self) -> dict[str, int]:
        """
        Returns a summary count of attendance statuses.
        """
        if not self.attendance:
            return {}

        summary: dict[str, int] = {}
        for att in self.attendance:
            summary[att.status] = summary.get(att.status, 0) + 1
        return summary


class Bill(PrintableModel):
    """
    Represents a bill in the peruvian parliament.

    Attributes:
        id (str): Unique identifier for the bill.
        title (str): Title of the bill.
        summary_congreso (str): Summary of the bill.
        observations (str): Observations on the bill.
        status (str): Current status of the bill.
        proponent (str): Type of proponent of the bill
        author_name (str): Unique identifier for the author of the bill.
        author_web (str): Unique identifier for the political group associated with the bill.
        bill_approved (bool): Boolean indicating if the bill has been published
        summary_oc (str): Summary generated by OpenCongress
    """

    # Attributes that fit in in Popolo structure
    id: str
    # biil_type: BillType TODO: Pending create types for bills
    title: str
    summary_congreso: str
    observations: str | None
    status: str
    proponent: Proponents
    author_name: str | None
    author_web: str | None
    bancada_name: str | None
    bill_approved: bool = False
    summary_oc: str

    model_config = ConfigDict(extra="forbid", use_enum_values=False)

    @field_validator("proponent", mode="before")
    @classmethod
    def validate_proponent(cls, v):
        if isinstance(v, Proponents):
            return v
        return parse_proponent(v)


class BillCongresistas(PrintableModel):
    """
    Represents a relation between a bill and parliament members based on their
    role during the presentation of the bill.

    Attributes:
        bill_id (str): A unique identifier for the bill.
        nombre (str): Name of the person.
        role_type (str): The type of role that the person has in the bill (e.g. author, coauthor, adherente, etc)
        web_page (str): Webpage.
    """

    bill_id: str
    nombre: str
    role_type: TypeRoleBill
    web_page: str | None = None

    @field_validator("role_type", mode="before")
    @classmethod
    def validate_role_type(cls, v):
        if isinstance(v, TypeRoleBill):
            return v
        return parse_role_bill(v)

    model_config = ConfigDict(extra="forbid", use_enum_values=False)


class BillOrganization(PrintableModel):
    """
    Represents the relation between bills and an organization

    Attributes:
        bill_id (str): The identifier of the bill.
        org_name (str): The identifier of the organization.
        org_type (str): Type of the organization.
        presentation_date (date): Date of presentation of the bill in the organization.
        decision_date (date): Date of the final decision of the bill in the organization.
    """

    bill_id: str
    org_name: str
    org_type: TypeOrganization
    presentation_date: date
    decision_date: date | None = None


class BillStep(PrintableModel):
    """
    Represents a bill step record with details about the actions taken on a bill.

    Attributes:
        bill_id (str): The identifier of the bill associated with this step.
        step_id (int): A unique identifier for each step record.
        step_type (TypeBillStep): Type of the step related to the bill
        vote_step (bool): Records if the step is a vote or not.
        vote_event_id (str): Id of the vote.
        step_date (date): The date and time when the step occured.
        step_detail (str): The details on the step
        step_committees (list[str]): The committees associated with this step
    """

    bill_id: str
    step_id: int
    step_type: TypeBillStep
    vote_step: bool
    vote_event_id: str | None = None
    step_date: date
    step_detail: str
    step_committees: list[str] | None

    model_config = ConfigDict(extra="forbid", use_enum_values=False)


class BillText(PrintableModel):
    """
    Represents a document object related to a Bill and to a specific BillStep

    Attributes:
        bill_id (str): The identifier of the bill associated with this step.
        step_id (int): A unique identifier for each step record.
        file_id (int): A unique identifier for each file record.
        version_id (int): The version of the bill's content
        text (str): Extracted text from the file
    """

    bill_id: str
    step_id: int
    file_id: int
    version_id: int
    text: str

    model_config = ConfigDict(extra="forbid", use_enum_values=False)


class Motion(PrintableModel):
    """
    Represents a motion in the peruvian parliament.

    Attributes:
        id (str): Unique identifier for the motion.
        motion_type (str): Type of the motion.
        summary_congreso (str): Summary of the motion.
        observations (str): Observations on the motion.
        status (str): Current status of the motion.
        author_name (str): Unique identifier for the author of the motion.
        author_web (str): Unique identifier for the political group associated with the motion.
        motion_approved (bool): Boolean indicating if the motion has been published
        summary_opencongress (str): Summary generated by OpenCongress
    """

    # Attributes that fit in in Popolo structure
    id: str
    motion_type: TypeMotion
    summary_congreso: str
    observations: str | None
    status: str
    author_name: str | None
    author_web: str | None
    motion_approved: bool
    summary_opencongress: str

    model_config = ConfigDict(extra="forbid", use_enum_values=False)

    @field_validator("motion_type", mode="before")
    @classmethod
    def validate_motion_type(cls, v):
        if isinstance(v, TypeMotion):
            return v
        return parse_motion_type(v)


class MotionCongresistas(PrintableModel):
    """
    Represents a relation between a motion and parliament members based on their
    role during the presentation of the motion.

    Attributes:
        motion_id (str): A unique identifier for the motion.
        nombre (str): Name of the person.
        role_type (str): The type of role that the person has in the motion (e.g. author, coauthor, adherente, etc)
        web_page (str): website.
    """

    motion_id: str
    nombre: str
    role_type: TypeRoleBill
    web_page: str | None = None

    @field_validator("role_type", mode="before")
    @classmethod
    def validate_role_type(cls, v):
        if isinstance(v, TypeRoleBill):
            return v
        return parse_role_bill(v)

    model_config = ConfigDict(extra="forbid", use_enum_values=False)


class MotionOrganization(PrintableModel):
    """
    Represents the relation between motions and an organization

    Attributes:
        motion_id (str): The identifier of the motion.
        org_name (str): The identifier of the organization.
        org_type (str): Type of the organization.
        presentation_date (date): Date of presentation of the motion in the organization.
        decision_date (date): Date of the final decision of the motion in the organization.
    """

    motion_id: str
    org_name: str
    org_type: TypeOrganization
    presentation_date: date
    decision_date: date | None = None


class MotionStep(PrintableModel):
    """
    Represents a motion step record with details about the actions taken on a motion.

    Attributes:
        motion_id (str): The identifier of the motion associated with this step.
        step_id (int): A unique identifier for each step record.
        step_type (TypeMotionStep): Type of the step related to the motion
        vote_step (bool): Records if the step is a vote or not.
        vote_event_id (int): Id of the vote.
        step_date (date): The date and time when the step occured.
        step_detail (str): The details on the step
    """

    motion_id: str
    step_id: int
    step_type: TypeMotionStep
    vote_step: bool
    vote_event_id: str | None = None
    step_date: date
    step_detail: str

    model_config = ConfigDict(extra="forbid", use_enum_values=False)


class MotionText(PrintableModel):
    """
    Represents the content of a Motion at during a MotionStep

    Attributes:
        motion_id (str): The identifier of the motion associated with this step.
        step_id (int): A unique identifier for each step record.
        file_id (int): A unique identifier for each file record.
        version_id (int): The version of the motion's content
        text (str): Extracted text from the file
    """

    motion_id: str
    step_id: int
    file_id: int
    version_id: int
    text: str

    model_config = ConfigDict(extra="forbid", use_enum_values=False)


class Congresista(PrintableModel):
    """
    Represents a member of the peruvian parliament

    Attributes:
        full_name (str): Full name of the person.
        first_name (str): First name of the person.
        last_name (str): Last name of the person.
        dni (str): DNI (Documento Nacional de Identidad) of the person.
        gender (str): Male or Female.
        photo_url (str): Official photo url of the congressperson.
        website (str): Official website of the congressperson.
    """

    full_name: str
    first_name: str | None = None
    last_name: str | None = None
    dni: str | None = None
    gender: str | None = None
    photo_url: str
    website: str

    @field_validator("gender", mode="before")
    @classmethod
    def validate_gender(cls, v):
        if v in ("Masculino", "Femenino"):
            return v
        return None

    @field_validator("dni", mode="before")
    @classmethod
    def validate_dni(cls, v):
        if isinstance(v, str) and len(v) == 8:
            return v
        return None


class Organization(PrintableModel):
    """
    Represents a legislative organization inside the parliament, such as a committee.

    Attributes:
        org_name (str): Name of the organization.
        org_type (str): Type of organization (e.g. bancada, partido, committee, etc)
        org_subtype (str): Subtype of organization (e.g. ordinaria, especial, etc)
        org_link (str): Url of the organization's website.
        parent_org_name (str): Name of other organization where this organization belongs to
        parent_org_type (TypeOrganization): Type of organization of parent
        date_founding (date): Date of establishment of the organization
        date_dissolution (date): Date of dissolution of the organization
    """

    # Attributes that fit in Popolo structure
    org_name: str
    org_type: TypeOrganization
    org_subtype: TypeCommittee | TypeAdmin | None = None
    org_link: str | None = None
    parent_org_name: str | None = None
    parent_org_type: TypeOrganization | None = None
    date_founding: date | None = None
    date_dissolution: date | None = None

    @model_validator(mode="after")
    def validate_org_subtype(self):
        if self.org_type == TypeOrganization.COMMITTEE:
            if not isinstance(self.org_subtype, TypeCommittee):
                self.org_subtype = None

        elif self.org_type == TypeOrganization.ADMINISTRATIVE:
            if not isinstance(self.org_subtype, TypeAdmin):
                self.org_subtype = None

        else:
            self.org_subtype = None

        return self

    @field_validator("org_name", "parent_org_name", mode="before")
    @classmethod
    def clean_string_fields(cls, v):
        if isinstance(v, str):
            return v.strip()
        return v

    @model_validator(mode="after")
    def validate_parent_org(self) -> Self:
        has_parent_name = bool(self.parent_org_name)
        has_parent_type = self.parent_org_type is not None

        if has_parent_name != has_parent_type:
            raise ValueError("If there is a parent, it should have name and org_type")

        return self

    model_config = ConfigDict(extra="forbid", use_enum_values=False)


class Membership(PrintableModel):
    """
    Represents a person's role in an organization during a specific time period.

    Attributes:
        cong_name (str): Name of the congresista.
        org_name (str): Name of the organization.
        org_type (str): Type of organization (e.g. bancada, partido, committee, etc)
        leg_period (str): Legislative period.
        role (str): Role of the person in the organization (e.g. vocero, miembro, presidente, etc)
        time_stamp (datetime): Date of the scraped record.
        start_date (date): Date of the beginning of the membership
        end_date (date): Date of the end of the membership
        condicion (str): Current status of their membership into the
        votes_in_election (int): Votes obtained in the election
        dist_electoral (str): Electoral district
    """

    # Attributes that fit in Popolo structure
    cong_name: str
    org_name: str
    org_type: TypeOrganization
    leg_period: LegPeriod
    role: RoleOrganization
    time_stamp: datetime
    website: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    condicion: str | None = None
    votes_in_election: int | None = None
    dist_electoral: str | None = None

    model_config = ConfigDict(extra="forbid", use_enum_values=False)

    @field_validator("leg_period", mode="before")
    @classmethod
    def validate_leg_period(cls, v):
        if isinstance(v, LegPeriod):
            return v
        return parse_leg_period(v)

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def validate_date_fields(cls, v):
        if isinstance(v, datetime):
            return v.date()
        return v

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date cannot be earlier than start_date")
        return self


class Ley(PrintableModel):
    """
    Represents a law (ley) in the peruvian parliament.

    Attributes:
        id (str): Unique identifier for the motion.
        title (str): Law title.
        bill_id (str): Bill id related to this law (Proyecto de Ley)
    """

    id: str
    title: str
    bill_id: str
