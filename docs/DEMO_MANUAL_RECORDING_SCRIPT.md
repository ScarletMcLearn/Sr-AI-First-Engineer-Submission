# Manual recording script (one scene at a time)

You run each scene with a terminal command. Playwright performs it, then **everything stays still** — both browser
windows, the database and the terminal — until you run the next command. Nothing advances on its own. Talk as long as
you like between scenes.

The fully automatic demo (`pnpm demo`) is unchanged; this is an additional mode. Background and troubleshooting:
[DEMO_RECORDING_GUIDE.md](DEMO_RECORDING_GUIDE.md). The automatic-mode script is
[DEMO_NARRATION_SCRIPT.md](DEMO_NARRATION_SCRIPT.md).

## Setup (not recorded)

```powershell
docker compose up -d --wait db      # once
cd frontend
pnpm demo:stack                     # Terminal A (optional, pre-builds; wait for "Demo stack is READY")
pnpm demo:session                   # Terminal B: seeds the l10_e2e database, opens Browser A, then waits
```

Use a **third terminal** (`cd frontend`) for the scene commands, next to the recorded screen but out of frame.
Start OBS when you are ready, then run `pnpm demo:scene intro`.

| Command | Effect |
|---|---|
| `pnpm demo:scene <id>` | Runs exactly that scene, prints PASS/FAIL and the next command, exits. |
| `pnpm demo:status` | Scenes done, scene timings, whether Browser B is open, what to run next. |
| `pnpm demo:reset` | Re-seeds the database, closes Browser B, returns Browser A to the Team Page. Start over. |
| `pnpm demo:stop` | Closes both browsers and ends the session. |

Rules enforced by the controller (nothing runs implicitly):

- Scenes run in order; you may skip a scene that has no prerequisite (for example `rocks`). Prerequisites:
  `issues`←`scorecard`, `meeting`←`issues`, `sync`←`meeting`, `reconnect`←`sync`, `summary`←`reconnect`.
  Otherwise: `Cannot run sync yet. Required scene: meeting`.
- A scene cannot be repeated, and a scene cannot run after a later one. Use `pnpm demo:reset`.
- If a scene fails, the browsers stay as they are, screenshots go to `frontend/test-results/demo-manual/`, and further
  scenes are refused until `pnpm demo:reset`. The database is never reset silently.

Pacing: in-scene pauses are 40 % of the automatic demo (`DEMO_MANUAL_PACE`, default `0.4`; `DEMO_PACE` still applies on
top). The nine scenes take about **3:16 of automation** (measured; see `pnpm demo:status`) plus your talking time, so the
video stays under seven minutes if your talking between scenes totals under about 3½ minutes. Raise `DEMO_MANUAL_PACE`
(for example `0.8`) for slower, more deliberate movements.

---

## 1. Introduction — `pnpm demo:scene intro` (≈ 15 s)

**Playwright shows:** the Team Page for Leadership as Casey Cho; each module card is scrolled into view and outlined
(Level 10 Meeting, Scorecard, Issues, To-Dos, Rocks).
**Say while it runs:** "This is the Level 10 meetings app. Everything you see is driven by Playwright against the real
app, the real API and a real PostgreSQL database. I'm Casey Cho, a Team Member of Leadership. The Team Page has the five
modules."
**Explain after:** stack (Next.js + TypeScript, FastAPI, PostgreSQL), the isolated `l10_e2e` database seeded
deterministically, frozen business clock `2026-11-11`.
**Next:** `pnpm demo:scene scorecard`

## 2. Scorecard — `pnpm demo:scene scorecard` (≈ 28 s)

**Playwright shows:** the 13-week table; an on-track, an off-track and a pending cell highlighted; edits the pending
score to 10 (goal "at least 10") and it turns On track; "Make it an Issue" on the off-track score creates one Issue;
clicking again shows "Issue already open".
**Say while it runs:** "Statuses are computed on the server from the data and the clock. A closed week with no score is
off track; a missing current-week score is pending. Ten meets a goal of at least ten, so the boundary is inclusive."
**Explain after:** no status is stored; text labels, not only colour; the duplicate guard is a database partial unique
index, so it is idempotent even with two clicks at once.
**Next:** `pnpm demo:scene issues`

## 3. Issues and To-Dos — `pnpm demo:scene issues` (≈ 35 s)

