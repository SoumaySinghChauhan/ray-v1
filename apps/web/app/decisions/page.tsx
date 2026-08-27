"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { X } from "lucide-react";
import { api, ApiError, type ApiOpportunity, type ApiEvaluation, type ApiExecutionStatus } from "@/lib/api";
import { inr, pct, num } from "@/lib/format";
import { Label, KpiCards } from "@/components/ui";
import { StageNode } from "@/components/StageIcon";
import { LoadingState, ErrorState, EmptyState } from "@/components/DataState";
import { PolicyRuleList } from "@/components/PolicyRuleList";

type Filter = "ALL" | "ALLOWED" | "BLOCKED" | "SKIPPED";

function rowStatus(o: ApiOpportunity): Filter {
  if (o.last_decision?.selected_action === "do_nothing") return "SKIPPED";
  if (o.last_decision?.policy_decision === "BLOCK") return "BLOCKED";
  if (o.last_decision?.policy_decision === "ALLOW") return "ALLOWED";
  return "SKIPPED";
}

export default function DecisionsPage() {
  const [opportunities, setOpportunities] = useState<ApiOpportunity[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("ALL");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    setOpportunities(null);
    try {
      const res = await api.listOpportunities();
      setOpportunities(res.opportunities);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load decisions.");
    }
  }, []);

  useEffect(() => {
    const id = setTimeout(load, 0);
    return () => clearTimeout(id);
  }, [load]);

  const decided = useMemo(() => (opportunities ?? []).filter((o) => o.decision_made), [opportunities]);
  const allowed = useMemo(() => decided.filter((o) => o.last_decision?.policy_decision === "ALLOW"), [decided]);
  const blocked = useMemo(() => decided.filter((o) => o.last_decision?.policy_decision === "BLOCK"), [decided]);
  const recoveredInr = useMemo(() => decided.filter((o) => o.recovered).reduce((s, o) => s + o.amount, 0), [decided]);
  const predictedNetEv = useMemo(
    () => decided.reduce((s, o) => s + (o.last_decision?.expected_value ?? 0), 0),
    [decided]
  );

  const rows = useMemo(() => {
    const list = (opportunities ?? []).filter((o) => o.decision_made);
    if (filter === "ALL") return list;
    return list.filter((o) => rowStatus(o) === filter);
  }, [opportunities, filter]);

  return (
    <div className="space-y-8">
      <header>
        <Label>OPERATIONS</Label>
        <h1 className="text-2xl font-medium tracking-tight mt-2">Decisions</h1>
        <p className="text-sm text-ink-2 mt-2 max-w-lg">Every decision RAY reached — with full reasoning trace.</p>
      </header>

      {opportunities === null && !error && <LoadingState label="Loading decisions from the RAY backend…" />}
      {error && <ErrorState message={error} onRetry={load} />}

      {opportunities !== null && !error && (
        <>
          <KpiCards
            items={[
              { label: "TOTAL DECISIONS", value: num(decided.length), sub: "All time" },
              { label: "ALLOWED", value: num(allowed.length), sub: decided.length > 0 ? pct(allowed.length / decided.length, 0) : "—", tone: "recovered" },
              { label: "BLOCKED", value: num(blocked.length), sub: decided.length > 0 ? pct(blocked.length / decided.length, 0) : "—", tone: "blocked" },
              { label: "RECOVERED", value: inr(recoveredInr), sub: "From allowed", tone: "recovered" },
              { label: "PREDICTED NET EV", value: inr(predictedNetEv), sub: "Model estimate" },
            ]}
          />

          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex gap-1">
              {(["ALL", "ALLOWED", "BLOCKED", "SKIPPED"] as Filter[]).map((f) => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  aria-pressed={filter === f}
                  className={`t-fast px-3 py-1.5 text-[0.6875rem] tracking-[0.1em] rounded-sm ${
                    filter === f ? "bg-surface-3 text-ink" : "text-ink-3 hover:text-ink-2 hover:bg-surface-2"
                  }`}
                >
                  {f}
                </button>
              ))}
            </div>
          </div>

          <div className={`grid grid-cols-1 gap-8 ${selectedId ? "xl:grid-cols-[minmax(0,1fr)_23rem]" : ""}`}>
            <div className="min-w-0">
              {rows.length === 0 ? (
                <EmptyState message="No decisions match this filter." />
              ) : (
                <div className="overflow-x-auto -mx-5 px-5 xl:mx-0 xl:px-0">
                  <table className="w-full text-left min-w-[46rem]">
                    <thead>
                      <tr className="border-b border-separator">
                        <th className="label py-3 pr-4 font-medium">TIME</th>
                        <th className="label py-3 pr-4 font-medium">CUSTOMER</th>
                        <th className="label py-3 pr-4 font-medium">AMOUNT</th>
                        <th className="label py-3 pr-4 font-medium">P(RECOVERY)</th>
                        <th className="label py-3 pr-4 font-medium">INCR. EV</th>
                        <th className="label py-3 pr-4 font-medium">ACTION</th>
                        <th className="label py-3 pr-4 font-medium">POLICY</th>
                        <th className="label py-3 pr-2 font-medium">OUTCOME</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((o) => {
                        const p = o.last_decision?.recovery_probability;
                        const ev = o.last_decision?.incremental_ev;
                        const selected = selectedId === o.opportunity_id;
                        return (
                          <tr
                            key={o.opportunity_id}
                            onClick={() => setSelectedId(o.opportunity_id)}
                            className={`t-fast cursor-pointer border-b border-separator/40 border-l-2 ${
                              selected ? "border-l-recovered bg-surface-2" : "border-l-transparent hover:bg-surface-2"
                            }`}
                          >
                            <td className="py-3 pr-4 pl-3 mono text-[0.625rem] text-ink-3">
                              {o.failed_at ? new Date(o.failed_at).toLocaleTimeString() : "—"}
                            </td>
                            <td className="py-3 pr-4">
                              <span className="text-xs text-ink block">{o.customer_name}</span>
                              <span className="mono text-[0.625rem] text-ink-3">{o.opportunity_id.slice(0, 12)}…</span>
                            </td>
                            <td className="py-3 pr-4 fin text-xs text-ink">{inr(o.amount)}</td>
                            <td className="py-3 pr-4">
                              {p != null ? (
                                <div className="flex items-center gap-2">
                                  <span className="fin text-xs text-ink">{pct(p)}</span>
                                  <span className="hidden sm:block w-14 h-[3px] rounded-full bg-separator overflow-hidden">
                                    <span className="block h-full bg-ink-2" style={{ width: `${Math.min(p * 100, 100)}%` }} />
                                  </span>
                                </div>
                              ) : (
                                <span className="text-ink-3 text-xs">—</span>
                              )}
                            </td>
                            <td className={`py-3 pr-4 fin text-xs ${ev != null && ev >= 0 ? "text-recovered" : ev != null ? "text-blocked" : "text-ink-3"}`}>
                              {ev != null ? inr(ev, { sign: true }) : "—"}
                            </td>
                            <td className="py-3 pr-4 mono text-[0.625rem] text-ink-2">
                              {o.selected_action ? o.selected_action.toUpperCase() : "—"}
                            </td>
                            <td className="py-3 pr-4">
                              <span className={`text-[0.625rem] tracking-[0.08em] font-medium ${o.last_decision?.policy_decision === "BLOCK" ? "text-blocked" : o.last_decision?.policy_decision === "ALLOW" ? "text-ink" : "text-ink-3"}`}>
                                {o.last_decision?.policy_decision ?? "—"}
                              </span>
                            </td>
                            <td className="py-3 pr-2 text-[0.6875rem]">
                              {o.recovered ? (
                                <span className="text-recovered">RECOVERED</span>
                              ) : o.last_decision?.policy_decision === "BLOCK" ? (
                                <span className="text-blocked">BLOCKED</span>
                              ) : o.selected_action === "create_payment_link" ? (
                                <span className="text-pending">PENDING</span>
                              ) : (
                                <span className="text-ink-3">—</span>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {selectedId && (
              <DecisionTracePanel opportunityId={selectedId} onClose={() => setSelectedId(null)} />
            )}
          </div>
        </>
      )}
    </div>
  );
}

function DecisionTracePanel({ opportunityId, onClose }: { opportunityId: string; onClose: () => void }) {
  const [tab, setTab] = useState<"TRACE" | "POLICY" | "PROVENANCE">("TRACE");
  const [opportunity, setOpportunity] = useState<ApiOpportunity | null>(null);
  const [evaluation, setEvaluation] = useState<ApiEvaluation | null>(null);
  const [status, setStatus] = useState<ApiExecutionStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    setOpportunity(null);
    setEvaluation(null);
    setStatus(null);
    try {
      const [opp, evalResult, statusResult] = await Promise.all([
        api.getOpportunity(opportunityId),
        api.evaluate(opportunityId),
        api.getStatus(opportunityId).catch(() => null),
      ]);
      setOpportunity(opp);
      setEvaluation(evalResult);
      setStatus(statusResult);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load this decision trace.");
    }
  }, [opportunityId]);

  useEffect(() => {
    const timer = setTimeout(() => {
      setTab("TRACE");
      load();
    }, 0);
    return () => clearTimeout(timer);
  }, [load]);

  const policy = evaluation?.policy;

  return (
    <aside className="xl:sticky xl:top-24 xl:self-start border border-separator bg-surface-1 anim-fade-up">
      <div className="flex items-center justify-between px-5 py-4 border-b border-separator">
        <div className="label">DECISION TRACE</div>
        <button onClick={onClose} aria-label="Close decision trace" className="t-fast text-ink-3 hover:text-ink">
          <X size={15} strokeWidth={1.75} />
        </button>
      </div>

      {!opportunity && !error && <LoadingState label="Loading trace…" />}
      {error && <ErrorState message={error} onRetry={load} />}

      {opportunity && !error && (
        <>
          <div className="px-5 py-4 border-b border-separator">
            <div className="flex items-center gap-2 mb-3">
              {policy && (
                <span className={`text-[0.625rem] tracking-[0.1em] font-medium px-2 py-0.5 border ${policy.decision === "ALLOW" ? "border-separator text-ink" : "border-blocked text-blocked"}`}>
                  {policy.decision === "ALLOW" ? "ALLOWED" : "BLOCKED"}
                </span>
              )}
              {status?.outcome?.outcome_type === "RECOVERED" && (
                <span className="text-[0.625rem] tracking-[0.1em] font-medium text-recovered flex items-center gap-1.5">
                  <span className="w-1 h-1 rounded-full bg-recovered" />
                  RECOVERED
                </span>
              )}
            </div>
            <div className="text-base font-medium text-ink">{opportunity.customer_name}</div>
            <div className="flex items-baseline justify-between mt-0.5">
              <span className="mono text-[0.6875rem] text-ink-3">{opportunity.opportunity_id.slice(0, 18)}…</span>
              <span className="fin text-lg font-medium text-ink">{inr(opportunity.amount)}</span>
            </div>
          </div>

          <div className="flex border-b border-separator">
            {(["TRACE", "POLICY", "PROVENANCE"] as const).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                aria-pressed={tab === t}
                className={`t-fast flex-1 py-2.5 text-[0.625rem] tracking-[0.1em] font-medium ${
                  tab === t ? "text-ink bg-surface-2 border-b-2 border-ink" : "text-ink-3 hover:text-ink-2"
                }`}
              >
                {t}
                {t === "POLICY" && policy ? ` (${policy.rules.length})` : ""}
              </button>
            ))}
          </div>

          <div className="p-5 max-h-[32rem] overflow-y-auto">
            {tab === "TRACE" && (
              <ol className="list-none">
                <PanelRow stage="failed" tone="blocked" label="FAILED PAYMENT" value={inr(opportunity.amount)} sub={(opportunity.failure_class ?? "unknown").replace(/_/g, " ")} />
                {evaluation && (
                  <PanelRow stage="prediction" label="PREDICTION" value={pct(evaluation.prediction.recovery_probability)} sub={`model v${evaluation.prediction.model_version}`} />
                )}
                {evaluation && (
                  <PanelRow stage="value" label="ECONOMIC VALUE" value={inr(evaluation.economics.incremental_ev, { sign: true })} sub="incremental EV" />
                )}
                {evaluation && (
                  <PanelRow stage="optimizer" label="OPTIMIZER" value={evaluation.optimizer.recommended_action.toUpperCase().replace(/_/g, " ")} sub={`optimizer v${evaluation.optimizer.optimizer_version}`} />
                )}
                {policy && (
                  <PanelRow stage="policy" tone={policy.decision === "ALLOW" ? "neutral" : "blocked"} label="POLICY" value={policy.decision} sub={`policy v${policy.policy_version}`} />
                )}
                {status?.execution && (
                  <PanelRow stage="execution" label="EXECUTION" value={status.execution.state} sub={status.execution.payment_link_id ?? ""} />
                )}
                {status?.webhook && <PanelRow stage="webhook" label="WEBHOOK" value="VERIFIED" sub={status.webhook.event_type} />}
                {status?.outcome && (
                  <PanelRow stage="outcome" tone="recovered" label="OUTCOME" value={inr(status.outcome.amount_recovered)} sub="verified recovery" isLast />
                )}
              </ol>
            )}

            {tab === "POLICY" && (
              <div>
                {!policy ? (
                  <p className="text-xs text-ink-3">Not evaluated — the optimizer selected do-nothing.</p>
                ) : (
                  <>
                    <PolicyRuleList rules={policy.rules} />
                    <div className="mt-5 pt-4 border-t border-separator flex items-center justify-between">
                      <span className="label">RESULT</span>
                      <span className={`text-sm font-medium tracking-[0.1em] ${policy.decision === "ALLOW" ? "text-ink" : "text-blocked"}`}>{policy.decision}</span>
                    </div>
                  </>
                )}
              </div>
            )}

            {tab === "PROVENANCE" && (
              <div className="space-y-1">
                <ProvenanceRow k="Model" v={evaluation ? `Model A v${evaluation.prediction.model_version}` : "—"} />
                <ProvenanceRow k="Optimizer" v={evaluation ? `optimizer_v${evaluation.optimizer.optimizer_version}` : "—"} />
                <ProvenanceRow k="Policy" v={policy ? `policy_v${policy.policy_version}` : "—"} />
                <ProvenanceRow k="Execution Service" v="execution_v1.0.0" />
                <ProvenanceRow k="Webhook Verifier" v="webhook_v1.0.0" />
                <ProvenanceRow k="Environment" v="Razorpay Test Mode" />
              </div>
            )}
          </div>

          <div className="px-5 py-4 border-t border-separator">
            <Link
              href={`/audit/${opportunity.opportunity_id}`}
              className="t-fast block text-center py-2 border border-separator text-[0.6875rem] tracking-[0.1em] text-ink-2 hover:text-ink hover:bg-surface-2"
            >
              VIEW FULL AUDIT RECORD →
            </Link>
          </div>
        </>
      )}
    </aside>
  );
}

function ProvenanceRow({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-1.5">
      <span className="label">{k}</span>
      <span className="mono text-xs text-ink">{v}</span>
    </div>
  );
}

function PanelRow({
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
    <li className="relative pl-9">
      <span className="absolute left-0 top-0" aria-hidden="true">
        <StageNode stage={stage} tone={tone} size={24} iconSize={12} />
      </span>
      {!isLast && <span className="absolute left-[11.5px] top-[28px] bottom-[-4px] w-px bg-separator" aria-hidden="true" />}
      <div className="pb-5 pt-0.5">
        <div className="flex items-baseline justify-between gap-2">
          <span className="label">{label}</span>
        </div>
        <div className={`text-sm font-medium mt-0.5 ${tone === "recovered" ? "text-recovered" : tone === "blocked" ? "text-blocked" : "text-ink"}`}>
          {value}
        </div>
        {sub && <div className="text-[0.6875rem] text-ink-3 mt-0.5 truncate">{sub}</div>}
      </div>
    </li>
  );
}
