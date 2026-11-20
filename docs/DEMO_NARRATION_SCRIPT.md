# Narration script (≈ 6 min, read while `pnpm demo` runs)

> This script is for the fully automatic `pnpm demo`. For scene-by-scene control (`pnpm demo:scene <id>`), with
> what to say during and after each scene, use [DEMO_MANUAL_RECORDING_SCRIPT.md](DEMO_MANUAL_RECORDING_SCRIPT.md).

Timestamps are offsets from the start of scene 1, taken from a measured full run (total 06:05; see
[DEMO_RECORDING_GUIDE.md](DEMO_RECORDING_GUIDE.md)). Run-to-run variation is a few seconds, so treat them as cues, not
exact marks. The same cues are printed in the terminal as each scene starts (`frontend/demo/demo-config.ts`).
Read at a relaxed pace: about 130 words per scene-minute.

## 0:00 — Introduction (≈ 26 s)
"This is the Level 10 meetings app I built for the assessment. Everything you'll see is driven by a Playwright script
against the real application: real browsers, real API, real PostgreSQL, no mocks. I'm signed in as Casey Cho, a Team
Member of the Leadership team. The Team Page has the five modules: the Level 10 Meeting launcher, the Scorecard, Issues,
To-Dos and Rocks."

## 0:26 — Scorecard (≈ 53 s)
"The Scorecard shows thirteen weeks of history. Statuses are computed on the server from the data and a frozen business
clock, so they're deterministic, and they're shown as text, not only colour. A closed week with no score is off track;
a score missing in the current week is only pending. I'll enter ten for a goal of at least ten: the threshold is
inclusive, so it turns on track. Now 'Make it an Issue' on this off-track score. It creates one Issue, linked to the
measurable. Clicking again says an Issue is already open, because a database constraint prevents duplicates."

## 1:19 — Issues and To-Dos (≈ 52 s)
"Issues are ordered by priority, highest first, oldest first within a priority, and unprioritised ones last. I can
change a priority. Now I add a To-Do to this Issue: it's linked to the Issue, due in seven days, and the owner list
never includes Observers, who are read-only. I complete the overdue To-Do. Finally I solve the new Issue. A resolution
note is required, and it's kept with the solved Issue."

## 2:11 — Rocks (≈ 25 s)
"Rocks for the current quarter. Status and progress come from the Milestones and the clock, not from stored fields:
this one is off track at thirteen percent, this one is complete. Opening a Rock shows its Milestones."

## 2:36 — Two-browser meeting (≈ 53 s)
"Now the core requirement. I'm splitting the screen: browser A on the left, browser B on the right. They are two
separate browser processes with separate cookies, signed in as two different seeded users. In A, Casey starts a Level 10
meeting and becomes the facilitator. The meeting starts in the Scorecard section and the timer is running. In B, Blake
Brooks opens the same team, sees a meeting in progress and joins. Both show the same section, the same facilitator and
two attendees. Starting a second meeting for the team is blocked by a database-level unique index."

## 3:29 — Live synchronization (≈ 52 s)
"Blake has no facilitator controls: no next button and no end button, and the server enforces that too, not just the
UI. Casey moves the agenda to IDS. Browser B follows by itself, with no refresh. The script even checks that the page was
never reloaded. Updates arrive over Server-Sent Events, fed by PostgreSQL LISTEN/NOTIFY, so it works across multiple API
processes. The timer is owned by the server, so both show the same time. Another change: Blake solves an Issue, and it
disappears from Casey's list. Casey adds a follow-up To-Do and it appears in Blake's view."

## 4:21 — Reconnection (≈ 28 s)
"Reliability. I refresh Blake's browser: the section and the timer come back from the server. Now Blake goes offline;
the connection indicator changes, and Casey moves on to Conclude. Blake still shows IDS, because he missed it. When
connectivity returns, the stream reconnects, starts from the full authoritative state, and Blake is on Conclude."

## 4:49 — Ratings and summary (≈ 43 s)
"Ratings are only possible in Conclude. Casey rates eight, Blake rates nine, and both screens show an average of eight
point five. Casey ends the meeting. Everyone sees the summary: the average rating, the Issue solved, the To-Do created,
the attendees and the scorecard snapshot. Ratings are now final. This summary is an immutable snapshot stored in the
database, so later changes to Issues or scores never rewrite history. Reloading both browsers shows it unchanged."

## 5:32 — Architecture (≈ 33 s)
"Engineering quality. PostgreSQL holds the data, with constraints and partial unique indexes guarding concurrency. The API
is FastAPI over REST; the frontend is Next.js with TypeScript, with types generated from the OpenAPI schema. The rules are
pure, deterministic functions, with a rules report you can diff. The backend has 204 passing tests including concurrency
and real-time tests, the Playwright suite exercises two browsers, and CI is green on GitHub Actions. The slide on screen
is built from the repository's own results files. Thank you."
