# Requirements analysis and traceability

Sources: `assessment-brief.docx` (primary spec, extracted in full including the section 2.2 diagram description and
tables) and the starter `README.md` (rules-report format). The starter README refers to `assessment-brief.pdf`; the
real file is `assessment-brief.docx` (corrected in the project README).

Evaluation weights: data model & API 20% · real-time, concurrency & rules 20% · usability 15% · security 15% ·
testing 15% · frontend quality 10% · docs & video 5%. Mandatory items were built and verified before bonus items.

Status values: **Tested** = implemented and covered by an automated test that was executed (results in
`TEST_CASES.md`); **Implemented** = implemented, not automatically tested; **Blocked**; **Open**.

## Easily overlooked requirements

| # | Trap | Where handled |
|---|------|---------------|
| 1 | `m5` has **no score** for week `2026-10-19` → closed-week missing score is `off_track`, current-week missing is `pending` | `rules.measurable_status`; R-RULE-01 |
| 2 | `t28` (Sun 23:59 Chicago) counts, `t29` (Mon 00:01 Chicago) does not; week end is DST-aware (DST ended 2026-11-01) | `rules.week_end_exclusive`; R-RULE-03 |
| 3 | `meets_target` uses the exact ratio (179/200 = 89.5% rounds to 90 but does **not** meet 90%) | `rules.todo_completion`; R-RULE-03 |
| 4 | Milestone/To-Do due **today** is not past due / overdue; "today" is the company-local date of `APP_NOW` | `rules.is_overdue`, `rock_status` |
| 5 | `r3` is complete with no Milestones → 100%; `r2` has an unfinished Milestone due Nov 10 → off track; `ms2` due Nov 11 is not past due | R-RULE-05/06 |
| 6 | Round **half up** (12.5→13, 8.25→8.3), never banker's rounding | `rules.round_half_up*` |
| 7 | Seeded meetings `mt1`, `mt2` must have summaries; their `scorecard_week` is relative to the meeting date, not `APP_NOW` | `seed.py`, `summary.py`; R-MTG-09 |
| 8 | Report must work at other `APP_NOW` values; no seed-specific constants | R-REP-03 |
| 9 | Issues without priority sort last; ties by oldest `created_at` | `rules.issue_sort_key` |
| 10 | Make it an Issue must be duplicate-free under concurrency (DB-level) | partial unique index; R-CONC-01 |
| 11 | Observer cannot own anything — enforced by DB trigger, API and UI | R-SEC-05 |
| 12 | Server owns the timer; overrun is displayed but **never auto-advances** | R-MTG-05 |
| 13 | `docker compose up` must self-initialise (migrations + idempotent seed), no sleeps | R-OPS-01 |
| 14 | Facilitator reconnect and late joins get current state (SSE sends full state on every connect) | R-MTG-07 |

## Traceability matrix

Test IDs refer to `TEST_CASES.md`. Files: `backend/tests/*` (pytest) and `frontend/e2e/*` (Playwright).

### Business rules (spec 2.6)

| ID | Source | Requirement | Pri | Implementation | Acceptance criteria | Tests | Status |
|----|--------|-------------|-----|----------------|---------------------|-------|--------|
| R-RULE-00 | 2.6 Time | Weeks Mon 00:00–Sun 23:59:59 America/Chicago; calendar quarters; DST-safe | Critical | `rules.py` (`current_week_start`, `week_end_exclusive`, `quarter_of`) | Boundary instants map to the expected week/quarter across DST changes | TC-RULE-01..04 | Tested |
| R-RULE-01 | 2.6 Measurable status | at_least / at_most / between / exactly, inclusive; closed week no score = off_track; current no score = pending | Critical | `rules.measurable_status`, `Goal.met_by` | Every goal type, both boundaries, missing score both ways | TC-RULE-05..09 | Tested |
| R-RULE-02 | 2.6 Time | Overdue = not done and due < today (company-local) | Critical | `rules.is_overdue` | due today not overdue; done late not overdue | TC-RULE-10 | Tested |
| R-RULE-03 | 2.6 To-Do completion | done-by-end-of-due-week ÷ due; target 90% exact ratio; none due → null; late completion not counted | Critical | `rules.todo_completion` | t28 counted, t29 not, 9/10 meets, 179/200 does not meet, null for none | TC-RULE-11..16 | Tested |
| R-RULE-04 | 2.6 Rock status | complete / off_track (seeded or past-due unfinished Milestone) / on_track; due today not past due | Critical | `rules.rock_status` | r1 on_track, r2 off_track, r3 complete | TC-RULE-17, TC-API-12 | Tested |
| R-RULE-05 | 2.6 Rock progress | completed ÷ total, half-up whole percent; no Milestones 0%/100% when complete | Critical | `rules.rock_progress` | r2 = 13%, r3 = 100% | TC-RULE-18, TC-API-12 | Tested |
| R-RULE-06 | 2.6 Issue order | priority 5→1, oldest first, unprioritised last | Critical | `rules.issue_sort_key` | i2,i1,i5,i3,i4 | TC-RULE-19, TC-API-07 | Tested |
| R-RULE-07 | 2.6 Meeting rating | mean of submitted ratings, 1 dp half-up; none → null | Critical | `rules.average_rating` | 8.25 → 8.3; [] → null | TC-RULE-20 | Tested |
| R-CONC-01 | 2.6 No duplicate Issues | Make it an Issue returns the existing unsolved Issue, also under concurrent clicks | Critical | partial unique index `uq_issues_open_per_source` + `INSERT … ON CONFLICT DO NOTHING` (`mutations.make_issue`) | 12 simultaneous requests → one Issue, same id for all | TC-CONC-01..02 | Tested |

