from sqlalchemy import (Column, Integer, String, Enum, Boolean, DateTime, 
                        ForeignKey, UniqueConstraint, PrimaryKeyConstraint,
                        ForeignKeyConstraint, Index)
from estecon.backend import (VoteOption, AttendanceStatus, BillStepType, RoleTypeBill, 
                     LegPeriod, Legislature, LegislativeYear, Proponents,
                     RoleOrganization, TypeOrganization)
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Vote(Base):
    '''
    Represents a vote in a parliament session.
    
    Attributes:
        vote_event_id (str): Unique identifier for the vote event.
        voter_id (str): Unique identifier for the voter.
        option (str): The voter's choice, e.g., 'yes', 'no', 'abstain'.
        bancada_id (str): The political group of the voter.
    '''
    __tablename__ = 'votes'

    vote_event_id = Column(String, ForeignKey('vote_events.id'), primary_key=True)
    voter_id = Column(Integer, ForeignKey('congresistas.id'), nullable=False)
    option = Column(Enum(VoteOption, name = "option"), nullable=False)
    bancada_id = Column(Integer, ForeignKey('organizations.org_id'), nullable=False)

    __table_args__ = (UniqueConstraint('vote_event_id', 'voter_id', name='uq_vote_event_voter'),
                      Index('ix_vote_vote_event_id', 'vote_event_id'),
                      Index('ix_vote_voter_id', 'voter_id'))

class VoteEvent(Base):
    '''
    Represents a vote event in a parliament session.

    Attributes:
        org_id (int): The org_id or parliament where the vote took place.
        leg_period (str): The legislative period during which the vote occurred.
        bill_id (str): Unique identifier for the bill associated with the vote.
        date (str): The date of the vote event.
    '''
    __tablename__ = 'vote_events'

    id = Column(String, primary_key=True)
    org_id = Column(Integer, ForeignKey('organizations.org_id'), nullable=False)
    leg_period = Column(Enum(LegPeriod, name = "leg_period"), nullable=False)
    bill_id = Column(String, ForeignKey('bills.id'), nullable=False)
    date = Column(DateTime, nullable=False)

    __table_args__ = (UniqueConstraint('org_id', 'leg_period', 'bill_id', 'id', name='uq_vote_event'),
                      Index('ix_vote_event_bill_id', 'bill_id'),)

class VoteCounts(Base):
    '''
    Represents the counts of votes in a vote event.

    Attributes:
        org_id (int): The org_id or parliament where the vote took place.
        vote_event_id (str): Unique identifier for the vote event.
        option (str): The voter's choice, e.g., 'yes', 'no', 'abstain'.
        bancada (str): The political group of the voter.
        count (int): Number of votes for the option.
    '''
    __tablename__ = 'vote_counts'

    org_id = Column(Integer, ForeignKey('organizations.org_id'), nullable=False)
    vote_event_id = Column(String, ForeignKey('vote_events.id'), nullable=False)
    option = Column(Enum(VoteOption, name = "option"), nullable=False)
    bancada_id =  Column(Integer, ForeignKey('organizations.org_id'), nullable=False)
    count = Column(Integer, nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint('org_id', 'vote_event_id', 'option', 'bancada_id', name='pk_vote_counts'),
        Index('ix_votecounts_vote_event_id', 'vote_event_id'),
        Index('ix_votecounts_bancada_id', 'bancada_id'))

class Attendance(Base):
    '''
    Represents attendance of a congressperson at an event.

    Attributes:
        org_id (int): The org_id or parliament where the event took place.
        event_id (str): Unique identifier for the event.
        attendee_id (str): Unique identifier for the congressperson.
        status (str): Attendance status, e.g., 'present', 'absent'.
    '''
    __tablename__ = 'attendance'

    org_id = Column(Integer, ForeignKey('organizations.org_id'), nullable=False)
    event_id = Column(String, ForeignKey('vote_events.id'), primary_key=True)
    attendee_id = Column(Integer, ForeignKey('congresistas.id'), nullable=False)
    status = Column(Enum(AttendanceStatus, name='attendance_status'), nullable=False)

    __table_args__ = (UniqueConstraint('org_id', 'event_id', 'attendee_id', name='uq_attendance'),
                      Index('ix_attendance_by_event', 'event_id'),
                      Index('ix_attendance_attendee_id', 'attendee_id'))

