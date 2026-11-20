import type { Page } from "@playwright/test";

import { USERS, expect, openAs, test } from "./fixtures";

/** Parse "mm:ss" from the timer element into seconds. */
async function timerSeconds(page: Page): Promise<number> {
  const text = (await page.getByTestId("timer").textContent()) ?? "00:00";
  const [m, s] = text.split(":").map(Number);
  return (m ?? 0) * 60 + (s ?? 0);
}

test("two browsers stay in sync through a whole Level 10 meeting", async ({ browser }) => {
  // 1. A Team Member opens their team.
  const casey = await openAs(browser, USERS.casey, "/");
  await expect(casey.page.getByTestId("team-name")).toHaveText("Leadership");
  await expect(casey.page.getByTestId("current-user")).toContainText("Casey Cho");

  // 2. The user starts a meeting (and becomes the facilitator).
  await casey.page.getByRole("button", { name: "Start meeting" }).click();
  await expect(casey.page).toHaveURL(/\/meetings\/mt_/);
  await expect(casey.page.getByTestId("current-section")).toHaveText("Scorecard");
  await expect(casey.page.getByTestId("facilitator-name")).toContainText("Casey Cho (you)");
  await expect(casey.page.getByTestId("connection-status")).toHaveText(/Live/);
  const meetingUrl = casey.page.url();

  // 3. A second authorised user joins from an independent browser context.
  const blake = await openAs(browser, USERS.blake, meetingUrl);

  // 4. Both browsers show the same initial section and attendees.
  await expect(blake.page.getByTestId("current-section")).toHaveText("Scorecard");
  await expect(blake.page.getByTestId("connection-status")).toHaveText(/Live/);
  for (const page of [casey.page, blake.page]) {
    await expect(page.getByTestId("attendees").getByRole("listitem")).toHaveCount(2);
    await expect(page.getByTestId("agenda-scorecard")).toHaveAttribute("aria-current", "step");
  }
  // Only the facilitator gets controls.
  await expect(blake.page.getByRole("button", { name: /Next:/ })).toHaveCount(0);
  await expect(blake.page.getByText("Only the facilitator can move the agenda")).toBeVisible();

  // 5. The facilitator advances the agenda; 6. the second browser follows without reloading.
  await casey.page.getByRole("button", { name: "Next: IDS" }).click();
  await expect(casey.page.getByTestId("current-section")).toHaveText("IDS");
  await expect(blake.page.getByTestId("current-section")).toHaveText("IDS");
  await expect(blake.page.getByTestId("agenda-ids")).toHaveAttribute("aria-current", "step");

  // 7. The timer is server-owned: both browsers show (nearly) the same elapsed time.
  await expect.poll(() => timerSeconds(casey.page)).toBeGreaterThanOrEqual(1);
  const [a, b] = [await timerSeconds(casey.page), await timerSeconds(blake.page)];
  expect(Math.abs(a - b)).toBeLessThanOrEqual(2);

  // 8. A refresh retains the correct meeting state (section and timer come from the server).
  await blake.page.reload();
  await expect(blake.page.getByTestId("current-section")).toHaveText("IDS");
  await expect.poll(() => timerSeconds(blake.page)).toBeGreaterThanOrEqual(1);

  // 9. A temporary disconnection followed by reconnection recovers the current state.
  await blake.context.setOffline(true);
  await casey.page.getByRole("button", { name: "Next: Conclude" }).click();
  await expect(casey.page.getByTestId("current-section")).toHaveText("Conclude");
  await expect(blake.page.getByTestId("current-section")).toHaveText("IDS"); // missed while offline
  await blake.context.setOffline(false);
  await expect(blake.page.getByTestId("current-section")).toHaveText("Conclude", {
    timeout: 15_000,
  });
  await expect(blake.page.getByTestId("connection-status")).toHaveText(/Live/, { timeout: 15_000 });

  // Ratings: attendees rate in Conclude; the average updates for everyone.
  await casey.page.getByRole("button", { name: "Rate 8", exact: true }).click();
  await blake.page.getByRole("button", { name: "Rate 9", exact: true }).click();
  await expect(casey.page.getByTestId("average-rating")).toHaveText("8.5");
  await expect(blake.page.getByTestId("average-rating")).toHaveText("8.5");

  // 10. The facilitator completes the meeting; 11. both browsers show the ended state and summary.
  await casey.page.getByRole("button", { name: "End meeting" }).click();
  await casey.page.getByRole("dialog").getByRole("button", { name: "End meeting" }).click();
  for (const page of [casey.page, blake.page]) {
    await expect(page.getByTestId("meeting-status")).toHaveText("Ended");
    const summary = page.getByTestId("summary");
    await expect(summary).toBeVisible();
    await expect(summary.getByTestId("summary-rating")).toHaveText("8.5");
    await expect(summary).toContainText("Scorecard — week of Nov 2");
    await expect(summary).toContainText("Cash on hand");
  }
  // Ratings are final once ended.
  await expect(blake.page.getByRole("button", { name: "Rate 1", exact: true })).toHaveCount(0);

  await casey.context.close();
  await blake.context.close();
});

test("observer joins read-only and a non-team member cannot reach the meeting", async ({
  browser,
}) => {
  const casey = await openAs(browser, USERS.casey, "/");
  await casey.page.getByRole("button", { name: "Start meeting" }).click();
  await expect(casey.page).toHaveURL(/\/meetings\/mt_/);
  const meetingUrl = casey.page.url();

  const ellis = await openAs(browser, USERS.ellis, meetingUrl); // Observer
  await expect(ellis.page.getByTestId("current-section")).toHaveText("Scorecard");
  await expect(ellis.page.getByText("You're observing")).toBeVisible();
  await expect(ellis.page.getByRole("button", { name: /Make it an Issue/ })).toHaveCount(0);
  await expect(ellis.page.getByRole("button", { name: /Edit score/ })).toHaveCount(0);

  const finley = await openAs(browser, USERS.finley, meetingUrl); // Sales only
  await expect(finley.page.getByText("This meeting is not available to you")).toBeVisible();

  await casey.context.close();
  await ellis.context.close();
  await finley.context.close();
});
