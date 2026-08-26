"use client";

import { useState } from "react";
import { OPPORTUNITIES, type Opportunity } from "@/lib/demo";
import { inr, pct, num } from "@/lib/format";
import { Label, OutcomeBadge } from "@/components/ui";
import { ProgressBar } from "@/components/charts";
import { DecisionPanel } from "@/components/DecisionPanel";

type Filter = "ALL" | "ALLOWED" | "BLOCKED" | "SKIPPED";

export default function DecisionsPage() {
  const [filter, setFilter] = useState<Filter>("ALL");
  const [selected, setSelected] = useState<Opportunity | null>(null);

  const allowed = OPPORTUNITIES.filter((o) => o.policy === "ALLOW");
  const blocked = OPPORTUNITIES.filter((o) => o.policy === "BLOCK");
  const recoveredInr = OPPORTUNITIES.filter((o) => o.outcome === "RECOVERED").reduce((s, o) => s + (o.recoveredInr ?? 0), 0);
  const predictedNetEv = OPPORTUNITIES.filter((o) => o.execution).reduce((s, o) => s + o.incrementalEv, 0);

  const rows = OPPORTUNITIES.filter((o) => {
    if (filter === "ALLOWED") return o.policy === "ALLOW";
    if (filter === "BLOCKED") return o.policy === "BLOCK";
    if (filter === "SKIPPED") return o.action === "DO_NOTHING";
    return true;
  });

  return (
    <div className="space-y-8">
      <header>
        <Label>OPERATIONS</Label>
        <h1 className="text-2xl font-medium tracking-tight mt-2">Decisions</h1>
        <p className="text-sm text-ink-2 mt-2 max-w-lg">
          Every decision RAY reached today, with full reasoning trace.
        </p>
      </header>

      {/* KPI strip */}
      <div className="border border-separator grid grid-cols-2 md:grid-cols-5">
        {[
          { label: "TOTAL DECISIONS", sub: "Today", value: num(OPPORTUNITIES.length) },
          { label: "ALLOWED", sub: pct(allowed.length / OPPORTUNITIES.length, 1), value: num(allowed.length), tone: "text-ink" },
          { label: "BLOCKED", sub: pct(blocked.length / OPPORTUNITIES.length, 1), value: num(blocked.length), tone: "text-blocked" },
          { label: "RECOVERED", sub: "From allowed", value: inr(recoveredInr), tone: "text-recovered" },
          { label: "PREDICTED NET EV", sub: "Model estimate", value: inr(predictedNetEv) },
        ].map((it, i) => (
          <div key={it.label} className={`p-5 ${i > 0 ? "border-t md:border-t-0 md:border-l border-separator" : ""}`}>
            <div className={`fin text-2xl font-medium ${it.tone ?? "text-ink"}`}>{it.value}</div>
            <div className="label mt-2">{it.label}</div>
            <div className="text-[0.6875rem] text-ink-3 mt-0.5">{it.sub}</div>
          </div>
        ))}
      </div>

      {/* Filter tabs */}
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

      {/* Table */}
      <div className="overflow-x-auto -mx-5 px-5">
        <table className="w-full text-left min-w-[64rem]">
          <thead>
            <tr className="border-b border-separator">
              <th className="label py-3 pr-4 font-medium">TIME</th>
              <th className="label py-3 pr-4 font-medium">CUSTOMER</th>
              <th className="label py-3 pr-4 font-medium">AMOUNT</th>
              <th className="label py-3 pr-4 font-medium">P(RECOVERY)</th>
              <th className="label py-3 pr-4 font-medium">INCR. EV</th>
              <th className="label py-3 pr-4 font-medium">ACTION</th>
              <th className="label py-3 pr-4 font-medium">POLICY</th>
              <th className="label py-3 pr-4 font-medium">OUTCOME</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((o) => (
              <tr
                key={o.id}
                onClick={() => setSelected(o)}
                className="t-fast border-b border-separator/40 hover:bg-surface-2 cursor-pointer"
              >
                <td className="py-3 pr-4 mono text-[0.6875rem] text-ink-3">{o.time}</td>
                <td className="py-3 pr-4">
                  <span className="text-xs text-ink block">{o.customer}</span>
                  <span className="mono text-[0.625rem] text-ink-3">{o.id}</span>
                </td>
                <td className="py-3 pr-4 fin text-xs text-ink">{inr(o.amountInr)}</td>
                <td className="py-3 pr-4">
                  <div className="flex items-center gap-2">
                    <ProgressBar value={o.probability} width={56} />
                    <span className="fin text-xs text-ink-2">{pct(o.probability)}</span>
                  </div>
                </td>
                <td className="py-3 pr-4">
                  <span className={`fin text-xs ${o.incrementalEv > 0 ? "text-recovered" : "text-blocked"}`}>
                    {inr(o.incrementalEv, { sign: true })}
                  </span>
                </td>
                <td className="py-3 pr-4">
                  <span className="mono text-[0.625rem] text-ink-2">
                    {o.action === "CREATE_PAYMENT_LINK" ? "PAYMENT LINK" : "DO NOTHING"}
                  </span>
                </td>
                <td className="py-3 pr-4">
                  <span className={`text-[0.6875rem] font-medium tracking-[0.06em] ${o.policy === "BLOCK" ? "text-blocked" : o.policy === "ALLOW" ? "text-ink" : "text-ink-3"}`}>
                    {o.policy === "NOT_EVALUATED" ? "SKIPPED" : o.policy}
                  </span>
                  <span className="block text-[0.625rem] text-ink-3">
                    {o.policy === "BLOCK" ? "1 rule failed" : o.policy === "ALLOW" ? "7 rules passed" : "low value"}
                  </span>
                </td>
                <td className="py-3 pr-4">
                  <OutcomeBadge outcome={o.outcome} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="text-[0.6875rem] text-ink-3">
        Showing {rows.length} of {OPPORTUNITIES.length} decisions · click a row for the full trace
      </p>

      {selected && <DecisionPanel opportunity={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
