import fs from "node:fs";
import path from "node:path";

import {
  chromium,
  expect,
  type Browser,
  type BrowserContext,
  type Locator,
  type Page,
} from "@playwright/test";

import { API_URL, LIMIT_SECONDS, SCENES, SOFT_LIMIT_SECONDS, settings } from "./demo-config";

export type Layout = "full" | "split";

/**
 * What a scene needs from its environment. The presentation stage drives real, visible windows with
 * deliberate pacing; the validation stage drives headless contexts with no pacing. Scenes contain the
 * real interactions and assertions, so both modes exercise exactly the same behaviour.
 */
export interface Stage {
  readonly mode: "presentation" | "validation";
  /** Browser A (facilitator). */
  readonly main: Page;
  /** Browser B (participant); only exists after `openSecond`. */
  second(): Page;
  /** Open an independent browser signed in as the given seeded user. */
  openSecond(userId: string, path: string): Promise<Page>;
  closeSecond(): Promise<void>;
  setOffline(page: Page, offline: boolean): Promise<void>;
  layout(kind: Layout): Promise<void>;
  /** Presentation pacing only. Never use it to wait for application state. */
  pause(ms: number): Promise<void>;
  setPacing(factor: number): void;
  click(target: Locator): Promise<void>;
  fill(target: Locator, text: string): Promise<void>;
  select(target: Locator, option: { label: string } | { value: string }): Promise<void>;
  check(target: Locator, checked?: boolean): Promise<void>;
  /** Smoothly bring the element into view and outline it briefly. */
  reveal(target: Locator): Promise<void>;
  scrollTop(page?: Page): Promise<void>;
  pages(): Page[];
}

export async function signInContext(context: BrowserContext, userId: string): Promise<void> {
  const login = await context.request.post(`${API_URL}/api/auth/login`, {
    data: { user_id: userId },
  });
  expect(login.ok(), `login as ${userId} failed (${String(login.status())})`).toBeTruthy();
}

// ---------------------------------------------------------------------------------------------
// Scene runner with timing report
// ---------------------------------------------------------------------------------------------

interface SceneResult {
  id: string;
  title: string;
  status: "PASS" | "FAIL";
  startedAtMs: number;
  endedAtMs: number;
  seconds: number;
  targetSeconds: number;
  error?: string;
}

