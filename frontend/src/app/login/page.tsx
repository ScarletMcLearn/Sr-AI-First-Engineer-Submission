"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import * as React from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, call, errorMessage } from "@/lib/api/client";
import { useUsers } from "@/lib/queries";

const ROLE_LABEL = { admin: "Admin", team_member: "Team Member", observer: "Observer" } as const;

export default function LoginPage() {
  const router = useRouter();
  const client = useQueryClient();
  const users = useUsers();
  const [pending, setPending] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  const signIn = async (userId: string) => {
    setPending(userId);
    setError(null);
    try {
      await call(api.POST("/api/auth/login", { body: { user_id: userId } }));
      client.clear();
      router.replace("/");
    } catch (e) {
      setError(errorMessage(e));
      setPending(null);
    }
  };

  return (
    <main id="main" className="mx-auto max-w-3xl space-y-4 p-6">
      <header>
        <h1 className="text-2xl font-semibold">Level 10 meetings</h1>
        <p className="text-muted-foreground text-sm">
          Assessment login: pick a seeded user. There are no passwords; the server still loads each
          user&apos;s role and teams itself and enforces them on every request.
        </p>
      </header>
      {error && (
        <p role="alert" className="text-danger text-sm">
          {error}
        </p>
      )}
      <Card aria-labelledby="users-title">
        <CardHeader>
          <CardTitle id="users-title">Sign in as</CardTitle>
        </CardHeader>
        <CardContent>
          {users.isPending && (
            <p className="text-muted-foreground flex items-center gap-2 text-sm" aria-busy="true">
              <Loader2 className="size-4 animate-spin" aria-hidden /> Loading users…
            </p>
          )}
          {users.isError && (
            <p role="alert" className="text-danger text-sm">
              {errorMessage(users.error)}
            </p>
          )}
          <ul className="grid gap-2 sm:grid-cols-2">
            {users.data?.map((user) => (
              <li key={user.id}>
                <Button
                  variant="outline"
                  className="h-auto w-full justify-between py-3 text-left"
                  disabled={pending !== null}
                  onClick={() => void signIn(user.id)}
                  aria-label={`Sign in as ${user.name} (${ROLE_LABEL[user.role]})`}
                >
                  <span>
                    <span className="block font-medium">{user.name}</span>
                    <span className="text-muted-foreground block text-xs">{user.email}</span>
                  </span>
                  {pending === user.id ? (
                    <Loader2 className="animate-spin" aria-hidden />
                  ) : (
                    <Badge variant={user.role === "observer" ? "outline" : "secondary"}>
                      {ROLE_LABEL[user.role]}
                    </Badge>
                  )}
                </Button>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </main>
  );
}
