/**
 * Configuration for the automated assessment demonstration.
 *
 * Scene titles, target durations and narration cues live here so that the test, the terminal
 * teleprompter and docs/DEMO_NARRATION_SCRIPT.md describe the same demonstration.
 */

export interface SceneConfig {
  id: string;
  title: string;
  /** Target duration in seconds (presentation mode). */
  targetSeconds: number;
  /** Multiplier applied to every pause in the scene (presentation mode), tuned from measured runs. */
  pacing: number;
  /** Short narration cues, printed to the terminal as the scene starts (never shown in the app). */
  cues: string[];
}

export const SCENES: Record<string, SceneConfig> = {
  intro: {
    id: "intro",
    title: "Introduction",
    targetSeconds: 25,
    pacing: 2.8,
    cues: [
      "Level 10 meetings app. Seeded user Casey Cho, Team Member of Leadership.",
      "Five modules on one Team Page: Scorecard, Issues, To-Dos, Rocks, Meetings.",
    ],
  },
  scorecard: {
    id: "scorecard",
    title: "Scorecard",
    targetSeconds: 55,
    pacing: 3.8,
    cues: [
      "13 weeks of history. Status is computed on the server from the data and a frozen business clock.",
      "Missing score in a closed week = off track. Missing score in the current week = pending.",
      "Enter 10 for a goal of at least 10: the boundary is inclusive, so it is on track.",
      "Make it an Issue from an off-track score; doing it twice returns the same Issue.",
    ],
  },
  issues: {
    id: "issues",
    title: "Issues and To-Dos",
    targetSeconds: 55,
    pacing: 3.1,
    cues: [
      "Issues are ordered by priority, then oldest first; unprioritised last.",
      "A To-Do linked to an Issue is due in seven days. Observers can never own To-Dos.",
      "Solving an Issue requires a resolution note.",
    ],
  },
  rocks: {
    id: "rocks",
    title: "Rocks",
    targetSeconds: 25,
    pacing: 3.8,
    cues: [
      "Rock status and progress are derived from Milestones, never stored.",
      "Expand a Rock to see its Milestones.",
    ],
  },
  meeting: {
    id: "meeting",
    title: "Two-Browser Meeting",
    targetSeconds: 55,
    pacing: 7.5,
    cues: [
      "Two separate browser processes, two seeded users, no shared cookies.",
      "Casey starts the meeting and becomes facilitator. Blake joins from his own browser.",
    ],
  },
  sync: {
    id: "sync",
    title: "Live Synchronization",
    targetSeconds: 55,
    pacing: 3.8,
    cues: [
      "The facilitator advances the agenda; the second browser follows without a reload.",
      "Updates travel over Server-Sent Events, fed by PostgreSQL LISTEN/NOTIFY.",
      "A participant has no facilitator controls. The server enforces this too.",
      "Solving an Issue in one browser appears in the other.",
    ],
  },
  reconnect: {
    id: "reconnect",
    title: "Reconnection",
    targetSeconds: 28,
    pacing: 3.4,
    cues: [
      "Reload: the section and the server-owned timer are recovered.",
      "Go offline, miss a section change, come back: the full state is re-fetched.",
    ],
  },
  summary: {
    id: "summary",
    title: "Ratings and Summary",
    targetSeconds: 45,
    pacing: 3.6,
    cues: [
      "Ratings only in Conclude. 8 and 9 give an average of 8.5.",
      "Ending the meeting stores an immutable summary snapshot; ratings become final.",
      "Reload: the summary is read from the database.",
    ],
  },
  architecture: {
    id: "architecture",
    title: "Architecture",
    targetSeconds: 35,
    pacing: 1.4,
    cues: [
      "PostgreSQL with constraints, FastAPI REST, Next.js and TypeScript.",
      "SSE with LISTEN/NOTIFY; partial unique indexes guard concurrency.",
      "Deterministic rules report, automated tests and CI.",
    ],
  },
};

export const SCENE_ORDER = [
  "intro",
  "scorecard",
  "issues",
  "rocks",
  "meeting",
  "sync",
  "reconnect",
  "summary",
  "architecture",
] as const;

/**
 * Manual (scene-by-scene) mode: scenes that must have passed before a scene may run. Nothing runs
 * implicitly. `issues` solves the Issue made in `scorecard`; the meeting summary then reports it.
 */
export const PREREQUISITES: Record<string, readonly string[]> = {
  issues: ["scorecard"],
  meeting: ["issues"],
  sync: ["meeting"],
  reconnect: ["sync"],
  summary: ["reconnect"],
};

export const CONTROL_PORT = Number(process.env.DEMO_CONTROL_PORT ?? 8199);

/** Hard limit from the assessment brief, and the margin the presentation aims to stay inside. */
export const LIMIT_SECONDS = 7 * 60;
export const SOFT_LIMIT_SECONDS = 6 * 60 + 30;

export const API_URL = "http://localhost:8100";

/** Seeded users (see seed.json). Only real seeded identities are used. */
export const USER_IDS = { facilitator: "u3", participant: "u2" } as const; // Casey Cho, Blake Brooks

function envNumber(name: string, fallback: number): number {
  const raw = process.env[name];
  const parsed = raw === undefined ? NaN : Number(raw);
  return Number.isFinite(parsed) ? parsed : fallback;
}

export const settings = {
  /** Seconds to wait after the first page is ready, so the recording can settle before scene 1. */
  startDelaySeconds: envNumber("DEMO_START_DELAY", 5),
  /** Multiplier for every presentation pause (1 = authored pacing). */
  pace: envNumber("DEMO_PACE", 1),
  /**
   * Extra multiplier for manual mode only (on top of `pace`): the operator narrates between scenes,
   * so in-scene pauses are shortened. 1 = same pauses as the automatic demonstration.
   */
  manualPace: envNumber("DEMO_MANUAL_PACE", 0.4),
  /** Optional "WIDTHxHEIGHT" override of the detected screen size, e.g. "1920x1080". */
  screen: process.env.DEMO_SCREEN,
  /** Passing CI status injected by demo/run.mjs ("success", "unknown", ...). */
  ciStatus: process.env.DEMO_CI_STATUS ?? "unknown",
  ciSha: process.env.DEMO_CI_SHA ?? "",
};
