"use client";

import { ListPlus, Loader2, Plus } from "lucide-react";
import * as React from "react";

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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { errorMessage } from "@/lib/api/client";
import type { Issue, TeamDetail } from "@/lib/api/types";
import { formatDay, formatInstant } from "@/lib/format";
import {
  useAddTodo,
  useCreateIssue,
  useIssues,
  useSetPriority,
  useSolveIssue,
} from "@/lib/queries";
import { cn } from "@/lib/utils";

interface IssuesPanelProps {
  teamId: string;
  team: TeamDetail;
  canWrite: boolean;
  /** When set, solved Issues and created To-Dos are attributed to this active meeting. */
  meetingId?: string;
  highlightIssueId?: string | null;
}

export function IssuesPanel({
  teamId,
  team,
  canWrite,
  meetingId,
  highlightIssueId,
}: IssuesPanelProps) {
  const [view, setView] = React.useState<"unsolved" | "solved">("unsolved");
  const issues = useIssues(teamId, view);

  return (
    <Card aria-labelledby="issues-title">
      <CardHeader>
        <CardTitle id="issues-title">Issues</CardTitle>
        <div role="group" aria-label="Issue list" className="ml-auto flex gap-1">
          {(["unsolved", "solved"] as const).map((option) => (
            <Button
              key={option}
              size="sm"
              variant={view === option ? "default" : "outline"}
              aria-pressed={view === option}
              onClick={() => {
                setView(option);
              }}
            >
              {option === "unsolved" ? "Unsolved" : "Solved"}
            </Button>
          ))}
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {canWrite && view === "unsolved" && <NewIssueForm teamId={teamId} meetingId={meetingId} />}
        {issues.isPending && (
          <p className="text-muted-foreground flex items-center gap-2 text-sm" aria-busy="true">
            <Loader2 className="size-4 animate-spin" aria-hidden /> Loading issues…
          </p>
        )}
        {issues.isError && (
          <p role="alert" className="text-danger text-sm">
            {errorMessage(issues.error)}
          </p>
        )}
        {issues.data?.length === 0 && (
          <p className="text-muted-foreground text-sm">
            {view === "unsolved" ? "No unsolved Issues. Nice." : "No solved Issues yet."}
          </p>
        )}
        <ol
          className="space-y-2"
          aria-label={view === "unsolved" ? "Unsolved issues in priority order" : "Solved issues"}
        >
          {issues.data?.map((issue) => (
            <IssueRow
              key={issue.id}
              issue={issue}
              teamId={teamId}
              team={team}
              canWrite={canWrite}
              meetingId={meetingId}
              highlighted={issue.id === highlightIssueId}
            />
          ))}
        </ol>
      </CardContent>
    </Card>
  );
}

function NewIssueForm({ teamId, meetingId }: { teamId: string; meetingId?: string }) {
  const toast = useToast();
  const create = useCreateIssue(teamId, meetingId);
  const [title, setTitle] = React.useState("");
  const [priority, setPriority] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);

  const submit = (event: React.SyntheticEvent) => {
    event.preventDefault();
    if (title.trim() === "") {
      setError("Title is required");
      return;
    }
    setError(null);
    create.mutate(
      { title: title.trim(), priority: priority === "" ? null : Number(priority) },
      {
        onSuccess: () => {
          setTitle("");
          setPriority("");
          toast.success("Issue added");
        },
        onError: (e) => {
          setError(errorMessage(e));
        },
      },
    );
  };

  return (
    <form onSubmit={submit} className="flex flex-wrap items-end gap-2" noValidate>
      <div className="min-w-48 flex-1 space-y-1">
        <Label htmlFor={`new-issue-title-${teamId}`}>New Issue</Label>
        <Input
          id={`new-issue-title-${teamId}`}
          value={title}
          placeholder="What problem should the team solve?"
          aria-invalid={error !== null}
          aria-describedby={error ? `new-issue-error-${teamId}` : undefined}
          disabled={create.isPending}
          onChange={(e) => {
            setTitle(e.target.value);
          }}
        />
      </div>
      <div className="w-32 space-y-1">
        <Label htmlFor={`new-issue-priority-${teamId}`}>Priority</Label>
        <Select
          id={`new-issue-priority-${teamId}`}
          value={priority}
          disabled={create.isPending}
          onChange={(e) => {
            setPriority(e.target.value);
          }}
        >
          <option value="">None</option>
          {[5, 4, 3, 2, 1].map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </Select>
      </div>
      <Button type="submit" disabled={create.isPending}>
        {create.isPending ? <Loader2 className="animate-spin" aria-hidden /> : <Plus aria-hidden />}
        Add Issue
      </Button>
      {error && (
        <p id={`new-issue-error-${teamId}`} role="alert" className="text-danger w-full text-sm">
          {error}
        </p>
      )}
    </form>
  );
}

