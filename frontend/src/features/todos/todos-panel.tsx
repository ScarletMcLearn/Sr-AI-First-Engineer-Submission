"use client";

import { Loader2 } from "lucide-react";
import * as React from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useToast } from "@/components/ui/toast";
import { errorMessage } from "@/lib/api/client";
import type { Todo } from "@/lib/api/types";
import { addDays, formatDay, formatInstant } from "@/lib/format";
import { useSetTodoDone, useTodos } from "@/lib/queries";
import { cn } from "@/lib/utils";

interface TodosPanelProps {
  teamId: string;
  canWrite: boolean;
  /** Show only To-Dos created in this meeting (Conclude section). */
  onlyMeetingId?: string;
}

export function TodosPanel({ teamId, canWrite, onlyMeetingId }: TodosPanelProps) {
  const todos = useTodos(teamId);
  const rows = (todos.data?.todos ?? []).filter(
    (t) => onlyMeetingId === undefined || t.created_in_meeting_id === onlyMeetingId,
  );

  return (
    <Card aria-labelledby={`todos-title-${onlyMeetingId ?? "team"}`}>
      <CardHeader>
        <CardTitle id={`todos-title-${onlyMeetingId ?? "team"}`}>
          {onlyMeetingId ? "To-Dos created in this meeting" : "To-Dos"}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {!onlyMeetingId && todos.data && <CompletionRate data={todos.data} />}
        {todos.isPending && (
          <p className="text-muted-foreground flex items-center gap-2 text-sm" aria-busy="true">
            <Loader2 className="size-4 animate-spin" aria-hidden /> Loading To-Dos…
          </p>
        )}
        {todos.isError && (
          <p role="alert" className="text-danger text-sm">
            {errorMessage(todos.error)}
          </p>
        )}
        {todos.data && rows.length === 0 && (
          <p className="text-muted-foreground text-sm">
            {onlyMeetingId ? "No To-Dos created yet in this meeting." : "No To-Dos."}
          </p>
        )}
        <ul className="space-y-2">
          {rows.map((todo) => (
            <TodoRow key={todo.id} todo={todo} teamId={teamId} canWrite={canWrite} />
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

function CompletionRate({ data }: { data: NonNullable<ReturnType<typeof useTodos>["data"]> }) {
  const { completion, last_closed_week: week } = data;
  const range = `${formatDay(week)}–${formatDay(addDays(week, 6))}`;
  return (
    <div className="bg-secondary rounded-md p-3 text-sm" data-testid="todo-completion">
      <p className="text-muted-foreground text-xs">Last closed week ({range}) completion rate</p>
      {completion ? (
        <p className="flex flex-wrap items-center gap-2">
          <span className="text-2xl font-semibold">{completion.rate_percent}%</span>
          <span>
            {completion.done} of {completion.due} done by end of week
          </span>
          <Badge variant={completion.meets_target ? "success" : "danger"}>
            {completion.meets_target ? "Meets" : "Below"} {data.target_percent}% target
          </Badge>
        </p>
      ) : (
        <p>No To-Dos were due that week.</p>
      )}
    </div>
  );
}

function TodoRow({ todo, teamId, canWrite }: { todo: Todo; teamId: string; canWrite: boolean }) {
  const toast = useToast();
  const setDone = useSetTodoDone(teamId);
  // While a toggle is in flight show the requested state; the server value replaces it on success.
  const [requested, setRequested] = React.useState<boolean | null>(null);
  const done = requested ?? todo.done_at !== null;
  const checkboxId = `todo-${todo.id}`;

  return (
    <li
      data-testid={`todo-${todo.id}`}
      className={cn(
        "flex items-start gap-3 rounded-md border p-3",
        todo.overdue && "border-danger/50",
      )}
    >
      <input
        id={checkboxId}
        type="checkbox"
        className="mt-1 size-4"
        checked={done}
        disabled={!canWrite || setDone.isPending}
        onChange={(event) => {
          setRequested(event.target.checked);
          setDone.mutate(
            { todoId: todo.id, done: event.target.checked },
            {
              onError: (error) => {
                toast.error(errorMessage(error));
              },
              onSettled: () => {
                setRequested(null);
              },
            },
          );
        }}
      />
      <div className="min-w-0 flex-1">
        <label
          htmlFor={checkboxId}
          className={cn("font-medium", done && "text-muted-foreground line-through")}
        >
          {todo.title}
        </label>
        <p className="text-muted-foreground text-xs">
          Owner {todo.owner.name} · due {formatDay(todo.due_date)}
          {todo.done_at && <> · done {formatInstant(todo.done_at)}</>}
          {todo.source_issue_title && <> · from Issue “{todo.source_issue_title}”</>}
        </p>
      </div>
      {todo.overdue && <Badge variant="danger">Overdue</Badge>}
      {setDone.isPending && <Loader2 className="size-4 animate-spin" aria-label="Saving" />}
    </li>
  );
}
