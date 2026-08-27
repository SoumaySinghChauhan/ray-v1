"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { CountUp } from "@/components/CountUp";
import { LiveFeed } from "@/components/LiveFeed";
import { ProgressBar } from "@/components/charts";
import { StageNode } from "@/components/StageIcon";
import { OutcomeBadge, Label } from "@/components/ui";
import { LoadingState, ErrorState, EmptyState } from "@/components/DataState";
import { api, ApiError, type ApiOpportunity, type ApiExecutionRow, type ApiAuditTrail, type ApiConfig } from "@/lib/api";
import { inr, pct, num } from "@/lib/format";

interface Stage {
  id: string;
  label: string;
  value: string;
  sub: string;
  time: string;
  tone: "neutral" | "recovered";
  iconTone?: "neutral" | "blocked" | "recovered";
}

function fmtTime(iso: string | null | undefined): string {
  return iso ? new Date(iso).toLocaleTimeString() : "—";
}

function buildStages(trail: ApiAuditTrail): Stage[] {
  const o = trail.opportunity;
  const prediction = trail.predictions[0];
  const run = trail.optimization_runs[0];
  const policyEvent = trail.events.find(
    (e) => e.event_type === "decision_evaluated" && (e.reason === "ALLOW" || e.reason === "BLOCK")
  );

  const stages: Stage[] = [
    {
      id: "failed",
      label: "FAILED PAYMENT",
      value: inr(o.amount),
      sub: (o.failure_class ?? "unknown").replace(/_/g, " "),
      time: fmtTime(o.failed_at),
      tone: "neutral",
      iconTone: "blocked",
    },
  ];

  if (prediction) {
    stages.push({
      id: "prediction",
      label: "PREDICTION",
      value: pct(prediction.recovery_probability),
      sub: "P(recovery)",
      time: fmtTime(prediction.created_at),
      tone: "neutral",
    });
  }
  if (run) {
    stages.push({
      id: "value",
      label: "ECONOMIC VALUE",
      value: inr(run.incremental_value, { sign: true }),
      sub: "Incremental EV",
      time: fmtTime(run.created_at),
      tone: "neutral",
    });
  }
  if (policyEvent) {
    stages.push({
      id: "policy",
      label: "POLICY",
      value: policyEvent.reason ?? "",
      sub: policyEvent.reason === "ALLOW" ? "authorized" : "blocked",
      time: fmtTime(policyEvent.timestamp),
      tone: "neutral",
      iconTone: policyEvent.reason === "ALLOW" ? "recovered" : "blocked",
    });
  }
  if (trail.execution) {
    stages.push({
      id: "execution",
      label: "EXECUTION",
      value: trail.execution.state,
      sub: trail.execution.payment_link_id ?? "Created",
      time: fmtTime(trail.execution.created_at),
      tone: "neutral",
    });
  }
  if (trail.outcome) {
    const recovered = trail.outcome.outcome_type === "RECOVERED";
    stages.push({
      id: "outcome",
      label: "OUTCOME",
      value: trail.outcome.outcome_type,
      sub: `${inr(trail.outcome.amount_recovered)} verified`,
      time: fmtTime(trail.outcome.observed_at),
      tone: recovered ? "recovered" : "neutral",
      iconTone: recovered ? "recovered" : "neutral",
    });
  }

  return stages;
}

function pickRepresentative(opportunities: ApiOpportunity[], executions: ApiExecutionRow[]): string | null {
  const recoveredExec = executions.find((e) => e.outcome?.outcome_type === "RECOVERED");
  if (recoveredExec) return recoveredExec.opportunity_id;
  const decided = opportunities.find((o) => o.decision_made);
  if (decided) return decided.opportunity_id;
  return opportunities[0]?.opportunity_id ?? null;
}