### Team page (spec 2.5)

| ID | Source | Requirement | Pri | Implementation | Acceptance criteria | Tests | Status |
|----|--------|-------------|-----|----------------|---------------------|-------|--------|
| R-TEAM-01 | Team page | Team switcher lists user's teams (all for Admin); inaccessible team (even by id) errors | Critical | `routes/identity.py`, `auth.require_team_read`, `AppShell` | 403 for foreign/unknown team; UI explains | TC-SEC-03, TC-SEC-04, TC-E2E-03 | Tested |
| R-TEAM-02 | Scorecard | 13 weeks incl. current; score + status per cell; names/owners/goals/units | Critical | `team_reads.scorecard`, `Scorecard` | weeks 08-17 … 11-09; statuses per cell | TC-API-01, TC-E2E-02 | Tested |
| R-TEAM-03 | Scorecard | Inline edit, last save wins (+ optional lost-update protection) | Critical | `mutations.set_score`, `ScoreCell` | PUT overwrites; stale `expected_version` → 409 | TC-API-02, TC-API-03, TC-E2E-02 | Tested |
| R-TEAM-04 | Scorecard | Make it an Issue on off-track cell: title "Measurable, week of …", owner = clicker, or existing unsolved | Critical | `mutations.make_issue` | 201 first, 200 afterwards, same Issue | TC-API-04, TC-API-05, TC-E2E-02 | Tested |
| R-TEAM-05 | Issues | Unsolved in Issue order with title, owner, priority, created, source; solved viewable separately with time + note | Critical | `team_reads.issues`, `IssuesPanel` | ordering + fields | TC-API-07, TC-API-08, TC-E2E-02 | Tested |
| R-TEAM-06 | Issues | Create (title required, priority optional, owner = creator) | Critical | `mutations.create_issue` | validation 422s | TC-API-09, TC-API-10 | Tested |
| R-TEAM-07 | Issues | Set priority 1–5 / clear | High | `mutations.set_issue_priority` | invalid 0/6/"high"/true → 422 | TC-API-11 | Tested |
| R-TEAM-08 | Issues | Solve with required note | Critical | `mutations.solve_issue` | blank note → 422; solved time stored | TC-API-13, TC-E2E-02 | Tested |
| R-TEAM-09 | Issues | Add To-Do: title, owner among team's Admins/Team Members, due +7 calendar days (company date), linked | Critical | `mutations.create_todo_from_issue` | due 2026-11-18; observer/non-member owner → 422 | TC-API-14, TC-API-15, TC-E2E-02 | Tested |
| R-TEAM-10 | To-Dos | Title, owner, due, done time, source Issue; overdue flag; last closed week completion rate | Critical | `team_reads.todos`, `TodosPanel` | t12/t31 overdue, t30 not; 90% meets | TC-API-16, TC-E2E-02 | Tested |
| R-TEAM-11 | To-Dos | Mark done / undo | Critical | `mutations.set_todo_done` | idempotent; overdue recomputed | TC-API-17, TC-E2E-02 | Tested |
| R-TEAM-12 | Rocks | Current quarter Rocks: owner, computed status, progress; expandable Milestones; read-only | Critical | `team_reads.rocks`, `RocksPanel` | r1..r5 values; no write endpoints | TC-API-12, TC-E2E-02 | Tested |
| R-TEAM-13 | 2.5 | Scorecard and Issues built once, reused on Team and Meeting pages | High | `Scorecard`, `IssuesPanel` components | same components in both pages | TC-E2E-01 | Tested |

