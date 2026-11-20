import { expect, test } from "../e2e/fixtures";

import { LIMIT_SECONDS, settings } from "./demo-config";
import { Demo, PresentationStage, mmss } from "./demo-helpers";
import { prepareMain, runAllScenes } from "./scenes";

/**
 * PRESENTATION MODE — the assessment video. Headed, two real browser windows, deliberate pacing.
 * Run with `pnpm demo` (see docs/DEMO_RECORDING_GUIDE.md). The database is reset to the seed by the
 * guarded test endpoint (isolated `l10_e2e` database only) before the browsers open.
 */
test("assessment demonstration (presentation)", async () => {
  test.setTimeout(12 * 60_000);
  const stage = await PresentationStage.create();
  try {
    await prepareMain(stage);
    console.log(`\nReady. Recording starts in ${String(settings.startDelaySeconds)}s…`);
    await stage.main.waitForTimeout(settings.startDelaySeconds * 1000);

    const demo = new Demo(stage);
    await runAllScenes(demo);
    const status = demo.report();
    console.log(`Total ${mmss(demo.totalSeconds())}`);
    expect(demo.totalSeconds(), "demo must stay under the 7:00 limit").toBeLessThan(LIMIT_SECONDS);
    expect(status.startsWith("PASS")).toBe(true);
  } finally {
    await stage.dispose();
  }
});
