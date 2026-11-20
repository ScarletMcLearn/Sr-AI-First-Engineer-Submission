"use client";

import { Loader2, Play, Video } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import * as React from "react";

import { AppShell, useRequireMe } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useToast } from "@/components/ui/toast";
import { ApiError, errorMessage } from "@/lib/api/client";
import { formatInstant } from "@/lib/format";
import { useActiveMeeting, useStartMeeting, useTeam, useTeamMeetings } from "@/lib/queries";
import { IssuesPanel } from "@/features/issues/issues-panel";
import { RocksPanel } from "@/features/rocks/rocks-panel";
import { Scorecard } from "@/features/scorecard/scorecard";
import { TodosPanel } from "@/features/todos/todos-panel";

export default function TeamPage() {
  const { teamId } = useParams<{ teamId: string }>();
  const { me, isLoading } = useRequireMe();

  if (isLoading || !me) {
    return (
      <p className="text-muted-foreground flex items-center gap-2 p-6 text-sm" aria-busy="true">
        <Loader2 className="size-4 animate-spin" aria-hidden /> Loading…
      </p>
    );
  }
  return (
    <AppShell me={me} teamId={teamId}>
      <TeamContent
        teamId={teamId}
        canWrite={me.user.role !== "observer"}
        firstTeamId={me.teams[0]?.id}
      />
    </AppShell>
  );
}

function TeamContent({
  teamId,
  canWrite,
  firstTeamId,
}: {
  teamId: string;
  canWrite: boolean;
  firstTeamId: string | undefined;
}) {
  const team = useTeam(teamId);
  const [focusedIssue, setFocusedIssue] = React.useState<string | null>(null);

  if (team.isPending) {
    return (
      <p className="text-muted-foreground flex items-center gap-2 text-sm" aria-busy="true">
        <Loader2 className="size-4 animate-spin" aria-hidden /> Loading team…
      </p>
    );
  }
  if (team.isError) {
    const denied =
      team.error instanceof ApiError && (team.error.status === 403 || team.error.status === 404);
    return (
      <Card>
        <CardContent role="alert" className="space-y-2 pt-4">
          <h1 className="text-lg font-semibold">
            {denied ? "You don't have access to this team" : "Could not load this team"}
          </h1>
          <p className="text-muted-foreground text-sm">{errorMessage(team.error)}</p>
          {firstTeamId && (
            <Button asChild variant="outline">
              <Link href={`/teams/${firstTeamId}`}>Go to one of your teams</Link>
            </Button>
          )}
        </CardContent>
      </Card>
    );
  }

  return (
    <>
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold" data-testid="team-name">
          {team.data.name}
        </h1>
      </div>
      <MeetingLauncher teamId={teamId} canWrite={canWrite} />
      <Scorecard teamId={teamId} canWrite={canWrite} onIssueFocus={setFocusedIssue} />
      <div className="grid gap-4 xl:grid-cols-2">
        <IssuesPanel
          teamId={teamId}
          team={team.data}
          canWrite={canWrite}
          highlightIssueId={focusedIssue}
        />
        <TodosPanel teamId={teamId} canWrite={canWrite} />
      </div>
      <RocksPanel teamId={teamId} />
    </>
  );
}

function MeetingLauncher({ teamId, canWrite }: { teamId: string; canWrite: boolean }) {
  const router = useRouter();
  const toast = useToast();
  const active = useActiveMeeting(teamId);
  const meetings = useTeamMeetings(teamId);
  const start = useStartMeeting(teamId);
  const ended = (meetings.data ?? []).filter((m) => m.status === "ended").slice(0, 3);

  const onStart = () => {
    start.mutate(undefined, {
      onSuccess: (meeting) => {
        router.push(`/meetings/${meeting.id}`);
      },
      onError: (error) => {
        toast.error(errorMessage(error));
        void active.refetch();
      },
    });
  };

  return (
    <Card aria-labelledby="meeting-title">
      <CardHeader>
        <CardTitle id="meeting-title">Level 10 Meeting</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {active.isPending && (
          <p className="text-muted-foreground text-sm" aria-busy="true">
            Checking for a running meeting…
          </p>
        )}
        {active.data ? (
          <div className="flex flex-wrap items-center gap-3">
            <p className="text-sm">
              A meeting is in progress, facilitated by{" "}
              <strong>{active.data.facilitator.name}</strong> (started{" "}
              {formatInstant(active.data.started_at)}).
            </p>
            <Button asChild>
              <Link href={`/meetings/${active.data.id}`}>
                <Video aria-hidden /> Join meeting
              </Link>
            </Button>
          </div>
        ) : (
          active.isSuccess && (
            <div className="flex flex-wrap items-center gap-3">
              <p className="text-muted-foreground text-sm">No meeting is running.</p>
              {canWrite ? (
                <Button onClick={onStart} disabled={start.isPending}>
                  {start.isPending ? (
                    <Loader2 className="animate-spin" aria-hidden />
                  ) : (
                    <Play aria-hidden />
                  )}
                  Start meeting
                </Button>
              ) : (
                <p className="text-muted-foreground text-sm">
                  Observers can join a meeting once a facilitator starts one.
                </p>
              )}
            </div>
          )
        )}
        {ended.length > 0 && (
          <div>
            <h3 className="text-muted-foreground mb-1 text-xs font-semibold uppercase">
              Recent meeting summaries
            </h3>
            <ul className="flex flex-wrap gap-2">
              {ended.map((m) => (
                <li key={m.id}>
                  <Button asChild variant="outline" size="sm">
                    <Link href={`/meetings/${m.id}`}>
                      {formatInstant(m.started_at)} · {m.facilitator.name}
                    </Link>
                  </Button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
