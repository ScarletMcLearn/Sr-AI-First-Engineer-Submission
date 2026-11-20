"""Request and response models (the OpenAPI contract)."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, StringConstraints

Number = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Note = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
Role = Literal["admin", "team_member", "observer"]
MeasurableStatus = Literal["on_track", "off_track", "pending"]
RockStatusValue = Literal["on_track", "off_track", "complete"]


class Strict(BaseModel):
    """Base for request bodies: unknown fields are rejected (e.g. a forged ``role``)."""

    model_config = ConfigDict(extra="forbid")


class ErrorDetail(BaseModel):
    """Error payload."""

    code: str
    message: str
    details: object | None = None


class ErrorResponse(BaseModel):
    """Error envelope."""

    error: ErrorDetail


# ------------------------------------------------------------------ identity


class UserOut(BaseModel):
    """A user."""

    id: str
    name: str
    email: str
    role: Role


class UserRef(BaseModel):
    """Compact user reference."""

    id: str
    name: str


class TeamOut(BaseModel):
    """A team."""

    id: str
    name: str


class LoginIn(Strict):
    """Seeded-user login."""

    user_id: str = Field(min_length=1, max_length=64)


class MeOut(BaseModel):
    """Current user and the teams they may access."""

    user: UserOut
    teams: list[TeamOut]


class TeamDetailOut(BaseModel):
    """Team with its roster (eligible owners exclude Observers)."""

    id: str
    name: str
    members: list[UserOut]
    eligible_owners: list[UserRef]


# ----------------------------------------------------------------- scorecard


class GoalOut(BaseModel):
    """A measurable goal."""

    type: Literal["at_least", "at_most", "between", "exactly"]
    value: Number | None = None
    min: Number | None = None
    max: Number | None = None


class CellOut(BaseModel):
    """One measurable-week cell."""

    week_start: date
    value: Number | None
    status: MeasurableStatus
    version: int | None
    issue_id: str | None = None


class MeasurableRowOut(BaseModel):
    """A scorecard row."""

    id: str
    name: str
    owner: UserRef
    unit: str
    goal: GoalOut
    cells: list[CellOut]


class ScorecardOut(BaseModel):
    """The 13-week scorecard."""

    team_id: str
    current_week: date
    last_closed_week: date
    weeks: list[date]
    measurables: list[MeasurableRowOut]


class ScoreIn(Strict):
    """Set a score (last save wins unless ``expected_version`` is supplied)."""

    value: Decimal = Field(max_digits=14, decimal_places=4)
    expected_version: int | None = Field(default=None, ge=0)


class SourceOut(BaseModel):
    """Measurable and week an Issue came from."""

    measurable_id: str
    measurable_name: str
    week_start: date


# -------------------------------------------------------------------- issues


class IssueOut(BaseModel):
    """An Issue."""

    id: str
    team_id: str
    title: str
    owner: UserRef
    priority: int | None
    created_at: datetime
    solved_at: datetime | None
    resolution_note: str | None
    source: SourceOut | None
    version: int


class IssueCreateIn(Strict):
    """Create an Issue; the creator becomes its owner."""

    title: Title
    priority: int | None = Field(default=None, ge=1, le=5, strict=True)
    meeting_id: str | None = None


class IssuePatchIn(Strict):
    """Change an Issue's priority (null clears it)."""

    priority: int | None = Field(ge=1, le=5, strict=True)
    expected_version: int | None = Field(default=None, ge=0)


class IssueSolveIn(Strict):
    """Solve an Issue; a note is required."""

    note: Note
    meeting_id: str | None = None


class TodoFromIssueIn(Strict):
    """Create a To-Do linked to an Issue (due in 7 days)."""

    title: Title
    owner_id: str = Field(min_length=1, max_length=64)
    meeting_id: str | None = None


class MakeIssueOut(BaseModel):
    """Result of Make it an Issue."""

    issue: IssueOut
    created: bool


# --------------------------------------------------------------------- todos


class TodoOut(BaseModel):
    """A To-Do."""

    id: str
    team_id: str
    title: str
    owner: UserRef
    due_date: date
    done_at: datetime | None
    created_at: datetime
    source_issue_id: str | None
    source_issue_title: str | None
    overdue: bool
    created_in_meeting_id: str | None


class CompletionOut(BaseModel):
    """To-Do completion rate for a week."""

    week_start: date
    due: int
    done: int
    rate_percent: int
    meets_target: bool


class TodosOut(BaseModel):
    """To-Dos plus the last closed week's completion rate."""

    todos: list[TodoOut]
    last_closed_week: date
    completion: CompletionOut | None
    target_percent: int = 90


# --------------------------------------------------------------------- rocks


class MilestoneOut(BaseModel):
    """A Milestone."""

    id: str
    title: str
    due_date: date
    done: bool
    past_due: bool


class RockOut(BaseModel):
    """A Rock with computed status and progress."""

    id: str
    title: str
    owner: UserRef
    quarter: str
    status: RockStatusValue
    progress_percent: int
    milestones: list[MilestoneOut]


class RocksOut(BaseModel):
    """Current quarter's Rocks."""

    quarter: str
    rocks: list[RockOut]


# ------------------------------------------------------------------ meetings


class SectionOut(BaseModel):
    """Agenda section."""

    key: Literal["scorecard", "ids", "conclude"]
    title: str
    planned_seconds: int


class AttendeeOut(BaseModel):
    """Meeting attendee."""

    user: UserOut
    joined_at: datetime
    rating: int | None


class MeetingSummaryOut(BaseModel):
    """Persisted summary of an ended meeting."""

    scorecard_week: date
    measurable_status: dict[str, MeasurableStatus]
    issues_solved: list[str]
    todos_created: list[str]
    attendee_ids: list[str]
    rating: float | None


class MeetingStateOut(BaseModel):
    """Authoritative meeting state (also the payload of live updates)."""

    id: str
    team_id: str
    status: Literal["active", "ended"]
    facilitator: UserRef
    started_at: datetime
    ended_at: datetime | None
    version: int
    scorecard_week: date
    sections: list[SectionOut]
    section_index: int
    section_key: Literal["scorecard", "ids", "conclude"]
    section_started_at: datetime
    server_time: datetime
    section_elapsed_seconds: int
    section_planned_seconds: int
    overtime_seconds: int
    attendees: list[AttendeeOut]
    average_rating: float | None
    summary: MeetingSummaryOut | None


class ActiveMeetingOut(BaseModel):
    """The team's active meeting, if any."""

    meeting: MeetingStateOut | None


class MeetingListItemOut(BaseModel):
    """Meeting list row."""

    id: str
    status: Literal["active", "ended"]
    facilitator: UserRef
    started_at: datetime
    ended_at: datetime | None


class AdvanceIn(Strict):
    """Facilitator advances the agenda; ``expected_version`` rejects stale clients."""

    expected_version: int | None = Field(default=None, ge=1)


class EndIn(Strict):
    """Facilitator ends the meeting."""

    expected_version: int | None = Field(default=None, ge=1)


class RatingIn(Strict):
    """An attendee's rating."""

    rating: int = Field(ge=1, le=10, strict=True)
