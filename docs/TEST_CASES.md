# Test cases

Each case is automated (the manual-only ones are marked). **Test data** is the seed (`seed.json`) with the business
clock frozen at `2026-11-11T15:00:00Z` unless stated. Users: `u1` Avery Admin (Leadership), `u2` Blake (Team Member,
Leadership+Sales), `u3` Casey (Team Member, Leadership), `u4` Dana (Team Member, Leadership+Operations), `u5` Ellis
(Observer, Leadership), `u7` Gray (Observer, Sales), `u8` Harper (Team Member, Operations). File prefixes:
`T` = `backend/tests/`, `E` = `frontend/e2e/`. Step lists are what the automated test performs, written so they can also
be executed by hand (Swagger UI at `http://localhost:8000/docs`, or the web app).

**Latest executed results** are at the bottom.

## Business rules (`T/test_rules.py`, no database)

| ID | Title / requirement | Steps → expected | Test |
|----|---------------------|------------------|------|
| TC-RULE-01 | Week = Monday 00:00 Chicago (R-RULE-00) | `current_week_start` of `2026-11-16T05:59:59Z` → 2026-11-09; of `…T06:00:00Z` → 2026-11-16; DST transition instants 2026-03-09T04:59Z/05:00Z and 2026-11-02T05:59Z map to the right Monday | `test_week_start_uses_company_timezone` |
| TC-RULE-02 | 13 weeks end with current week | `last_n_weeks(2026-11-11T15Z)` → 13 Mondays 2026-08-17…2026-11-09 | `test_thirteen_weeks_end_with_current_week` |
| TC-RULE-03 | Week end is DST-aware | week of Nov 2 ends 2026-11-09T06:00Z; week of Oct 19 ends 2026-10-26T05:00Z; week of Oct 26 ends 2026-11-02T06:00Z | `test_week_end_is_dst_aware` |
| TC-RULE-04 | Calendar quarter in company time | 2026-10-01T04:59Z → Q3, `05:00Z` → Q4; 2027-01-01T05:59Z → 2026-Q4, `06:00Z` → 2027-Q1 | `test_quarter_is_calendar_quarter_in_company_time` |
| TC-RULE-05 | Goal types & inclusive boundaries (R-RULE-01) | at_least 10: 10→on, 9.99→off; at_most 3.0: 3.0→on, 3.1→off; between 2–4: 2,4→on, 1.8,4.5→off; exactly 1: 1→on, 0,2→off; 0 is a real score | `test_measurable_status_goal_types_and_inclusive_boundaries` |
| TC-RULE-06 | Closed week without score | status `off_track` | `test_closed_week_without_score_is_off_track` |
| TC-RULE-07 | Current week without score | status `pending` | `test_current_week_without_score_is_pending` |
| TC-RULE-08 | Current week with score evaluated | 520 vs ≥500 → `on_track` | `test_current_week_with_score_is_evaluated_not_pending` |
| TC-RULE-09 | Invalid goal rejected | unknown goal type → ValueError | `test_invalid_goal_raises` |
| TC-RULE-10 | Overdue (R-RULE-02) | due Nov 10 open → overdue; due Nov 11 (today) → not; done late → not; Chicago-local "today" at 04:00Z vs 06:00Z | `test_overdue_rules`, `test_today_is_company_local_date` |
| TC-RULE-11 | t28 counts (R-RULE-03) | todo due 2026-11-06 done `2026-11-09T05:59Z` (Sun 23:59 CST) in week of Nov 2 → done=1 | `test_t28_done_sunday_2359_chicago_counts_in_due_week` |
| TC-RULE-12 | t29 does not count | due 2026-11-08 done `2026-11-09T06:01Z` (Mon 00:01 CST) → done=0 | `test_t29_done_monday_0001_chicago_does_not_count` |
| TC-RULE-13 | Done at the exact week end / after due date inside week / before week | 06:00Z not counted; Nov 7 counted; earlier counted | `test_done_exactly_at_week_end_instant_does_not_count`, `…inside_due_week_counts`, `…before_due_week_counts` |
| TC-RULE-14 | DST-end week boundary | week of Oct 26: done 05:30Z Nov 2 counted, 06:30Z not | `test_dst_end_week_boundary_uses_cst_offset` |
| TC-RULE-15 | Zero due → null; week membership by due date | none due → `None`; Mon & Sun due included, adjacent days excluded | `test_zero_due_returns_none`, `test_week_membership_is_by_due_date_inclusive_of_monday_and_sunday` |
| TC-RULE-16 | 90% target uses exact ratio; half-up percent | 9/10 → 90, meets; 179/200 → rate 90 but **not** met; 1/8→13, 1/16→6, 1/3→33, 2/3→67 | `test_exactly_ninety_percent_meets_target`, `test_target_compares_exact_ratio_not_rounded_percent`, `test_rate_percent_rounds_half_up` |
| TC-RULE-17 | Rock status (R-RULE-04) | complete wins; no Milestones → seeded; due today not past due; unfinished past due → off_track; done past due → ok | `test_rock_status` |
| TC-RULE-18 | Rock progress (R-RULE-05) | 1/8 → 13 (12.5), 1/3 → 33, 2/3 → 67; none & complete → 100; none → 0 | `test_rock_progress` |
| TC-RULE-19 | Issue order (R-RULE-06) | P5 oldest first, P4, P3, unprioritised last, deterministic tie-breaker | `test_issue_order_*` |
| TC-RULE-20 | Meeting rating (R-RULE-07) | [8,9,7] → 8.0; [8,9,8,8] → 8.3 (8.25); [] → null; 7.666→7.7; 9.875→9.9 | `test_average_rating`, `test_round_half_up_*` |