interface IssueRowProps {
  issue: Issue;
  teamId: string;
  team: TeamDetail;
  canWrite: boolean;
  meetingId?: string;
  highlighted: boolean;
}

function IssueRow({ issue, teamId, team, canWrite, meetingId, highlighted }: IssueRowProps) {
  const toast = useToast();
  const setPriority = useSetPriority(teamId);
  const solved = issue.solved_at !== null;

  return (
    <li
      data-testid={`issue-${issue.id}`}
      className={cn(
        "rounded-md border p-3",
        highlighted && "border-primary ring-primary/30 ring-2",
      )}
    >
      <div className="flex flex-wrap items-start gap-3">
        <div className="min-w-48 flex-1">
          <p className="font-medium">{issue.title}</p>
          <p className="text-muted-foreground text-xs">
            Owner {issue.owner.name} · created {formatInstant(issue.created_at)}
            {issue.source && (
              <>
                {" "}
                · from <span className="font-medium">{issue.source.measurable_name}</span>, week of{" "}
                {formatDay(issue.source.week_start)}
              </>
            )}
          </p>
          {solved && issue.solved_at && issue.resolution_note && (
            <p className="mt-1 text-sm">
              <Badge variant="success">Solved {formatInstant(issue.solved_at)}</Badge>{" "}
              <span>{issue.resolution_note}</span>
            </p>
          )}
        </div>
        {!solved && (
          <div className="flex items-center gap-2">
            <Label htmlFor={`priority-${issue.id}`} className="sr-only">
              Priority for {issue.title}
            </Label>
            {canWrite ? (
              <Select
                id={`priority-${issue.id}`}
                className="w-24"
                value={issue.priority === null ? "" : String(issue.priority)}
                disabled={setPriority.isPending}
                onChange={(e) => {
                  setPriority.mutate(
                    {
                      issueId: issue.id,
                      priority: e.target.value === "" ? null : Number(e.target.value),
                    },
                    {
                      onError: (error) => {
                        toast.error(errorMessage(error));
                      },
                    },
                  );
                }}
              >
                <option value="">No priority</option>
                {[5, 4, 3, 2, 1].map((p) => (
                  <option key={p} value={p}>
                    P{p}
                  </option>
                ))}
              </Select>
            ) : (
              <Badge variant="secondary">
                {issue.priority === null ? "No priority" : `P${String(issue.priority)}`}
              </Badge>
            )}
          </div>
        )}
        {solved && issue.priority !== null && <Badge variant="secondary">P{issue.priority}</Badge>}
      </div>
      {canWrite && !solved && (
        <div className="mt-2 flex flex-wrap gap-2">
          <SolveDialog issue={issue} teamId={teamId} meetingId={meetingId} />
          <AddTodoDialog issue={issue} teamId={teamId} team={team} meetingId={meetingId} />
        </div>
      )}
    </li>
  );
}

