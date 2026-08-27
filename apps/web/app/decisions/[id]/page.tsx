"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api, ApiError, type ApiOpportunity, type ApiEvaluation, type ApiExecutionStatus } from "@/lib/api";
import { inr, pct } from "@/lib/format";
import { Label, Section, KV } from "@/components/ui";
import { StageNode } from "@/components/StageIcon";
import { LoadingState, ErrorState } from "@/components/DataState";

const POLICY_RULE_LABELS: Record<string, string> = {
  VALID_ACTION_TYPE: "VALID_ACTION_TYPE",
  OPPORTUNITY_ACTIONABLE: "OPPORTUNITY_ACTIONABLE",
  DO_NOT_CONTACT_CHECK: "DO_NOT_CONTACT_CHECK",
  DUPLICATE_ACTION_CHECK: "DUPLICATE_ACTION_CHECK",
  AUTONOMOUS_AMOUNT_LIMIT_CHECK: "AUTONOMOUS_AMOUNT_LIMIT_CHECK",
  MAX_CONTACTS_CHECK: "MAX_CONTACTS_CHECK",
  DAILY_CAPACITY_CHECK: "DAILY_CAPACITY_CHECK",
};

export default function DecisionDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [opportunity, setOpportunity] = useState<ApiOpportunity | null>(null);
  const [evaluation, setEvaluation] = useState<ApiEvaluation | null>(null);
  const [status, setStatus] = useState<ApiExecutionStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [opp, evalResult, statusResult] = await Promise.all([
        api.getOpportunity(id),
        api.evaluate(id),
        api.getStatus(id).catch(() => null),
      ]);
      setOpportunity(opp);
      setEvaluation(evalResult);
      setStatus(statusResult);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load this decision.");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    const timer = setTimeout(load, 0);
    return () => clearTimeout(timer);
  }, [load]);

  if (loading) return <LoadingState label="Loading decision record from the RAY backend…" />;
  if (error || !opportunity) return <ErrorState message={error ?? "Decision not found."} onRetry={load} />;

  const o = opportunity;
  const policy = evaluation?.policy;
  const hasExecution = !!status?.execution;

  return (
    <div className="space-y-10">
      <header className="flex items-start justify-between gap-6 flex-wrap">
        <div>
          <div className="flex items-center gap-3">
            <Label>DECISION RECORD</Label>
            <span className="text-[0.625rem] tracking-[0.1em] text-ink-3">LIVE — BACKEND CONNECTED</span>
          </div>
          <h1 className="text-2xl font-medium tracking-tight mt-3">
            {o.customer_name} · <span className="fin">{inr(o.amount)}</span>
          </h1>
          <div className="mono text-xs text-ink-3 mt-2">{o.opportunity_id}</div>
        </div>
        <Link
          href={`/opportunities/${o.opportunity_id}`}
          className="t-fast text-xs text-ink-2 hover:text-ink border-b border-separator pb-0.5"
        >
          Open opportunity →
        </Link>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)] gap-10 lg:gap-14">
        <Section title="DECISION TRACE">
          <ol className="list-none max-w-lg">
            <TraceRow
              stage="failed"
              tone="blocked"
              label="FAILED PAYMENT"
              value={inr(o.amount)}
              sub={(o.failure_class ?? "unknown").replace(/_/g, " ")}
            />
            {evaluation && (
              <TraceRow
                stage="prediction"
                label="PREDICTION"
                value={pct(evaluation.prediction.recovery_probability)}
                sub={`P(recovery) · model v${evaluation.prediction.model_version}`}
              />
            )}
            {evaluation && (
              <TraceRow
                stage="value"
                label="ECONOMIC VALUE"
                value={inr(evaluation.economics.incremental_ev, { sign: true })}
                sub="incremental EV vs do-nothing"
              />
            )}
            {evaluation && (
              <TraceRow
                stage="optimizer"
                label="OPTIMIZER"
                value={evaluation.optimizer.recommended_action.toUpperCase()}
                sub={`optimizer v${evaluation.optimizer.optimizer_version}`}
              />
            )}
            {policy && (
              <TraceRow
                stage="policy"
                tone={policy.decision === "ALLOW" ? "neutral" : "blocked"}
                label="POLICY"
                value={policy.decision}
                sub={`policy v${policy.policy_version}`}
              />
            )}
            {hasExecution && status?.execution && (
              <TraceRow stage="execution" label="EXECUTION" value={status.execution.state} sub={status.execution.payment_link_id ?? ""} />
            )}
            {status?.webhook && <TraceRow stage="webhook" label="WEBHOOK" value="VERIFIED" sub={status.webhook.event_type} />}
            {status?.outcome && (
              <TraceRow
                stage="outcome"
                tone="recovered"
                label="OUTCOME"
                value={inr(status.outcome.amount_recovered)}
                sub="verified recovery"
                isLast
              />
            )}
          </ol>
        </Section>

        <div className="space-y-8">
          {policy ? (
            <Section title="POLICY EVALUATION">
              <div className="space-y-1.5">
                {policy.rules.map((r) => (
                  <div key={r.rule_id} className="flex items-center justify-between gap-4">
                    <span className={`mono text-[0.6875rem] ${r.passed ? "text-ink-2" : "text-blocked"}`}>
                      {POLICY_RULE_LABELS[r.rule_id] ?? r.rule_id}
                    </span>
                    <span className={`mono text-[0.6875rem] ${r.passed ? "text-ink-2" : "text-blocked"}`}>
                      {r.passed ? "✓ PASS" : "✕ BLOCK"}
                    </span>
                  </div>
                ))}
              </div>
              <div className="mt-5 flex items-center justify-between">
                <span className="label">RESULT</span>
                <span className={`text-sm font-medium tracking-[0.14em] ${policy.decision === "ALLOW" ? "text-ink" : "text-blocked"}`}>
                  {policy.decision}
                </span>
              </div>
              <p className="text-[0.6875rem] text-ink-3 mt-4">OPTIMIZER CHOOSES. POLICY AUTHORIZES.</p>
            </Section>
          ) : (
            <Section title="POLICY EVALUATION">
              <p className="text-xs text-ink-3">
                Not evaluated — the optimizer selected do-nothing, so no execution authorization was required.
              </p>
            </Section>
          )}

          <Section title="EXECUTION & RECOVERY">
            {hasExecution && status?.execution ? (
              <>
                <KV k="State" v={status.execution.state} monoV />
                <KV k="Payment Link" v={status.execution.payment_link_id ?? "—"} monoV />
                <KV k="Reference" v={status.execution.reference_id} monoV />
                <KV k="Webhook" v={status.webhook ? "VERIFIED" : "AWAITING"} monoV />
                <KV
                  k="Outcome"
                  v={status.outcome ? `${inr(status.outcome.amount_recovered)} RECOVERED` : "PENDING"}
                  monoV
                />
                <Link
                  href={`/execution/${o.opportunity_id}`}
                  className="t-fast inline-block mt-4 text-xs text-ink-2 hover:text-ink border-b border-separator pb-0.5"
                >
                  Open execution record →
                </Link>
              </>
            ) : policy?.decision === "ALLOW" ? (
              <p className="text-xs text-ink-3">
                Policy authorizes execution.{" "}
                <Link
                  href={`/opportunities/${o.opportunity_id}`}
                  className="text-ink-2 hover:text-ink border-b border-separator pb-0.5"
                >
                  Open opportunity to execute →
                </Link>
              </p>
            ) : (
              <p className="text-xs text-ink-3">
                {policy?.decision === "BLOCK"
                  ? "Policy blocked this action — nothing to execute."
                  : "The optimizer selected do-nothing — no execution authorization was required."}
              </p>
            )}
          </Section>

          <Section title="PROVENANCE">
            <KV k="Model" v={evaluation ? `v${evaluation.prediction.model_version}` : "—"} monoV />
            <KV k="Optimizer" v={evaluation ? `v${evaluation.optimizer.optimizer_version}` : "—"} monoV />
            <KV k="Policy" v={policy ? `v${policy.policy_version}` : "—"} monoV />
          </Section>
        </div>
      </div>
    </div>
  );
}

function TraceRow({
  stage,
  label,
  value,
  sub,
  tone = "neutral",
  isLast = false,
}: {
  stage: string;
  label: string;
  value: string;
  sub?: string;
  tone?: "neutral" | "recovered" | "blocked";
  isLast?: boolean;
}) {
  return (
    <li className="relative pl-11">
      <span className="absolute left-0 top-0" aria-hidden="true">
        <StageNode stage={stage} tone={tone} size={30} iconSize={14} />
      </span>
      {!isLast && <span className="absolute left-[14.5px] top-[34px] bottom-[-6px] w-px bg-separator" aria-hidden="true" />}
      <div className="pb-8 pt-1">
        <div className="label">{label}</div>
        <div className={`fin text-lg font-medium mt-1 ${tone === "recovered" ? "text-recovered" : tone === "blocked" ? "text-blocked" : "text-ink"}`}>
          {value}
        </div>
        {sub && <div className="text-xs text-ink-3 mt-0.5">{sub}</div>}
      </div>
    </li>
  );
}
