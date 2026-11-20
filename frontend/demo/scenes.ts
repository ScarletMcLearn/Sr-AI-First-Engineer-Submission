import fs from "node:fs";
import path from "node:path";

import { expect, type Page } from "@playwright/test";

import { SCENE_ORDER, settings, USER_IDS } from "./demo-config";
import { type Demo, type Stage, signInContext } from "./demo-helpers";

/**
 * The nine scenes. Every interaction is a real UI action against the real stack (no mocks);
 * `stage.pause` is presentation pacing only and is a no-op in validation mode.
 */

async function timerSeconds(page: Page): Promise<number> {
  const text = (await page.getByTestId("timer").textContent()) ?? "00:00";
  const [m, s] = text.split(":").map(Number);
  return (m ?? 0) * 60 + (s ?? 0);
}

/** Sign the facilitator's browser in and load the Team Page. Runs before the first scene. */
export async function prepareMain(stage: Stage): Promise<void> {
  await signInContext(stage.main.context(), USER_IDS.facilitator);
  await stage.main.goto("/");
  await expect(stage.main.getByTestId("team-name")).toHaveText("Leadership");
  await expect(stage.main.getByTestId("cell-m1-2026-11-09")).toBeVisible();
}

/** Scene functions by id, in demonstration order. Used by `runAllScenes` and by manual mode. */
export const SCENE_RUNNERS: Record<(typeof SCENE_ORDER)[number], (demo: Demo) => Promise<void>> = {
  intro: (demo) => introduction(demo, demo.stage),
  scorecard: (demo) => scorecard(demo, demo.stage),
  issues: (demo) => issuesAndTodos(demo, demo.stage),
  rocks: (demo) => rocks(demo, demo.stage),
  meeting: (demo) => twoBrowserMeeting(demo, demo.stage),
  sync: (demo) => liveSync(demo, demo.stage),
  reconnect: (demo) => reconnection(demo, demo.stage),
  summary: (demo) => ratingsAndSummary(demo, demo.stage),
  architecture: (demo) => architecture(demo, demo.stage),
};

export async function runAllScenes(demo: Demo): Promise<void> {
  for (const id of SCENE_ORDER) await SCENE_RUNNERS[id](demo);
}

// ---- Scene 1 ----------------------------------------------------------------------------------
async function introduction(demo: Demo, stage: Stage): Promise<void> {
  await demo.scene("intro", async () => {
    const page = stage.main;
    await expect(page.getByTestId("team-name")).toHaveText("Leadership");
    await expect(page.getByTestId("current-user")).toContainText("Casey Cho");
    await stage.reveal(page.getByRole("banner"));
    await stage.pause(1500);
    const modules = [
      page.getByRole("region", { name: "Level 10 Meeting", exact: true }),
      page.getByRole("region", { name: "Scorecard", exact: true }),
      page.getByRole("region", { name: "Issues", exact: true }),
      page.getByRole("region", { name: "To-Dos", exact: true }),
      page.getByRole("region", { name: "Rocks", exact: true }),
    ];
    for (const card of modules) {
      await expect(card).toBeVisible();
      await stage.reveal(card);
      await stage.pause(1000);
    }
    await stage.scrollTop();
  });
}

// ---- Scene 2 ----------------------------------------------------------------------------------
async function scorecard(demo: Demo, stage: Stage): Promise<void> {
  await demo.scene("scorecard", async () => {
    const page = stage.main;
    const table = page.getByRole("region", { name: /Scorecard table/ });
    await expect(table.getByRole("columnheader")).toHaveCount(14); // measurable + 13 weeks
    await stage.reveal(table);
    // Show the whole 13-week history by scrolling the table sideways and back.
    await table.evaluate((el) => {
      el.scrollTo({ left: 0, behavior: "smooth" });
    });
    await stage.pause(800);

    const onTrack = page.getByTestId("cell-m1-2026-10-19");
    const offTrack = page.getByTestId("cell-m5-2026-10-19"); // no score in a closed week
    const pending = page.getByTestId("cell-m1-2026-11-09"); // no score in the current week
    await expect(onTrack).toContainText("On track");
    await expect(offTrack).toContainText("Off track");
    await expect(pending).toContainText("Pending");
    await stage.reveal(onTrack);
    await stage.pause(1200);
    await stage.reveal(offTrack);
    await stage.pause(1800); // missing closed-week score = off track
    await stage.reveal(pending);
    await stage.pause(1800); // missing current-week score = pending

    // Edit the pending score: 10 meets "at least 10" (inclusive boundary).
    await stage.click(pending.getByRole("button", { name: /Edit score/ }));
    await stage.fill(pending.getByLabel(/Score for/), "10");
    await stage.pause(600);
    await stage.click(pending.getByRole("button", { name: "Save" }));
    await expect(pending).toContainText("On track");
    await stage.pause(2000);

    // Make it an Issue from the off-track score; repeating it must not create a duplicate.
    await stage.click(offTrack.getByRole("button", { name: /Make it an Issue/ }));
    await expect(offTrack.getByTestId("issue-badge-m5-2026-10-19")).toBeVisible();
    const issues = page.getByRole("region", { name: "Issues", exact: true });
    const created = issues
      .getByRole("listitem")
      .filter({ hasText: "Cash on hand, week of Oct 19" });
    await expect(created).toHaveCount(1);
    await stage.pause(1500);
    await stage.click(offTrack.getByRole("button", { name: /Make it an Issue/ }));
    await expect(page.getByText(/Issue already open/)).toBeVisible();
    await expect(created).toHaveCount(1);
    await stage.pause(2000);
  });
}

