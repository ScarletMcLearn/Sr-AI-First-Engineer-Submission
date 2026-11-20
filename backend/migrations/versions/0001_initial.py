"""Initial schema: entities, integrity constraints, concurrency guards."""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

UPGRADE_SQL = """
CREATE TABLE companies (
    id text PRIMARY KEY,
    name text NOT NULL CHECK (btrim(name) <> ''),
    timezone text NOT NULL
);

CREATE TABLE users (
    id text PRIMARY KEY,
    company_id text NOT NULL REFERENCES companies (id),
    name text NOT NULL CHECK (btrim(name) <> ''),
    email text NOT NULL UNIQUE,
    role text NOT NULL CHECK (role IN ('admin', 'team_member', 'observer'))
);

CREATE TABLE teams (
    id text PRIMARY KEY,
    company_id text NOT NULL REFERENCES companies (id),
    name text NOT NULL CHECK (btrim(name) <> ''),
    UNIQUE (company_id, name)
);

CREATE TABLE team_memberships (
    user_id text NOT NULL REFERENCES users (id),
    team_id text NOT NULL REFERENCES teams (id),
    PRIMARY KEY (user_id, team_id)
);
CREATE INDEX ix_team_memberships_team ON team_memberships (team_id);

CREATE TABLE measurables (
    id text PRIMARY KEY,
    team_id text NOT NULL REFERENCES teams (id),
    name text NOT NULL CHECK (btrim(name) <> ''),
    owner_id text NOT NULL REFERENCES users (id),
    unit text NOT NULL,
    goal_type text NOT NULL CHECK (goal_type IN ('at_least', 'at_most', 'between', 'exactly')),
    goal_value numeric,
    goal_min numeric,
    goal_max numeric,
    position integer NOT NULL DEFAULT 0,
    UNIQUE (id, team_id),
    CHECK (
        (goal_type IN ('at_least', 'at_most', 'exactly')
            AND goal_value IS NOT NULL AND goal_min IS NULL AND goal_max IS NULL)
        OR (goal_type = 'between'
            AND goal_value IS NULL AND goal_min IS NOT NULL AND goal_max IS NOT NULL
            AND goal_min <= goal_max)
    )
);
CREATE INDEX ix_measurables_team ON measurables (team_id);

CREATE TABLE scores (
    measurable_id text NOT NULL REFERENCES measurables (id),
    week_start date NOT NULL CHECK (EXTRACT(ISODOW FROM week_start) = 1),
    value numeric NOT NULL,
    version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
    updated_at timestamptz,
    updated_by text REFERENCES users (id),
    PRIMARY KEY (measurable_id, week_start)
);

CREATE TABLE rocks (
    id text PRIMARY KEY,
    team_id text NOT NULL REFERENCES teams (id),
    title text NOT NULL CHECK (btrim(title) <> ''),
    owner_id text NOT NULL REFERENCES users (id),
    quarter text NOT NULL CHECK (quarter ~ '^[0-9]{4}-Q[1-4]$'),
    status text NOT NULL CHECK (status IN ('on_track', 'off_track', 'complete'))
);
CREATE INDEX ix_rocks_team_quarter ON rocks (team_id, quarter);

CREATE TABLE milestones (
    id text PRIMARY KEY,
    rock_id text NOT NULL REFERENCES rocks (id) ON DELETE CASCADE,
    title text NOT NULL CHECK (btrim(title) <> ''),
    due_date date NOT NULL,
    done boolean NOT NULL DEFAULT false,
    position integer NOT NULL DEFAULT 0
);
CREATE INDEX ix_milestones_rock ON milestones (rock_id);

CREATE TABLE meetings (
    id text PRIMARY KEY,
    team_id text NOT NULL REFERENCES teams (id),
    facilitator_id text NOT NULL REFERENCES users (id),
    status text NOT NULL CHECK (status IN ('active', 'ended')),
    started_at timestamptz NOT NULL,
    ended_at timestamptz,
    section_index smallint NOT NULL DEFAULT 0 CHECK (section_index BETWEEN 0 AND 2),
    section_started_at timestamptz NOT NULL,
    version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
    scorecard_week date NOT NULL CHECK (EXTRACT(ISODOW FROM scorecard_week) = 1),
    summary jsonb,
    CHECK ((status = 'ended') = (ended_at IS NOT NULL AND summary IS NOT NULL)),
    CHECK (ended_at IS NULL OR ended_at >= started_at)
);
-- Database-level guarantee: at most one active meeting per team, even under concurrent starts.
CREATE UNIQUE INDEX uq_meetings_one_active_per_team ON meetings (team_id) WHERE status = 'active';
CREATE INDEX ix_meetings_team_started ON meetings (team_id, started_at DESC);

CREATE TABLE meeting_attendees (
    meeting_id text NOT NULL REFERENCES meetings (id) ON DELETE CASCADE,
    user_id text NOT NULL REFERENCES users (id),
    joined_at timestamptz NOT NULL,
    PRIMARY KEY (meeting_id, user_id)
);

CREATE TABLE meeting_ratings (
    meeting_id text NOT NULL,
    user_id text NOT NULL,
    rating smallint NOT NULL CHECK (rating BETWEEN 1 AND 10),
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (meeting_id, user_id),
    FOREIGN KEY (meeting_id, user_id) REFERENCES meeting_attendees (meeting_id, user_id) ON DELETE CASCADE
);

CREATE TABLE meeting_events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    meeting_id text NOT NULL REFERENCES meetings (id) ON DELETE CASCADE,
    type text NOT NULL,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL
);
CREATE INDEX ix_meeting_events_meeting ON meeting_events (meeting_id, id);

CREATE TABLE issues (
    id text PRIMARY KEY,
    team_id text NOT NULL REFERENCES teams (id),
    title text NOT NULL CHECK (btrim(title) <> ''),
    owner_id text NOT NULL REFERENCES users (id),
    priority smallint CHECK (priority BETWEEN 1 AND 5),
    created_at timestamptz NOT NULL,
    solved_at timestamptz,
    resolution_note text,
    source_measurable_id text,
    source_week_start date CHECK (EXTRACT(ISODOW FROM source_week_start) = 1),
    solved_in_meeting_id text REFERENCES meetings (id),
    seq bigint GENERATED ALWAYS AS IDENTITY,
    version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
    UNIQUE (id, team_id),
    FOREIGN KEY (source_measurable_id, team_id) REFERENCES measurables (id, team_id),
    CHECK ((source_measurable_id IS NULL) = (source_week_start IS NULL)),
    CHECK ((solved_at IS NULL) = (resolution_note IS NULL)),
    CHECK (resolution_note IS NULL OR btrim(resolution_note) <> ''),
    CHECK (solved_at IS NULL OR solved_at >= created_at),
    CHECK (solved_in_meeting_id IS NULL OR solved_at IS NOT NULL)
);
-- Duplicate prevention for "Make it an Issue": one UNSOLVED issue per measurable+week.
CREATE UNIQUE INDEX uq_issues_open_per_source
    ON issues (source_measurable_id, source_week_start)
    WHERE solved_at IS NULL AND source_measurable_id IS NOT NULL;
CREATE INDEX ix_issues_team_open ON issues (team_id) WHERE solved_at IS NULL;
CREATE INDEX ix_issues_team_solved ON issues (team_id, solved_at DESC) WHERE solved_at IS NOT NULL;

CREATE TABLE todos (
    id text PRIMARY KEY,
    team_id text NOT NULL REFERENCES teams (id),
    title text NOT NULL CHECK (btrim(title) <> ''),
    owner_id text NOT NULL REFERENCES users (id),
    due_date date NOT NULL,
    done_at timestamptz,
    source_issue_id text,
    created_at timestamptz NOT NULL,
    created_in_meeting_id text REFERENCES meetings (id),
    seq bigint GENERATED ALWAYS AS IDENTITY,
    FOREIGN KEY (source_issue_id, team_id) REFERENCES issues (id, team_id)
);
CREATE INDEX ix_todos_team_due ON todos (team_id, due_date);
CREATE INDEX ix_todos_source_issue ON todos (source_issue_id);

-- Owners must be Admins or Team Members (never Observers); Team Members must belong to the team.
CREATE FUNCTION assert_eligible_owner() RETURNS trigger AS $$
DECLARE
    owner_role text;
BEGIN
    SELECT role INTO owner_role FROM users WHERE id = NEW.owner_id;
    IF owner_role IS NULL OR owner_role = 'observer' THEN
        RAISE EXCEPTION 'user % cannot own items (observer or unknown)', NEW.owner_id
            USING ERRCODE = 'check_violation';
    END IF;
    IF owner_role <> 'admin' AND NOT EXISTS (
        SELECT 1 FROM team_memberships WHERE user_id = NEW.owner_id AND team_id = NEW.team_id
    ) THEN
        RAISE EXCEPTION 'user % is not a member of team %', NEW.owner_id, NEW.team_id
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_measurables_owner BEFORE INSERT OR UPDATE OF owner_id, team_id ON measurables
    FOR EACH ROW EXECUTE FUNCTION assert_eligible_owner();
CREATE TRIGGER trg_rocks_owner BEFORE INSERT OR UPDATE OF owner_id, team_id ON rocks
    FOR EACH ROW EXECUTE FUNCTION assert_eligible_owner();
CREATE TRIGGER trg_issues_owner BEFORE INSERT OR UPDATE OF owner_id, team_id ON issues
    FOR EACH ROW EXECUTE FUNCTION assert_eligible_owner();
CREATE TRIGGER trg_todos_owner BEFORE INSERT OR UPDATE OF owner_id, team_id ON todos
    FOR EACH ROW EXECUTE FUNCTION assert_eligible_owner();

-- Ratings: observers cannot rate; ratings are immutable once the meeting has ended.
-- Seed loading (only) sets the transaction-local flag app.seeding to import historical ratings.
CREATE FUNCTION assert_rating_allowed() RETURNS trigger AS $$
DECLARE
    rater_role text;
    meeting_status text;
BEGIN
    IF current_setting('app.seeding', true) = 'on' THEN
        RETURN COALESCE(NEW, OLD);
    END IF;
    IF TG_OP = 'DELETE' THEN
        SELECT status INTO meeting_status FROM meetings WHERE id = OLD.meeting_id;
    ELSE
        SELECT status INTO meeting_status FROM meetings WHERE id = NEW.meeting_id;
        SELECT role INTO rater_role FROM users WHERE id = NEW.user_id;
        IF rater_role = 'observer' THEN
            RAISE EXCEPTION 'observers cannot rate meetings' USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    IF meeting_status IS DISTINCT FROM 'active' THEN
        RAISE EXCEPTION 'ratings are immutable once the meeting has ended' USING ERRCODE = 'check_violation';
    END IF;
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_ratings_guard BEFORE INSERT OR UPDATE OR DELETE ON meeting_ratings
    FOR EACH ROW EXECUTE FUNCTION assert_rating_allowed();
"""

DOWNGRADE_SQL = """
DROP TABLE IF EXISTS meeting_events, meeting_ratings, meeting_attendees, todos, issues, meetings,
    milestones, rocks, scores, measurables, team_memberships, teams, users, companies CASCADE;
DROP FUNCTION IF EXISTS assert_rating_allowed();
DROP FUNCTION IF EXISTS assert_eligible_owner();
"""


def upgrade() -> None:
    """Create the schema."""
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    """Drop the schema."""
    op.execute(DOWNGRADE_SQL)
