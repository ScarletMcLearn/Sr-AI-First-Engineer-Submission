import { expect, test } from "../e2e/fixtures";

import { Demo, ValidationStage } from "./demo-helpers";
import { prepareMain, runAllScenes } from "./scenes";

/**
 * VALIDATION MODE — the same nine scenes and assertions as the presentation, headless and without
 * pacing. Fast enough for local development and CI.
 */
test("assessment demonstration (validation)", async ({ browser }) => {
  test.setTimeout(3 * 60_000);
  const stage = await ValidationStage.create(browser);
  try {
    await prepareMain(stage);
    const demo = new Demo(stage);
    await runAllScenes(demo);
    expect(demo.report()).toBe("PASS");
  } finally {
    await stage.dispose();
  }
});
