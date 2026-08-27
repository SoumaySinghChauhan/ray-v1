import { AlertTriangle, Loader2, Inbox } from "lucide-react";

/** Inline loading state — matches the existing quiet, restrained visual language. */
export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2.5 py-12 text-ink-3 text-xs">
      <Loader2 size={14} strokeWidth={1.75} className="animate-spin" />
      {label}
    </div>
  );
}

/** Error state with an explicit retry — never fails silently. */
export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="border border-separator py-10 px-6 flex flex-col items-center text-center gap-3">
      <AlertTriangle size={18} strokeWidth={1.75} className="text-blocked" />
      <div className="text-xs text-ink-2 max-w-sm">{message}</div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="t-fast text-[0.6875rem] tracking-[0.1em] text-ink-2 hover:text-ink border border-separator px-3 py-1.5 mt-1"
        >
          RETRY
        </button>
      )}
    </div>
  );
}

/** Empty state — no records, not an error. */
export function EmptyState({ message }: { message: string }) {
  return (
    <div className="py-12 flex flex-col items-center text-center gap-3 text-ink-3">
      <Inbox size={18} strokeWidth={1.75} />
      <div className="text-xs">{message}</div>
    </div>
  );
}