// ---- Scene 3 ----------------------------------------------------------------------------------
async function issuesAndTodos(demo: Demo, stage: Stage): Promise<void> {
  await demo.scene("issues", async () => {
    const page = stage.main;
    const issues = page.getByRole("region", { name: "Issues", exact: true });
    await stage.reveal(issues);

    // Priority order: P5 (oldest first), P4, P3, ... then unprioritised.
    const list = issues.getByRole("list", { name: /Unsolved issues/ });
    const titles = await list.getByRole("listitem").locator("p.font-medium").allTextContents();
    expect(titles.slice(0, 5)).toEqual([
      "Two key accounts at risk",
      "Hiring pipeline is slow",
      "New deals closed, week of Nov 2",
      "Support coverage on weekends",
      "Idea: quarterly customer survey",
    ]);
    await stage.pause(2200);

    // Change a priority (a Team Member may).
    const priority = issues.getByLabel("Priority for Idea: quarterly customer survey");
    await stage.select(priority, { value: "4" });
    await expect(priority).toHaveValue("4");
    await stage.pause(1500);

    // Create a linked To-Do (due in 7 days, eligible owners only).
    await stage.click(issues.getByRole("button", { name: /^Add To-Do for: Hiring pipeline/ }));
    const todoDialog = page.getByRole("dialog", { name: "Add To-Do" });
    const owners = await todoDialog.getByLabel("Owner").locator("option").allTextContents();
    expect(owners).not.toContain("Ellis Evans"); // Observers cannot own To-Dos
    await stage.fill(todoDialog.getByLabel("Title"), "Interview three candidates");
    await stage.select(todoDialog.getByLabel("Owner"), { label: "Dana Diaz" });
    await stage.pause(800);
    await stage.click(todoDialog.getByRole("button", { name: "Add To-Do" }));
    const todo = page.getByTestId(/^todo-/).filter({ hasText: "Interview three candidates" });
    await expect(todo).toContainText("due Nov 18");
    await expect(todo).toContainText("Hiring pipeline is slow");
    await stage.reveal(todo);
    await stage.pause(2000);

    // Complete an existing To-Do (the overdue one).
    const overdue = page.getByTestId("todo-t12");
    await expect(overdue).toContainText("Overdue");
    await stage.reveal(overdue);
    await stage.check(overdue.getByRole("checkbox"));
    await expect(overdue).toContainText("done Nov 11");
    await stage.pause(1800);

    // Solve the Issue created from the Scorecard, with the mandatory note.
    await stage.reveal(issues);
    const cash = issues.getByRole("listitem").filter({ hasText: "Cash on hand, week of Oct 19" });
    await stage.click(cash.getByRole("button", { name: /^Solve:/ }));
    const dialog = page.getByRole("dialog", { name: "Solve Issue" });
    await stage.fill(dialog.getByLabel(/Resolution note/), "Forecast updated with finance");
    await stage.pause(600);
    await stage.click(dialog.getByRole("button", { name: "Mark solved" }));
    await expect(dialog).toBeHidden();
    await expect(cash).toHaveCount(0);
    await stage.click(issues.getByRole("button", { name: "Solved", exact: true }));
    await expect(issues.getByText("Forecast updated with finance")).toBeVisible();
    await stage.pause(2200);
    await stage.click(issues.getByRole("button", { name: "Unsolved", exact: true }));
    await stage.pause(500);
  });
}

