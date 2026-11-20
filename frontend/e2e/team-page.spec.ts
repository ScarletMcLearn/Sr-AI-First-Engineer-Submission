import AxeBuilder from "@axe-core/playwright";

import { USERS, expect, openAs, test } from "./fixtures";

test("team member reviews the scorecard, turns an off-track score into one Issue, solves it and adds a To-Do", async ({
  browser,
}) => {
  const { page, context } = await openAs(browser, USERS.casey, "/");
  await expect(page.getByTestId("team-name")).toHaveText("Leadership");

  // Scorecard: 13 week columns + the measurable column; statuses are text, not just colour.
  const scorecard = page.getByRole("region", { name: /Scorecard table/ });
  await expect(scorecard.getByRole("columnheader")).toHaveCount(14);
  const missing = page.getByTestId("cell-m5-2026-10-19"); // no score in a closed week
  await expect(missing).toContainText("Off track");
  const pending = page.getByTestId("cell-m1-2026-11-09"); // no score in the current week
  await expect(pending).toContainText("Pending");

  // Inline edit: 10 meets "at least 10" (inclusive boundary) -> On track.
  await pending.getByRole("button", { name: /Edit score/ }).click();
  await pending.getByLabel(/Score for/).fill("10");
  await pending.getByRole("button", { name: "Save" }).click();
  await expect(pending).toContainText("On track");

  // Make it an Issue: creates one, and repeating it returns the same Issue (no duplicate).
  await missing.getByRole("button", { name: /Make it an Issue/ }).click();
  const issues = page.getByRole("region", { name: "Issues" });
  const created = issues.getByRole("listitem").filter({ hasText: "Cash on hand, week of Oct 19" });
  await expect(created).toHaveCount(1);
  await expect(created).toContainText("Owner Casey Cho");
  await expect(missing.getByTestId("issue-badge-m5-2026-10-19")).toBeVisible();
  await missing.getByRole("button", { name: /Make it an Issue/ }).click();
  await expect(page.getByText(/Issue already open/)).toBeVisible();
  await expect(created).toHaveCount(1);

  // Issue order: P5 oldest first, then P4, P3, ..., unprioritised last.
  const titles = await issues
    .getByRole("list", { name: /Unsolved issues/ })
    .getByRole("listitem")
    .locator("p.font-medium")
    .allTextContents();
  expect(titles.slice(0, 5)).toEqual([
    "Two key accounts at risk",
    "Hiring pipeline is slow",
    "New deals closed, week of Nov 2",
    "Support coverage on weekends",
    "Idea: quarterly customer survey",
  ]);

  // Solving requires a note.
  await created.getByRole("button", { name: /^Solve:/ }).click();
  const dialog = page.getByRole("dialog", { name: "Solve Issue" });
  await dialog.getByRole("button", { name: "Mark solved" }).click();
  await expect(dialog.getByRole("alert")).toHaveText("A resolution note is required");
  await dialog.getByLabel(/Resolution note/).fill("Forecast updated with finance");
  await dialog.getByRole("button", { name: "Mark solved" }).click();
  await expect(dialog).toBeHidden();
  await expect(created).toHaveCount(0);
  await issues.getByRole("button", { name: "Solved", exact: true }).click();
  await expect(issues.getByText("Forecast updated with finance")).toBeVisible();

  // Add a To-Do for an Issue: eligible owners only; due in 7 days.
  await issues.getByRole("button", { name: "Unsolved", exact: true }).click();
  await issues.getByRole("button", { name: /^Add To-Do for: Hiring pipeline/ }).click();
  const todoDialog = page.getByRole("dialog", { name: "Add To-Do" });
  const owners = await todoDialog.getByLabel("Owner").locator("option").allTextContents();
  expect(owners).not.toContain("Ellis Evans"); // Observers cannot own
  await todoDialog.getByLabel("Title").fill("Interview three candidates");
  await todoDialog.getByLabel("Owner").selectOption({ label: "Dana Diaz" });
  await todoDialog.getByRole("button", { name: "Add To-Do" }).click();
  const todo = page.getByTestId(/^todo-/).filter({ hasText: "Interview three candidates" });
  await expect(todo).toContainText("due Nov 18");
  await expect(todo).toContainText("Hiring pipeline is slow");

  // Mark done and undo.
  await todo.getByRole("checkbox").check();
  await expect(todo).toContainText("done Nov 11");
  await todo.getByRole("checkbox").uncheck();
  await expect(todo).not.toContainText("done Nov 11");

  // Completion rate for the last closed week and the overdue flag.
  await expect(page.getByTestId("todo-completion")).toContainText("90%");
  await expect(page.getByTestId("todo-completion")).toContainText("Meets 90% target");
  await expect(page.getByTestId("todo-t12")).toContainText("Overdue");
  await expect(page.getByTestId("todo-t30")).not.toContainText("Overdue"); // due today

  // Rocks: computed status/progress and expandable Milestones.
  await expect(page.getByTestId("rock-r2")).toContainText("Off track");
  await expect(page.getByTestId("rock-r2")).toContainText("13%");
  await expect(page.getByTestId("rock-r3")).toContainText("100%");
  await page.getByTestId("rock-r1").getByRole("button").click();
  await expect(page.getByTestId("rock-r1")).toContainText("Portal beta");
  await expect(page.getByTestId("rock-r1")).not.toContainText("Past due"); // ms2 is due today

  await context.close();
});

