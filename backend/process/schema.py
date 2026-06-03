from pydantic import BaseModel, field_validator, ConfigDict
from backend import (
    VoteOption,
    VoteResult,
    MajorityType,
    AttendanceStatus,
    RoleTypeBill,
    LegPeriod,
    Legislature,
    LegislativeYear,
    Proponents,
    TypeOrganization,
    RoleOrganization,
    TypeCommittee,
    MotionType,
    parse_leg_period,
    parse_legislature,
    parse_role_bill,
    parse_proponent,
    parse_motion_type,
)
from typing import Optional
from datetime import datetime


class PrintableModel(BaseModel):
    def __str__(self):
        return "\n".join(f"{key}: {value}" for key, value in self.model_dump().items())


class Vote(PrintableModel):
    """
    Pydantic model representing a vote.

    Attributes:
        vote_event_id (str):
        voter_id (str):
        option (str):
        bancada_id (str):
    """

    # Attributes that fit in in Popolo structure
    vote_event_id: str
    voter_id: int
    option: VoteOption
    bancada_id: int

    model_config = ConfigDict(use_enum_values=False)


class Attendance(PrintableModel):
    """
    Represents attendance of a congressperson at an event.

    Attributes:
        event_id (str): Unique identifier for the event.
        attendee_id (str): Unique identifier for the congressperson.
        status (str): Attendance status, e.g., 'present', 'absent'.
    """

    event_id: str
    attendee_id: int
    status: AttendanceStatus

    model_config = ConfigDict(use_enum_values=False)


class VoteEvent(PrintableModel):
    """
    Represents a vote event in a parliament session.
    Attributes:
        leg_period (str): The legislative period during which the vote occurred.
        bill_id (str): Unique identifier for the bill associated with the vote.
        date (str): The date of the vote event.
    """

    # Attributes that fit in in Popolo structure
    leg_period: LegPeriod
    bill_or_motion: str
    bill_motion_id: str
    date: datetime
    result: VoteResult
    majority_type: MajorityType | None
    votes: Optional[list[Vote]] = None
    attendance: Optional[list[Attendance]] = None

    @field_validator("leg_period", mode="before")
    @classmethod
    def validate_leg_period(cls, v):
        if isinstance(v, LegPeriod):
            return v
        return parse_leg_period(v)

    model_config = ConfigDict(use_enum_values=False)

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

    def get_counts_by_bancada(self) -> dict[int, dict[VoteOption, int]]:
        """
        Returns vote counts grouped by bancada and option.
        """
        if not self.votes:
            return {}

        counts: dict[int, dict[VoteOption, int]] = {}
        for vote in self.votes:
            counts.setdefault(vote.bancada_id, {}).setdefault(vote.option, 0)
            counts[vote.bancada_id][vote.option] += 1
        return counts

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
    bancada_id: int
    count: int

    model_config = ConfigDict(use_enum_values=False)


class Bill(PrintableModel):
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
        author_name (str): Unique identifier for the author of the bill.
        author_web (str): Unique identifier for the political group associated with the bill.
        bill_approved (bool): Boolean indicating if the bill has been published
    """

    # Attributes that fit in in Popolo structure
    id: str
    leg_period: LegPeriod
    legislature: Legislature
    presentation_date: datetime
    title: str
    summary: str
    observations: str | None
    complete_text: str | None
    status: str
    proponent: Proponents
    author_name: str | None
    author_web: str | None
    bill_approved: bool

    model_config = ConfigDict(use_enum_values=False)

    @field_validator("leg_period", mode="before")
    @classmethod
    def validate_leg_period(cls, v):
        if isinstance(v, LegPeriod):
            return v
        return parse_leg_period(v)

    @field_validator("legislature", mode="before")
    @classmethod
    def validate_legislature(cls, v):
        if isinstance(v, Legislature):
            return v
        return parse_legislature(v)

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
        leg_period (str): Legislative period.
        role_type (str): The type of role that the person has in the bill (e.g. author, coauthor, adherente, etc)
        web_page (str): Webpage.
    """

    bill_id: str
    nombre: str
    leg_period: LegPeriod
    role_type: RoleTypeBill
    web_page: str | None = None

    @field_validator("leg_period", mode="before")
    @classmethod
    def validate_leg_period(cls, v):
        if isinstance(v, LegPeriod):
            return v
        return parse_leg_period(v)

    @field_validator("role_type", mode="before")
    @classmethod
    def validate_role_type(cls, v):
        if isinstance(v, RoleTypeBill):
            return v
        return parse_role_bill(v)

    model_config = ConfigDict(use_enum_values=False)


