"""SQLAlchemy ORM models. The schema itself is owned by the Alembic migrations."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Table,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base."""


class Company(Base):
    """A tenant company with its business time zone."""

    __tablename__ = "companies"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    timezone: Mapped[str] = mapped_column(Text)


class User(Base):
    """A seeded user with a single company-wide role."""

    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"))
    name: Mapped[str] = mapped_column(Text)
    email: Mapped[str] = mapped_column(Text, unique=True)
    role: Mapped[str] = mapped_column(Text)


class Team(Base):
    """A leadership team."""

    __tablename__ = "teams"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"))
    name: Mapped[str] = mapped_column(Text)


class TeamMembership(Base):
    """User belongs to team."""

    __tablename__ = "team_memberships"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id"), primary_key=True)


class Measurable(Base):
    """A weekly number with a goal."""

    __tablename__ = "measurables"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id"))
    name: Mapped[str] = mapped_column(Text)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    unit: Mapped[str] = mapped_column(Text)
    goal_type: Mapped[str] = mapped_column(Text)
    goal_value: Mapped[Decimal | None] = mapped_column(Numeric)
    goal_min: Mapped[Decimal | None] = mapped_column(Numeric)
    goal_max: Mapped[Decimal | None] = mapped_column(Numeric)
    position: Mapped[int] = mapped_column(Integer, default=0)


class Score(Base):
    """A measurable's value for one company-local week."""

    __tablename__ = "scores"
    measurable_id: Mapped[str] = mapped_column(ForeignKey("measurables.id"), primary_key=True)
    week_start: Mapped[date] = mapped_column(Date, primary_key=True)
    value: Mapped[Decimal] = mapped_column(Numeric)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))


class Rock(Base):
    """A quarterly goal."""

    __tablename__ = "rocks"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id"))
    title: Mapped[str] = mapped_column(Text)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    quarter: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)


class Milestone(Base):
    """A dated step within a Rock."""

    __tablename__ = "milestones"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    rock_id: Mapped[str] = mapped_column(ForeignKey("rocks.id"))
    title: Mapped[str] = mapped_column(Text)
    due_date: Mapped[date] = mapped_column(Date)
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    position: Mapped[int] = mapped_column(Integer, default=0)


class Meeting(Base):
    """A Level 10 meeting; the database is the single source of truth for its state."""

    __tablename__ = "meetings"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id"))
    facilitator_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    section_index: Mapped[int] = mapped_column(SmallInteger, default=0)
    section_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, default=1)
    scorecard_week: Mapped[date] = mapped_column(Date)
    summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class MeetingAttendee(Base):
    """User attended meeting."""

    __tablename__ = "meeting_attendees"
    meeting_id: Mapped[str] = mapped_column(ForeignKey("meetings.id"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class MeetingRating(Base):
    """An attendee's 1-10 rating."""

    __tablename__ = "meeting_ratings"
    meeting_id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, primary_key=True)
    rating: Mapped[int] = mapped_column(SmallInteger)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class MeetingEvent(Base):
    """Append-only log of meeting lifecycle events."""

    __tablename__ = "meeting_events"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    meeting_id: Mapped[str] = mapped_column(ForeignKey("meetings.id"))
    type: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Issue(Base):
    """A problem to solve; optionally sourced from a measurable's week."""

    __tablename__ = "issues"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id"))
    title: Mapped[str] = mapped_column(Text)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    priority: Mapped[int | None] = mapped_column(SmallInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    solved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_note: Mapped[str | None] = mapped_column(Text)
    source_measurable_id: Mapped[str | None] = mapped_column(String)
    source_week_start: Mapped[date | None] = mapped_column(Date)
    solved_in_meeting_id: Mapped[str | None] = mapped_column(ForeignKey("meetings.id"))
    seq: Mapped[int] = mapped_column(BigInteger, Identity(always=True))
    version: Mapped[int] = mapped_column(Integer, default=1)


class Todo(Base):
    """A dated task; optionally created from an Issue."""

    __tablename__ = "todos"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id"))
    title: Mapped[str] = mapped_column(Text)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    due_date: Mapped[date] = mapped_column(Date)
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_issue_id: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_in_meeting_id: Mapped[str | None] = mapped_column(ForeignKey("meetings.id"))
    seq: Mapped[int] = mapped_column(BigInteger, Identity(always=True))


def table_of(model: type[Base]) -> Table:
    """The Core ``Table`` behind an ORM model (for INSERT ... ON CONFLICT and similar)."""
    return cast("Table", model.__table__)
