"use client";

import { ChevronDown, ChevronRight, Loader2 } from "lucide-react";
import * as React from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { errorMessage } from "@/lib/api/client";
import type { Rock } from "@/lib/api/types";
import { formatDay } from "@/lib/format";
import { useRocks } from "@/lib/queries";

const STATUS_BADGE = {
  on_track: { label: "On track", variant: "success" },
  off_track: { label: "Off track", variant: "danger" },
  complete: { label: "Complete", variant: "default" },
} as const;

export function RocksPanel({ teamId }: { teamId: string }) {
  const rocks = useRocks(teamId);
  return (
    <Card aria-labelledby="rocks-title">
      <CardHeader>
        <CardTitle id="rocks-title">Rocks</CardTitle>
        {rocks.data && <span className="text-muted-foreground text-sm">{rocks.data.quarter}</span>}
      </CardHeader>
      <CardContent className="space-y-2">
        {rocks.isPending && (
          <p className="text-muted-foreground flex items-center gap-2 text-sm" aria-busy="true">
            <Loader2 className="size-4 animate-spin" aria-hidden /> Loading Rocks…
          </p>
        )}
        {rocks.isError && (
          <p role="alert" className="text-danger text-sm">
            {errorMessage(rocks.error)}
          </p>
        )}
        {rocks.data?.rocks.length === 0 && (
          <p className="text-muted-foreground text-sm">No Rocks for this quarter.</p>
        )}
        <ul className="space-y-2">
          {rocks.data?.rocks.map((rock) => (
            <RockRow key={rock.id} rock={rock} />
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

function RockRow({ rock }: { rock: Rock }) {
  const [open, setOpen] = React.useState(false);
  const badge = STATUS_BADGE[rock.status];
  const panelId = `rock-milestones-${rock.id}`;
  return (
    <li className="rounded-md border" data-testid={`rock-${rock.id}`}>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => {
          setOpen((v) => !v);
        }}
        className="flex w-full flex-wrap items-center gap-3 p-3 text-left"
      >
        {open ? (
          <ChevronDown className="size-4" aria-hidden />
        ) : (
          <ChevronRight className="size-4" aria-hidden />
        )}
        <span className="min-w-40 flex-1">
          <span className="block font-medium">{rock.title}</span>
          <span className="text-muted-foreground block text-xs">Owner {rock.owner.name}</span>
        </span>
        <Badge variant={badge.variant}>{badge.label}</Badge>
        <span className="flex w-32 items-center gap-2">
          <span
            role="progressbar"
            aria-label={`${rock.title} progress`}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={rock.progress_percent}
            className="bg-secondary h-2 flex-1 overflow-hidden rounded-full"
          >
            <span
              className="bg-primary block h-full"
              style={{ width: `${String(rock.progress_percent)}%` }}
            />
          </span>
          <span className="w-10 text-right text-sm font-medium">{rock.progress_percent}%</span>
        </span>
      </button>
      {open && (
        <ul id={panelId} className="space-y-1 border-t px-3 py-2 text-sm">
          {rock.milestones.length === 0 && (
            <li className="text-muted-foreground">No Milestones.</li>
          )}
          {rock.milestones.map((ms) => (
            <li key={ms.id} className="flex flex-wrap items-center gap-2">
              <span aria-hidden>{ms.done ? "☑" : "☐"}</span>
              <span className={ms.done ? "text-muted-foreground line-through" : ""}>
                {ms.title}
              </span>
              <span className="text-muted-foreground text-xs">due {formatDay(ms.due_date)}</span>
              <span className="sr-only">{ms.done ? "Done" : "Not done"}</span>
              {ms.past_due && <Badge variant="danger">Past due</Badge>}
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}