## Seed and rules report (`T/test_seed_report.py`)

| ID | Title | Steps → expected | Test |
|----|-------|------------------|------|
| TC-SEED-01 | Seed matches source (R-OPS-01) | after load, row counts equal `seed.json` counts and id sets equal (users, issues, todos, measurables, rocks, milestones, meetings) | `test_seed_matches_source_counts_and_ids` |
| TC-SEED-02 | Idempotent, non-destructive | edit an Issue title and a score, run seed again → 0 rows inserted, edits preserved | `test_seed_is_idempotent_and_never_overwrites_user_changes` |
| TC-SEED-03 | History linked by timestamp | `i7→mt1`, `i6→mt2`, `t20→mt1`, `t30→mt2` | `test_seed_links_issues_and_todos_to_meetings_by_timestamp` |
| TC-REP-01 | Report structure (R-REP-01) | keys `now`,`teams`; 3 teams; each team has 6 keys; every measurable × 13 weeks 2026-08-17…11-09 | `test_report_structure_and_coverage` |
| TC-REP-02 | Independent oracle (R-REP-03) | `m5` 10-19 off_track; `m1` 11-09 pending; boundary cases; `todo_completion` Nov 2 = {due 10, done 9, 90, true}; Oct 26 = {3, 2, 67, false}; null weeks; overdue `[t12, t31]`; rocks r1 33 on_track, r2 13 off_track, r3 100 complete; issue_order `[i2,i1,i5,i3,i4]` | `test_report_independent_oracle_for_trap_cases` |
| TC-REP-03 | Historical meetings | mt1 `2026-10-19`, mt2 `2026-10-26`, solved/created ids, attendees, ratings 8.0 / 8.3 | `test_report_historical_meetings` |
| TC-REP-04 | Sorting, derived values, alternative `APP_NOW` | ids sorted as strings; data edits change output; four other instants (incl. Sunday 23:59:59 vs Monday 00:00:00 Chicago, next quarter/year) → correct 13-week window and values; mt summaries unchanged | `test_report_ids_are_plain_string_sorted`, `test_report_is_derived_from_data_not_constants`, `test_report_adapts_to_other_app_now_values`, `test_report_alternative_now_changes_computed_values` |
| TC-REP-05 | Seeded summaries via API (R-MTG-09) | `GET /api/meetings/mt1/summary` and `mt2` return the stored snapshots; list shows `[mt2, mt1]` | `test_seeded_meeting_summaries_available_via_api` (`T/test_api_meetings.py`) |
| TC-REP-06 | CLI emits only JSON, deterministic, honours `APP_NOW` | run `python -m app.cli rules-report` twice → parseable JSON, identical output; `APP_NOW=2026-11-18T15:00:00Z` → last week 2026-11-16 | `test_report_cli_prints_only_json_to_stdout`, `test_report_cli_honours_app_now_env` |