function SolveDialog({
  issue,
  teamId,
  meetingId,
}: {
  issue: Issue;
  teamId: string;
  meetingId?: string;
}) {
  const toast = useToast();
  const solve = useSolveIssue(teamId, meetingId);
  const [open, setOpen] = React.useState(false);
  const [note, setNote] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);

  const submit = (event: React.SyntheticEvent) => {
    event.preventDefault();
    if (note.trim() === "") {
      setError("A resolution note is required");
      return;
    }
    setError(null);
    solve.mutate(
      { issueId: issue.id, note: note.trim() },
      {
        onSuccess: () => {
          setOpen(false);
          setNote("");
          toast.success("Issue solved");
        },
        onError: (e) => {
          setError(errorMessage(e));
        },
      },
    );
  };

  return (
    <>
      <Button
        size="sm"
        variant="outline"
        onClick={() => {
          setOpen(true);
        }}
        aria-label={`Solve: ${issue.title}`}
      >
        Solve
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <form onSubmit={submit} noValidate className="grid gap-4">
            <DialogHeader>
              <DialogTitle>Solve Issue</DialogTitle>
              <DialogDescription>{issue.title}</DialogDescription>
            </DialogHeader>
            <div className="space-y-1">
              <Label htmlFor={`solve-note-${issue.id}`}>Resolution note (required)</Label>
              <Textarea
                id={`solve-note-${issue.id}`}
                value={note}
                aria-invalid={error !== null}
                aria-describedby={error ? `solve-error-${issue.id}` : undefined}
                disabled={solve.isPending}
                onChange={(e) => {
                  setNote(e.target.value);
                }}
              />
              {error && (
                <p id={`solve-error-${issue.id}`} role="alert" className="text-danger text-sm">
                  {error}
                </p>
              )}
            </div>
            <DialogFooter>
              <DialogClose asChild>
                <Button type="button" variant="outline" disabled={solve.isPending}>
                  Cancel
                </Button>
              </DialogClose>
              <Button type="submit" disabled={solve.isPending}>
                {solve.isPending && <Loader2 className="animate-spin" aria-hidden />}
                Mark solved
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}

function AddTodoDialog({
  issue,
  teamId,
  team,
  meetingId,
}: {
  issue: Issue;
  teamId: string;
  team: TeamDetail;
  meetingId?: string;
}) {
  const toast = useToast();
  const add = useAddTodo(teamId, meetingId);
  const [open, setOpen] = React.useState(false);
  const [title, setTitle] = React.useState("");
  const [ownerId, setOwnerId] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);

  const submit = (event: React.SyntheticEvent) => {
    event.preventDefault();
    if (title.trim() === "") {
      setError("Title is required");
      return;
    }
    if (ownerId === "") {
      setError("Choose an owner");
      return;
    }
    setError(null);
    add.mutate(
      { issueId: issue.id, title: title.trim(), ownerId },
      {
        onSuccess: (todo) => {
          setOpen(false);
          setTitle("");
          setOwnerId("");
          toast.success(`To-Do added, due ${formatDay(todo.due_date)}`);
        },
        onError: (e) => {
          setError(errorMessage(e));
        },
      },
    );
  };

  return (
    <>
      <Button
        size="sm"
        variant="outline"
        onClick={() => {
          setOpen(true);
        }}
        aria-label={`Add To-Do for: ${issue.title}`}
      >
        <ListPlus aria-hidden /> Add To-Do
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <form onSubmit={submit} noValidate className="grid gap-4">
            <DialogHeader>
              <DialogTitle>Add To-Do</DialogTitle>
              <DialogDescription>
                For “{issue.title}”. Due in 7 days (company time).
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-1">
              <Label htmlFor={`todo-title-${issue.id}`}>Title</Label>
              <Input
                id={`todo-title-${issue.id}`}
                value={title}
                disabled={add.isPending}
                onChange={(e) => {
                  setTitle(e.target.value);
                }}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor={`todo-owner-${issue.id}`}>Owner</Label>
              <Select
                id={`todo-owner-${issue.id}`}
                value={ownerId}
                disabled={add.isPending}
                onChange={(e) => {
                  setOwnerId(e.target.value);
                }}
              >
                <option value="">Choose an owner…</option>
                {team.eligible_owners.map((owner) => (
                  <option key={owner.id} value={owner.id}>
                    {owner.name}
                  </option>
                ))}
              </Select>
            </div>
            {error && (
              <p role="alert" className="text-danger text-sm">
                {error}
              </p>
            )}
            <DialogFooter>
              <DialogClose asChild>
                <Button type="button" variant="outline" disabled={add.isPending}>
                  Cancel
                </Button>
              </DialogClose>
              <Button type="submit" disabled={add.isPending}>
                {add.isPending && <Loader2 className="animate-spin" aria-hidden />}
                Add To-Do
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