### Meeting page (spec 2.5)

| ID | Source | Requirement | Pri | Implementation | Acceptance criteria | Tests | Status |
|----|--------|-------------|-----|----------------|---------------------|-------|--------|
| R-MTG-01 | Control | Admin/Team Member starts meeting and becomes facilitator | Critical | `meetings.start` | starter = facilitator + attendee | TC-MTG-01 | Tested |
| R-MTG-02 | Control | One active meeting per team (DB-enforced, concurrency-safe) | Critical | partial unique index `uq_meetings_one_active_per_team` | 12 concurrent starts → 1×201, rest 409 | TC-MTG-02, TC-CONC-03, TC-DB-02 | Tested |
| R-MTG-03 | Control | Anyone who can read the team may join (Observers too) | Critical | `meetings.join` | observer joins; other-team user 403 | TC-MTG-04, TC-SEC-09, TC-E2E-04 | Tested |
| R-MTG-04 | Control | Only facilitator advances/ends, at any time; no handoff | Critical | `meetings.advance/end` | non-facilitator (even Admin) 403; end from section 1 OK | TC-MTG-05..07 | Tested |
| R-MTG-05 | Sync | Server-owned timer; overrun shown, never auto-advance | Critical | `meetings.state` (elapsed from DB timestamps), `useSectionClock` | 365 s in 300 s section → overtime 65, still section 1 | TC-MTG-08 | Tested |
| R-MTG-06 | Sync | Changes reach all attendees within ~1 s | Critical | SSE + LISTEN/NOTIFY (`realtime.py`) | event < 1 s | TC-RT-01, TC-E2E-01 | Tested |
| R-MTG-07 | Sync | Late joins, refreshes, reconnects (facilitator included) get current state | Critical | SSE sends full state on every connect; version ordering | reconnect snapshot = current section | TC-RT-04, TC-MTG-09, TC-E2E-01 | Tested |
| R-MTG-08 | Rating | Attending Admin/Team Member rates 1–10 in Conclude only (409 earlier), changeable until end, immutable after; Observers cannot | Critical | `meetings.rate`, trigger `trg_ratings_guard` | 0/11/5.5/"9"/true → 422; after end 409; DB blocks too | TC-MTG-10..12, TC-DB-03 | Tested |
| R-MTG-09 | Summary | Ended meeting summary: last closed week statuses, Issues solved, To-Dos created, attendees, rating; includes seeded mt1/mt2 | Critical | `summary.build_summary`, persisted JSON snapshot | snapshot values; unchanged after edits | TC-MTG-13, TC-MTG-14, TC-REP-05 | Tested |
| R-MTG-10 | Layout | Agenda (5/60/10), current section, timer, attendees; Conclude shows new To-Dos + ratings | High | `MeetingView` | agenda marks current step | TC-E2E-01 | Tested |
| R-MTG-11 | Sync | Stale updates cannot override valid transitions | High | `version` + `expected_version` | double-advance with same version applies once | TC-CONC-04, TC-MTG-06 | Tested |

### Security, data, operations, deliverables

