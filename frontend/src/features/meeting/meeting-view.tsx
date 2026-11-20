"use client";

import { CheckCircle2, Circle, Loader2, Radio, WifiOff } from "lucide-react";
import Link from "next/link";
import * as React from "react";

import { AppShell } from "@/components/app-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useToast } from "@/components/ui/toast";
import { ApiError, errorMessage } from "@/lib/api/client";
import type { Me, MeetingState } from "@/lib/api/types";
import { formatClock, formatDay, formatInstant } from "@/lib/format";
import { useIssues, useScorecard, useTeam, useTodos } from "@/lib/queries";
import { cn } from "@/lib/utils";
import { IssuesPanel } from "@/features/issues/issues-panel";
import { Scorecard } from "@/features/scorecard/scorecard";
import { TodosPanel } from "@/features/todos/todos-panel";

import {
  useAdvanceMeeting,
  useEndMeeting,
  useJoinMeeting,
  useMeeting,
  useRateMeeting,
  useSectionClock,
  type Connection,
  type MeetingSnapshot,
} from "./use-meeting";

const ROLE_LABEL = { admin: "Admin", team_member: "Team Member", observer: "Observer" } as const;

export function MeetingView({ meetingId, me }: { meetingId: string; me: Me }) {
  const { snapshot, connection, error } = useMeeting(meetingId);
  return (
    <AppShell me={me} teamId={snapshot?.state.team_id}>
      <MeetingContent
        meetingId={meetingId}
        me={me}
        snapshot={snapshot}
        connection={connection}
        error={error}
      />
    </AppShell>
  );
}

interface MeetingContentProps {
  meetingId: string;
  me: Me;
  snapshot: MeetingSnapshot | undefined;
  connection: Connection;
  error: Error | null;
}

function MeetingContent({ meetingId, me, snapshot, connection, error }: MeetingContentProps) {
  const join = useJoinMeeting(meetingId);
  const joined = React.useRef(false);
  const state = snapshot?.state;
  const isAttendee = state?.attendees.some((a) => a.user.id === me.user.id) ?? false;

  // Anyone who can read the team may join; the server makes this idempotent.
  React.useEffect(() => {
    if (state?.status === "active" && !isAttendee && !joined.current) {
      joined.current = true;
      join.mutate(undefined);
    }
  }, [state?.status, isAttendee, join]);

  if (error) {
    const status = error instanceof ApiError ? error.status : 0;
    return (
      <Card>
        <CardContent role="alert" className="space-y-2 pt-4">
          <h1 className="text-lg font-semibold">
            {status === 403 || status === 404
              ? "This meeting is not available to you"
              : "Could not load the meeting"}
          </h1>
          <p className="text-muted-foreground text-sm">{errorMessage(error)}</p>
          <Button asChild variant="outline">
            <Link href="/">Back to your teams</Link>
          </Button>
        </CardContent>
      </Card>
    );
  }
  if (!snapshot || !state) {
    return (
      <p className="text-muted-foreground flex items-center gap-2 text-sm" aria-busy="true">
        <Loader2 className="size-4 animate-spin" aria-hidden /> Loading meeting…
      </p>
    );
  }
  return <MeetingBody snapshot={snapshot} connection={connection} me={me} />;
}

function MeetingBody({
  snapshot,
  connection,
  me,
}: {
  snapshot: MeetingSnapshot;
  connection: Connection;
  me: Me;
}) {
  const { state } = snapshot;
  const team = useTeam(state.team_id);
  const canWrite = me.user.role !== "observer";
  const isFacilitator = state.facilitator.id === me.user.id;
  const ended = state.status === "ended";

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold">
          Level 10 Meeting{team.data ? ` · ${team.data.name}` : ""}
        </h1>
        <Badge variant={ended ? "secondary" : "success"} data-testid="meeting-status">
          {ended ? "Ended" : "In progress"}
        </Badge>
        {!ended && <ConnectionBadge connection={connection} />}
        <Button asChild variant="ghost" size="sm" className="ml-auto">
          <Link href={`/teams/${state.team_id}`}>← Team page</Link>
        </Button>
      </div>

      <div className="grid gap-4 lg:grid-cols-[22rem_1fr]">
        <aside
          className="space-y-4 lg:sticky lg:top-16 lg:self-start"
          aria-label="Meeting controls"
        >
          <Agenda state={state} />
          {!ended && <TimerCard snapshot={snapshot} />}
          {!ended && (
            <FacilitatorControls state={state} isFacilitator={isFacilitator} canWrite={canWrite} />
          )}
          <Attendees state={state} meId={me.user.id} />
        </aside>
        <section className="space-y-4" aria-label="Current section">
          {ended ? (
            <SummaryView state={state} />
          ) : (
            team.data && (
              <SectionContent state={state} team={team.data} canWrite={canWrite} me={me} />
            )
          )}
        </section>
      </div>
    </div>
  );
}

