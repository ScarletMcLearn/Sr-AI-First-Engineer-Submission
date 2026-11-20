"use client";

import { Loader2 } from "lucide-react";
import { useParams } from "next/navigation";

import { useRequireMe } from "@/components/app-shell";
import { MeetingView } from "@/features/meeting/meeting-view";

export default function MeetingPage() {
  const { meetingId } = useParams<{ meetingId: string }>();
  const { me, isLoading } = useRequireMe();
  if (isLoading || !me) {
    return (
      <p className="text-muted-foreground flex items-center gap-2 p-6 text-sm" aria-busy="true">
        <Loader2 className="size-4 animate-spin" aria-hidden /> Loading…
      </p>
    );
  }
  return <MeetingView meetingId={meetingId} me={me} />;
}
