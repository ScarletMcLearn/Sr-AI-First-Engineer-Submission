"use client";

import { AlertTriangle, CheckCircle2, Clock, Loader2, Pencil } from "lucide-react";
import * as React from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { errorMessage } from "@/lib/api/client";
import type { Cell, MeasurableRow, MeasurableStatus } from "@/lib/api/types";
import { formatDay } from "@/lib/format";
import { useMakeIssue, useScorecard, useSetScore } from "@/lib/queries";
import { cn } from "@/lib/utils";

const STATUS: Record<
  MeasurableStatus,
  { label: string; className: string; Icon: typeof CheckCircle2 }
> = {
  on_track: { label: "On track", className: "bg-success-bg text-success", Icon: CheckCircle2 },
  off_track: { label: "Off track", className: "bg-danger-bg text-danger", Icon: AlertTriangle },
  pending: { label: "Pending", className: "bg-warning-bg text-warning", Icon: Clock },
};

function goalText(row: MeasurableRow): string {
  const { goal, unit } = row;
  switch (goal.type) {
    case "at_least":
      return `≥ ${String(goal.value)} ${unit}`;
    case "at_most":
      return `≤ ${String(goal.value)} ${unit}`;
    case "exactly":
      return `= ${String(goal.value)} ${unit}`;
    case "between":
      return `${String(goal.min)}–${String(goal.max)} ${unit}`;
  }
}

interface ScorecardProps {
  teamId: string;
  canWrite: boolean;
  /** Week highlighted as the one under review (the last closed week in a meeting). */
  reviewWeek?: string;
  onIssueFocus?: (issueId: string) => void;
}