function ConnectionBadge({ connection }: { connection: Connection }) {
  if (connection === "live") {
    return (
      <Badge variant="outline" data-testid="connection-status">
        <Radio className="size-3" aria-hidden /> Live
      </Badge>
    );
  }
  return (
    <Badge variant="warning" role="status" data-testid="connection-status">
      <WifiOff className="size-3" aria-hidden />
      {connection === "connecting" ? "Connecting…" : "Reconnecting…"}
    </Badge>
  );
}

function Agenda({ state }: { state: MeetingState }) {
  const ended = state.status === "ended";
  return (
    <Card aria-labelledby="agenda-title">
      <CardHeader>
        <CardTitle id="agenda-title">Agenda</CardTitle>
      </CardHeader>
      <CardContent>
        <ol className="space-y-1">
          {state.sections.map((section, index) => {
            const done = ended || index < state.section_index;
            const current = !ended && index === state.section_index;
            return (
              <li
                key={section.key}
                aria-current={current ? "step" : undefined}
                data-testid={`agenda-${section.key}`}
                className={cn(
                  "flex items-center gap-2 rounded-md px-3 py-2",
                  current ? "bg-primary text-primary-foreground font-semibold" : "text-foreground",
                )}
              >
                {done ? (
                  <CheckCircle2 className="size-4" aria-hidden />
                ) : (
                  <Circle className="size-4" aria-hidden />
                )}
                <span className="flex-1">{section.title}</span>
                <span className={cn("text-xs", current ? "" : "text-muted-foreground")}>
                  {section.planned_seconds / 60} min
                </span>
                <span className="sr-only">
                  {done ? "(done)" : current ? "(current section)" : "(upcoming)"}
                </span>
              </li>
            );
          })}
        </ol>
      </CardContent>
    </Card>
  );
}