export function mmss(seconds: number): string {
  const total = Math.round(seconds);
  return `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
}

export class Demo {
  readonly results: SceneResult[] = [];
  private readonly t0 = Date.now();
  private firstSceneAt: number | null = null;

  /**
   * `manual`: scene-by-scene operator mode. Time between scenes is the operator talking, so no
   * running clock, no 7-minute report; output goes through `log`.
   */
  constructor(
    readonly stage: Stage,
    private readonly outDir = "test-results",
    private readonly options: { manual?: boolean; log?: (line: string) => void } = {},
  ) {}

  /** Run one scene: real interactions + assertions. Failures are recorded, screenshotted and rethrown. */
  async scene(id: keyof typeof SCENES, body: () => Promise<void>): Promise<void> {
    const config = SCENES[id];
    if (!config) throw new Error(`unknown scene ${id}`);
    const log = this.options.log ?? console.log;
    this.stage.setPacing(config.pacing);
    const start = Date.now();
    this.firstSceneAt ??= start;
    if (this.options.manual) {
      log(`\n[DEMO] Running: ${config.title}`);
    } else if (this.stage.mode === "presentation") {
      const at = mmss((start - this.firstSceneAt) / 1000);
      log(`\n[${at}] ▶ ${config.title}  (target ${mmss(config.targetSeconds)})`);
      for (const cue of config.cues) log(`        · ${cue}`);
    }
    try {
      await body();
      this.results.push(this.result(config.id, config.title, "PASS", start, config.targetSeconds));
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      this.results.push(
        this.result(config.id, config.title, "FAIL", start, config.targetSeconds, message),
      );
      await this.captureFailure(id);
      if (!this.options.manual) this.report();
      throw new Error(`Scene "${config.title}" failed: ${message}`, { cause: error });
    }
  }

  private result(
    id: string,
    title: string,
    status: "PASS" | "FAIL",
    start: number,
    targetSeconds: number,
    error?: string,
  ): SceneResult {
    const end = Date.now();
    return {
      id,
      title,
      status,
      startedAtMs: start,
      endedAtMs: end,
      seconds: (end - start) / 1000,
      targetSeconds,
      ...(error === undefined ? {} : { error }),
    };
  }

  private async captureFailure(id: string): Promise<void> {
    fs.mkdirSync(this.outDir, { recursive: true });
    let index = 0;
    for (const page of this.stage.pages()) {
      try {
        await page.screenshot({
          path: path.join(this.outDir, `demo-failure-${id}-browser-${String(index)}.png`),
        });
      } catch {
        // The page may already be closed; the error itself is still reported.
      }
      index += 1;
    }
  }

  totalSeconds(): number {
    const first = this.results[0];
    const last = this.results[this.results.length - 1];
    if (!first || !last) return 0;
    return (last.endedAtMs - first.startedAtMs) / 1000;
  }

  /** Print the timing table and persist it as JSON and Markdown next to the other test artifacts. */
  report(): string {
    const width = Math.max(...this.results.map((r) => r.title.length), 20) + 2;
    const rows = this.results.map(
      (r) =>
        `${r.title.padEnd(width)}${r.status}   ${mmss(r.seconds)}   (target ${mmss(r.targetSeconds)}, ${r.seconds >= r.targetSeconds ? "+" : "-"}${Math.abs(Math.round(r.seconds - r.targetSeconds))}s)`,
    );
    const total = this.totalSeconds();
    const failed = this.results.some((r) => r.status === "FAIL");
    const status = failed
      ? "FAIL"
      : total >= LIMIT_SECONDS
        ? "FAIL (over 7:00)"
        : total > SOFT_LIMIT_SECONDS
          ? "PASS (over 6:30 target)"
          : "PASS";
    const line = "-".repeat(width + 40);
    const text = [
      "",
      `Assessment Demonstration (${this.stage.mode})`,
      line,
      ...rows,
      line,
      `${"Total".padEnd(width)}${mmss(total)}   (limit 07:00)`,
      `${"Status".padEnd(width)}${status}`,
      "",
    ].join("\n");
    console.log(text);
    fs.mkdirSync(this.outDir, { recursive: true });
    fs.writeFileSync(
      path.join(this.outDir, `demo-report-${this.stage.mode}.json`),
      JSON.stringify(
        {
          mode: this.stage.mode,
          totalSeconds: total,
          status,
          scenes: this.results.map((r) => ({
            id: r.id,
            title: r.title,
            status: r.status,
            seconds: Number(r.seconds.toFixed(1)),
            targetSeconds: r.targetSeconds,
            error: r.error,
          })),
          wallClockSeconds: (Date.now() - this.t0) / 1000,
        },
        null,
        2,
      ),
    );
    return status;
  }
}

// ---------------------------------------------------------------------------------------------
// Presentation stage: real windows, visible cursor, human pacing
// ---------------------------------------------------------------------------------------------

const CURSOR_SCRIPT = `
(() => {
  if (window.__demoCursor) return;
  const install = () => {
    if (!document.body || window.__demoCursor) return;
    const dot = document.createElement('div');
    dot.setAttribute('aria-hidden', 'true');
    dot.style.cssText = 'position:fixed;left:0;top:0;width:22px;height:22px;margin:-11px 0 0 -11px;' +
      'border-radius:50%;background:rgba(239,68,68,.45);border:2px solid #ef4444;z-index:2147483647;' +
      'pointer-events:none;transition:transform .05s linear;display:none';
    document.body.appendChild(dot);
    window.__demoCursor = dot;
    window.addEventListener('mousemove', (e) => {
      dot.style.display = 'block';
      dot.style.transform = 'translate(' + e.clientX + 'px,' + e.clientY + 'px)';
    }, true);
    window.addEventListener('mousedown', () => { dot.style.background = 'rgba(239,68,68,.85)'; }, true);
    window.addEventListener('mouseup', () => { dot.style.background = 'rgba(239,68,68,.45)'; }, true);
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install);
  else install();
})();
`;

interface ScreenSize {
  width: number;
  height: number;
}

async function detectScreen(page: Page): Promise<ScreenSize> {
  const override = /^(\d+)x(\d+)$/.exec(settings.screen ?? "");
  if (override?.[1] && override[2]) {
    return { width: Number(override[1]), height: Number(override[2]) };
  }
  const size = await page.evaluate(() => ({
    width: window.screen.availWidth,
    height: window.screen.availHeight,
  }));
  return size;
}

async function setWindow(
  context: BrowserContext,
  page: Page,
  bounds: { left: number; top: number; width: number; height: number },
): Promise<void> {
  const cdp = await context.newCDPSession(page);
  try {
    const { windowId } = (await cdp.send("Browser.getWindowForTarget")) as { windowId: number };
    await cdp.send("Browser.setWindowBounds", { windowId, bounds: { windowState: "normal" } });
    await cdp.send("Browser.setWindowBounds", { windowId, bounds });
  } finally {
    await cdp.detach();
  }
}

export class PresentationStage implements Stage {
  readonly mode = "presentation" as const;
  private secondPage: Page | null = null;
  private secondBrowser: Browser | null = null;
  private secondContext: BrowserContext | null = null;
  private screen: ScreenSize = { width: 1920, height: 1080 };
  private currentLayout: Layout = "full";

  private constructor(
    private readonly browser: Browser,
    private readonly context: BrowserContext,
    readonly main: Page,
  ) {}

  static async create(): Promise<PresentationStage> {
    // Browser A is its own Chromium process. `viewport: null` makes the page follow the real window.
    const browser = await chromium.launch({
      headless: false,
      args: ["--window-position=0,0", "--force-device-scale-factor=1", "--disable-infobars"],
    });
    const context = await browser.newContext({ viewport: null });
    await context.addInitScript(CURSOR_SCRIPT);
    const page = await context.newPage();
    const stage = new PresentationStage(browser, context, page);
    await page.goto("about:blank");
    stage.screen = await detectScreen(page);
    await stage.layout("full");
    return stage;
  }

  second(): Page {
    if (!this.secondPage) throw new Error("second browser has not been opened");
    return this.secondPage;
  }

  pages(): Page[] {
    return this.secondPage ? [this.main, this.secondPage] : [this.main];
  }

  private bounds(side: "left" | "right" | "full") {
    const { width, height } = this.screen;
    if (side === "full") return { left: 0, top: 0, width, height };
    const half = Math.floor(width / 2);
    return side === "left"
      ? { left: 0, top: 0, width: half, height }
      : { left: half, top: 0, width: width - half, height };
  }

  async layout(kind: Layout): Promise<void> {
    this.currentLayout = kind;
    if (kind === "full") {
      await setWindow(this.context, this.main, this.bounds("full"));
    } else {
      await setWindow(this.context, this.main, this.bounds("left"));
      if (this.secondContext && this.secondPage) {
        await setWindow(this.secondContext, this.secondPage, this.bounds("right"));
      }
    }
    await this.main.bringToFront();
    if (this.secondPage) await this.secondPage.bringToFront();
  }

  async openSecond(userId: string, pagePath: string): Promise<Page> {
    const right = this.bounds("right");
    // A second Chromium process: separate cookie jar, storage and network stack from browser A.
    this.secondBrowser = await chromium.launch({
      headless: false,
      args: [
        `--window-position=${String(right.left)},${String(right.top)}`,
        `--window-size=${String(right.width)},${String(right.height)}`,
        "--force-device-scale-factor=1",
        "--disable-infobars",
      ],
    });
    this.secondContext = await this.secondBrowser.newContext({ viewport: null });
    await this.secondContext.addInitScript(CURSOR_SCRIPT);
    if (this.actionTimeoutMs > 0) this.secondContext.setDefaultTimeout(this.actionTimeoutMs);
    await signInContext(this.secondContext, userId);
    this.secondPage = await this.secondContext.newPage();
    await this.secondPage.goto(pagePath);
    if (this.currentLayout === "split") await this.layout("split");
    return this.secondPage;
  }

  async closeSecond(): Promise<void> {
    await this.secondContext?.close();
    await this.secondBrowser?.close();
    this.secondPage = this.secondContext = this.secondBrowser = null;
  }

  async setOffline(page: Page, offline: boolean): Promise<void> {
    await page.context().setOffline(offline);
  }

  private actionTimeoutMs = 0;
  /** Bound every action/navigation (Playwright's default inside a test with no timeout is "forever"). */
  setActionTimeout(ms: number): void {
    this.actionTimeoutMs = ms;
    this.context.setDefaultTimeout(ms);
    this.secondContext?.setDefaultTimeout(ms);
  }

  private pacing = 1;
  setPacing(factor: number): void {
    this.pacing = factor;
  }

  async pause(ms: number): Promise<void> {
    await this.main.waitForTimeout(Math.round(ms * settings.pace * this.pacing));
  }

  private async glide(target: Locator): Promise<void> {
    const page = target.page();
    await target.scrollIntoViewIfNeeded();
    const box = await target.boundingBox();
    if (!box) return;
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 22 });
    await page.waitForTimeout(150);
  }

  async click(target: Locator): Promise<void> {
    await this.glide(target);
    await target.click();
  }

  async fill(target: Locator, text: string): Promise<void> {
    await this.glide(target);
    await target.click();
    await target.fill("");
    await target.pressSequentially(text, { delay: 70 });
  }

  async select(target: Locator, option: { label: string } | { value: string }): Promise<void> {
    await this.glide(target);
    await target.selectOption(option);
  }

  async check(target: Locator, checked = true): Promise<void> {
    await this.glide(target);
    await target.setChecked(checked);
  }

  async reveal(target: Locator): Promise<void> {
    await target.evaluate((el) => {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
    });
    await target.page().waitForTimeout(700);
    await target.evaluate((el) => {
      const node = el as HTMLElement;
      const previous = node.style.cssText;
      node.style.transition = "outline-color .3s";
      node.style.outline = "3px solid #2563eb";
      node.style.outlineOffset = "3px";
      setTimeout(() => {
        node.style.cssText = previous;
      }, 1600);
    });
    await target.page().waitForTimeout(500);
  }

  async scrollTop(page: Page = this.main): Promise<void> {
    await page.evaluate(() => {
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
    await page.waitForTimeout(600);
  }

  async dispose(): Promise<void> {
    await this.closeSecond();
    await this.context.close();
    await this.browser.close();
  }
}

// ---------------------------------------------------------------------------------------------
// Validation stage: headless, instant
// ---------------------------------------------------------------------------------------------

export class ValidationStage implements Stage {
  readonly mode = "validation" as const;
  private secondPage: Page | null = null;
  private secondContext: BrowserContext | null = null;

  private constructor(
    private readonly browser: Browser,
    private readonly context: BrowserContext,
    readonly main: Page,
  ) {}

  static async create(browser: Browser): Promise<ValidationStage> {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    return new ValidationStage(browser, context, await context.newPage());
  }

  second(): Page {
    if (!this.secondPage) throw new Error("second browser has not been opened");
    return this.secondPage;
  }

  pages(): Page[] {
    return this.secondPage ? [this.main, this.secondPage] : [this.main];
  }

  async openSecond(userId: string, pagePath: string): Promise<Page> {
    this.secondContext = await this.browser.newContext({ viewport: { width: 1440, height: 900 } });
    await signInContext(this.secondContext, userId);
    this.secondPage = await this.secondContext.newPage();
    await this.secondPage.goto(pagePath);
    return this.secondPage;
  }

  async closeSecond(): Promise<void> {
    await this.secondContext?.close();
    this.secondPage = this.secondContext = null;
  }

  async setOffline(page: Page, offline: boolean): Promise<void> {
    await page.context().setOffline(offline);
  }

  layout(): Promise<void> {
    return Promise.resolve();
  }
  pause(): Promise<void> {
    return Promise.resolve();
  }
  setPacing(): void {
    // no pacing in validation mode
  }
  async click(target: Locator): Promise<void> {
    await target.click();
  }
  async fill(target: Locator, text: string): Promise<void> {
    await target.fill(text);
  }
  async select(target: Locator, option: { label: string } | { value: string }): Promise<void> {
    await target.selectOption(option);
  }
  async check(target: Locator, checked = true): Promise<void> {
    await target.setChecked(checked);
  }
  reveal(): Promise<void> {
    return Promise.resolve();
  }
  scrollTop(): Promise<void> {
    return Promise.resolve();
  }

  async dispose(): Promise<void> {
    await this.closeSecond();
    await this.context.close();
  }
}