class BillCommittees(PrintableModel):
    """
    Represents the relation between bills and a committee

    Attributes:
        bill_id (str): The identifier of the bill.
        committee_name (str): The identifier of the committee.
    """

    bill_id: str
    committee_name: str


class BillStep(PrintableModel):
    """
    Represents a bill step record with details about the actions taken on a bill.

    Attributes:
        id (int): A unique identifier for each step record.
        bill_id (str): The identifier of the bill associated with this step.
        vote_step (bool): Records if the step is a vote or not.
        step_date (datetime): The date and time when the step occured.
        step_detail (str): The details on the step
    """

    id: int
    bill_id: str
    vote_step: bool
    vote_id: str | None
    step_date: datetime
    step_status: str | None = None
    step_detail: str
    step_files: list[int]

    model_config = ConfigDict(use_enum_values=False)


class BillDocument(PrintableModel):
    """
    Represents a document object related to a Bill and to a specific BillStep

    Attributes:
        bill_id (str): The identifier of the bill associated with this step.
        step_id (int): A unique identifier for each step record.
        archivo_id (int): A unique identifier for each file record.
        url (str): The url associated to the file
        text (str): Extracted text from the file
        vote_doc (bool): Records if the step is a vote or not.
    """

    bill_id: str
    step_id: int
    archivo_id: int
    url: str
    text: str
    vote_doc: bool

    model_config = ConfigDict(use_enum_values=False)