## API (`T/test_api_team.py`)

| ID | Title | Steps → expected | Test |
|----|-------|------------------|------|
| TC-API-01 | Scorecard shape | `GET /api/teams/team_lead/scorecard` as u3 → 13 weeks, 5 measurables, m5/10-19 null+off_track, m1/11-09 pending, i5 surfaced as `issue_id`, goal/owner fields | `test_scorecard_shape_and_statuses` |
| TC-API-02 | Inline edit, last save wins | PUT 12 then another user PUT 4 to m1/11-09 → values 12→4, status on→off, versions 1→2 | `test_set_score_updates_status_and_last_save_wins`, `test_set_score_boundary_is_on_track` |
| TC-API-03 | Lost-update protection | PUT with `expected_version: 1` twice → 200 then 409 `stale_version` | `test_set_score_lost_update_protection` |
| TC-API-04 | Score validation | non-Monday, outside window, future week, non-numeric, missing value → 422; unknown measurable → 404 | `test_set_score_validation` |
| TC-API-05 | Make it an Issue | `POST …/measurables/m5/weeks/2026-10-19/issue` → 201, title "Cash on hand, week of Oct 19", owner = caller; repeat by another user → 200, same id | `test_make_issue_creates_then_returns_existing`, `test_make_issue_returns_seeded_unsolved_issue`, `test_make_issue_after_solving_creates_a_new_issue`, `test_make_issue_only_for_off_track_cells` |
| TC-API-07 | Issue order | `GET …/issues` → `[i2,i1,i5,i3,i4]`; a new P5 slots after older P5s | `test_issue_order_matches_rule`, `test_new_issue_slots_into_order` |
| TC-API-08 | Solved issues | `?status=solved` → `[i6,i7]` with note and `2026-11-04T15:40:00Z` | `test_solved_issues_listed_separately` |
| TC-API-09 | Create Issue | title trimmed, priority optional, owner = creator | `test_create_issue_owner_is_creator_and_priority_optional` |
| TC-API-10 | Issue validation | missing/blank title, priority 0/6/"high"/true, client-supplied `owner_id` → 422 | `test_create_issue_validation` |
| TC-API-11 | Priority | set 5, clear null, 9 → 422, `{}` → 422; stale `expected_version` → 409 | `test_set_and_clear_priority`, `test_priority_lost_update_protection` |
| TC-API-12 | Rocks | quarter 2026-Q4; r1 on_track 33% (ms2 due today not past due); r2 off_track 13%; r3 complete 100% no milestones; read-only (no write endpoints) | `test_rocks_current_quarter`, `test_rocks_are_read_only` |
| TC-API-13 | Solve needs a note | `{}`/blank → 422; valid → 200 with `solved_at` = business now; second solve → 409; leaves unsolved list | `test_solve_requires_note_and_sets_solved_time` |
| TC-API-14 | To-Do from Issue | title "Interview 3 candidates", owner u4 → 201, due `2026-11-18`, linked to i1; at 22:00 Chicago (04:00Z next UTC day) still due Nov 18 | `test_todo_from_issue_due_in_seven_days_and_linked`, `test_todo_due_date_uses_company_local_date` |
| TC-API-15 | To-Do validation | missing/blank title, missing owner, observer (u5), unknown owner, wrong-team owner (u8) → 422; unknown/other-team Issue → 404 | `test_todo_from_issue_validation`, `test_observer_cannot_own_via_todo_owner_assignment`, `test_todo_owner_must_belong_to_team` |
| TC-API-16 | To-Dos list | t12,t31 overdue, t30 (due today) not; completion {Nov 2, 10, 9, 90, meets} | `test_todos_overdue_flags_and_completion_rate` |
| TC-API-17 | Complete / undo | complete sets `done_at` (idempotent), undo clears, overdue recomputed; unknown → 404; late completion doesn't change last week's rate | `test_complete_and_undo_todo`, `test_completion_rate_is_computed_not_stored` |
| TC-API-18 | Team detail | eligible owners = {u1,u2,u3,u4} (no observer) | `test_team_detail_lists_eligible_owners` |

