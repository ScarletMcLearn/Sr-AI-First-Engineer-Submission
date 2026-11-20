"use client";

import {
  useMutation,
  useQuery,
  useQueryClient,
  type QueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from "@tanstack/react-query";

import { api, call } from "./api/client";
import type {
  Issue,
  Me,
  MeetingListItem,
  MeetingState,
  MeetingSummary,
  Rocks,
  Scorecard,
  TeamDetail,
  Todo,
  Todos,
  User,
} from "./api/types";

export type TeamResource = "scorecard" | "issues" | "todos";

export const keys = {
  me: ["me"] as const,
  users: ["users"] as const,
  team: (teamId: string) => ["team", teamId, "detail"] as const,
  scorecard: (teamId: string) => ["team", teamId, "scorecard"] as const,
  issues: (teamId: string, status: "unsolved" | "solved") =>
    ["team", teamId, "issues", status] as const,
  todos: (teamId: string) => ["team", teamId, "todos"] as const,
  rocks: (teamId: string) => ["team", teamId, "rocks"] as const,
  activeMeeting: (teamId: string) => ["team", teamId, "active-meeting"] as const,
  teamMeetings: (teamId: string) => ["team", teamId, "meetings"] as const,
  meeting: (meetingId: string) => ["meeting", meetingId] as const,
  summary: (meetingId: string) => ["meeting", meetingId, "summary"] as const,
};

/** Refetch only what a mutation (or a live `data_changed` event) can have changed. */
export function invalidateResource(
  client: QueryClient,
  teamId: string,
  resource: TeamResource | "all",
): void {
  const targets: TeamResource[] =
    resource === "all" ? ["scorecard", "issues", "todos"] : [resource];
  for (const target of targets) {
    void client.invalidateQueries({ queryKey: ["team", teamId, target] });
  }
}

export function useMe(): UseQueryResult<Me> {
  return useQuery({
    queryKey: keys.me,
    queryFn: () => call(api.GET("/api/me")),
    retry: false,
    staleTime: 60_000,
  });
}

export function useUsers(): UseQueryResult<User[]> {
  return useQuery({ queryKey: keys.users, queryFn: () => call(api.GET("/api/users")) });
}

export function useTeam(teamId: string): UseQueryResult<TeamDetail> {
  return useQuery({
    queryKey: keys.team(teamId),
    queryFn: () => call(api.GET("/api/teams/{team_id}", { params: { path: { team_id: teamId } } })),
    retry: false,
  });
}

export function useScorecard(teamId: string): UseQueryResult<Scorecard> {
  return useQuery({
    queryKey: keys.scorecard(teamId),
    queryFn: () =>
      call(api.GET("/api/teams/{team_id}/scorecard", { params: { path: { team_id: teamId } } })),
  });
}

export function useIssues(teamId: string, status: "unsolved" | "solved"): UseQueryResult<Issue[]> {
  return useQuery({
    queryKey: keys.issues(teamId, status),
    queryFn: () =>
      call(
        api.GET("/api/teams/{team_id}/issues", {
          params: { path: { team_id: teamId }, query: { status } },
        }),
      ),
  });
}

export function useTodos(teamId: string): UseQueryResult<Todos> {
  return useQuery({
    queryKey: keys.todos(teamId),
    queryFn: () =>
      call(api.GET("/api/teams/{team_id}/todos", { params: { path: { team_id: teamId } } })),
  });
}

export function useRocks(teamId: string): UseQueryResult<Rocks> {
  return useQuery({
    queryKey: keys.rocks(teamId),
    queryFn: () =>
      call(api.GET("/api/teams/{team_id}/rocks", { params: { path: { team_id: teamId } } })),
  });
}

export function useActiveMeeting(teamId: string): UseQueryResult<MeetingState | null> {
  return useQuery({
    queryKey: keys.activeMeeting(teamId),
    queryFn: async () =>
      (
        await call(
          api.GET("/api/teams/{team_id}/meetings/active", {
            params: { path: { team_id: teamId } },
          }),
        )
      ).meeting ?? null,
  });
}

export function useTeamMeetings(teamId: string): UseQueryResult<MeetingListItem[]> {
  return useQuery({
    queryKey: keys.teamMeetings(teamId),
    queryFn: () =>
      call(api.GET("/api/teams/{team_id}/meetings", { params: { path: { team_id: teamId } } })),
  });
}

export function useMeetingSummary(
  meetingId: string,
  enabled: boolean,
): UseQueryResult<MeetingSummary> {
  return useQuery({
    queryKey: keys.summary(meetingId),
    enabled,
    queryFn: () =>
      call(
        api.GET("/api/meetings/{meeting_id}/summary", {
          params: { path: { meeting_id: meetingId } },
        }),
      ),
  });
}

// ---------------------------------------------------------------- mutations

export function useSetScore(
  teamId: string,
): UseMutationResult<
  Scorecard,
  Error,
  { measurableId: string; weekStart: string; value: number; expectedVersion?: number }
> {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (v) =>
      call(
        api.PUT("/api/teams/{team_id}/measurables/{measurable_id}/scores/{week_start}", {
          params: {
            path: { team_id: teamId, measurable_id: v.measurableId, week_start: v.weekStart },
          },
          body: { value: v.value, expected_version: v.expectedVersion ?? null },
        }),
      ),
    onSuccess: (scorecard) => {
      client.setQueryData(keys.scorecard(teamId), scorecard);
    },
  });
}

