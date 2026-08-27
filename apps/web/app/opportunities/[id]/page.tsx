"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ExternalLink } from "lucide-react";
import { api, ApiError, type ApiOpportunity, type ApiEvaluation, type ApiExecutionStatus } from "@/lib/api";
import { inr, pct } from "@/lib/format";
import { KV, Label, Section, TestModeTag } from "@/components/ui";
import { StageNode } from "@/components/StageIcon";
import { LoadingState, ErrorState } from "@/components/DataState";
import { PolicyRuleList } from "@/components/PolicyRuleList";

const POLL_INTERVAL_MS = 4000;
const POLL_MAX_ATTEMPTS = 30; // ~2 minutes, then stop hammering the backend

function terminalOutcome(status: ApiExecutionStatus | null): boolean {
  const t = status?.outcome?.outcome_type;
  return t === "RECOVERED" || t === "EXPIRED" || t === "CANCELLED" || t === "PARTIALLY_RECOVERED";
}

export default function OpportunityDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [opportunity, setOpportunity] = useState<ApiOpportunity | null>(null);
  const [evaluation, setEvaluation] = useState<ApiEvaluation | null>(null);
  const [status, setStatus] = useState<ApiExecutionStatus | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [executing, setExecuting] = useState(false);
  const [executeError, setExecuteError] = useState<string | null>(null);

  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pollAttempts = useRef(0);

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
      setError(e instanceof ApiError ? e.message : "Failed to load this opportunity.");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    const timer = setTimeout(load, 0);
    return () => clearTimeout(timer);
  }, [load]);

  // Poll for webhook/outcome updates once an execution exists and isn't terminal yet.
  useEffect(() => {
    if (!status?.execution || terminalOutcome(status)) return;

    const tick = async () => {
      pollAttempts.current += 1;
      try {
        const next = await api.getStatus(id);
        setStatus(next);
        if (!terminalOutcome(next) && pollAttempts.current < POLL_MAX_ATTEMPTS) {
          pollRef.current = setTimeout(tick, POLL_INTERVAL_MS);
        }
      } catch {
        // Transient failure — try again on the next tick rather than surfacing an error banner.
        if (pollAttempts.current < POLL_MAX_ATTEMPTS) {
          pollRef.current = setTimeout(tick, POLL_INTERVAL_MS);
        }
      }
    };

    pollRef.current = setTimeout(tick, POLL_INTERVAL_MS);
    return () => {
      if (pollRef.current) clearTimeout(pollRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, status?.execution?.execution_id]);

  const handleExecute = async () => {
    setExecuting(true);
    setExecuteError(null);
    try {
      const result = await api.execute(id);
      if (!result.success) {
        setExecuteError(result.error_message ?? "Execution failed.");
      }
      const next = await api.getStatus(id);
      setStatus(next);
      pollAttempts.current = 0;
    } catch (e) {
      setExecuteError(e instanceof ApiError ? e.message : "Execution failed.");
    } finally {
      setExecuting(false);
    }
  };

  if (loading) return <LoadingState label="Loading opportunity and requesting a decision…" />;
  if (error || !opportunity) return <ErrorState message={error ?? "Opportunity not found."} onRetry={load} />;

  const o = opportunity;
  const policy = evaluation?.policy;
  const hasExecution = !!status?.execution;
  const canExecute =
    evaluation?.optimizer.recommended_action === "create_payment_link" &&
    policy?.decision === "ALLOW" &&
    !hasExecution;

  return (
    <div className="space-y-10">
      <header className="flex items-start justify-between gap-6 flex-wrap">
        <div>
          <div className="flex items-center gap-3">
            <Label>RECOVERY OPPORTUNITY</Label>
            <span className="text-[0.625rem] tracking-[0.1em] text-ink-3">LIVE — BACKEND CONNECTED</span>
          </div>
          <h1 className="fin text-4xl lg:text-5xl font-medium tracking-tight mt-3">{inr(o.amount)}</h1>
          <div className="text-sm text-ink-2 mt-2">
            {(o.failure_class ?? "unknown").replace(/_/g, " ")} · {o.customer_name}
          </div>
        </div>
        <div className="text-right space-y-1">
          <div className="mono text-xs text-ink-3">{o.opportunity_id}</div>
          {o.failed_at && <div className="mono text-xs text-ink-3">{new Date(o.failed_at).toLocaleString()}</div>}
        </div>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)] gap-10 lg:gap-14">
        {/* ── LEFT: observable facts ─────────────────────────── */}
        <div className="space-y-8">
          <Section title="PAYMENT">
            <KV k="Amount" v={inr(o.amount)} monoV />
            <KV k="Failure class" v={(o.failure_class ?? "unknown").replace(/_/g, " ")} />
            <KV k="Payment method" v={(o.payment_method ?? "unknown").replace(/_/g, " ")} />
            <KV k="Failed at" v={o.failed_at ? new Date(o.failed_at).toLocaleString() : "—"} monoV />
          </Section>

          <Section title="CUSTOMER">
            <KV k="Name" v={o.customer_name} />
            <KV k="Customer ID" v={o.customer_id} monoV />
          </Section>
        </div>

        {/* ── RIGHT: the RAY decision ────────────────────────── */}
        <div className="space-y-8">
          <Section title="RAY DECISION">
            {evaluation ? (
              <>
                <div className="grid grid-cols-2 gap-x-8 gap-y-6 mb-2">
                  <div>
                    <div className="label mb-1.5">PROBABILITY</div>
                    <div className="fin text-3xl font-medium">{pct(evaluation.prediction.recovery_probability)}</div>
                    <div className="text-[0.6875rem] text-ink-3 mt-1">MODEL ESTIMATE · v{evaluation.prediction.model_version}</div>
                  </div>
                  <div>
                    <div className="label mb-1.5">EXPECTED RECOVERY</div>
                    <div className="fin text-3xl font-medium text-ink-2">{inr(evaluation.economics.gross_ev)}</div>
                    <div className="text-[0.6875rem] text-ink-3 mt-1">MODEL ESTIMATE</div>
                  </div>
                </div>

                <div className="border-l border-separator pl-4 mt-6">
                  <KV k="Payment-link net EV" v={inr(evaluation.economics.net_ev)} monoV />
                  <KV k="Do-nothing EV" v={inr(evaluation.economics.do_nothing_ev)} monoV />
                  <KV k="Incremental EV" v={inr(evaluation.economics.incremental_ev, { sign: true })} monoV />
                  <KV k="Recommended action" v={evaluation.optimizer.recommended_action.toUpperCase()} monoV />
                </div>
              </>
            ) : (
              <p className="text-xs text-ink-3">No decision requested yet.</p>
            )}
          </Section>

          <Section title="POLICY">
            {!policy ? (
              <p className="text-xs text-ink-3">
                Not evaluated — the optimizer selected do-nothing, so no execution authorization was required.
              </p>
            ) : (
              <>
                <PolicyRuleList rules={policy.rules} dense />
                <div className="mt-5 flex items-center justify-between">
                  <span className="label">RESULT</span>
                  <span className={`text-sm font-medium tracking-[0.14em] ${policy.decision === "ALLOW" ? "text-ink" : "text-blocked"}`}>
                    {policy.decision}
                  </span>
                </div>
                <p className="text-[0.6875rem] text-ink-3 mt-4">OPTIMIZER CHOOSES. POLICY AUTHORIZES.</p>
              </>
            )}
          </Section>

          <Section title="EXECUTION" action={<TestModeTag />}>
            {hasExecution && status?.execution ? (
              <>
                <KV k="State" v={status.execution.state} monoV />
                <KV k="Execution ID" v={status.execution.execution_id} monoV />
                {status.execution.payment_link_id && <KV k="Payment Link" v={status.execution.payment_link_id} monoV />}
                <KV k="Reference" v={status.execution.reference_id} monoV />
                {status.execution.short_url && (
                  <div className="mt-4">
                    <a
                      href={status.execution.short_url}
                      target="_blank"
                      rel="noreferrer"
                      className="t-fast inline-flex items-center gap-1.5 text-xs text-ink-2 hover:text-ink border-b border-separator pb-0.5"
                    >
                      OPEN PAYMENT LINK
                      <ExternalLink size={12} strokeWidth={1.75} />
                    </a>
                  </div>
                )}

                <div className="mt-6 pt-4 border-t border-separator">
                  <div className="label mb-2">RECOVERY STATE</div>
                  <div className="flex items-center gap-2 flex-wrap text-[0.6875rem] tracking-[0.08em] font-medium">
                    <span className="text-ink">RECEIVED</span>
                    <span className="w-4 h-px bg-separator" />
                    <span className={status.webhook ? "text-ink" : "text-ink-3"}>VERIFIED</span>
                    <span className="w-4 h-px bg-separator" />
                    <span className={status.outcome ? "text-recovered" : "text-ink-3"}>RECORDED</span>
                  </div>
                  {status.outcome ? (
                    <div className="mt-3 anim-fade-up">
                      <div className="fin text-2xl font-medium text-recovered">{inr(status.outcome.amount_recovered)}</div>
                      <div className="text-[0.6875rem] text-recovered mt-1">{status.outcome.outcome_type} · VERIFIED RECOVERY</div>
                    </div>
                  ) : (
                    <p className="text-[0.6875rem] text-ink-3 mt-2">
                      Awaiting payment. This page checks for updates automatically.
                    </p>
                  )}
                </div>
              </>
            ) : canExecute ? (
              <>
                <p className="text-xs text-ink-2 leading-relaxed mb-4">
                  Policy has authorized <span className="text-ink">create_payment_link</span> for{" "}
                  <span className="fin text-ink">{inr(o.amount)}</span> to {o.customer_name}. Expected recovery{" "}
                  {evaluation && <span className="fin text-ink">{inr(evaluation.economics.gross_ev)}</span>}, incremental EV{" "}
                  {evaluation && <span className="fin text-ink">{inr(evaluation.economics.incremental_ev, { sign: true })}</span>}.
                  This will create exactly one Razorpay Payment Link in Test Mode; the idempotency key prevents duplicates.
                </p>
                {executeError && <p className="text-xs text-blocked mb-3">{executeError}</p>}
                <button
                  onClick={handleExecute}
                  disabled={executing}
                  className="t-fast px-6 py-2.5 bg-ink text-canvas text-xs font-medium tracking-[0.18em] hover:bg-ink-2 disabled:opacity-50"
                >
                  {executing ? "CREATING…" : "CREATE PAYMENT LINK"}
                </button>
              </>
            ) : (
              <p className="text-xs text-ink-3">
                {policy?.decision === "BLOCK"
                  ? "Policy blocked this action — nothing to execute."
                  : "The optimizer selected do-nothing — no execution authorization was required."}
              </p>
            )}
          </Section>
        </div>
      </div>

      {/* ── Decision trace summary ───────────────────────────── */}
      <Section title="DECISION TRACE">
        <ol className="list-none max-w-lg">
          <TraceRow stage="failed" tone="blocked" label="FAILED PAYMENT" value={inr(o.amount)} sub={(o.failure_class ?? "unknown").replace(/_/g, " ")} />
          {evaluation && (
            <TraceRow stage="prediction" label="PREDICTION" value={pct(evaluation.prediction.recovery_probability)} sub="P(recovery) · model estimate" />
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
        <Link href={`/audit/${id}`} className="t-fast text-xs text-ink-2 hover:text-ink border-b border-separator pb-0.5">
          Open audit trail →
        </Link>
      </Section>
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