class Motion(PrintableModel):
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
        author_name (str): Unique identifier for the author of the motion.
        author_web (str): Unique identifier for the political group associated with the motion.
        motion_approved (bool): Boolean indicating if the motion has been published
    """

    # Attributes that fit in in Popolo structure
    id: str
    leg_period: LegPeriod
    legislature: Legislature
    presentation_date: datetime
    motion_type: MotionType
    summary: str
    observations: str | None
    complete_text: str | None
    status: str
    author_name: str | None
    author_web: str | None
    motion_approved: bool

    model_config = ConfigDict(use_enum_values=False)

    @field_validator("leg_period", mode="before")
    @classmethod
    def validate_leg_period(cls, v):
        if isinstance(v, LegPeriod):
            return v
        return parse_leg_period(v)

    @field_validator("legislature", mode="before")
    @classmethod
    def validate_legislature(cls, v):
        if isinstance(v, Legislature):
            return v
        return parse_legislature(v)

    @field_validator("motion_type", mode="before")
    @classmethod
    def validate_motion_type(cls, v):
        if isinstance(v, MotionType):
            return v
        return parse_motion_type(v)


class MotionCongresistas(PrintableModel):
    """
    Represents a relation between a motion and parliament members based on their
    role during the presentation of the motion.

    Attributes:
        motion_id (str): A unique identifier for the motion.
        nombre (str): Name of the person.
        leg_period (str): Legislative period.
        role_type (str): The type of role that the person has in the motion (e.g. author, coauthor, adherente, etc)
        web_page (str): website.
    """

    motion_id: str
    nombre: str
    leg_period: LegPeriod
    role_type: RoleTypeBill
    web_page: str | None = None

    @field_validator("leg_period", mode="before")
    @classmethod
    def validate_leg_period(cls, v):
        if isinstance(v, LegPeriod):
            return v
        return parse_leg_period(v)

    @field_validator("role_type", mode="before")
    @classmethod
    def validate_role_type(cls, v):
        if isinstance(v, RoleTypeBill):
            return v
        return parse_role_bill(v)

    model_config = ConfigDict(use_enum_values=False)


class MotionStep(PrintableModel):
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

    id: int
    motion_id: str
    vote_step: bool
    vote_id: str | None
    step_date: datetime
    step_status: str | None = None
    step_detail: str
    step_files: list[int]

    model_config = ConfigDict(use_enum_values=False)


class MotionDocument(PrintableModel):
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

    motion_id: str
    step_id: int
    archivo_id: int
    url: str
    text: str
    vote_doc: bool

    model_config = ConfigDict(use_enum_values=False)


class Congresista(PrintableModel):
    """
    Represents a member of the peruvian parliament

    Attributes:
        nombre (str): Name of the person.
        leg_period (str): Legislative period.
        party_name (str): Name of the party from where the person was elected.
        current_bancada (str): Name of the current bancada.
        votes_in_election (int): Number of votes obtain in elections
        dist_electoral (str): Electoral district.
        condicion (str): Condition of the congressperson, e.g., 'active', 'inactive'.
        website (str): Official website of the congressperson.
        photo_url (str): Official photo url of the congressperson.
    """

    # Attributes that fit in Popolo structure
    nombre: str
    leg_period: LegPeriod
    party_name: str
    current_bancada: str
    votes_in_election: int
    dist_electoral: Optional[str]
    condicion: str
    website: str
    photo_url: str

    @field_validator("leg_period", mode="before")
    @classmethod
    def validate_leg_period(cls, v):
        if isinstance(v, LegPeriod):
            return v
        return parse_leg_period(v)

    model_config = ConfigDict(use_enum_values=False)


class Bancada(PrintableModel):
    """
    Represent a Bancada in the peruvian government

    Attributes:
        leg_year (str): Year period of the bancada
        bancada_name (str): Name of the bancada
    """

    leg_year: LegislativeYear
    bancada_name: str

    model_config = ConfigDict(use_enum_values=False)


class Organization(PrintableModel):
    """
    Represents a legislative organization inside the parliament, such as a committee.

    Attributes:
        leg_period (str): Legislative period.
        leg_year (str): Legislative year.
        org_name (str): Name of the organization.
        org_type (str): Type of organization (e.g. bancada, partido, committee, etc)
        comm_type (str): Type of committee (e.g. ordinaria, especial, etc)
        org_link (str): Url of the organization's website.
    """

    leg_period: LegPeriod
    leg_year: LegislativeYear

    # Attributes that fit in Popolo structure
    org_name: str
    org_type: TypeOrganization
    comm_type: TypeCommittee | None
    org_link: str

    @field_validator("leg_period", mode="before")
    @classmethod
    def validate_leg_period(cls, v):
        if isinstance(v, LegPeriod):
            return v
        return parse_leg_period(v)

    model_config = ConfigDict(use_enum_values=False)


class Membership(PrintableModel):
    """
    Represents a person's role in an organization during a specific time period.

    Attributes:
        role (str): Role of the person in the organization (e.g. vocero, miembro, presidente, etc)
        nombre (str): Name of the person.
        leg_period (str): Legislative period.
        org_name (str): Name of the organization.
        org_type (str): Type of organization (e.g. bancada, partido, committee, etc)
        comm_type (str): Type of committee (e.g. ordinaria, especial, etc)
        start_date (datetime): Date of the beginning of the membership
        end_date (datetime): Date of the end of the membership
    """

    # Attributes that fit in Popolo structure
    role: RoleOrganization
    nombre: str
    web_page: str
    leg_period: LegPeriod
    org_name: str
    org_type: TypeOrganization
    comm_type: TypeCommittee | None
    start_date: datetime
    end_date: datetime | None

    model_config = ConfigDict(use_enum_values=False)

    @field_validator("leg_period", mode="before")
    @classmethod
    def validate_leg_period(cls, v):
        if isinstance(v, LegPeriod):
            return v
        return parse_leg_period(v)

    @field_validator("end_date")
    def check_end_after_start(cls, end, info):
        start = info.data.get("start_date")
        if start and end and end < start:
            raise ValueError("end_date must be after start_date")
        return end


class BancadaMembership(PrintableModel):
    """
    Represents a person's membership in a bancada during a specific time period.

    Attributes:
        leg_year (str): Year period of the membership
        cong_name (str): Name of the congresista
        website (str): Congresista's website
        bancada_name (str): Bancada's name
    """

    leg_year: LegislativeYear
    cong_name: str
    website: str
    bancada_name: str


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
