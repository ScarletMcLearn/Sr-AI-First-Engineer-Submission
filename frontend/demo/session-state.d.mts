export interface RunnableInput {
  order: readonly string[];
  prerequisites: Record<string, readonly string[]>;
  passed: readonly string[];
  failed: readonly string[];
  running: string | null;
}

export function checkRunnable(
  input: RunnableInput,
  id: string,
): { ok: true } | { ok: false; message: string };

export function nextScene(order: readonly string[], passed: readonly string[]): string | null;