## Security (`T/test_api_authz.py`)

| ID | Title | Steps → expected |
|----|-------|------------------|
| TC-SEC-01 | Unauthenticated / forged cookie | requests without cookie → 401 `unauthorized`; cookie `dTE=.deadbeef` → 401 (`test_unauthenticated_requests_are_401`, `test_forged_cookie_is_rejected`) |
| TC-SEC-02 | No trust in client-provided role | login body with `role: admin` → 422; unknown user → 404 (`test_login_rejects_role_in_body`, `test_login_unknown_user_is_404`) |
| TC-SEC-03 | Admin sees all teams | u1 `/api/teams` = 3 teams; reads each scorecard (`test_admin_sees_every_team`); member sees own only (`test_member_sees_only_own_teams`) |
| TC-SEC-04 | Team member denied another team | u3 GET 7 `team_sales` endpoints → 403 `forbidden`; guessed unknown id → 403 for non-admin, 404 for admin (`test_member_denied_other_team_reads`, `test_guessed_unknown_team_id_is_refused_for_non_admin`) |
| TC-SEC-05 | Observer reads own team, all writes refused | u5 reads 5 endpoints → 200; 9 write endpoints → 403 (`test_observer_can_read_own_team`, `test_observer_write_is_refused`, `test_observer_denied_other_team_reads`) |
| TC-SEC-06 | Cross-team entity modification | u3 writes to `team_sales` → 403; u2 (both teams) using `team_lead` path with a `team_sales` entity (i8, t40, m6) → 404 (`test_member_denied_cross_team_writes`, `test_entity_from_another_team_cannot_be_modified_via_own_team_path`) |
| TC-SEC-07 | Admin may write in any team | u1 creates Issue in `team_ops`, starts meeting in `team_sales` (`test_admin_can_write_in_any_team`) |
| TC-SEC-08 | Error hygiene | 403 body has exactly `code,message,details`; no traceback (`test_error_responses_hide_internals`) |
| TC-SEC-09 | Meeting authorization | outsider u8 on a Leadership meeting: get/join/rate/advance → 403; seeded `mt1` summary → 403; unknown meeting → 404 (`test_meeting_actions_denied_across_teams`, `test_unknown_meeting_is_404_for_authenticated_users`) |

## Database constraints (`T/test_api_team.py`, `T/test_api_meetings.py`)

| ID | Title | Steps → expected |
|----|-------|------------------|
| TC-DB-01 | Invalid data rejected below the API (R-DATA-01) | raw INSERTs: observer owner, non-member owner, priority 9, solved without note, non-Monday score, cross-team source measurable, duplicate unsolved source → all `IntegrityError` (`test_db_rejects_invalid_data_even_if_app_would_not`) |
| TC-DB-02 | Single active meeting | second active meeting for the team inserted directly → rejected (`test_two_active_meetings_for_one_team_rejected_by_database`) |
| TC-DB-03 | Ratings immutable after end | UPDATE/INSERT on `mt1` ratings → rejected (`test_ratings_on_ended_meeting_are_blocked_by_the_database_too`) |

## Meetings (`T/test_api_meetings.py`)

