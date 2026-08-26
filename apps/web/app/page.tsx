"use client";

import Link from "next/link";
import { CountUp } from "@/components/CountUp";
import { LiveFeed } from "@/components/LiveFeed";
import { Section, OutcomeBadge, Figure, TestModeTag } from "@/components/ui";
import { OPPORTUNITIES, TODAY } from "@/lib/demo";
import { inr, pct, num } from "@/lib/format";

/* Compact hero pipeline — the product story in one column */
function HeroPipeline() {
  const steps = [
    { label: "FAILED PAYMENT", value: "₹4,200", sub: "soft decline" },
    { label: "PREDICTION", value: "63.4%", sub: "P(recovery)" },
    { label: "ECONOMIC VALUE", value: "+₹2,490", sub: "incremental EV" },
    { label: "POLICY", value: "ALLOW", sub: "7 rules · 0 failed" },
    { label: "EXECUTION", value: "PAYMENT LINK", sub: "test mode" },
    { label: "OUTCOME", value: "RECOVERED", sub: "₹4,200 verified", recovered: true },
  ];
  return (
    <ol className="list-none">
      {steps.map((s, i) => (
        <li key={s.label} className="relative pl-6">
          <span className={`absolute left-0 top-1.5 w-1.5 h-1.5 rounded-full ${s.recovered ? "bg-recovered" : "bg-ink-3"}`} />
          {i < steps.length - 1 && (
            <span className="absolute left-[2.5px] top-4 bottom-0 w-px bg-separator" />
          )}
          <div className="pb-4">
            <div className="label">{s.label}</div>
            <div className={`fin text-sm font-medium mt-0.5 ${s.recovered ? "text-recovered" : "text-ink"}`}>
              {s.value}
            </div>
            <div className="text-[0.6875rem] text-ink-3">{s.sub}</div>
          </div>
        </li>
      ))}
    </ol>
  );
}

