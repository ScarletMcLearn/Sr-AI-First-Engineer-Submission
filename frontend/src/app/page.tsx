"use client";

import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import * as React from "react";

import { useRequireMe } from "@/components/app-shell";

/** Entry point: send the user to their first team (or to the user switcher). */
export default function HomePage() {
  const router = useRouter();
  const { me } = useRequireMe();
  const firstTeam = me?.teams[0]?.id;

  React.useEffect(() => {
    if (firstTeam) router.replace(`/teams/${firstTeam}`);
  }, [firstTeam, router]);

  return (
    <main
      id="main"
      className="text-muted-foreground flex items-center gap-2 p-6 text-sm"
      aria-busy="true"
    >
      <Loader2 className="size-4 animate-spin" aria-hidden />
      {me && !firstTeam ? "You are not a member of any team." : "Loading…"}
    </main>
  );
}
