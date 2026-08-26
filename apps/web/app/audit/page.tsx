"use client";

import { useMemo, useState } from "react";
import { Search, Copy } from "lucide-react";
import { OPPORTUNITIES, type Opportunity } from "@/lib/demo";
import { inr } from "@/lib/format";
import { Label, OutcomeBadge, KV } from "@/components/ui";
import { DecisionTrace } from "@/components/DecisionTrace";

function auditTitle(o: Opportunity): string {
  if (o.execution) return "Payment Link Created";
  if (o.policy === "BLOCK") return "Policy Blocked";
  return "Action Skipped";
}

function ChecksumRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 py-1.5">
      <span className="label">{label}</span>
      <span className="flex items-center gap-1.5">
        <span className="mono text-[0.6875rem] text-ink-2">{value}</span>
        <Copy size={11} strokeWidth={1.75} className="text-ink-3" />
      </span>
    </div>
  );
}

export default function AuditPage() {
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<Opportunity>(OPPORTUNITIES[0]);

  const records = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return OPPORTUNITIES;
    return OPPORTUNITIES.filter(
      (o) =>
        o.customer.toLowerCase().includes(q) ||
        o.id.toLowerCase().includes(q) ||
        (o.execution?.referenceId.toLowerCase().includes(q) ?? false) ||
        (o.blockedRule?.toLowerCase().includes(q) ?? false)
    );
  }, [query]);

  return (
    <div className="space-y-8">
      <header>
        <Label>SYSTEM</Label>
        <h1 className="text-2xl font-medium tracking-tight mt-2">Audit</h1>
        <p className="text-sm text-ink-2 mt-2 max-w-lg">
          Every action is attributable. Expand any record to reconstruct the full reasoning and execution path.
        </p>
      </header>

      {/* KPI strip */}
      <div className="border border-separator grid grid-cols-3">
        <div className="p-5">
          <div className="fin text-2xl font-medium text-ink">84</div>
          <div className="label mt-2">TOTAL RECORDS</div>
          <div className="text-[0.6875rem] text-ink-3 mt-0.5">All time</div>
        </div>
        <div className="p-5 border-l border-separator">
          <div className="fin text-2xl font-medium text-ink">{OPPORTUNITIES.length}</div>
          <div className="label mt-2">TODAY</div>
          <div className="text-[0.6875rem] text-ink-3 mt-0.5">New records</div>
        </div>
        <div className="p-5 border-l border-separator">
          <div className="fin text-2xl font-medium text-ink">0</div>
          <div className="label mt-2">DISPUTES</div>
          <div className="text-[0.6875rem] text-ink-3 mt-0.5">All time</div>
        </div>
      </div>

      {/* Search */}
      <div className="relative max-w-md">
        <Search size={14} strokeWidth={1.75} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-3" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search by customer, ID, reference, rule..."
          className="w-full bg-surface-2 border border-separator rounded-sm pl-9 pr-3 py-2 text-xs text-ink placeholder:text-ink-3 focus-visible:outline-1 focus-visible:outline-ink-2"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[16rem_minmax(0,1fr)_16rem] gap-8">
        {/* Record list */}
        <div>
          <div className="label mb-3">AUDIT RECORDS</div>
          <div className="max-h-[36rem] overflow-y-auto pr-1">
            {records.map((o) => (
              <button
                key={o.id}
                onClick={() => setSelected(o)}
                aria-current={selected.id === o.id ? "true" : undefined}
                className={`t-fast w-full text-left px-3 py-2.5 border-l-2 mb-0.5 ${
                  selected.id === o.id ? "border-ink bg-surface-2" : "border-transparent hover:bg-surface-2"
                }`}
              >
                <div className="flex items-baseline justify-between gap-2">
                  <span className="mono text-[0.625rem] text-ink-3">{o.time}</span>
                  <span className="fin text-[0.6875rem] text-ink-2">{inr(o.amountInr)}</span>
                </div>
                <div className="text-xs text-ink mt-0.5">{auditTitle(o)}</div>
                <div className="flex items-center justify-between gap-2 mt-1">
                  <span className="mono text-[0.625rem] text-ink-3 truncate">
                    {o.execution?.executionId ?? o.id}
                  </span>
                  <OutcomeBadge outcome={o.outcome} />
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Detail + trace */}
        <div>
          <div className="flex items-center gap-3">
            <OutcomeBadge outcome={selected.outcome} />
            <span className="mono text-[0.6875rem] text-ink-3">{selected.time} IST · 26 Aug 2026</span>
          </div>
          <h2 className="text-xl font-medium tracking-tight mt-2">{auditTitle(selected)}</h2>
          <div className="fin text-2xl font-medium text-ink mt-2">{inr(selected.amountInr)}</div>
          <div className="text-xs text-ink-2 mt-0.5">{selected.customer}</div>

          {selected.execution && (
            <div className="grid grid-cols-2 gap-6 mt-5 max-w-md">
              <KV k="Execution ID" v={selected.execution.executionId} monoV />
              <KV k="Reference" v={selected.execution.referenceId} monoV />
            </div>
          )}

          <div className="label mt-8 mb-4">DECISION TRACE</div>
          <DecisionTrace opportunity={selected} />
        </div>

        {/* Provenance / links / checksums / notes */}
        <div className="space-y-8">
          <div>
            <div className="label mb-3">PROVENANCE</div>
            <KV k="Model" v="Model A v1.0.0" monoV />
            <KV k="Optimizer" v="optimizer_v1.0.0" monoV />
            <KV k="Policy" v="policy_v1.0.0" monoV />
            <KV k="Policy ruleset" v="rules_v1.0.0" monoV />
            {selected.execution && <KV k="Execution service" v="execution_v1.0.0" monoV />}
            {selected.webhook && <KV k="Webhook verifier" v="webhook_v1.0.0" monoV />}
            <KV k="Environment" v="Razorpay Test Mode" />
          </div>

          <div>
            <div className="label mb-3">RELATED LINKS</div>
            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-xs">
                <span className="text-ink-3">Opportunity</span>
                <span className="mono text-ink-2">{selected.id}</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-ink-3">Decision</span>
                <span className="mono text-ink-2">dec_{selected.id.slice(4)}</span>
              </div>
              {selected.execution && (
                <div className="flex items-center justify-between text-xs">
                  <span className="text-ink-3">Execution</span>
                  <span className="mono text-ink-2">{selected.execution.executionId}</span>
                </div>
              )}
            </div>
          </div>

          <div>
            <div className="label mb-3">CHECKSUMS</div>
            <ChecksumRow label="Record hash" value={`${selected.id.slice(4, 12)}…`} />
            <ChecksumRow label="Trace hash" value="f4e2b1a7c9d8…" />
            <ChecksumRow label="Payload hash" value="b8d3f6a1c2e4…" />
          </div>

          <div>
            <div className="label mb-3">NOTES</div>
            <p className="text-xs text-ink-3">No notes for this record.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