export function useMakeIssue(
  teamId: string,
): UseMutationResult<
  { issue: Issue; created: boolean },
  Error,
  { measurableId: string; weekStart: string }
> {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (v) =>
      call(
        api.POST("/api/teams/{team_id}/measurables/{measurable_id}/weeks/{week_start}/issue", {
          params: {
            path: { team_id: teamId, measurable_id: v.measurableId, week_start: v.weekStart },
          },
        }),
      ),
    onSuccess: () => {
      invalidateResource(client, teamId, "scorecard");
      invalidateResource(client, teamId, "issues");
    },
  });
}

export function useCreateIssue(
  teamId: string,
  meetingId?: string,
): UseMutationResult<Issue, Error, { title: string; priority: number | null }> {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (v) =>
      call(
        api.POST("/api/teams/{team_id}/issues", {
          params: { path: { team_id: teamId } },
          body: { title: v.title, priority: v.priority, meeting_id: meetingId ?? null },
        }),
      ),
    onSuccess: () => {
      invalidateResource(client, teamId, "issues");
    },
  });
}

export function useSetPriority(
  teamId: string,
): UseMutationResult<Issue, Error, { issueId: string; priority: number | null }> {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (v) =>
      call(
        api.PATCH("/api/teams/{team_id}/issues/{issue_id}", {
          params: { path: { team_id: teamId, issue_id: v.issueId } },
          body: { priority: v.priority },
        }),
      ),
    onSuccess: () => {
      invalidateResource(client, teamId, "issues");
    },
  });
}

export function useSolveIssue(
  teamId: string,
  meetingId?: string,
): UseMutationResult<Issue, Error, { issueId: string; note: string }> {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (v) =>
      call(
        api.POST("/api/teams/{team_id}/issues/{issue_id}/solve", {
          params: { path: { team_id: teamId, issue_id: v.issueId } },
          body: { note: v.note, meeting_id: meetingId ?? null },
        }),
      ),
    onSuccess: () => {
      invalidateResource(client, teamId, "issues");
      invalidateResource(client, teamId, "scorecard");
    },
  });
}

export function useAddTodo(
  teamId: string,
  meetingId?: string,
): UseMutationResult<Todo, Error, { issueId: string; title: string; ownerId: string }> {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (v) =>
      call(
        api.POST("/api/teams/{team_id}/issues/{issue_id}/todos", {
          params: { path: { team_id: teamId, issue_id: v.issueId } },
          body: { title: v.title, owner_id: v.ownerId, meeting_id: meetingId ?? null },
        }),
      ),
    onSuccess: () => {
      invalidateResource(client, teamId, "todos");
    },
  });
}

export function useSetTodoDone(
  teamId: string,
): UseMutationResult<Todo, Error, { todoId: string; done: boolean }> {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (v) =>
      call(
        v.done
          ? api.POST("/api/teams/{team_id}/todos/{todo_id}/complete", {
              params: { path: { team_id: teamId, todo_id: v.todoId } },
            })
          : api.POST("/api/teams/{team_id}/todos/{todo_id}/undo", {
              params: { path: { team_id: teamId, todo_id: v.todoId } },
            }),
      ),
    onSuccess: () => {
      invalidateResource(client, teamId, "todos");
    },
  });
}

export function useStartMeeting(teamId: string): UseMutationResult<MeetingState, Error, undefined> {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () =>
      call(api.POST("/api/teams/{team_id}/meetings", { params: { path: { team_id: teamId } } })),
    onSuccess: (meeting) => {
      client.setQueryData(keys.activeMeeting(teamId), meeting);
    },
  });
}
