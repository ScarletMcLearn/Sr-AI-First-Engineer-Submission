import {
  test as base,
  expect,
  type Browser,
  type BrowserContext,
  type Page,
} from "@playwright/test";

export const API = "http://localhost:8100";

/** Seeded users by id (see seed.json). */
export const USERS = {
  admin: "u1", // Avery Admin, Leadership
  blake: "u2", // Team Member, Leadership + Sales
  casey: "u3", // Team Member, Leadership
  dana: "u4", // Team Member, Leadership + Operations
  ellis: "u5", // Observer, Leadership
  finley: "u6", // Team Member, Sales
} as const;

/** Every test starts from a freshly seeded database (isolated l10_e2e database only). */
export const test = base.extend<{ resetDb: undefined }>({
  resetDb: [
    async ({ request }, use) => {
      const response = await request.post(`${API}/api/__test__/reset`);
      expect(response.ok()).toBeTruthy();
      await use(undefined);
    },
    { auto: true },
  ],
});

export { expect };

/** A fully independent browser context (own cookies) signed in as the given seeded user. */
export async function openAs(
  browser: Browser,
  userId: string,
  path = "/",
): Promise<{ context: BrowserContext; page: Page }> {
  const context = await browser.newContext();
  const login = await context.request.post(`${API}/api/auth/login`, { data: { user_id: userId } });
  expect(login.ok()).toBeTruthy();
  const page = await context.newPage();
  await page.goto(path);
  return { context, page };
}