function TimerCard({ snapshot }: { snapshot: MeetingSnapshot }) {
  const { state } = snapshot;
  const elapsed = useSectionClock(snapshot);
  const planned = state.section_planned_seconds;
  const over = elapsed > planned;
  const section = state.sections[state.section_index];
  return (
    <Card aria-labelledby="timer-title" className={cn(over && "border-danger")}>
      <CardHeader>
        <CardTitle id="timer-title">{section?.title ?? "Section"} timer</CardTitle>
      </CardHeader>
      <CardContent>
        <div
          role="timer"
          aria-label={`${section?.title ?? "Section"} elapsed time`}
          data-testid="timer"
          className={cn(
            "text-5xl font-bold tabular-nums",
            over ? "text-danger" : "text-foreground",
          )}
        >
          {formatClock(elapsed)}
        </div>
        <p className="text-muted-foreground mt-1 text-sm" data-testid="timer-detail">
          of {formatClock(planned)} planned
        </p>
        {over && (
          <p className="text-danger mt-1 font-semibold" role="status" data-testid="overtime">
            Over time by {formatClock(elapsed - planned)}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

function FacilitatorControls({
  state,
  isFacilitator,
  canWrite,
}: {
  state: MeetingState;
  isFacilitator: boolean;
  canWrite: boolean;
}) {
  const toast = useToast();
  const advance = useAdvanceMeeting(state.id);
  const end = useEndMeeting(state.id);
  const [confirmEnd, setConfirmEnd] = React.useState(false);
  const next = state.sections[state.section_index + 1];

  const report = (error: Error) => {
    toast.error(error.message);
  };

  return (
    <Card aria-labelledby="controls-title">
      <CardHeader>
        <CardTitle id="controls-title">Facilitator</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <p className="text-sm" data-testid="facilitator-name">
          {state.facilitator.name}
          {isFacilitator && " (you)"}
        </p>
        {isFacilitator ? (
          <div className="flex flex-col gap-2">
            {next && (
              <Button
                onClick={() => {
                  advance.mutate(state.version, { onError: report });
                }}
                disabled={advance.isPending || end.isPending}
              >
                {advance.isPending && <Loader2 className="animate-spin" aria-hidden />}
                Next: {next.title}
              </Button>
            )}
            <Button
              variant="destructive"
              onClick={() => {
                setConfirmEnd(true);
              }}
              disabled={end.isPending}
            >
              End meeting
            </Button>
            <Dialog open={confirmEnd} onOpenChange={setConfirmEnd}>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>End the meeting?</DialogTitle>
                  <DialogDescription>
                    Everyone will see the summary and ratings become final. This can&apos;t be
                    undone.
                  </DialogDescription>
                </DialogHeader>
                <DialogFooter>
                  <DialogClose asChild>
                    <Button variant="outline">Keep going</Button>
                  </DialogClose>
                  <Button
                    variant="destructive"
                    disabled={end.isPending}
                    onClick={() => {
                      end.mutate(state.version, {
                        onSuccess: () => {
                          setConfirmEnd(false);
                        },
                        onError: report,
                      });
                    }}
                  >
                    {end.isPending && <Loader2 className="animate-spin" aria-hidden />}
                    End meeting
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        ) : (
          <p className="text-muted-foreground text-sm">
            {canWrite
              ? "Only the facilitator can move the agenda or end the meeting."
              : "You're observing. Only the facilitator controls the meeting."}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

function Attendees({ state, meId }: { state: MeetingState; meId: string }) {
  return (
    <Card aria-labelledby="attendees-title">
      <CardHeader>
        <CardTitle id="attendees-title">Attendees ({state.attendees.length})</CardTitle>
      </CardHeader>
      <CardContent>
        <ul className="space-y-1" data-testid="attendees">
          {state.attendees.map((a) => (
            <li key={a.user.id} className="flex items-center gap-2 text-sm">
              <span className="flex-1">
                {a.user.name}
                {a.user.id === meId && " (you)"}
                {a.user.id === state.facilitator.id && " · facilitator"}
              </span>
              <Badge variant="secondary">{ROLE_LABEL[a.user.role]}</Badge>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

function SectionContent({
  state,
  team,
  canWrite,
  me,
}: {
  state: MeetingState;
  team: NonNullable<ReturnType<typeof useTeam>["data"]>;
  canWrite: boolean;
  me: Me;
}) {
  const [focusedIssue, setFocusedIssue] = React.useState<string | null>(null);
  const section = state.section_key;
  return (
    <>
      <h2 className="text-xl font-semibold" data-testid="current-section">
        {state.sections[state.section_index]?.title}
      </h2>
      {section === "scorecard" && (
        <>
          <p className="text-muted-foreground text-sm">
            Review the last closed week (week of {formatDay(state.scorecard_week)}). Use “Make it an
            Issue” on off-track scores.
          </p>
          <Scorecard
            teamId={state.team_id}
            canWrite={canWrite}
            reviewWeek={state.scorecard_week}
            onIssueFocus={setFocusedIssue}
          />
          <IssuesPanel
            teamId={state.team_id}
            team={team}
            canWrite={canWrite}
            meetingId={state.id}
            highlightIssueId={focusedIssue}
          />
        </>
      )}
      {section === "ids" && (
        <>
          <p className="text-muted-foreground text-sm">
            Work the list from the top. Solve Issues and add follow-up To-Dos.
          </p>
          <IssuesPanel
            teamId={state.team_id}
            team={team}
            canWrite={canWrite}
            meetingId={state.id}
            highlightIssueId={focusedIssue}
          />
          <TodosPanel teamId={state.team_id} canWrite={canWrite} onlyMeetingId={state.id} />
        </>
      )}
      {section === "conclude" && (
        <>
          <TodosPanel teamId={state.team_id} canWrite={canWrite} onlyMeetingId={state.id} />
          <RatingPanel state={state} canRate={canWrite} meId={me.user.id} />
        </>
      )}
    </>
  );
}

function RatingPanel({
  state,
  canRate,
  meId,
}: {
  state: MeetingState;
  canRate: boolean;
  meId: string;
}) {
  const toast = useToast();
  const rate = useRateMeeting(state.id);
  const mine = state.attendees.find((a) => a.user.id === meId)?.rating ?? null;
  const rated = state.attendees.filter((a) => a.rating !== null);
  return (
    <Card aria-labelledby="rating-title">
      <CardHeader>
        <CardTitle id="rating-title">Rate this meeting</CardTitle>
        <span className="text-muted-foreground text-sm">
          1 = poor, 10 = excellent. You can change it until the meeting ends.
        </span>
      </CardHeader>
      <CardContent className="space-y-3">
        {canRate ? (
          <div role="group" aria-label="Your rating" className="flex flex-wrap gap-1">
            {Array.from({ length: 10 }, (_, i) => i + 1).map((value) => (
              <Button
                key={value}
                size="icon"
                variant={mine === value ? "default" : "outline"}
                aria-pressed={mine === value}
                aria-label={`Rate ${String(value)}`}
                disabled={rate.isPending}
                onClick={() => {
                  rate.mutate(value, {
                    onError: (error) => {
                      toast.error(error.message);
                    },
                  });
                }}
              >
                {value}
              </Button>
            ))}
          </div>
        ) : (
          <p className="text-muted-foreground text-sm">Observers can&apos;t rate meetings.</p>
        )}
        <div data-testid="ratings">
          <p className="text-sm">
            Average:{" "}
            <strong data-testid="average-rating">
              {state.average_rating === null ? "no ratings yet" : state.average_rating.toFixed(1)}
            </strong>{" "}
            ({rated.length} of {state.attendees.filter((a) => a.user.role !== "observer").length}{" "}
            possible raters)
          </p>
          <ul className="text-muted-foreground mt-1 text-sm">
            {rated.map((a) => (
              <li key={a.user.id}>
                {a.user.name}: {a.rating}
              </li>
            ))}
          </ul>
        </div>
      </CardContent>
    </Card>
  );
}

function SummaryView({ state }: { state: MeetingState }) {
  const summary = state.summary;
  const scorecard = useScorecard(state.team_id);
  const solved = useIssues(state.team_id, "solved");
  const todos = useTodos(state.team_id);
  if (!summary) {
    return <p className="text-muted-foreground text-sm">Summary unavailable.</p>;
  }
  const names = new Map(scorecard.data?.measurables.map((m) => [m.id, m.name]));
  const issueTitles = new Map(solved.data?.map((i) => [i.id, i.title]));
  const todoTitles = new Map(todos.data?.todos.map((t) => [t.id, t.title]));
  const attendeeNames = new Map(state.attendees.map((a) => [a.user.id, a.user.name]));

  return (
    <Card aria-labelledby="summary-title" data-testid="summary">
      <CardHeader>
        <CardTitle id="summary-title">Meeting summary</CardTitle>
        {state.ended_at && (
          <span className="text-muted-foreground text-sm">
            Ended {formatInstant(state.ended_at)}
          </span>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        <section aria-labelledby="sum-score">
          <h3 id="sum-score" className="font-semibold">
            Scorecard — week of {formatDay(summary.scorecard_week)}
          </h3>
          <ul className="mt-1 grid gap-1 sm:grid-cols-2">
            {Object.entries(summary.measurable_status).map(([id, status]) => (
              <li key={id} className="flex items-center gap-2 text-sm">
                <Badge
                  variant={
                    status === "on_track"
                      ? "success"
                      : status === "off_track"
                        ? "danger"
                        : "warning"
                  }
                >
                  {status === "on_track"
                    ? "On track"
                    : status === "off_track"
                      ? "Off track"
                      : "Pending"}
                </Badge>
                {names.get(id) ?? id}
              </li>
            ))}
          </ul>
        </section>
        <section aria-labelledby="sum-issues">
          <h3 id="sum-issues" className="font-semibold">
            Issues solved ({summary.issues_solved.length})
          </h3>
          <ul className="list-disc pl-5 text-sm">
            {summary.issues_solved.length === 0 && <li className="list-none">None</li>}
            {summary.issues_solved.map((id) => (
              <li key={id}>{issueTitles.get(id) ?? id}</li>
            ))}
          </ul>
        </section>
        <section aria-labelledby="sum-todos">
          <h3 id="sum-todos" className="font-semibold">
            To-Dos created ({summary.todos_created.length})
          </h3>
          <ul className="list-disc pl-5 text-sm">
            {summary.todos_created.length === 0 && <li className="list-none">None</li>}
            {summary.todos_created.map((id) => (
              <li key={id}>{todoTitles.get(id) ?? id}</li>
            ))}
          </ul>
        </section>
        <section aria-labelledby="sum-att">
          <h3 id="sum-att" className="font-semibold">
            Attendees ({summary.attendee_ids.length})
          </h3>
          <p className="text-sm">
            {summary.attendee_ids.map((id) => attendeeNames.get(id) ?? id).join(", ")}
          </p>
        </section>
        <section aria-labelledby="sum-rating">
          <h3 id="sum-rating" className="font-semibold">
            Meeting rating
          </h3>
          <p className="text-2xl font-semibold" data-testid="summary-rating">
            {summary.rating === null ? "No ratings" : summary.rating.toFixed(1)}
          </p>
        </section>
      </CardContent>
    </Card>
  );
}
