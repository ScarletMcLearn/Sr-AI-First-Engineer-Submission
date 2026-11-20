"use client";

import { CheckCircle2, XCircle } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

interface ToastItem {
  id: number;
  kind: "success" | "error";
  message: string;
}

interface ToastApi {
  success: (message: string) => void;
  error: (message: string) => void;
}

const ToastContext = React.createContext<ToastApi | null>(null);

export function useToast(): ToastApi {
  const ctx = React.useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used inside <ToastProvider>");
  return ctx;
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = React.useState<ToastItem[]>([]);
  const counter = React.useRef(0);

  const push = React.useCallback((kind: ToastItem["kind"], message: string) => {
    counter.current += 1;
    const id = counter.current;
    setItems((current) => [...current.slice(-3), { id, kind, message }]);
    window.setTimeout(
      () => {
        setItems((current) => current.filter((item) => item.id !== id));
      },
      kind === "error" ? 8000 : 4000,
    );
  }, []);

  const api = React.useMemo<ToastApi>(
    () => ({
      success: (message) => {
        push("success", message);
      },
      error: (message) => {
        push("error", message);
      },
    }),
    [push],
  );

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div
        role="region"
        aria-label="Notifications"
        aria-live="polite"
        className="fixed right-4 bottom-4 z-[60] flex w-80 max-w-[calc(100vw-2rem)] flex-col gap-2"
      >
        {items.map((item) => (
          <div
            key={item.id}
            role={item.kind === "error" ? "alert" : "status"}
            className={cn(
              "flex items-start gap-2 rounded-md border p-3 text-sm shadow-md",
              item.kind === "error"
                ? "border-danger/40 bg-danger-bg text-danger"
                : "border-success/40 bg-success-bg text-success",
            )}
          >
            {item.kind === "error" ? (
              <XCircle className="mt-0.5 size-4 shrink-0" aria-hidden />
            ) : (
              <CheckCircle2 className="mt-0.5 size-4 shrink-0" aria-hidden />
            )}
            <span>{item.message}</span>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