function HeroRail({ stages }: { stages: Stage[] }) {
  return (
    <div className="flex items-start overflow-x-auto pb-1">
      {stages.map((s, i) => (
        <div key={s.id} className="flex items-start shrink-0">
          <div className="flex flex-col items-start w-[7.25rem]">
            <StageNode stage={s.id} tone={s.iconTone ?? s.tone} size={30} iconSize={14} />
            <div className="label mt-2.5 leading-snug">{s.label}</div>
            <div className={`fin text-xs font-medium mt-1 leading-snug ${s.tone === "recovered" ? "text-recovered" : "text-ink"}`}>
              {s.value}
            </div>
            <div className="text-[0.625rem] text-ink-3 mt-0.5 leading-snug">{s.sub}</div>
            <div className="mono text-[0.5625rem] text-ink-3 mt-2">{s.time}</div>
          </div>
          {i < stages.length - 1 && (
            <div className="flex items-center h-[30px] w-3.5 shrink-0">
              <span className="w-full border-t border-dashed border-separator" />
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function MiniRail({ stages, representativeId }: { stages: Stage[]; representativeId: string | null }) {
  return (
    <div className="border-l border-separator pl-6 h-full flex flex-col">
      <div className="label mb-5">DECISION RAIL</div>
      <ol className="list-none flex-1">
        {stages.map((s, i) => (
          <li key={s.id} className="relative pl-8 pb-6 last:pb-0">
            <span className="absolute left-0 top-0" aria-hidden="true">
              <StageNode stage={s.id} tone={s.iconTone ?? s.tone} size={22} iconSize={11} />
            </span>
            {i < stages.length - 1 && (
              <span className="absolute left-[10.5px] top-[24px] bottom-0 w-px bg-separator" aria-hidden="true" />
            )}
            <div className="label">{s.label}</div>
            <div className={`fin text-sm font-medium mt-0.5 ${s.tone === "recovered" ? "text-recovered" : "text-ink"}`}>{s.value}</div>
            <div className="text-[0.6875rem] text-ink-3">{s.sub}</div>
          </li>
        ))}
      </ol>
      <Link
        href={representativeId ? `/opportunities/${representativeId}` : "/opportunities"}
        className="t-fast block mt-4 text-xs text-ink-2 hover:text-ink border-t border-separator pt-4"
      >
        Open this opportunity →
      </Link>
    </div>
  );
}

function KpiStrip({
  opportunities,
  executions,
  config,
}: {
  opportunities: ApiOpportunity[];
  executions: ApiExecutionRow[];
  config: ApiConfig | null;
}) {
  const decided = opportunities.filter((o) => o.decision_made).length;
  const actionsSelected = opportunities.filter((o) => o.selected_action === "create_payment_link").length;
  const policyBlocks = opportunities.filter((o) => o.last_decision?.policy_decision === "BLOCK").length;
  const capacityTotal = config?.max_actions_per_day ?? 0;
  const capacityUsed = executions.length;

  const items = [
    { label: "OPPORTUNITIES", value: num(opportunities.length), sub: "Operational total" },
    { label: "DECISIONS MADE", value: num(decided), sub: "Evaluated by RAY" },
    { label: "ACTIONS SELECTED", value: num(actionsSelected), sub: "Payment Link chosen" },
    { label: "POLICY BLOCKS", value: num(policyBlocks), sub: "Blocked by policy" },
    {
      label: "CAPACITY UTILIZATION",
      value: capacityTotal > 0 ? pct(capacityUsed / capacityTotal, 0) : "—",
      sub: `${num(capacityUsed)} / ${num(capacityTotal)} actions`,
      progress: capacityTotal > 0 ? capacityUsed / capacityTotal : 0,
    },
  ];

  return (
    <div className="border border-separator">
      <div className="grid grid-cols-2 md:grid-cols-5">
        {items.map((it, i) => (
          <div key={it.label} className={`p-5 ${i > 0 ? "border-t md:border-t-0 border-separator" : ""}`}>
            <div className="label">{it.label}</div>
            <div className="fin text-3xl font-medium text-ink mt-2">{it.value}</div>
            <div className="text-[0.6875rem] text-ink-3 mt-0.5 mb-2">{it.sub}</div>
            {it.progress !== undefined && <ProgressBar value={it.progress} width={80} />}
          </div>
        ))}
      </div>
    </div>
  );
}

function RecoveryComposition({ executions }: { executions: ApiExecutionRow[] }) {
  const total = executions.reduce((s, e) => s + e.amount, 0);
  const recovered = executions
    .filter((e) => e.outcome?.outcome_type === "RECOVERED")
    .reduce((s, e) => s + (e.outcome?.amount_recovered ?? 0), 0);
  const pending = executions.filter((e) => !e.outcome).reduce((s, e) => s + e.amount, 0);
  const notRecovered = Math.max(total - recovered - pending, 0);

  const segs = [
    { label: "RECOVERED", value: recovered, cls: "bg-recovered" },
    { label: "PENDING", value: pending, cls: "bg-pending" },
    { label: "NOT RECOVERED", value: notRecovered, cls: "bg-ink-3" },
  ];

  return (
    <div>
      <div className="label mb-4">RECOVERY COMPOSITION (ALL EXECUTIONS)</div>
      <div className="h-2 rounded-full overflow-hidden flex bg-surface-2">
        {segs.map((s) => (
          <div key={s.label} className={`h-full ${s.cls} t-slow`} style={{ width: `${total > 0 ? (s.value / total) * 100 : 0}%` }} />
        ))}
      </div>
      <div className="flex flex-wrap gap-x-8 gap-y-2 mt-4">
        {segs.map((s) => (
          <div key={s.label} className="flex items-center gap-2 text-xs">
            <span className={`w-2 h-2 rounded-full ${s.cls}`} />
            <span className="text-ink-2">{s.label}</span>
            <span className="fin text-ink">{inr(s.value)}</span>
            <span className="text-ink-3">({total > 0 ? pct(s.value / total, 1) : "0%"})</span>
          </div>
        ))}
        <div className="text-xs text-ink-3 ml-auto">
          TOTAL ATTEMPTED <span className="fin text-ink-2">{inr(total)}</span>
        </div>
      </div>
    </div>
  );
}

export default function OverviewPage() {
  const [opportunities, setOpportunities] = useState<ApiOpportunity[] | null>(null);
  const [executions, setExecutions] = useState<ApiExecutionRow[] | null>(null);
  const [config, setConfig] = useState<ApiConfig | null>(null);
  const [trail, setTrail] = useState<ApiAuditTrail | null>(null);
  const [representativeId, setRepresentativeId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    setOpportunities(null);
    setExecutions(null);
    setTrail(null);
    try {
      const [oppRes, execRes, configRes] = await Promise.all([
        api.listOpportunities(),
        api.listExecutions(),
        api.getConfig(),
      ]);
      setOpportunities(oppRes.opportunities);
      setExecutions(execRes.executions);
      setConfig(configRes);

      const repId = pickRepresentative(oppRes.opportunities, execRes.executions);
      setRepresentativeId(repId);
      if (repId) {
        try {
          setTrail(await api.getAudit(repId));
        } catch {
          setTrail(null);
        }
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load the RAY overview.");
    }
  }, []);

  useEffect(() => {
    const id = setTimeout(load, 0);
    return () => clearTimeout(id);
  }, [load]);

  if (opportunities === null && executions === null && !error) {
    return <LoadingState label="Loading operational overview from the RAY backend…" />;
  }
  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!opportunities || !executions) return <LoadingState label="Loading operational overview from the RAY backend…" />;
  if (opportunities.length === 0) {
    return <EmptyState message="No operational opportunities yet. Seed data has not been loaded." />;
  }

  const recentExec = executions.slice(0, 5);
  const blocks = opportunities.filter((o) => o.last_decision?.policy_decision === "BLOCK").slice(0, 5);
  const stages = trail ? buildStages(trail) : [];
  const recoveredTotal = executions
    .filter((e) => e.outcome?.outcome_type === "RECOVERED")
    .reduce((s, e) => s + (e.outcome?.amount_recovered ?? 0), 0);

  return (
    <div className="space-y-10">
      {/* ── Hero ────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_18rem] gap-10 items-stretch">
        <div className="min-w-0">
          <div className="flex items-start justify-between gap-8 flex-wrap mb-8">
            <div className="max-w-lg">
              <h1 className="text-3xl lg:text-4xl font-medium tracking-tight leading-snug">
                Autonomous recovery decisions
                <br />
                for failed payments.
              </h1>
              <p className="text-sm text-ink-2 mt-4 leading-relaxed">
                RAY diagnoses each failure, predicts recovery, evaluates economics,
                enforces policy, executes safely, and verifies outcomes.
              </p>
            </div>

            <div>
              <div className="label mb-2">RECOVERED</div>
              <div className="fin text-4xl font-medium text-ink">
                <CountUp value={recoveredTotal} format={(n) => inr(n)} />
              </div>
              <div className="text-[0.6875rem] text-recovered mt-1.5">VERIFIED RECOVERY</div>
            </div>
          </div>

          {stages.length > 0 ? (
            <HeroRail stages={stages} />
          ) : (
            <p className="text-xs text-ink-3">No decisions recorded yet.</p>
          )}
        </div>

        <MiniRail stages={stages} representativeId={representativeId} />
      </div>

      {/* ── KPI strip ───────────────────────────────────────── */}
      <KpiStrip opportunities={opportunities} executions={executions} config={config} />

      {/* ── Feed + executions + blocks ──────────────────────── */}
      <div className="grid lg:grid-cols-3 gap-8">
        <div>
          <Label>DECISION ACTIVITY</Label>
          <div className="mt-4">
            <LiveFeed opportunities={opportunities} limit={7} />
          </div>
          <Link href="/decisions" className="t-fast inline-block mt-4 text-xs text-ink-2 hover:text-ink">
            View all activity →
          </Link>
        </div>

        <div>
          <Label>RECENT EXECUTIONS</Label>
          <div className="mt-4">
            {recentExec.length === 0 && <p className="text-xs text-ink-3 py-2">No executions yet.</p>}
            {recentExec.map((e) => (
              <Link
                key={e.execution_id}
                href={`/execution/${e.opportunity_id}`}
                className="t-fast grid grid-cols-[1fr_auto_auto] items-baseline gap-4 py-2.5 border-b border-separator/50 last:border-b-0 hover:bg-surface-2 -mx-2 px-2 rounded-sm"
              >
                <span className="min-w-0">
                  <span className="mono text-[0.6875rem] text-ink-2 block truncate">{e.payment_link_id ?? e.execution_id}</span>
                  <span className="mono text-[0.625rem] text-ink-3">{e.reference_id}</span>
                </span>
                <span className="fin text-xs text-ink">{inr(e.amount)}</span>
                <OutcomeBadge
                  outcome={
                    e.outcome?.outcome_type === "RECOVERED"
                      ? "RECOVERED"
                      : e.outcome
                        ? "NOT_RECOVERED"
                        : "PENDING"
                  }
                />
              </Link>
            ))}
          </div>
          <Link href="/execution" className="t-fast inline-block mt-4 text-xs text-ink-2 hover:text-ink">
            View all executions →
          </Link>
        </div>

        <div>
          <Label>POLICY BLOCKS</Label>
          <div className="mt-4">
            {blocks.length === 0 && <p className="text-xs text-ink-3 py-2">No policy blocks recorded.</p>}
            {blocks.map((o) => (
              <Link
                key={o.opportunity_id}
                href={`/decisions/${o.opportunity_id}`}
                className="t-fast block py-2.5 border-b border-separator/50 last:border-b-0 hover:bg-surface-2 -mx-2 px-2 rounded-sm"
              >
                <div className="flex items-baseline justify-between gap-4">
                  <span className="mono text-[0.6875rem] text-blocked">{o.last_decision?.policy_reason ?? "BLOCKED"}</span>
                  <span className="fin text-xs text-ink-2">{inr(o.amount)}</span>
                </div>
                <div className="text-[0.6875rem] text-ink-3 mt-0.5">{o.customer_name}</div>
              </Link>
            ))}
          </div>
          <Link href="/decisions" className="t-fast inline-block mt-4 text-xs text-ink-2 hover:text-ink">
            View all policy blocks →
          </Link>
        </div>
      </div>

      {/* ── Recovery composition ────────────────────────────── */}
      <div className="rule pt-8">
        <RecoveryComposition executions={executions} />
      </div>
    </div>
  );
}