class Bill(Base):
    '''
    Represents a bill in the peruvian parliament.

    Attributes:
        id (str): Unique identifier for the bill.
        org_id (int): The org_id or parliament where the bill was presented.
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
    '''
    __tablename__ = 'bills'

    id = Column(String, primary_key=True)
    org_id = Column(Integer, ForeignKey('organizations.org_id'), nullable = False)
    leg_period = Column(Enum(LegPeriod, name = "leg_period"), nullable=False)
    legislature = Column(Enum(Legislature, name ="legislature"), nullable=False)
    presentation_date = Column(DateTime, nullable=False)
    title = Column(String, nullable=False)
    summary = Column(String, nullable=False)
    observations = Column(String, nullable=False)
    complete_text = Column(String, nullable=False)
    status = Column(String, nullable=False)
    proponent = Column(Enum(Proponents, name = "proponent"), nullable=False)
    author_id = Column(Integer, ForeignKey('congresistas.id'), nullable=True)
    bancada_id = Column(Integer, ForeignKey('organizations.org_id'), nullable=True)
    bill_approved = Column(Boolean, nullable=False)

    __table_args__ = (UniqueConstraint('id', 'org_id', name='bill_unique'),
                      Index('ix_bill_author_id', 'author_id'),
                      Index('ix_bill_bancada_id', 'bancada_id'))

class BillCongresistas(Base):
    '''
    Represents a relation between a bill and parliament members based on their 
    role during the presentation of the bill.
    
    Attributes:
        bill_id (str): A unique identifier for the bill.
        person_id (str): A unique identifier for the person.
        role_type (str): The type of role that the person has in the bill (e.g. author, coauthor, adherente, etc) 
    '''
    __tablename__ = "bills_congresistas"
    
    bill_id = Column(String, ForeignKey('bills.id'), nullable = False)
    person_id = Column(Integer, ForeignKey('congresistas.id'), nullable = False)
    role_type = Column(Enum(RoleTypeBill, name="role_type"), nullable = False)

    __table_args__ = (PrimaryKeyConstraint('bill_id', 'person_id'),
                      Index('ix_billcongresistas_person_id', 'person_id'))

class BillStep(Base):
    '''
    Represents a bill step record with details about the actions taken on a bill.

    Attributes:
        id (int): A unique identifier for each step record.
        bill_id (str): The identifier of the bill associated with this step.
        step_type (str): The type of step record (e.g. "Vote", "Assigned to Committee", "Presented", etc.)
        step_date (datetime): The date and time when the step occured.
        step_detail (str): The details on the step
        step_url (str): The url associated to the step
    '''
    __tablename__ = "bill_steps"

    id = Column(Integer, primary_key=True)
    bill_id = Column(String, ForeignKey('bills.id'), nullable=True)
    step_type = Column(Enum(BillStepType, name='type_step'), nullable=False)
    step_date = Column(DateTime, nullable=False)
    step_detail = Column(String, nullable=False)
    step_url = Column(String, nullable=False)

    __table_args__ = (Index('ix_billstep_bill_id', 'bill_id'),)

class BillCommittees(Base):
    '''
    Represents the relation between bills and a committee

    Attributes:
        bill_id (str): The identifier of the bill.
        committee_id (str): The identifier of the committee.
    '''
    __tablename__ = "bill_committees"

    bill_id = Column(String, ForeignKey('bills.id'), nullable=False)
    committee_id = Column(Integer, ForeignKey('committees.id'), nullable=False)

    __table_args__ = (PrimaryKeyConstraint('bill_id', 'committee_id'),
                      UniqueConstraint('bill_id', 'committee_id', name='bill_committee_uniq'),
                      Index('ix_billcommittees_committee_id', "committee_id"))
    