export function Scorecard({ teamId, canWrite, reviewWeek, onIssueFocus }: ScorecardProps) {
  const scorecard = useScorecard(teamId);

  if (scorecard.isPending) {
    return (
      <Card aria-busy="true">
        <CardHeader>
          <CardTitle>Scorecard</CardTitle>
        </CardHeader>
        <CardContent className="text-muted-foreground flex items-center gap-2 text-sm">
          <Loader2 className="size-4 animate-spin" aria-hidden /> Loading scorecard…
        </CardContent>
      </Card>
    );
  }
  if (scorecard.isError) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Scorecard</CardTitle>
        </CardHeader>
        <CardContent role="alert" className="text-danger text-sm">
          {errorMessage(scorecard.error)}{" "}
          <Button
            variant="link"
            className="h-auto p-0"
            onClick={() => {
              void scorecard.refetch();
            }}
          >
            Retry
          </Button>
        </CardContent>
      </Card>
    );
  }

  const { weeks, measurables, current_week: currentWeek } = scorecard.data;
  return (
    <Card aria-labelledby="scorecard-title">
      <CardHeader>
        <CardTitle id="scorecard-title">Scorecard</CardTitle>
        <span className="text-muted-foreground text-sm">
          Last 13 weeks · weeks start Monday · {canWrite ? "click a score to edit" : "read-only"}
        </span>
      </CardHeader>
      <CardContent>
        <div
          className="overflow-x-auto rounded-md border"
          // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex -- a scrollable region must be keyboard-focusable (WCAG 2.1.1)
          tabIndex={0}
          role="region"
          aria-label="Scorecard table, scrolls horizontally"
        >
          <table className="w-max min-w-full border-collapse text-sm">
            <caption className="sr-only">
              Weekly scores per measurable for the last 13 weeks, including the current week
            </caption>
            <thead>
              <tr>
                <th
                  scope="col"
                  className="bg-card sticky top-0 left-0 z-30 min-w-56 border-r border-b p-2 text-left font-semibold"
                >
                  Measurable
                </th>
                {weeks.map((week) => (
                  <th
                    key={week}
                    scope="col"
                    className={cn(
                      "bg-card sticky top-0 z-20 min-w-28 border-b p-2 text-center font-medium",
                      week === reviewWeek && "bg-accent",
                    )}
                  >
                    <span className="block">{formatDay(week)}</span>
                    {week === currentWeek && (
                      <span className="text-muted-foreground block text-xs">current</span>
                    )}
                    {week === reviewWeek && (
                      <span className="text-accent-foreground block text-xs font-semibold">
                        reviewing
                      </span>
                    )}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {measurables.map((row) => (
                <tr key={row.id}>
                  <th
                    scope="row"
                    className="bg-card sticky left-0 z-10 border-r border-b p-2 text-left font-normal"
                  >
                    <span className="block font-semibold">{row.name}</span>
                    <span className="text-muted-foreground block text-xs">
                      {row.owner.name} · goal {goalText(row)}
                    </span>
                  </th>
                  {row.cells.map((cell) => (
                    <ScoreCell
                      key={cell.week_start}
                      teamId={teamId}
                      row={row}
                      cell={cell}
                      canWrite={canWrite}
                      highlighted={cell.week_start === reviewWeek}
                      onIssueFocus={onIssueFocus}
                    />
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}

interface ScoreCellProps {
  teamId: string;
  row: MeasurableRow;
  cell: Cell;
  canWrite: boolean;
  highlighted: boolean;
  onIssueFocus?: (issueId: string) => void;
}

function ScoreCell({ teamId, row, cell, canWrite, highlighted, onIssueFocus }: ScoreCellProps) {
  const toast = useToast();
  const setScore = useSetScore(teamId);
  const makeIssue = useMakeIssue(teamId);
  const [editing, setEditing] = React.useState(false);
  const [draft, setDraft] = React.useState("");
  const [fieldError, setFieldError] = React.useState<string | null>(null);
  const inputRef = React.useRef<HTMLInputElement>(null);
  React.useEffect(() => {
    if (editing) inputRef.current?.focus();
  }, [editing]);
  const status = STATUS[cell.status];
  const label = `${row.name}, week of ${formatDay(cell.week_start)}`;

  const startEditing = () => {
    setDraft(cell.value === null ? "" : String(cell.value));
    setFieldError(null);
    setEditing(true);
  };

  const save = () => {
    const trimmed = draft.trim();
    if (trimmed === "" || Number.isNaN(Number(trimmed))) {
      setFieldError("Enter a number");
      return;
    }
    const value = Number(trimmed);
    if (cell.value !== null && value === cell.value) {
      setEditing(false);
      return;
    }
    setScore.mutate(
      { measurableId: row.id, weekStart: cell.week_start, value },
      {
        onSuccess: () => {
          setEditing(false);
          toast.success(`Saved ${label}`);
        },
        onError: (error) => {
          setFieldError(errorMessage(error));
        },
      },
    );
  };

  const onMakeIssue = () => {
    makeIssue.mutate(
      { measurableId: row.id, weekStart: cell.week_start },
      {
        onSuccess: ({ issue, created }) => {
          toast.success(
            created ? `Issue created: ${issue.title}` : `Issue already open: ${issue.title}`,
          );
          onIssueFocus?.(issue.id);
        },
        onError: (error) => {
          toast.error(errorMessage(error));
        },
      },
    );
  };

  return (
    <td
      className={cn("border-b p-1.5 align-top", highlighted && "bg-accent/40")}
      data-testid={`cell-${row.id}-${cell.week_start}`}
    >
      <div className={cn("rounded-md p-1.5 text-center", status.className)}>
        {editing ? (
          <form
            onSubmit={(event) => {
              event.preventDefault();
              save();
            }}
            className="flex flex-col gap-1"
          >
            <Input
              ref={inputRef}
              inputMode="decimal"
              aria-label={`Score for ${label}`}
              aria-invalid={fieldError !== null}
              aria-describedby={fieldError ? `err-${row.id}-${cell.week_start}` : undefined}
              value={draft}
              disabled={setScore.isPending}
              onChange={(event) => {
                setDraft(event.target.value);
              }}
              onKeyDown={(event) => {
                if (event.key === "Escape") setEditing(false);
              }}
              className="h-8 text-center"
            />
            {fieldError && (
              <span id={`err-${row.id}-${cell.week_start}`} role="alert" className="text-xs">
                {fieldError}
              </span>
            )}
            <div className="flex justify-center gap-1">
              <Button type="submit" size="sm" disabled={setScore.isPending}>
                {setScore.isPending && <Loader2 className="animate-spin" aria-hidden />}
                Save
              </Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={setScore.isPending}
                onClick={() => {
                  setEditing(false);
                }}
              >
                Cancel
              </Button>
            </div>
          </form>
        ) : (
          <>
            {canWrite ? (
              <button
                type="button"
                onClick={startEditing}
                aria-label={`Edit score for ${label}: ${cell.value === null ? "no score" : String(cell.value)}, ${status.label}`}
                className="group flex w-full items-center justify-center gap-1 rounded-sm text-base font-semibold"
              >
                {cell.value ?? "—"}
                <Pencil
                  className="size-3 opacity-0 group-hover:opacity-60 group-focus-visible:opacity-60"
                  aria-hidden
                />
              </button>
            ) : (
              <span className="text-base font-semibold">
                <span className="sr-only">{label}: </span>
                {cell.value ?? "—"}
              </span>
            )}
            <span className="mt-0.5 flex items-center justify-center gap-1 text-xs font-medium">
              <status.Icon className="size-3" aria-hidden />
              {status.label}
            </span>
          </>
        )}
      </div>
      {cell.status === "off_track" && !editing && (
        <div className="mt-1 flex flex-col items-center gap-1">
          {cell.issue_id && (
            <Badge variant="outline" data-testid={`issue-badge-${row.id}-${cell.week_start}`}>
              Issue open
            </Badge>
          )}
          {canWrite && (
            <Button
              size="sm"
              variant="outline"
              className="h-7 px-2 text-xs"
              disabled={makeIssue.isPending}
              onClick={onMakeIssue}
              aria-label={`Make it an Issue: ${label}`}
            >
              {makeIssue.isPending && <Loader2 className="animate-spin" aria-hidden />}
              Make it an Issue
            </Button>
          )}
        </div>
      )}
    </td>
  );
}
