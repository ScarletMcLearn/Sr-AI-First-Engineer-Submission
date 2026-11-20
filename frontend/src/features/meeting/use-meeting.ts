"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as React from "react";

import { API_URL, api, call } from "@/lib/api/client";
import type { MeetingState } from "@/lib/api/types";
import { invalidateResource, keys, type TeamResource } from "@/lib/queries";

/** Server state plus the local monotonic instant at which it arrived (for ticking the timer). */
export interface MeetingSnapshot {
  state: MeetingState;
  receivedAt: number;
}

export type Connection = "connecting" | "live" | "reconnecting";

function snapshotOf(state: MeetingState): MeetingSnapshot {
  return { state, receivedAt: performance.now() };
}

/**
 * Subscribes to the meeting's Server-Sent Events stream.
 *
 * Every (re)connection begins with a full authoritative state event, so a refresh, a late join
 * or a dropped connection all converge on the server's state. Stale or duplicate events are
 * ignored using the monotonically increasing `version`.
 */
export function useMeeting(meetingId: string): {
  snapshot: MeetingSnapshot | undefined;
  connection: Connection;
  error: Error | null;
} {
  const client = useQueryClient();
  const [connection, setConnection] = React.useState<Connection>("connecting");

  const query = useQuery({
    queryKey: keys.meeting(meetingId),
    queryFn: async () =>
      snapshotOf(
        await call(
          api.GET("/api/meetings/{meeting_id}", { params: { path: { meeting_id: meetingId } } }),
        ),
      ),
    staleTime: Infinity,
    retry: false,
  });

  React.useEffect(() => {
    let source: EventSource | null = null;

    const apply = (state: MeetingState) => {
      client.setQueryData<MeetingSnapshot>(keys.meeting(meetingId), (current) =>
        current && current.state.version > state.version ? current : snapshotOf(state),
      );
      if (state.status === "ended") {
        void client.invalidateQueries({ queryKey: keys.summary(meetingId) });
      }
    };

    const connect = () => {
      source?.close();
      const next = new EventSource(`${API_URL}/api/meetings/${meetingId}/events`, {
        withCredentials: true,
      });
      next.addEventListener("open", () => {
        setConnection("live");
      });
      next.addEventListener("error", () => {
        setConnection("reconnecting"); // EventSource retries by itself; the next connect resyncs
      });
      // The first event after every (re)connect is the full authoritative state.
      next.addEventListener("state", (event: MessageEvent<string>) => {
        apply(JSON.parse(event.data) as MeetingState);
      });
      next.addEventListener("data_changed", (event: MessageEvent<string>) => {
        const { resource } = JSON.parse(event.data) as { resource: TeamResource | "all" };
        const teamId = client.getQueryData<MeetingSnapshot>(keys.meeting(meetingId))?.state.team_id;
        if (teamId) invalidateResource(client, teamId, resource);
      });
      source = next;
    };

    // Network awareness: drop the stream when the browser goes offline and reconnect (which
    // resyncs from the server) as soon as it is back, instead of waiting for backoff timers.
    const goOffline = () => {
      source?.close();
      source = null;
      setConnection("reconnecting");
    };
    const goOnline = () => {
      setConnection("connecting");
      connect();
    };

    connect();
    window.addEventListener("offline", goOffline);
    window.addEventListener("online", goOnline);
    return () => {
      window.removeEventListener("offline", goOffline);
      window.removeEventListener("online", goOnline);
      source?.close();
    };
  }, [client, meetingId]);

  return { snapshot: query.data, connection, error: query.error };
}

/** Elapsed seconds in the current section: server value at receipt + local monotonic delta. */
export function useSectionClock(snapshot: MeetingSnapshot | undefined): number {
  const [now, setNow] = React.useState(() => performance.now());
  const active = snapshot?.state.status === "active";
  React.useEffect(() => {
    if (!active) return;
    const id = window.setInterval(() => {
      setNow(performance.now());
    }, 250);
    return () => {
      window.clearInterval(id);
    };
  }, [active]);
  if (!snapshot) return 0;
  const { state, receivedAt } = snapshot;
  if (state.status === "ended") return state.section_elapsed_seconds;
  return state.section_elapsed_seconds + Math.max(0, (now - receivedAt) / 1000);
}

function useMeetingAction<V>(
  meetingId: string,
  run: (variables: V) => Promise<MeetingState>,
): ReturnType<typeof useMutation<MeetingState, Error, V>> {
  const client = useQueryClient();
  return useMutation({
    mutationFn: run,
    onSuccess: (state) => {
      client.setQueryData<MeetingSnapshot>(keys.meeting(meetingId), (current) =>
        current && current.state.version > state.version ? current : snapshotOf(state),
      );
      void client.invalidateQueries({ queryKey: keys.activeMeeting(state.team_id) });
    },
  });
}

export function useJoinMeeting(meetingId: string) {
  return useMeetingAction<undefined>(meetingId, () =>
    call(
      api.POST("/api/meetings/{meeting_id}/join", { params: { path: { meeting_id: meetingId } } }),
    ),
  );
}

export function useAdvanceMeeting(meetingId: string) {
  return useMeetingAction<number>(meetingId, (expectedVersion) =>
    call(
      api.POST("/api/meetings/{meeting_id}/advance", {
        params: { path: { meeting_id: meetingId } },
        body: { expected_version: expectedVersion },
      }),
    ),
  );
}

export function useEndMeeting(meetingId: string) {
  return useMeetingAction<number>(meetingId, (expectedVersion) =>
    call(
      api.POST("/api/meetings/{meeting_id}/end", {
        params: { path: { meeting_id: meetingId } },
        body: { expected_version: expectedVersion },
      }),
    ),
  );
}

export function useRateMeeting(meetingId: string) {
  return useMeetingAction<number>(meetingId, (rating) =>
    call(
      api.PUT("/api/meetings/{meeting_id}/rating", {
        params: { path: { meeting_id: meetingId } },
        body: { rating },
      }),
    ),
  );
}