export default function OverviewPage() {
  const recentExec = OPPORTUNITIES.filter((o) => o.execution).slice(0, 5);
  const blocks = OPPORTUNITIES.filter((o) => o.outcome === "BLOCKED");

  return (
    <div className="space-y-10">
      {/* ── Hero ────────────────────────────────────────────── */}
      <header className="grid lg:grid-cols-[1fr_16rem] gap-10 items-start">
        <div>
          <div className="flex items-center gap-3 mb-6">
            <span className="label-2">REVENUE RECOVERY ORCHESTRATOR</span>
            <TestModeTag />
          </div>
          <h1 className="text-3xl lg:text-4xl font-medium tracking-tight leading-snug max-w-xl">
            Autonomous recovery decisions
            <br />
            for failed payments.
          </h1>
          <p className="text-sm text-ink-2 mt-4 max-w-md leading-relaxed">
            RAY diagnoses each failure, prices the recovery, allocates scarce
            capacity, enforces deterministic policy, and executes safely — then
            verifies what actually happened.
          </p>

          {/* Executive figures */}
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-10 gap-y-8 mt-10">
            <div>
              <div className="label mb-2">RECOVERED TODAY</div>
              <div className="fin text-4xl font-medium text-ink">
                <CountUp value={TODAY.recoveredInr} format={(n) => inr(n)} />
              </div>
              <div className="text-xs text-recovered mt-1.5">VERIFIED RECOVERY</div>
            </div>
            <div>
              <div className="label mb-2">REALIZED RATE</div>
              <div className="fin text-4xl font-medium text-ink">
                <CountUp value={TODAY.realizedRate} format={(n) => pct(n)} />
              </div>
              <div className="text-xs text-ink-3 mt-1.5">
                {TODAY.recoveredCount} of {TODAY.executed} executed
              </div>
            </div>
            <div>
              <div className="label mb-2">CAPACITY</div>
              <div className="fin text-4xl font-medium text-ink">
                {TODAY.capacityUsed}
                <span className="text-ink-3"> / {TODAY.capacityTotal}</span>
              </div>
              <div className="text-xs text-ink-3 mt-1.5">actions today</div>
            </div>
          </div>
        </div>

        <div className="hidden lg:block border-l border-separator pl-8 pt-1">
          <div className="label mb-5">DECISION RAIL</div>
          <HeroPipeline />
          <Link
            href="/demo"
            className="t-fast inline-block mt-2 text-xs text-ink-2 hover:text-ink border-b border-separator pb-0.5"
          >
            Run the live demo →
          </Link>
        </div>
      </header>

      {/* ── KPI strip ───────────────────────────────────────── */}
      <Section title="TODAY">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-x-8 gap-y-6">
          <Figure label="OPPORTUNITIES" value={num(TODAY.opportunities)} size="md" />
          <Figure label="ACTIONS SELECTED" value={num(TODAY.actionsSelected)} size="md" />
          <Figure
            label="PREDICTED NET EV"
            value={inr(TODAY.predictedNetEv)}
            context="MODEL ESTIMATE"
            tone="dim"
            size="md"
          />
          <Figure label="POLICY BLOCKS" value={num(TODAY.policyBlocks)} size="md" />
          <Figure
            label="CAPACITY UTILIZATION"
            value={pct(TODAY.capacityUsed / TODAY.capacityTotal, 0)}
            size="md"
          />
        </div>
      </Section>

      {/* ── Feed + executions ───────────────────────────────── */}
      <div className="grid lg:grid-cols-2 gap-10">
        <Section title="DECISION ACTIVITY">
          <LiveFeed />
        </Section>

        <div className="space-y-10">
          <Section title="RECENT EXECUTION">
            <div>
              {recentExec.map((o) => (
                <Link
                  key={o.id}
                  href={`/execution/${o.id}`}
                  className="t-fast grid grid-cols-[1fr_auto_auto] items-baseline gap-4 py-2.5 border-b border-separator/50 last:border-b-0 hover:bg-surface-2 -mx-2 px-2 rounded-sm"
                >
                  <span className="mono text-[0.6875rem] text-ink-2 truncate">
                    {o.execution!.paymentLinkId}
                  </span>
                  <span className="fin text-xs text-ink">{inr(o.amountInr)}</span>
                  <OutcomeBadge outcome={o.outcome} />
                </Link>
              ))}
            </div>
          </Section>

          <Section title="POLICY BLOCKS">
            <div>
              {blocks.map((o) => (
                <Link
                  key={o.id}
                  href={`/decisions/${o.id}`}
                  className="t-fast block py-2.5 border-b border-separator/50 last:border-b-0 hover:bg-surface-2 -mx-2 px-2 rounded-sm"
                >
                  <div className="flex items-baseline justify-between gap-4">
                    <span className="mono text-[0.6875rem] text-blocked">{o.blockedRule}</span>
                    <span className="fin text-xs text-ink-2">{inr(o.amountInr)}</span>
                  </div>
                  <div className="text-[0.6875rem] text-ink-3 mt-0.5">{o.blockedReason}</div>
                </Link>
              ))}
            </div>
          </Section>
        </div>
      </div>

      {/* ── Recovery composition ────────────────────────────── */}
      <Section title="RECOVERY COMPOSITION">
        <RecoveryBars />
      </Section>
    </div>
  );
}

/* Monochrome horizontal composition bars — realized recovery is the only color */
function RecoveryBars() {
  const executed = OPPORTUNITIES.filter((o) => o.execution);
  const total = executed.reduce((s, o) => s + o.amountInr, 0);
  const recoveredAmt = executed.reduce((s, o) => s + (o.recoveredInr ?? 0), 0);
  const pendingAmt = executed
    .filter((o) => o.outcome === "PENDING")
    .reduce((s, o) => s + o.amountInr, 0);

  const rows = [
    { label: "ATTEMPTED", value: total, cls: "bg-ink-3", text: "text-ink-2" },
    { label: "PENDING", value: pendingAmt, cls: "bg-ink-2", text: "text-ink-2" },
    { label: "RECOVERED", value: recoveredAmt, cls: "bg-recovered", text: "text-recovered" },
  ];

  return (
    <div className="space-y-4 max-w-2xl">
      {rows.map((r) => (
        <div key={r.label} className="grid grid-cols-[6rem_1fr_6rem] items-center gap-4">
          <span className="label">{r.label}</span>
          <div className="h-px bg-separator relative">
            <div
              className={`absolute inset-y-[-1.5px] left-0 ${r.cls} t-slow`}
              style={{ width: `${total > 0 ? (r.value / total) * 100 : 0}%`, height: 3 }}
            />
          </div>
          <span className={`fin text-xs text-right ${r.text}`}>{inr(r.value)}</span>
        </div>
      ))}
      <p className="text-[0.6875rem] text-ink-3 pt-1">
        Attempted and pending are operational amounts. Recovered is verified via
        signed webhook.
      </p>
    </div>
  );
}