**Playwright shows:** the priority order, a priority change, a linked To-Do (owner list without Observers, due in 7
days), completing the overdue To-Do, solving the Scorecard Issue with the mandatory note, then the Solved tab.
**Say while it runs:** "Priority first, oldest first within a priority, unprioritised last. A To-Do linked to an Issue is
due in seven days and Observers can never own one. Solving needs a resolution note."
**Explain after:** role checks are re-loaded on the server for every request, not trusted from the client.
**Next:** `pnpm demo:scene rocks`

## 4. Rocks — `pnpm demo:scene rocks` (≈ 12 s)

**Playwright shows:** the Rocks card; one Rock off track at 13 %, one complete at 100 %; expands a Rock to its
Milestones (due today is not past due).
**Say while it runs:** "Rock status and progress are derived from Milestones and the clock, never stored."
**Explain after:** the rules are pure functions; `rules_report.json` is the diffable proof.
**Next:** `pnpm demo:scene meeting`

## 5. Two-browser meeting — `pnpm demo:scene meeting` (≈ 23 s)

**Playwright shows:** Browser A moves to the left half; Casey starts the meeting (Scorecard section, timer, Live); a
second, separate Chromium process opens on the right as Blake Brooks, sees "A meeting is in progress" and clicks
Join. Both show two attendees and the same facilitator. **Then everything stops with both windows visible.**
**Say while it runs:** "Two separate browser processes, separate cookies, two different seeded users."
**Explain after (take your time here):** only one active meeting per team is a database unique index; the facilitator is
Casey; the SSE connection starts every time from the full authoritative state; the timer is server-owned.
**Next:** `pnpm demo:scene sync`

## 6. Live synchronization — `pnpm demo:scene sync` (≈ 29 s)

**Playwright shows:** Blake has no Next/End buttons; Casey clicks "Next: IDS" and Browser B follows without reloading
(checked with a marker on the page); timers match; Blake solves an Issue and it disappears from Casey's list; Casey
adds a To-Do that appears in Blake's browser.
**Say while it runs:** "Updates arrive over Server-Sent Events, fed by PostgreSQL LISTEN/NOTIFY. Blake never refreshes."
**Explain after:** why LISTEN/NOTIFY (works across several API processes), why SSE (one-way, simple, auto-reconnect),
the server also rejects participant facilitator actions.
**Next:** `pnpm demo:scene reconnect`

## 7. Reconnection — `pnpm demo:scene reconnect` (≈ 12 s)

**Playwright shows:** reloads Browser B (section and timer recover); takes B offline; Casey advances to Conclude; B still
shows IDS; B goes back online and catches up to Conclude.
**Say while it runs:** "A refresh or a dropped connection does not lose state: the stream restarts from full state."
**Explain after:** no event replay is needed because every connect sends the complete state.
**Next:** `pnpm demo:scene summary`

## 8. Ratings and summary — `pnpm demo:scene summary` (≈ 23 s)

**Playwright shows:** Casey rates 8, Blake rates 9, both show 8.5; Casey ends the meeting; both browsers show the
summary (rating, Issue solved, To-Do created, attendees); both are reloaded and show the same stored summary.
**Say while it runs:** "Ratings are only possible in Conclude. Ending stores an immutable snapshot."
**Explain after:** the summary is read from the database, so later edits never rewrite history; ratings are final.
**Next:** `pnpm demo:scene architecture`

## 9. Architecture — `pnpm demo:scene architecture` (≈ 16 s)

**Playwright shows:** closes Browser B, restores Browser A to full screen and shows an evidence slide built from the
repository's own files (`docs/TEST_RESULTS.md`, `rules_report.json`, CI status), highlighting each card.
**Say while it runs:** "Engineering quality, from the repository's own results."
**Explain after:** PostgreSQL constraints and partial unique indexes, FastAPI REST, OpenAPI-generated TypeScript types,
deterministic rules report, backend and Playwright suites, CI on GitHub Actions. Then thank the viewer.
**Finish:** stop OBS, then `pnpm demo:stop`.

---

## If something goes wrong

- **`No demo session is running`** — start `pnpm demo:session` in its own terminal.
- **Scene fails** — read the message (and `frontend/test-results/demo-manual/`), then `pnpm demo:reset` and re-record
  from `intro`. Cut the video at the failure; the previous scenes' state is rebuilt by re-running them.
- **Port 8199 busy** — set `DEMO_CONTROL_PORT` identically in the session terminal and the command terminal.
- **A scene waits** — each browser action times out after 15 s (`DEMO_ACTION_TIMEOUT_MS`) and then fails the scene.