test("observer sees everything read-only; team switcher only lists own teams; foreign team is refused", async ({
  browser,
}) => {
  const { page, context } = await openAs(browser, USERS.ellis, "/");
  await expect(page.getByTestId("team-name")).toHaveText("Leadership");
  await expect(page.getByRole("button", { name: /Edit score/ })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /Make it an Issue/ })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Add Issue" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Start meeting" })).toHaveCount(0);
  await expect(page.getByRole("checkbox").first()).toBeDisabled();

  const options = await page.getByLabel("Team").locator("option").allTextContents();
  expect(options).toEqual(["Leadership"]);

  await page.goto("/teams/team_ops"); // guessed id of a team the user does not belong to
  await expect(
    page.getByRole("heading", { name: "You don't have access to this team" }),
  ).toBeVisible();
  await context.close();
});

test("admin sees every team; unauthenticated visitors are sent to the user switcher", async ({
  browser,
}) => {
  const { page, context } = await openAs(browser, USERS.admin, "/");
  await expect(page.getByLabel("Team").locator("option")).toHaveCount(3);
  const options = await page.getByLabel("Team").locator("option").allTextContents();
  expect(options.sort()).toEqual(["Leadership", "Operations", "Sales"]);
  await context.close();

  const anonymous = await browser.newContext();
  const anonPage = await anonymous.newPage();
  await anonPage.goto("/teams/team_lead");
  await expect(anonPage).toHaveURL(/\/login$/);
  await anonPage.getByRole("button", { name: /Sign in as Casey Cho/ }).click();
  await expect(anonPage.getByTestId("team-name")).toHaveText("Leadership");
  await anonymous.close();
});

test("no serious accessibility violations on the team page and the user switcher", async ({
  browser,
}) => {
  const { page, context } = await openAs(browser, USERS.casey, "/");
  await expect(page.getByTestId("team-name")).toBeVisible();
  await expect(page.getByTestId("cell-m1-2026-11-02")).toBeVisible();
  const team = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  expect(team.violations.filter((v) => v.impact === "serious" || v.impact === "critical")).toEqual(
    [],
  );
  await context.close();

  const anonymous = await browser.newContext();
  const login = await anonymous.newPage();
  await login.goto("/login");
  await expect(login.getByRole("heading", { name: "Level 10 meetings" })).toBeVisible();
  await expect(login.getByRole("button", { name: /Sign in as Avery Admin/ })).toBeVisible();
  const result = await new AxeBuilder({ page: login }).withTags(["wcag2a", "wcag2aa"]).analyze();
  expect(
    result.violations.filter((v) => v.impact === "serious" || v.impact === "critical"),
  ).toEqual([]);
  await anonymous.close();
});
