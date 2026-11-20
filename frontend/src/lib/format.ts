/** The company's business time zone. All calendar dates and times are shown in it. */
export const COMPANY_TZ = "America/Chicago";

const dateTime = new Intl.DateTimeFormat("en-US", {
  timeZone: COMPANY_TZ,
  dateStyle: "medium",
  timeStyle: "short",
});
const shortDate = new Intl.DateTimeFormat("en-US", {
  timeZone: "UTC",
  month: "short",
  day: "numeric",
});
const longDate = new Intl.DateTimeFormat("en-US", {
  timeZone: "UTC",
  month: "short",
  day: "numeric",
  year: "numeric",
});

/** Format an ISO instant in company time, e.g. "Nov 11, 2026, 9:00 AM". */
export function formatInstant(iso: string): string {
  return dateTime.format(new Date(iso));
}

/** Format a calendar date (YYYY-MM-DD) without any timezone shifting, e.g. "Nov 11". */
export function formatDay(day: string): string {
  return shortDate.format(new Date(`${day}T00:00:00Z`));
}

/** Format a calendar date including the year. */
export function formatDayLong(day: string): string {
  return longDate.format(new Date(`${day}T00:00:00Z`));
}

/** Add whole days to a YYYY-MM-DD date. */
export function addDays(day: string, days: number): string {
  const date = new Date(`${day}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

/** mm:ss for a non-negative number of seconds. */
export function formatClock(totalSeconds: number): string {
  const seconds = Math.max(0, Math.floor(totalSeconds));
  const minutes = Math.floor(seconds / 60);
  return `${String(minutes).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}
