"use client";

import Link from "next/link";
import { OPPORTUNITIES } from "@/lib/demo";
import { inr, pct, num } from "@/lib/format";
import { Label, OutcomeBadge } from "@/components/ui";
import { Sparkline, Donut } from "@/components/charts";
import { CheckCircle2 } from "lucide-react";

const executed = OPPORTUNITIES.filter((o) => o.execution);
const recovered = executed.filter((o) => o.outcome === "RECOVERED");
const pending = executed.filter((o) => o.outcome === "PENDING");
const notRecovered = executed.filter((o) => o.outcome === "NOT_RECOVERED");
const verifiedInr = recovered.reduce((s, o) => s + (o.recoveredInr ?? 0), 0);

const TREND = {
  actions: [5, 6, 6, 7, 7, 8, 7],
  recovered: [1, 1, 2, 2, 3, 2, 3],
  pending: [2, 2, 3, 2, 2, 3, 3],
  notRecovered: [0, 1, 1, 0, 1, 1, 1],
  verified: [8000, 11000, 14500, 16000, 18500, 19800, 21600],
};

export default function ExecutionIndexPage() {
  return (
    <div className="space-y-8">
      <header>
        <Label>OPERATIONS</Label>
        <h1 className="text-2xl font-medium tracking-tight mt-2">Execution</h1>
        <p className="text-sm text-ink-2 mt-2 max-w-lg">
          Payment Links created by RAY through Razorpay, and their verified outcomes.
        </p>
      </header>

      {/* KPI strip */}
      <div className="border border-separator grid grid-cols-2 md:grid-cols-5">
        {[
          { label: "ACTIONS TODAY", sub: "Executed", value: num(executed.length), spark: TREND.actions, tone: "muted" as const },
          { label: "RECOVERED", sub: pct(recovered.length / executed.length, 0) + " of executed", value: num(recovered.length), tone: "text-recovered", spark: TREND.recovered, sparkTone: "recovered" as const },
          { label: "PENDING", sub: "Awaiting payment", value: num(pending.length), tone: "text-pending", spark: TREND.pending, sparkTone: "muted" as const },
          { label: "NOT RECOVERED", sub: "Link expired unpaid", value: num(notRecovered.length), tone: "text-ink-2", spark: TREND.notRecovered, sparkTone: "blocked" as const },
          { label: "VERIFIED RECOVERED", sub: "From executed", value: inr(verifiedInr), tone: "text-recovered", spark: TREND.verified, sparkTone: "recovered" as const },
        ].map((it, i) => (
          <div key={it.label} className={`p-5 ${i > 0 ? "border-t md:border-t-0 md:border-l border-separator" : ""}`}>
            <div className={`fin text-2xl font-medium ${it.tone ?? "text-ink"}`}>{it.value}</div>
            <div className="label mt-2">{it.label}</div>
            <div className="text-[0.6875rem] text-ink-3 mt-0.5 mb-2">{it.sub}</div>
            <Sparkline points={it.spark} tone={it.sparkTone} />
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_20rem] gap-10">
        {/* Ledger */}
        <div className="overflow-x-auto -mx-5 px-5 lg:mx-0 lg:px-0">
          <table className="w-full text-left min-w-[52rem]">
            <thead>
              <tr className="border-b border-separator">
                <th className="label py-3 pr-4 font-medium">STATUS</th>
                <th className="label py-3 pr-4 font-medium">EXECUTION</th>
                <th className="label py-3 pr-4 font-medium">PAYMENT LINK</th>
                <th className="label py-3 pr-4 font-medium">REFERENCE</th>
                <th className="label py-3 pr-4 font-medium">AMOUNT</th>
                <th className="label py-3 pr-4 font-medium">CREATED</th>
                <th className="label py-3 pr-4 font-medium">WEBHOOK</th>
              </tr>
            </thead>
            <tbody>
              {executed.map((o) => (
                <tr key={o.id} className="t-fast border-b border-separator/40 hover:bg-surface-2">
                  <td className="py-3 pr-4">
                    <OutcomeBadge outcome={o.outcome} />
                  </td>
                  <td className="py-3 pr-4">
                    <Link href={`/execution/${o.id}`} className="mono text-[0.6875rem] text-ink-2 hover:text-ink t-fast">
                      {o.execution!.executionId}
                    </Link>
                  </td>
                  <td className="py-3 pr-4 mono text-[0.6875rem] text-ink-3">{o.execution!.paymentLinkId}</td>
                  <td className="py-3 pr-4 mono text-[0.6875rem] text-ink-3">{o.execution!.referenceId}</td>
                  <td className="py-3 pr-4 fin text-xs text-ink">{inr(o.amountInr)}</td>
                  <td className="py-3 pr-4 mono text-[0.625rem] text-ink-3">{o.execution!.createdAt}</td>
                  <td className="py-3 pr-4 text-[0.6875rem]">
                    {o.webhook ? <span className="text-recovered">verified</span> : <span className="text-ink-3">—</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Right panel */}
        <div className="space-y-8">
          <div>
            <div className="label mb-4">EXECUTION FLOW</div>
            <div className="border border-separator p-4">
              <div className="text-[0.6875rem] text-ink-3">RAY AUTHORIZES</div>
              <div className="text-xs text-ink mt-0.5">Policy ALLOW</div>
            </div>
            <ol className="list-none mt-4">
              {[
                { label: "AUTHORIZED", sub: "Policy ALLOW", time: "10:42:11" },
                { label: "SUBMITTED", sub: "Payment Link created", time: "10:42:12" },
                { label: "SUCCEEDED", sub: "Payment Link active", time: "10:42:14", tag: "TEST MODE" },
                { label: "RECEIVED", sub: "payment_link.paid", time: "10:44:19" },
                { label: "VERIFIED", sub: "Signature verified", time: "10:44:19" },
                { label: "RECORDED", sub: "Recovery recorded", time: "10:44:21" },
              ].map((s, i, arr) => (
                <li key={s.label} className="relative pl-7">
                  <span className="absolute left-0 top-0.5 text-recovered" aria-hidden="true">
                    <CheckCircle2 size={16} strokeWidth={1.75} />
                  </span>
                  {i < arr.length - 1 && (
                    <span className="absolute left-[7.5px] top-[22px] bottom-[-4px] w-px bg-recovered/40" aria-hidden="true" />
                  )}
                  <div className="pb-4">
                    <div className="flex items-center gap-2">
                      <span className="text-recovered text-xs font-medium tracking-[0.08em]">{s.label}</span>
                      {s.tag && (
                        <span className="border border-separator px-1.5 py-0.5 text-[0.5625rem] tracking-[0.08em] text-ink-2">
                          {s.tag}
                        </span>
                      )}
                    </div>
                    <div className="text-[0.6875rem] text-ink-3 mt-0.5">{s.sub}</div>
                    <div className="mono text-[0.625rem] text-ink-3 mt-0.5">{s.time}</div>
                  </div>
                </li>
              ))}
            </ol>
            <Link href="/decisions" className="t-fast block text-xs text-ink-2 hover:text-ink border-t border-separator pt-4">
              View full trace →
            </Link>
          </div>

          <div>
            <div className="label mb-4">EXECUTION OUTCOMES</div>
            <div className="flex items-center gap-6">
              <Donut
                slices={[
                  { label: "Recovered", value: recovered.length, color: "var(--recovered)" },
                  { label: "Pending", value: pending.length, color: "var(--pending)" },
                  { label: "Not recovered", value: notRecovered.length, color: "var(--ink-3)" },
                ]}
              />
              <div className="space-y-1.5 text-xs">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-recovered" />
                  <span className="text-ink-2">Recovered</span>
                  <span className="fin text-ink ml-auto">{recovered.length} ({pct(recovered.length / executed.length, 0)})</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-pending" />
                  <span className="text-ink-2">Pending</span>
                  <span className="fin text-ink ml-auto">{pending.length} ({pct(pending.length / executed.length, 0)})</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-ink-3" />
                  <span className="text-ink-2">Not recovered</span>
                  <span className="fin text-ink ml-auto">{notRecovered.length} ({pct(notRecovered.length / executed.length, 0)})</span>
                </div>
              </div>
            </div>
          </div>

          <div>
            <div className="label mb-4">TEST MODE GUARDRAILS</div>
            <ul className="space-y-2">
              {["All executions in Razorpay Test Mode", "No live payments or captures", "No secrets exposed in frontend"].map((g) => (
                <li key={g} className="flex items-center gap-2 text-xs text-ink-2">
                  <CheckCircle2 size={14} strokeWidth={1.75} className="text-recovered shrink-0" />
                  {g}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
