"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { api, ApiError, type ApiOpportunity, type ApiConfig } from "@/lib/api";
import { inr, pct, num } from "@/lib/format";
import { Label, KpiCards } from "@/components/ui";
import { LoadingState, ErrorState, EmptyState } from "@/components/DataState";

const FAILURE_FILTERS = ["ALL", "soft_decline", "hard_decline", "gateway_error", "authentication_failure"] as const;

export default function OpportunitiesPage() {
  const [opportunities, setOpportunities] = useState<ApiOpportunity[] | null>(null);
  const [config, setConfig] = useState<ApiConfig | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [failure, setFailure] = useState<(typeof FAILURE_FILTERS)[number]>("ALL");

  const load = useCallback(async () => {
    setError(null);
    setOpportunities(null);
    try {
      const [res, cfg] = await Promise.all([api.listOpportunities(), api.getConfig()]);
      setOpportunities(res.opportunities);
      setConfig(cfg);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load opportunities.");
    }
  }, []);

  useEffect(() => {
    const id = setTimeout(load, 0);
    return () => clearTimeout(id);
  }, [load]);

  const rows = useMemo(() => {
    if (!opportunities) return [];
    let r = [...opportunities];
    if (failure !== "ALL") r = r.filter((o) => o.failure_class === failure);
    r.sort((a, b) => (a.created_at ?? "") < (b.created_at ?? "") ? 1 : -1);
    return r;
  }, [opportunities, failure]);

  const actionsSelected = useMemo(
    () => (opportunities ?? []).filter((o) => o.selected_action === "create_payment_link").length,
    [opportunities]
  );
  const policyBlocks = useMemo(
    () => (opportunities ?? []).filter((o) => o.last_decision?.policy_decision === "BLOCK").length,
    [opportunities]
  );
  const predictedNetEv = useMemo(
    () => (opportunities ?? []).reduce((s, o) => s + (o.last_decision?.expected_value ?? 0), 0),
    [opportunities]
  );
  const capacityTotal = config?.max_actions_per_day ?? 0;

  return (
    <div className="space-y-8">
      <header>
        <Label>OPERATIONS</Label>
        <h1 className="text-2xl font-medium tracking-tight mt-2">Opportunities</h1>
        <p className="text-sm text-ink-2 mt-2 max-w-lg">
          Every failed payment RAY has evaluated — separate from the frozen benchmark.
        </p>
      </header>

      {opportunities === null && !error && <LoadingState label="Loading opportunities from the RAY backend…" />}
      {error && <ErrorState message={error} onRetry={load} />}

      {opportunities !== null && !error && (
        <>
          <KpiCards
            items={[
              { label: "ACTIVE", value: num(opportunities.length), sub: "Operational total" },
              { label: "ACTIONS SELECTED", value: num(actionsSelected), sub: "Payment Link" },
              { label: "PREDICTED NET EV", value: inr(predictedNetEv), sub: "Model estimate" },
              { label: "POLICY BLOCKS", value: num(policyBlocks), sub: "All time", tone: policyBlocks > 0 ? "blocked" : "ink" },
              { label: "CAPACITY", value: capacityTotal > 0 ? `${num(actionsSelected)} / ${num(capacityTotal)}` : "—", sub: "Actions / day" },
            ]}
          />

          <div className="flex flex-wrap gap-x-8 gap-y-4">
            <div>
              <div className="label mb-2">FAILURE</div>
              <div className="flex flex-wrap gap-1">
                {FAILURE_FILTERS.map((opt) => (
                  <button
                    key={opt}
                    onClick={() => setFailure(opt)}
                    aria-pressed={failure === opt}
                    className={`t-fast px-2 py-1 text-[0.625rem] tracking-[0.1em] rounded-sm ${
                      failure === opt ? "bg-surface-3 text-ink" : "text-ink-3 hover:text-ink-2 hover:bg-surface-2"
                    }`}
                  >
                    {opt.replace(/_/g, " ").toUpperCase()}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {rows.length === 0 ? (
            <EmptyState message="No opportunities match the current filter." />
          ) : (
            <>
              <div className="overflow-x-auto -mx-5 px-5">
                <table className="w-full text-left min-w-[56rem]">
                  <thead>
                    <tr className="border-b border-separator">
                      <Th>STATUS</Th>
                      <Th>CUSTOMER</Th>
                      <Th>AMOUNT</Th>
                      <Th>FAILURE</Th>
                      <Th>P(RECOVERY)</Th>
                      <Th>INCR. EV</Th>
                      <Th>ACTION</Th>
                      <Th>POLICY</Th>
                      <Th>OUTCOME</Th>
                      <Th>TIME</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((o) => {
                      const p = o.last_decision?.recovery_probability;
                      const ev = o.last_decision?.incremental_ev;
                      return (
                        <tr key={o.opportunity_id} className="t-fast border-b border-separator/40 hover:bg-surface-2 group">
                          <Td>
                            <span
                              className={`text-[0.625rem] tracking-[0.1em] font-medium ${
                                o.decision_made ? "text-ink-2" : "text-ink-3"
                              }`}
                            >
                              {o.decision_made ? "DECIDED" : "PENDING"}
                            </span>
                          </Td>
                          <Td>
                            <Link href={`/opportunities/${o.opportunity_id}`} className="block group-hover:text-ink text-ink-2 t-fast">
                              <span className="text-xs">{o.customer_name}</span>
                              <span className="mono block text-[0.625rem] text-ink-3">{o.opportunity_id.slice(0, 12)}…</span>
                            </Link>
                          </Td>
                          <Td>
                            <span className="fin text-xs text-ink">{inr(o.amount)}</span>
                          </Td>
                          <Td>
                            <span className="text-[0.6875rem] text-ink-2">{(o.failure_class ?? "unknown").replace(/_/g, " ")}</span>
                          </Td>
                          <Td>
                            {p != null ? (
                              <div className="flex items-center gap-2">
                                <span className="fin text-xs text-ink">{pct(p)}</span>
                                <span className="hidden sm:block w-12 h-[3px] rounded-full bg-separator overflow-hidden">
                                  <span className="block h-full bg-ink-2" style={{ width: `${Math.min(p * 100, 100)}%` }} />
                                </span>
                              </div>
                            ) : (
                              <span className="text-ink-3 text-xs">—</span>
                            )}
                          </Td>
                          <Td>
                            <span className={`fin text-xs ${ev != null && ev >= 0 ? "text-recovered" : ev != null ? "text-blocked" : "text-ink-3"}`}>
                              {ev != null ? inr(ev, { sign: true }) : "—"}
                            </span>
                          </Td>
                          <Td>
                            <span className="mono text-[0.625rem] text-ink-2">
                              {o.selected_action ? o.selected_action.toUpperCase() : "—"}
                            </span>
                          </Td>
                          <Td>
                            <span className={`text-[0.625rem] tracking-[0.08em] font-medium ${o.last_decision?.policy_decision === "BLOCK" ? "text-blocked" : o.last_decision?.policy_decision === "ALLOW" ? "text-ink" : "text-ink-3"}`}>
                              {o.last_decision?.policy_decision ?? "—"}
                            </span>
                          </Td>
                          <Td>
                            {o.recovered ? (
                              <span className="text-[0.6875rem] text-recovered">RECOVERED</span>
                            ) : o.last_decision?.policy_decision === "BLOCK" ? (
                              <span className="text-[0.6875rem] text-blocked">BLOCKED</span>
                            ) : o.selected_action === "create_payment_link" ? (
                              <span className="text-[0.6875rem] text-pending">PENDING</span>
                            ) : (
                              <span className="text-[0.6875rem] text-ink-3">—</span>
                            )}
                          </Td>
                          <Td>
                            <span className="mono text-[0.625rem] text-ink-3">
                              {o.failed_at ? new Date(o.failed_at).toLocaleTimeString() : "—"}
                            </span>
                          </Td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <p className="text-[0.6875rem] text-ink-3">{rows.length} of {opportunities.length} opportunities</p>
            </>
          )}
        </>
      )}
    </div>
  );
}

function Th({ children }: { children: React.ReactNode }) {
  return <th className="label py-3 pr-4 font-medium">{children}</th>;
}

function Td({ children }: { children: React.ReactNode }) {
  return <td className="py-3 pr-4 align-baseline">{children}</td>;
}
