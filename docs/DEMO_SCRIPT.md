# Demo script (≤ 7 minutes)

> **Automated alternative:** `pnpm demo` in `frontend/` performs this walkthrough automatically; see [DEMO_RECORDING_GUIDE.md](DEMO_RECORDING_GUIDE.md).
>
> **Status: the video has NOT been recorded.** This is the script and checklist for recording it (Loom or an unlisted
> YouTube video). Make sure the link opens without a login before submitting.

## Setup (before recording)

```bash
docker compose down -v && docker compose up --build -d --wait     # fresh, seeded stack
```
Open two *separate* browser profiles/windows side by side (e.g. a normal window and a private window) so the cookies
are independent: **Window A** `http://localhost:3000` as Casey Cho, **Window B** as Blake Brooks. Resolution ≥ 1440×900,
zoom 100%, close unrelated tabs, enable "Do not disturb". Have `http://localhost:8000/docs` and a terminal ready.

## Script

| Time | Do | Say (key points) |
|------|----|------------------|
| 0:00–0:25 | Terminal: show `docker compose up` already healthy (`docker compose ps`) | One command starts PostgreSQL → migrations → idempotent seed → API → web. Health checks, no sleeps. |
| 0:25–1:00 | Window A: `/login`, sign in as **Casey Cho**; show team switcher (Leadership only). Switch user to **Avery Admin**: three teams; **Ellis Evans** (Observer): read-only | Seeded-user login is the assessment shortcut; roles/teams are always reloaded server-side. Forbidden team URL → access error. |
| 1:00–2:00 | Team page as Casey: scorecard (13 weeks, sticky column, status text + icon, not colour only). Edit **New deals closed, week of Nov 9** → 10 → "On track" (inclusive boundary). Note `m5` Oct 19 is off track (missing score) | Business rules are computed server-side from `APP_NOW` (Nov 11, 9:00 Chicago). |
| 2:00–3:00 | Click **Make it an Issue** on *Cash on hand, Oct 19* twice → one Issue. Solve an Issue (note required, show the validation). **Add To-Do** (due Nov 18, owner list has no Observer). Show To-Dos: overdue badge, last closed week completion 90% "Meets target". Rocks: expand r2 (off track, 13%) | Concurrency: partial unique index; show the test or the `DECISIONS.md` section briefly. |
| 3:00–4:30 | **Start meeting** (Casey = facilitator). Window B (Blake) joins the same meeting. Both show Scorecard section, timer, attendees. Casey clicks **Next: IDS** → Blake follows instantly | Server-owned timer; SSE + LISTEN/NOTIFY; PostgreSQL is the only owner of state. |
| 4:30–5:15 | In IDS: solve an Issue and add a To-Do in Window B (Team Member) → appears in Window A. Reload Window B: state and timer recovered. DevTools → Network offline in B, advance in A, back online → B catches up | Late join, refresh, reconnect: each connect starts with the full authoritative state. |
| 5:15–6:00 | Conclude: both rate (8, 9) → average 8.5; Casey ends the meeting; both see the summary; ratings are final. Open `mt2` summary (seeded: rating 8.3) | Summary is a persisted snapshot (history never changes). |
| 6:00–6:30 | Terminal: `docker compose run --rm -T backend python -m app.cli rules-report \| head`; show `rules_report.json`; mention `APP_NOW=… ` works | Every value derived from data and the clock. |
| 6:30–7:00 | `pixi run test` result summary (pytest, Playwright), `docs/DECISIONS.md` | Main decisions: data model links, REST design, SSE+NOTIFY, partial unique index, snapshot summaries; limitations in README. |

## Recording checklist

1. Rehearse once; keep the cursor visible and move slowly.
2. Record at 1080p; speak over the screen; keep it under 7:00 (trim, don't speed up).
3. Show **two browsers in the same meeting** (required) and your main decisions.
4. Upload as *unlisted*/link-viewable; open the link in a private window to verify no access request.
5. Paste the link into the README ("Video" line) before submitting.
