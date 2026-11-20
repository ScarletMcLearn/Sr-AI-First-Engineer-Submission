"use client";

import { LogOut, Users } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import * as React from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { ApiError, api, call } from "@/lib/api/client";
import type { Me } from "@/lib/api/types";
import { useMe } from "@/lib/queries";
import { useQueryClient } from "@tanstack/react-query";

const ROLE_LABEL = { admin: "Admin", team_member: "Team Member", observer: "Observer" } as const;

/** Resolves the signed-in user, redirecting to the user switcher when there is no session. */
export function useRequireMe(): { me: Me | undefined; isLoading: boolean } {
  const router = useRouter();
  const query = useMe();
  const unauthenticated = query.error instanceof ApiError && query.error.status === 401;
  React.useEffect(() => {
    if (unauthenticated) router.replace("/login");
  }, [unauthenticated, router]);
  return { me: query.data, isLoading: query.isPending || unauthenticated };
}

interface AppShellProps {
  me: Me;
  teamId?: string;
  children: React.ReactNode;
}

export function AppShell({ me, teamId, children }: AppShellProps) {
  const router = useRouter();
  const client = useQueryClient();

  const signOut = async () => {
    await call(api.POST("/api/auth/logout"));
    client.clear();
    router.replace("/login");
  };

  return (
    <div className="min-h-screen">
      <a
        href="#main"
        className="bg-primary text-primary-foreground sr-only z-50 rounded-md p-2 focus:not-sr-only focus:fixed focus:top-2 focus:left-2"
      >
        Skip to content
      </a>
      <header className="bg-card sticky top-0 z-40 border-b">
        <div className="mx-auto flex max-w-[110rem] flex-wrap items-center gap-4 px-4 py-2">
          <Link href="/" className="text-lg font-semibold">
            Level 10
          </Link>
          <div className="flex items-center gap-2">
            <Users className="text-muted-foreground size-4" aria-hidden />
            <Label htmlFor="team-switcher" className="sr-only">
              Team
            </Label>
            <Select
              id="team-switcher"
              className="w-48"
              value={teamId ?? ""}
              onChange={(event) => {
                router.push(`/teams/${event.target.value}`);
              }}
            >
              {!teamId && <option value="">Choose a team…</option>}
              {me.teams.map((team) => (
                <option key={team.id} value={team.id}>
                  {team.name}
                </option>
              ))}
            </Select>
          </div>
          <div className="ml-auto flex items-center gap-3 text-sm">
            <span data-testid="current-user">
              <span className="font-medium">{me.user.name}</span>{" "}
              <Badge variant="secondary">{ROLE_LABEL[me.user.role]}</Badge>
            </span>
            <Button asChild variant="outline" size="sm">
              <Link href="/login">Switch user</Link>
            </Button>
            <Button variant="ghost" size="sm" onClick={() => void signOut()}>
              <LogOut aria-hidden /> Sign out
            </Button>
          </div>
        </div>
      </header>
      <main id="main" className="mx-auto max-w-[110rem] space-y-4 p-4">
        {children}
      </main>
    </div>
  );
}