// ---- Scene 4 ----------------------------------------------------------------------------------
async function rocks(demo: Demo, stage: Stage): Promise<void> {
  await demo.scene("rocks", async () => {
    const page = stage.main;
    await stage.reveal(page.getByRole("region", { name: "Rocks", exact: true }));
    const r2 = page.getByTestId("rock-r2");
    await expect(r2).toContainText("Off track");
    await expect(r2).toContainText("13%");
    await expect(page.getByTestId("rock-r3")).toContainText("100%");
    await stage.pause(2500);
    const r1 = page.getByTestId("rock-r1");
    await stage.click(r1.getByRole("button"));
    await expect(r1).toContainText("Portal beta");
    await expect(r1).not.toContainText("Past due"); // due today is not past due
    await stage.reveal(r1);
    await stage.pause(3000);
    await stage.scrollTop();
  });
}

// ---- Scene 5 ----------------------------------------------------------------------------------
async function twoBrowserMeeting(demo: Demo, stage: Stage): Promise<void> {
  await demo.scene("meeting", async () => {
    const a = stage.main;
    await stage.layout("split");
    await stage.pause(800);

    // Browser A: the facilitator starts the meeting.
    await stage.click(a.getByRole("button", { name: "Start meeting" }));
    await expect(a).toHaveURL(/\/meetings\/mt_/);
    await expect(a.getByTestId("current-section")).toHaveText("Scorecard");
    await expect(a.getByTestId("facilitator-name")).toContainText("Casey Cho (you)");
    await expect(a.getByTestId("connection-status")).toHaveText(/Live/);
    await expect(a.getByTestId("timer")).toBeVisible();
    await stage.pause(1500);

    // Browser B: a different seeded user in a separate browser process opens the same team and joins.
    const b = await stage.openSecond(USER_IDS.participant, "/");
    await expect(b.getByTestId("current-user")).toContainText("Blake Brooks");
    await expect(b.getByTestId("team-name")).toHaveText("Leadership");
    await expect(b.getByText(/A meeting is in progress, facilitated by/)).toBeVisible();
    await stage.pause(1500);
    await stage.click(b.getByRole("link", { name: /Join meeting/ }));
    await expect(b).toHaveURL(/\/meetings\/mt_/);

    for (const page of [a, b]) {
      await expect(page.getByTestId("current-section")).toHaveText("Scorecard");
      await expect(page.getByTestId("connection-status")).toHaveText(/Live/);
      await expect(page.getByTestId("attendees").getByRole("listitem")).toHaveCount(2);
      await expect(page.getByTestId("agenda-scorecard")).toHaveAttribute("aria-current", "step");
      await expect(page.getByTestId("timer")).toBeVisible();
    }
    expect(await a.getByTestId("facilitator-name").textContent()).toContain("Casey Cho");
    expect(await b.getByTestId("facilitator-name").textContent()).toContain("Casey Cho");
    await stage.pause(3000);
  });
}

// ---- Scene 6 ----------------------------------------------------------------------------------
async function liveSync(demo: Demo, stage: Stage): Promise<void> {
  await demo.scene("sync", async () => {
    const a = stage.main;
    const b = stage.second();

    // A marker proves browser B is never reloaded in this scene: it would vanish on navigation.
    await b.evaluate(() => {
      (window as unknown as { __noReload: boolean }).__noReload = true;
    });

    // The participant has no facilitator controls.
    await expect(b.getByRole("button", { name: /Next:/ })).toHaveCount(0);
    await expect(b.getByRole("button", { name: "End meeting" })).toHaveCount(0);
    await expect(b.getByText("Only the facilitator can move the agenda")).toBeVisible();
    await stage.pause(2500);

    // 1. Advance the agenda in A; B follows by itself.
    await stage.click(a.getByRole("button", { name: "Next: IDS" }));
    await expect(a.getByTestId("current-section")).toHaveText("IDS");
    await expect(b.getByTestId("current-section")).toHaveText("IDS");
    await expect(b.getByTestId("agenda-ids")).toHaveAttribute("aria-current", "step");
    await stage.pause(2500);

    // Server-owned timer: both show (nearly) the same elapsed time.
    await expect.poll(() => timerSeconds(a)).toBeGreaterThanOrEqual(1);
    const [ta, tb] = [await timerSeconds(a), await timerSeconds(b)];
    expect(Math.abs(ta - tb)).toBeLessThanOrEqual(2);

    // 2. Another state change: the participant solves an Issue; the facilitator's list updates.
    const issuesA = a.getByRole("region", { name: "Issues", exact: true });
    const issuesB = b.getByRole("region", { name: "Issues", exact: true });
    const title = "Two key accounts at risk";
    await expect(issuesA.getByRole("listitem").filter({ hasText: title })).toHaveCount(1);
    await stage.click(issuesB.getByRole("button", { name: `Solve: ${title}` }));
    const dialog = b.getByRole("dialog", { name: "Solve Issue" });
    await stage.fill(dialog.getByLabel(/Resolution note/), "Account plans agreed");
    await stage.pause(500);
    await stage.click(dialog.getByRole("button", { name: "Mark solved" }));
    await expect(dialog).toBeHidden();
    await expect(issuesA.getByRole("listitem").filter({ hasText: title })).toHaveCount(0);
    await stage.pause(2500);

    // 3. The facilitator adds a follow-up To-Do; it appears in the participant's browser.
    await stage.click(issuesA.getByRole("button", { name: /^Add To-Do for: Hiring pipeline/ }));
    const todoDialog = a.getByRole("dialog", { name: "Add To-Do" });
    await stage.fill(todoDialog.getByLabel("Title"), "Review candidate shortlist");
    await stage.select(todoDialog.getByLabel("Owner"), { label: "Dana Diaz" });
    await stage.pause(500);
    await stage.click(todoDialog.getByRole("button", { name: "Add To-Do" }));
    await expect(a.getByText("Review candidate shortlist")).toBeVisible();
    await expect(b.getByText("Review candidate shortlist")).toBeVisible();
    await stage.pause(3000);

    expect(await b.evaluate(() => (window as unknown as { __noReload?: boolean }).__noReload)).toBe(
      true,
    );
  });
}

