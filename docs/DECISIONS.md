# Decision record (assessment section 2.8)

Longer reasoning, the 1,000-company scaling note and the locking protocol live in `ARCHITECTURE.md`.

**1. Data model.** Normalized PostgreSQL schema with the seed ids as text keys. Scores are one row per (measurable,
company-local Monday `week_start`, CHECK ISODOW = 1), so SQL never does time-zone arithmetic. An Issue links to its source
with child-side columns (`source_measurable_id`, `source_week_start`, composite FK with `team_id` so sources stay inside
the team); a To-Do links via `source_issue_id`. Chosen over a polymorphic `source` table because one source type is in
scope and the duplicate guard stays a simple index; new source types mean new nullable columns. Integrity is enforced by
the database (CHECKs, partial unique indexes, triggers: no Observer owners, ratings immutable after the meeting).
Timestamps are `timestamptz`; due dates are `date`.

**2. REST API.** Resource-oriented under `/api`, team-scoped, with `/meetings/{id}/join|advance|end|rating` verbs.
Non-CRUD commands (`solve`, `complete`, Make it an Issue) are explicit sub-resources so they validate and retry safely;
Make it an Issue returns 201 (created) or 200 (existing). One error envelope (401/403/404/409/422), strict bodies, and
the OpenAPI document generates the frontend types. Trade-off: more endpoints than a generic PATCH, in exchange for clear
authorization and semantics.

**3. Real-time transport and recovery.** Server-Sent Events for push, REST for every mutation, PostgreSQL as sole owner of
meeting state (section, attendees, ratings, timestamps, monotonic `version`, event log). WebSockets would add a custom
protocol and manual reconnect/auth for traffic that is one-directional. Each connection starts with a full authoritative
`state` event, so recovery after refresh, late join or reconnect is "reconnect and read"; clients drop stale versions and
the facilitator's actions may carry `expected_version`. Mutations `NOTIFY` in their transaction and every worker
`LISTEN`s, so no sticky sessions are needed. The timer derives from a persisted `section_started_at` on the server's
clock. Trade-off: NOTIFY carries ids only, so state is reloaded per event.

**4. Duplicate-free Make it an Issue.** Partial unique index `uq_issues_open_per_source ON issues(source_measurable_id,
source_week_start) WHERE solved_at IS NULL` plus `INSERT … ON CONFLICT DO NOTHING RETURNING id`; the loser reads the
winner's row, so both callers get the same Issue with no check-then-insert window and no held locks. Solving frees the
slot. The same pattern guards "one active meeting per team". Verified with 12 concurrent HTTP requests against Postgres.
Related: meeting-attributed To-Dos/solves take `FOR SHARE` on the meeting row and `end` takes `FOR UPDATE`, so a mutation
either lands before the summary snapshot or is rejected with 409 (see `ARCHITECTURE.md`).

**5. Immutable meeting summaries.** A persisted snapshot: when a meeting ends, the server computes statuses (last closed
week as of the meeting start), solved Issue ids, created To-Do ids, attendees and rating, and stores them as JSON on the
meeting row (`ended ⇔ summary NOT NULL`); reads never recompute, so later edits cannot rewrite history. Membership comes
from explicit FKs (`solved_in_meeting_id`, `created_in_meeting_id`) set at action time. Trade-off: a snapshot cannot be
re-derived if rules change, which is intended for history.

**Judgment calls.** Ratings are server-enforced to the Conclude section, as the brief specifies. Seeded-user login has no
passwords and the business clock is frozen (determinism over realism). Done beyond the brief: lost-update protection
(scores, Issue priority) and a meeting event log. Not done: Issues from Rocks/To-Dos, full audit trail.