| ID | Title | Steps → expected |
|----|-------|------------------|
| TC-MTG-01 | Start (R-MTG-01) | u3 `POST /api/teams/team_lead/meetings` → 201, facilitator u3, only attendee u3, section scorecard, week `2026-11-02`, sections 300/3600/600 (`test_start_makes_starter_facilitator_and_attendee`) |
| TC-MTG-02 | One active meeting (R-MTG-02) | second start by u2 → 409 `meeting_already_active`; other team OK; new meeting allowed after end (`test_only_one_active_meeting_per_team`, `test_new_meeting_allowed_after_previous_ended`, `test_active_meeting_endpoint`) |
| TC-MTG-04 | Observer joins read-only | u5 join → 200 attendee; advance/end/rating → 403 (`test_observer_can_join_but_not_start_or_facilitate`); join twice → same version (`test_join_is_idempotent_and_does_not_bump_version`) |
| TC-MTG-05 | Facilitator only | other member and even Admin → 403 on advance/end; facilitator advances to IDS (`test_only_facilitator_advances_and_ends`) |
| TC-MTG-06 | Stale version | `expected_version: 1` → 409 `stale_version`; current version → 200 (`test_stale_expected_version_is_rejected`) |
| TC-MTG-07 | Advance & end any time | scorecard → ids → conclude → 409 `last_section`; end from section 1 → ended (`test_advance_through_sections_and_stop_at_last`, `test_facilitator_can_end_at_any_time`) |
| TC-MTG-08 | Server timer, overtime, no auto-advance (R-MTG-05) | advance timer clock +290 s → elapsed 290, overtime 0; +75 s → 365 / 65, section still scorecard; both users see the same; advance resets to 0 (`test_timer_is_server_owned_and_overtime_does_not_auto_advance`) |
| TC-MTG-09 | Late join | joins 42 s into IDS → section `ids`, elapsed 42 (`test_late_joiner_gets_current_section_and_elapsed`) |
| TC-MTG-10 | Rating rules | In Conclude: 8 then 6 (changeable); 0, 11, -1, 5.5, "9", null, true → 422; non-attendee and Observer → 403 (`test_ratings_rules`) |
| TC-MTG-15 | Ratings only in Conclude | Scorecard and IDS → 409 `rating_not_open`, nothing stored; Conclude → 200 (`test_ratings_only_open_in_conclude`) |
| TC-MTG-12 | Rating immutable after end | PUT after end → 409; value unchanged; join after end → 409 (`test_ratings_become_immutable_after_end`) |
| TC-MTG-13 | Summary snapshot (R-MTG-09) | meeting with 3 attendees, 2 ratings (8, 9), 1 Issue solved *in meeting*, 1 outside, 1 To-Do created in meeting, 1 outside → summary lists exactly the meeting's items, rating 8.5; later score/To-Do edits don't change it (`test_summary_of_new_meeting_is_a_stable_snapshot`) |
| TC-MTG-15 | Event log | events `started, joined, advanced, ended` persisted (`test_meeting_events_are_persisted`) |

## Concurrency and real-time (`T/test_concurrency_realtime.py`, real HTTP + PostgreSQL)

| ID | Title | Steps → expected |
|----|-------|------------------|
| TC-CONC-01 | Concurrent Make it an Issue (R-CONC-01) | 12 clients (4 users) released by a barrier POST the same off-track cell → exactly one 201, all others 200, one distinct Issue id, `count(*)` of open source rows = 1; a retry → 200 same id (`test_concurrent_make_it_an_issue_creates_exactly_one_issue`) |
| TC-CONC-02 | Many rounds | 4 users × 4 different cells → one Issue per cell (`test_make_issue_is_repeatable_over_many_rounds`) |
| TC-CONC-03 | Concurrent meeting starts | 12 simultaneous starts → one 201, eleven 409 `meeting_already_active`, one active row (`test_concurrent_meeting_starts_create_one_active_meeting`) |
| TC-CONC-04 | Concurrent advance, same version | 6 requests with the same `expected_version` → one 200 and five 409; section IDS (`test_concurrent_advance_requests_with_same_version_apply_once`) |

### Meeting-summary race (`T/test_meeting_summary_race.py`, real PostgreSQL, deterministic gates)