// ---- Scene 7 ----------------------------------------------------------------------------------
async function reconnection(demo: Demo, stage: Stage): Promise<void> {
  await demo.scene("reconnect", async () => {
    const a = stage.main;
    const b = stage.second();

    // A page refresh recovers the section and the server-owned timer.
    await b.reload();
    await expect(b.getByTestId("current-section")).toHaveText("IDS");
    await expect(b.getByTestId("connection-status")).toHaveText(/Live/);
    await expect.poll(() => timerSeconds(b)).toBeGreaterThanOrEqual(1);
    await stage.pause(2000);

    // A temporary disconnection: B misses a section change, then catches up on reconnect.
    await stage.setOffline(b, true);
    await expect(b.getByTestId("connection-status")).not.toHaveText(/Live/);
    await stage.pause(1500);
    await stage.click(a.getByRole("button", { name: "Next: Conclude" }));
    await expect(a.getByTestId("current-section")).toHaveText("Conclude");
    await expect(b.getByTestId("current-section")).toHaveText("IDS"); // missed while offline
    await stage.pause(2000);
    await stage.setOffline(b, false);
    await expect(b.getByTestId("current-section")).toHaveText("Conclude", { timeout: 20_000 });
    await expect(b.getByTestId("connection-status")).toHaveText(/Live/, { timeout: 20_000 });
    await expect(b.getByTestId("agenda-conclude")).toHaveAttribute("aria-current", "step");
    const [ta, tb] = [await timerSeconds(a), await timerSeconds(b)];
    expect(Math.abs(ta - tb)).toBeLessThanOrEqual(3);
    await stage.pause(2500);
  });
}

// ---- Scene 8 ----------------------------------------------------------------------------------
async function ratingsAndSummary(demo: Demo, stage: Stage): Promise<void> {
  await demo.scene("summary", async () => {
    const a = stage.main;
    const b = stage.second();

    await stage.click(a.getByRole("button", { name: "Rate 8", exact: true }));
    await stage.click(b.getByRole("button", { name: "Rate 9", exact: true }));
    await expect(a.getByTestId("average-rating")).toHaveText("8.5");
    await expect(b.getByTestId("average-rating")).toHaveText("8.5");
    await stage.pause(2500);

    await stage.click(a.getByRole("button", { name: "End meeting" }));
    await stage.pause(800);
    await stage.click(a.getByRole("dialog").getByRole("button", { name: "End meeting" }));
    for (const page of [a, b]) {
      await expect(page.getByTestId("meeting-status")).toHaveText("Ended");
      const summary = page.getByTestId("summary");
      await expect(summary).toBeVisible();
      await expect(summary.getByTestId("summary-rating")).toHaveText("8.5");
      await expect(summary).toContainText("Issues solved (1)");
      await expect(summary).toContainText("To-Dos created (1)");
      await expect(summary).toContainText("Cash on hand");
    }
    await expect(b.getByRole("button", { name: "Rate 1", exact: true })).toHaveCount(0); // final
    await stage.reveal(a.getByTestId("summary"));
    await stage.reveal(b.getByTestId("summary"));
    await stage.pause(3500);

    // Reload: the stored summary is still there (read from the database, not rebuilt).
    await Promise.all([a.reload(), b.reload()]);
    for (const page of [a, b]) {
      await expect(page.getByTestId("meeting-status")).toHaveText("Ended");
      await expect(page.getByTestId("summary-rating")).toHaveText("8.5");
      await stage.reveal(page.getByTestId("summary"));
    }
    await stage.pause(3000);
  });
}

