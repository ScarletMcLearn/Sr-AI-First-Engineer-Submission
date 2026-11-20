import * as React from "react";

import { cn } from "@/lib/utils";

/** Native select styled like shadcn's Select: fully keyboard and screen-reader accessible. */
export function Select({ className, ...props }: React.ComponentProps<"select">) {
  return (
    <select
      className={cn(
        "border-input bg-card flex h-9 w-full rounded-md border px-2 py-1 text-sm shadow-xs disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    />
  );
}