| ID | Source | Requirement | Pri | Implementation | Acceptance criteria | Tests | Status |
|----|--------|-------------|-----|----------------|---------------------|-------|--------|
| R-SEC-01 | 2.4/2.7 | Roles enforced on the server (not hidden buttons); roles/teams loaded from DB, never from the request | Critical | `auth.py` | forged cookie 401; `role` in body 422 | TC-SEC-01, TC-SEC-02 | Tested |
| R-SEC-02 | 2.5 | Team Member reading another team's data is refused (incl. guessed ids) | Critical | `require_team_read` | 403 on 7 read endpoints | TC-SEC-03, TC-SEC-04 | Tested |
| R-SEC-03 | 2.4 | Observer writes refused (scores, issues, todos, meetings) | Critical | `require_team_write` | 403 on 9 write endpoints | TC-SEC-05 | Tested |
| R-SEC-04 | 2.4 | Cross-team entity modification refused even for members of both teams | Critical | `_load_issue` etc. filter by team | 404 for entity from other team | TC-SEC-06 | Tested |
| R-SEC-05 | 2.4/2.7 | Observers own nothing (DB trigger + API) | Critical | `assert_eligible_owner` trigger | observer/non-member owner rejected | TC-SEC-07, TC-DB-01 | Tested |
| R-SEC-06 | 2.7 | Inputs validated at the API; consistent error envelope; no stack traces | High | Pydantic `extra=forbid`, `errors.py` | 422/409/403 envelopes | TC-API-10, TC-SEC-08 | Tested |
| R-DATA-01 | 2.7 | DB constraints reject invalid data (CHECK, FK, partial unique, triggers) | Critical | `migrations/versions/0001_initial.py` | raw invalid INSERTs rejected | TC-DB-01..03 | Tested |
| R-DATA-02 | 2.7 | Timestamps in UTC; `APP_NOW` (default 2026-11-11T15:00:00Z), no system-clock business logic | Critical | `clock.py`, `config.py` | frozen clock in all tests | TC-RULE-01, TC-API-13 | Tested |
| R-OPS-01 | 2.7 | `docker compose up` starts everything with seed data; seed is safe to rerun | Critical | `docker-compose.yml`, `seed.py` | fresh volume → healthy stack, seeded; rerun inserts 0 | TC-SEED-01, TC-SEED-02, manual TC-OPS-01 | Tested |
| R-API-01 | 2.7 | Documented REST API serves everything in 2.5 | Critical | FastAPI OpenAPI at `/docs` | typed client generated from it | build + TC-API-* | Tested |
| R-REP-01 | Part 3 | One documented command prints every computed value as JSON in the README format | Critical | `python -m app.cli rules-report` | valid JSON on stdout only | TC-REP-01, TC-REP-06 | Tested |
| R-REP-02 | Part 3 | `rules_report.json` committed, from a freshly seeded DB | Critical | repo root | generated via Docker on fresh volume | manual TC-OPS-02 | Tested |
| R-REP-03 | Part 3 | Works at other dates; every value computed | Critical | `services/report.py` | 4 alternative `APP_NOW` values | TC-REP-02..04 | Tested |
| R-TEST-01 | Part 3 | Unattended single test command, fixed clock & seed; fixture/clock note; one failure artifact | Critical | `pixi run test`, `docs/TEST_STRATEGY.md`, `docs/artifacts/` | see strategy | — | Tested |
| R-E2E-01 | Part 3 | One Playwright test, two browsers: facilitator advances, second follows | Critical | `frontend/e2e/meeting-sync.spec.ts` | passes | TC-E2E-01 | Tested |
| R-DOC-01 | Part 3 | README ≤ 2 pages, decision record ≈ 1 page, walkthrough | High | `README.md`, `docs/DECISIONS.md`, `docs/DEMO_SCRIPT.md` | present | n/a (docs) | Implemented |
| R-DOC-02 | Part 3 | Video ≤ 7 min | High | **Not recorded** — script in `docs/DEMO_SCRIPT.md` | — | — | Open (needs the author to record) |
| R-BONUS-01 | Part 3 | Lost-update protection for scores and Issue priority | Medium | `expected_version` on score PUT / issue PATCH | stale version → 409 | TC-API-03, TC-API-11 | Tested |
| R-BONUS-02 | Part 3 | Audit trail | Medium | `meeting_events` log for meetings only | — | TC-MTG-15 | Partial (meetings only) |
| R-BONUS-03 | Part 3 | Make it an Issue from Rock / overdue To-Do; 1,000-company note | Medium | — | — | — | Not implemented (see `DECISIONS.md` scaling note) |

## Ambiguities and the calls made

1. **Who may own items?** "Owner from the team's Admins and Team Members": Admins act as members of every team, so an
   Admin may own items in any team; Team Members only in teams they belong to; Observers never (DB trigger).
2. **Ratings only in Conclude?** Yes - the brief says "Rating: in Conclude". The API enforces it: an attending Admin/Team
   Member may rate (and change the rating) only while the meeting is active and in the Conclude section; earlier sections
   get 409 `rating_not_open`, Observers/non-attendees 403, an ended meeting 409, invalid values 422.
3. **`rules_report.rocks`** contains all of a team's Rocks (the seed has only Q4 Rocks); the Team page shows only the
   current quarter's.
4. **Time zone of "now" for meetings:** the *business* clock is the frozen `APP_NOW`; meeting timers use real UTC
   because a frozen clock cannot measure elapsed time (see `ARCHITECTURE.md`).
5. **Historical meeting statuses** are evaluated as of the meeting's own start (a week that was closed then is closed
   in its summary), stored as a snapshot.