// ---- Scene 9 ----------------------------------------------------------------------------------
function escapeHtml(text: string): string {
  return text.replace(/[&<>"]/g, (c) => `&#${String(c.charCodeAt(0))};`);
}

function readRepo(...parts: string[]): string {
  return fs.readFileSync(path.resolve(process.cwd(), "..", ...parts), "utf8");
}

interface RulesReport {
  now?: string;
  teams?: Record<string, { measurable_status?: Record<string, Record<string, string>> }>;
}

/** Build the evidence slide from real repository files (nothing is hard-coded except the headings). */
export function architectureSlide(): string {
  const results = readRepo("docs", "TEST_RESULTS.md");
  const backend = /\*\*(\d+) passed\*\*[^|]*\|?/.exec(results.split("test-backend")[1] ?? "");
  const e2e = /\*\*(\d+) passed\*\*/.exec(results.split("test-e2e")[1] ?? "");
  const report = JSON.parse(readRepo("rules_report.json")) as RulesReport;
  const counts: Record<string, number> = {};
  for (const team of Object.values(report.teams ?? {})) {
    for (const weeks of Object.values(team.measurable_status ?? {})) {
      for (const status of Object.values(weeks)) counts[status] = (counts[status] ?? 0) + 1;
    }
  }
  const teamCount = Object.keys(report.teams ?? {}).length;
  const ci =
    settings.ciStatus === "success"
      ? `passing on GitHub Actions (commit ${settings.ciSha.slice(0, 7)})`
      : `status not verified in this run (${settings.ciStatus})`;
  const ruleCounts = Object.entries(counts)
    .map(([k, v]) => `${k.replace("_", " ")}: ${String(v)}`)
    .join(" · ");
  const card = (title: string, lines: string[]) =>
    `<section><h2>${escapeHtml(title)}</h2><ul>${lines.map((l) => `<li>${escapeHtml(l)}</li>`).join("")}</ul></section>`;
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Engineering quality</title>
<style>
  body{font:20px/1.45 system-ui,Segoe UI,sans-serif;margin:0;padding:36px 48px;background:#f8fafc;color:#0f172a}
  h1{margin:0 0 20px;font-size:34px}
  .grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}
  section{background:#fff;border:1px solid #cbd5e1;border-radius:12px;padding:16px 22px}
  h2{margin:0 0 8px;font-size:22px;color:#1d4ed8}
  ul{margin:0;padding-left:22px}li{margin:4px 0}
  small{color:#475569}
</style></head><body>
<h1>Engineering quality and architecture</h1>
<div class="grid">
${card("Automated verification (docs/TEST_RESULTS.md)", [
  `Backend: ${backend?.[1] ?? "n/a"} tests passed (rules, API, authorization, concurrency, real-time)`,
  `Playwright e2e: ${e2e?.[1] ?? "n/a"} tests passed (two browser contexts)`,
  `CI: ${ci}`,
])}
${card("Deterministic rules report (rules_report.json)", [
  `Business time frozen at ${report.now ?? "n/a"} (APP_NOW)`,
  `${String(teamCount)} teams; measurable cells → ${ruleCounts}`,
  "Every status is derived from data and the clock, never stored",
])}
${card("Data and API", [
  "PostgreSQL: constraints and partial unique indexes enforce invariants",
  "FastAPI REST API, role checks re-loaded on the server",
  "Next.js + TypeScript client generated from the OpenAPI schema",
])}
${card("Real time and history", [
  "SSE stream fed by PostgreSQL LISTEN/NOTIFY; every connect starts from full state",
  "One active meeting per team and idempotent Issue creation are database guarantees",
  "Ending a meeting stores an immutable summary snapshot",
])}
</div><p><small>Source: files in this repository (docs/DECISIONS.md, docs/ARCHITECTURE.md).</small></p>
</body></html>`;
}

async function architecture(demo: Demo, stage: Stage): Promise<void> {
  await demo.scene("architecture", async () => {
    const page = stage.main;
    if (stage.mode === "presentation") {
      await stage.closeSecond();
      await stage.layout("full");
    }
    await page.setContent(architectureSlide());
    await expect(
      page.getByRole("heading", { name: "Engineering quality and architecture" }),
    ).toBeVisible();
    for (const section of await page.locator("section").all()) {
      await stage.reveal(section);
      await stage.pause(4500);
    }
    await stage.pause(2000);
  });
}