| ID | Case | Expected |
|----|------|----------|
| TC-CONC-05 | Mutation holds the meeting lock, `end` requested | `end` is blocked on the lock (checked via `pg_stat_activity`), then succeeds; summary lists the To-Do / solved Issue (`test_mutation_holding_lock_makes_end_wait_and_summary_includes_it`, To-Do / solve / Issue) |
| TC-CONC-06 | `end` holds the lock, mutation requested | Mutation blocks, then fails 409 `meeting_ended`; no To-Do/Issue row or solve persists; stored summary empty and equal to the returned one (`test_end_holding_lock_rejects_the_mutation_with_conflict`) |
| TC-CONC-07 | Shared lock / no needless locking | A second attributed mutation validates while the first holds its lock; an unattributed solve completes while `end` holds the lock (`test_attributed_mutations_share_the_lock`, `test_unattributed_mutations_ignore_the_meeting_lock`) |
| TC-CONC-08 | HTTP after end | To-Do, solve and Issue with the ended `meeting_id` → 409 `meeting_ended`; summary unchanged (`test_http_mutations_after_end_are_409_and_leave_no_rows`) |
| TC-RT-01 | Follower sees advance < 1 s | SSE reader as u2; u3 advances → `state` with section ids within 1 s, higher version; end → ended state with summary (`test_second_browser_follows_facilitator_within_a_second`) |
| TC-RT-02 | Join & rating events | watcher sees attendee count 2, then average 7.0 (`test_join_and_rating_events_reach_other_attendees`) |
| TC-RT-03 | Data-change events | solving an Issue in the meeting → `data_changed:issues` (`test_data_changes_are_pushed_so_clients_can_refetch`) |
| TC-RT-04 | Reconnect gets current state | reader closes, two advances happen, reader reconnects → first event is section `conclude` with higher version (`test_reconnect_receives_current_authoritative_state`) |
| TC-RT-05 | Stream security | no cookie → 401; other-team user → 403 (`test_stream_requires_authentication_and_team_access`) |

## End-to-end (`E/*.spec.ts`, Playwright, two browser contexts)

| ID | Title | Steps → expected | Test |
|----|-------|------------------|------|
| TC-E2E-01 | Whole meeting in two browsers (R-E2E-01) | 1) Casey opens Leadership. 2) Start meeting → facilitator "Casey Cho (you)", status Live. 3) Blake (separate context) opens the meeting URL. 4) both show section Scorecard and 2 attendees. 5) Casey clicks "Next: IDS" → 6) Blake's section becomes IDS without reload. 7) timers differ ≤ 2 s. 8) Blake reloads → still IDS, timer running. 9) Blake offline; Casey → Conclude; Blake still IDS; back online → Conclude, Live. Ratings 8 and 9 → both show average 8.5. 10) Casey ends (confirm dialog). 11) both show "Ended" + summary (rating 8.5, "Scorecard — week of Nov 2", "Cash on hand"); rating buttons gone | `meeting-sync.spec.ts › two browsers stay in sync…` |
| TC-E2E-04 | Observer & outsider | Ellis (Observer) joins: "You're observing", no edit/Make-it-an-Issue buttons; Finley (Sales only) sees "This meeting is not available to you" | `meeting-sync.spec.ts › observer joins read-only…` |
| TC-E2E-02 | Team page journey | scorecard has 14 column headers; m5/10-19 "Off track"; m1/11-09 "Pending"; edit to 10 → "On track"; Make it an Issue creates one Issue owned by Casey, second click says "Issue already open"; Issue order matches rule; solving needs a note, solved tab shows it; Add To-Do (owner list excludes Ellis) → due Nov 18, linked to the Issue; mark done/undo; completion 90% "Meets 90% target"; t12 Overdue, t30 not; r2 Off track 13%, r3 100%; r1 expands, no "Past due" | `team-page.spec.ts › team member reviews…` |
| TC-E2E-03 | Read-only, team switcher, redirect | Observer: no write controls, switcher = ["Leadership"], `/teams/team_ops` shows "You don't have access to this team"; Admin switcher = 3 teams; anonymous → `/login`, sign in as Casey | `team-page.spec.ts › observer sees…`, `› admin sees…` |
| TC-E2E-05 | Accessibility | axe-core (WCAG 2 A/AA): no serious/critical violations on team page and login | `team-page.spec.ts › no serious accessibility violations…` |

## Manual / operational

| ID | Title | Steps → expected |
|----|-------|------------------|
| TC-OPS-01 | Fresh start (R-OPS-01) | `docker compose down -v && docker compose up --build -d --wait` → db, init (exits 0), backend, frontend healthy; `http://localhost:3000/login` lists 9 users; `http://localhost:8000/docs` loads. **Executed manually during development: passed.** |
| TC-OPS-02 | Rules report from a fresh DB (R-REP-02) | after TC-OPS-01 (no data added): `docker compose run --rm -T backend python -m app.cli rules-report > rules_report.json` → valid JSON, 3 teams, 13 weeks. **Executed: passed; this is the committed file.** |

## Latest executed results

See the "Test results" section of the final handover in the README / PR description and `docs/TEST_RESULTS.md`
(written by the verification run).
