"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ShieldCheck } from "lucide-react";
import { api, ApiError, type ApiExecutionRow } from "@/lib/api";
import { inr, num } from "@/lib/format";
import { Label, KpiCards } from "@/components/ui";
import { LoadingState, ErrorState, EmptyState } from "@/components/DataState";

const STATE_TONE: Record<string, string> = {
  SUCCEEDED: "text-recovered",
  PENDING: "text-pending",
  SUBMITTED: "text-pending",
  FAILED: "text-blocked",
  UNKNOWN: "text-ink-3",
  CANCELLED: "text-ink-3",
};

const GUARDRAILS = [
  "All executions in Razorpay Test Mode",
  "No live payments or captures",
  "No secrets exposed in frontend",
];

function FlowStep({ label, reached, tone = "neutral" }: { label: string; reached: boolean; tone?: "neutral" | "recovered" | "pending" | "blocked" }) {
  const cls =
    tone === "recovered" ? "text-recovered" : tone === "pending" ? "text-pending" : tone === "blocked" ? "text-blocked" : reached ? "text-ink" : "text-ink-3";
  return (
    <div className="flex items-center gap-2.5">
      <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${reached ? "bg-current" : "bg-ink-3"} ${cls}`} />
      <span className={`text-[0.6875rem] tracking-[0.08em] font-medium ${cls}`}>{label}</span>
    </div>
  );
}

function ExecutionFlowPanel({ latest }: { latest: ApiExecutionRow | null }) {
  if (!latest) {
    return (
      <div className="border border-separator p-5">
        <div className="label mb-4">EXECUTION FLOW</div>
        <p className="text-xs text-ink-3">No executions yet.</p>
      </div>
    );
  }

  const recovered = latest.outcome?.outcome_type === "RECOVERED";

  return (
    <div className="border border-separator p-5">
      <div className="label mb-1">EXECUTION FLOW</div>
      <div className="text-xs text-ink-2 mb-4">{latest.customer_name}</div>
      <div className="space-y-3">
        <FlowStep label="AUTHORIZED" reached />
        <FlowStep label="SUBMITTED" reached={latest.state !== "PENDING"} />
        <FlowStep label="SUCCEEDED" reached={latest.state === "SUCCEEDED"} tone={latest.state === "FAILED" ? "blocked" : "neutral"} />
        <div className="pt-2 mt-2 border-t border-separator" />
        <FlowStep label="AWAITING PAYMENT" reached={latest.state === "SUCCEEDED" && !latest.webhook} tone="pending" />
        <FlowStep label="RECEIVED" reached={!!latest.webhook} />
        <FlowStep label="VERIFIED" reached={!!latest.webhook?.signature_verified} />
        <FlowStep label="RECORDED" reached={!!latest.outcome} tone={recovered ? "recovered" : "neutral"} />
      </div>
      <Link
        href={`/execution/${latest.opportunity_id}`}
        className="t-fast block mt-5 pt-4 border-t border-separator text-[0.6875rem] tracking-[0.1em] text-ink-2 hover:text-ink"
      >
        VIEW FULL TRACE →
      </Link>
    </div>
  );
}

export default function ExecutionIndexPage() {
  const [executions, setExecutions] = useState<ApiExecutionRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    setExecutions(null);
    try {
      const res = await api.listExecutions();
      setExecutions(res.executions);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load executions.");
    }
  }, []);

  useEffect(() => {
    const id = setTimeout(load, 0);
    return () => clearTimeout(id);
  }, [load]);

  const succeeded = executions?.filter((e) => e.state === "SUCCEEDED").length ?? 0;
  const pending = executions?.filter((e) => e.state === "SUCCEEDED" && !e.outcome).length ?? 0;
  const failed = executions?.filter((e) => e.state === "FAILED").length ?? 0;
  const verifiedInr = executions
    ?.filter((e) => e.outcome?.outcome_type === "RECOVERED")
    .reduce((s, e) => s + e.outcome!.amount_recovered, 0) ?? 0;

  return (
    <div className="space-y-8">
      <header>
        <Label>OPERATIONS</Label>
        <h1 className="text-2xl font-medium tracking-tight mt-2">Execution</h1>
        <p className="text-sm text-ink-2 mt-2 max-w-lg">
          Payment Links created by RAY through Razorpay, and their verified outcomes.
        </p>
      </header>

      {executions === null && !error && <LoadingState label="Loading executions from the RAY backend…" />}
      {error && <ErrorState message={error} onRetry={load} />}
      {executions !== null && !error && executions.length === 0 && (
        <EmptyState message="No executions yet. Create a Payment Link from an opportunity to see it here." />
      )}

      {executions !== null && !error && executions.length > 0 && (
        <>
          <KpiCards
            items={[
              { label: "ACTIONS", value: num(executions.length), sub: "All time" },
              { label: "SUCCEEDED", value: num(succeeded), sub: executions.length > 0 ? `${((succeeded / executions.length) * 100).toFixed(0)}% success rate` : "—", tone: "recovered" },
              { label: "AWAITING PAYMENT", value: num(pending), sub: "Pending", tone: "pending" },
              { label: "FAILED", value: num(failed), sub: executions.length > 0 ? `${((failed / executions.length) * 100).toFixed(0)}% failure rate` : "—", tone: failed > 0 ? "blocked" : "ink" },
              { label: "VERIFIED RECOVERED", value: inr(verifiedInr), sub: "From succeeded", tone: "recovered" },
            ]}
          />

          <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_18rem] gap-8">
            <div className="min-w-0">
              <div className="overflow-x-auto -mx-5 px-5 xl:mx-0 xl:px-0">
                <table className="w-full text-left min-w-[52rem]">
                  <thead>
                    <tr className="border-b border-separator">
                      <th className="label py-3 pr-4 font-medium">STATE</th>
                      <th className="label py-3 pr-4 font-medium">EXECUTION ID / REFERENCE</th>
                      <th className="label py-3 pr-4 font-medium">PAYMENT LINK ID</th>
                      <th className="label py-3 pr-4 font-medium">AMOUNT</th>
                      <th className="label py-3 pr-4 font-medium">CREATED AT</th>
                      <th className="label py-3 pr-4 font-medium">OUTCOME</th>
                    </tr>
                  </thead>
                  <tbody>
                    {executions.map((e) => (
                      <tr key={e.execution_id} className="t-fast border-b border-separator/40 hover:bg-surface-2">
                        <td className="py-3 pr-4">
                          <span className={`text-[0.625rem] tracking-[0.1em] font-medium ${STATE_TONE[e.state] ?? "text-ink-2"}`}>
                            {e.state}
                          </span>
                        </td>
                        <td className="py-3 pr-4">
                          <Link href={`/execution/${e.opportunity_id}`} className="mono text-[0.6875rem] text-ink-2 hover:text-ink t-fast block">
                            {e.execution_id.slice(0, 12)}…
                          </Link>
                          <span className="mono text-[0.625rem] text-ink-3">{e.reference_id}</span>
                        </td>
                        <td className="py-3 pr-4 mono text-[0.6875rem] text-ink-3">{e.payment_link_id ?? "—"}</td>
                        <td className="py-3 pr-4 fin text-xs text-ink">{inr(e.amount)}</td>
                        <td className="py-3 pr-4 mono text-[0.625rem] text-ink-3">
                          {e.created_at ? new Date(e.created_at).toLocaleString() : "—"}
                        </td>
                        <td className="py-3 pr-4 text-[0.6875rem]">
                          {e.outcome ? (
                            <span className="text-recovered">{inr(e.outcome.amount_recovered)} verified</span>
                          ) : e.webhook ? (
                            <span className="text-pending">awaiting outcome</span>
                          ) : (
                            <span className="text-ink-3">awaiting payment</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="space-y-6">
              <ExecutionFlowPanel latest={executions[0] ?? null} />
              <div className="border border-separator p-5">
                <div className="label mb-4">TEST MODE GUARDRAILS</div>
                <div className="space-y-2.5">
                  {GUARDRAILS.map((g) => (
                    <div key={g} className="flex items-start gap-2.5">
                      <ShieldCheck size={13} strokeWidth={1.75} className="text-ink-3 shrink-0 mt-0.5" />
                      <span className="text-[0.6875rem] text-ink-2 leading-relaxed">{g}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
