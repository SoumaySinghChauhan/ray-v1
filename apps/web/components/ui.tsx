import type { ReactNode } from "react";
import type { Outcome } from "@/lib/demo";

/** Tiny uppercase editorial label */
export function Label({ children, dim = true }: { children: ReactNode; dim?: boolean }) {
  return <div className={dim ? "label" : "label-2"}>{children}</div>;
}

/** Structural section separator with optional heading */
export function Section({
  title,
  children,
  action,
  className = "",
}: {
  title?: string;
  children: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <section className={`rule pt-6 ${className}`}>
      {(title || action) && (
        <div className="flex items-baseline justify-between mb-6">
          {title && <h2 className="label-2">{title}</h2>}
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

const OUTCOME_STYLE: Record<Outcome, { text: string; cls: string; dot: string }> = {
  RECOVERED: { text: "RECOVERED", cls: "text-recovered", dot: "bg-recovered" },
  PENDING: { text: "PENDING", cls: "text-pending", dot: "bg-pending" },
  NOT_RECOVERED: { text: "NOT RECOVERED", cls: "text-ink-2", dot: "bg-ink-3" },
  BLOCKED: { text: "BLOCKED", cls: "text-blocked", dot: "bg-blocked" },
  SKIPPED: { text: "SKIPPED", cls: "text-ink-3", dot: "bg-ink-3" },
};

/** Semantic outcome status — the only place persistent color appears */
export function OutcomeBadge({ outcome }: { outcome: Outcome }) {
  const s = OUTCOME_STYLE[outcome];
  return (
    <span className={`inline-flex items-center gap-1.5 text-[0.625rem] tracking-[0.14em] font-medium ${s.cls}`}>
      <span className={`w-1 h-1 rounded-full ${s.dot}`} />
      {s.text}
    </span>
  );
}

export function PolicyBadge({ policy }: { policy: "ALLOW" | "BLOCK" | "NOT_EVALUATED" }) {
  if (policy === "ALLOW")
    return <span className="text-[0.625rem] tracking-[0.14em] font-medium text-ink">ALLOW</span>;
  if (policy === "BLOCK")
    return <span className="text-[0.625rem] tracking-[0.14em] font-medium text-blocked">BLOCK</span>;
  return <span className="text-[0.625rem] tracking-[0.14em] font-medium text-ink-3">—</span>;
}

/** Monospace identifier */
export function Id({ children }: { children: ReactNode }) {
  return <span className="mono text-xs text-ink-2">{children}</span>;
}

/** Key-value row for technical detail panes */
export function KV({ k, v, monoV = false }: { k: string; v: ReactNode; monoV?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-6 py-1.5">
      <span className="label">{k}</span>
      <span className={`text-xs text-ink text-right ${monoV ? "mono" : "fin"}`}>{v}</span>
    </div>
  );
}

/** Large financial figure with label above and context below */
export function Figure({
  label,
  value,
  context,
  tone = "ink",
  size = "lg",
}: {
  label: string;
  value: ReactNode;
  context?: ReactNode;
  tone?: "ink" | "dim" | "recovered" | "pending" | "blocked";
  size?: "md" | "lg" | "xl";
}) {
  const toneCls = {
    ink: "text-ink",
    dim: "text-ink-2",
    recovered: "text-recovered",
    pending: "text-pending",
    blocked: "text-blocked",
  }[tone];
  const sizeCls = { md: "text-2xl", lg: "text-3xl", xl: "text-5xl" }[size];
  return (
    <div>
      <div className="label mb-2">{label}</div>
      <div className={`fin font-medium ${sizeCls} ${toneCls}`}>{value}</div>
      {context && <div className="text-xs text-ink-3 mt-1.5">{context}</div>}
    </div>
  );
}

export interface KpiCardItem {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  tone?: "ink" | "recovered" | "pending" | "blocked";
  chart?: ReactNode;
}

const KPI_TONE: Record<NonNullable<KpiCardItem["tone"]>, string> = {
  ink: "text-ink",
  recovered: "text-recovered",
  pending: "text-pending",
  blocked: "text-blocked",
};

/**
 * Separate bordered KPI cards with gaps between them — the pattern used on
 * Decisions, Execution, Audit, and Evaluation (distinct from Overview's
 * single unified strip).
 */
export function KpiCards({ items }: { items: KpiCardItem[] }) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:flex lg:flex-nowrap gap-3">
      {items.map((it) => (
        <div key={it.label} className="border border-separator px-5 py-4 lg:flex-1 lg:min-w-0">
          <div className={`fin text-2xl font-medium ${KPI_TONE[it.tone ?? "ink"]}`}>{it.value}</div>
          <div className="label mt-1.5">{it.label}</div>
          {it.sub && <div className="text-[0.6875rem] text-ink-3 mt-0.5">{it.sub}</div>}
          {it.chart && <div className="mt-2">{it.chart}</div>}
        </div>
      ))}
    </div>
  );
}

export function TestModeTag() {
  return (
    <span className="inline-flex items-center gap-1.5 border border-separator px-2 py-0.5 text-[0.625rem] tracking-[0.14em] text-ink-2">
      <span className="w-1 h-1 rounded-full bg-pending" />
      RAZORPAY TEST MODE
    </span>
  );
}