class Committee(Base):
    '''
    Represents a committee in the peruvian parliament.

    Attributes:
        leg_period (str): Legislative period of the committee.
        leg_year (str): Year period of the committee
        org_id (int): The org_id or parliament where the committee belongs.
        id (int): A unique identifier for the committee.
        name (str): Name of the committee
    '''
    __tablename__ = 'committees'

    leg_period = Column(Enum(LegPeriod, name = "leg_period"), primary_key=True, nullable=False)
    leg_year = Column(Enum(LegislativeYear, name = "leg_period"), primary_key=True, nullable=False)
    org_id = Column(Integer, ForeignKey('organizations.org_id'), nullable=False)
    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(String, nullable=False)

    __table_args__ = (UniqueConstraint('leg_period', 'leg_year', 'org_id', 'id', name='committee_uniq'),)

class Congresista(Base):
    '''
    Represents a member of the peruvian parliament

    Attributes:
        id (str): Unique identifier for the person.
        nombre (str): Name of the person.
        leg_period (str): Legislative period.
        party_id (str): Unique identifier for the party.
        votes_in_election (int): Number of votes obtain in elections
        dist_electoral (str): Electoral district.
        condicion (str): Condition of the congressperson, e.g., 'active', 'inactive'.
        website (str): Official website of the congressperson.
    '''
    __tablename__ = 'congresistas'

    id = Column(Integer, nullable=False)
    nombre = Column(String, nullable=False)
    leg_period = Column(Enum(LegPeriod, name = "leg_period"), nullable=False)
    party_id = Column(Integer, ForeignKey('partidos.party_id'), nullable=False)
    votes_in_election = Column(Integer, nullable=False)
    dist_electoral = Column(String, nullable=False)
    condicion = Column(String, nullable=False)
    website = Column(String, nullable=False)

    __table_args__ = (UniqueConstraint('id', 'leg_period', name='congresista_uniq'),
                      PrimaryKeyConstraint('id', 'leg_period'))

class Party(Base):
    '''
    Represent a Political Party in the peruvian government

    Attributes:
        leg_period (str): Legislative period.
        party_id (int): Unique identifier for the party
        party_name (str): Name of the party
    '''
    __tablename__ = "partidos"

    leg_period = Column(Enum(LegPeriod, name = "leg_period"), nullable=False)
    party_id = Column(Integer, primary_key = True)
    party_name= Column(String, nullable = False)

class Organization(Base):
    '''
    Represents a legislative organization, such as a parliament or congress.

    Attributes:
        leg_period (str): Legislative period.
        leg_year (str): Legislative year.
        org_id (int): Unique identifier for the organization.
        org_name (str): Name of the organization.
        org_type (str): Type of organization (e.g. bancada, partido, committee, etc)

    '''
    __tablename__ = "organizations"

    leg_period = Column(Enum(LegPeriod, name = "leg_period"), nullable=False)
    leg_year = Column(Enum(LegislativeYear, name = "leg_year"), primary_key=True, nullable=False)
    org_id = Column(Integer, primary_key=True)
    org_name = Column(String, nullable=False)
    org_type = Column(Enum(TypeOrganization, name = "type_organization"), nullable = False)
    
    __table_args__ = (UniqueConstraint('leg_period', 'org_id', name='org_uniq'),)

class Membership(Base):
    '''
    Represents a person's role in an organization during a specific time period.
    
    Attributes:
        id (int): Unique identifier for the membership relationship.
        role (str): Role of the person in the organization (e.g. vocero, miembro, presidente, etc)
        person_id (int): Identifier for the person
        org_id (int): Identifier for the organization
        start_date (datetime): Date of the beginning of the membership
        end_date (datetime): Date of the end of the membership
    '''

    __tablename__ = "memberships"

    id = Column(Integer, primary_key = True)
    role = Column(Enum(RoleOrganization, name = "role"), nullable = False)
    person_id = Column(Integer, ForeignKey('congresistas.id'), nullable = False)
    org_id = Column(Integer, ForeignKey('organizations.org_id'), nullable = False)
    start_date = Column(DateTime, nullable = False)
    end_date = Column(DateTime, nullable = True)

    __table_args__ = (UniqueConstraint("id", name = "membership"),)