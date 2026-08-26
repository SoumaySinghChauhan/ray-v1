"use client";

import Link from "next/link";
import { CountUp } from "@/components/CountUp";
import { LiveFeed } from "@/components/LiveFeed";
import { Sparkline, ProgressBar } from "@/components/charts";
import { StageNode } from "@/components/StageIcon";
import { OutcomeBadge, Label } from "@/components/ui";
import { OPPORTUNITIES, TODAY } from "@/lib/demo";
import { inr, pct, num } from "@/lib/format";

const HERO = OPPORTUNITIES[0]; // Meridian Textiles — soft decline, full recovery

const HERO_STAGES: {
  id: "failed" | "diagnosis" | "prediction" | "value" | "policy" | "execution" | "outcome";
  label: string;
  value: string;
  sub: string;
  time: string;
  tone: "neutral" | "recovered";
  iconTone?: "neutral" | "blocked" | "recovered";
}[] = [
  { id: "failed", label: "FAILED PAYMENT", value: inr(HERO.amountInr), sub: "Soft decline", time: HERO.time, tone: "neutral", iconTone: "blocked" },
  { id: "diagnosis", label: "DIAGNOSIS", value: HERO.diagnosis!.class.replace(/_/g, " "), sub: `confidence ${HERO.diagnosis!.confidence.toFixed(2)}`, time: HERO.time, tone: "neutral" },
  { id: "prediction", label: "PREDICTION", value: pct(HERO.probability), sub: "P(recovery)", time: HERO.time, tone: "neutral" },
  { id: "value", label: "ECONOMIC VALUE", value: inr(HERO.incrementalEv, { sign: true }), sub: "Incremental EV", time: HERO.time, tone: "neutral" },
  { id: "policy", label: "POLICY", value: "ALLOW", sub: "7 rules passed", time: HERO.time, tone: "neutral" },
  { id: "execution", label: "EXECUTION", value: "PAYMENT LINK", sub: "Created", time: HERO.execution!.createdAt, tone: "neutral" },
  { id: "outcome", label: "OUTCOME", value: "RECOVERED", sub: `${inr(HERO.amountInr)} verified`, time: HERO.webhook!.receivedAt, tone: "recovered", iconTone: "recovered" },
];

function HeroRail() {
  return (
    <div className="flex items-start overflow-x-auto pb-1">
      {HERO_STAGES.map((s, i) => (
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
          {i < HERO_STAGES.length - 1 && (
            <div className="flex items-center h-[30px] w-3.5 shrink-0">
              <span className="w-full border-t border-dashed border-separator" />
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function MiniRail() {
  return (
    <div className="border-l border-separator pl-6 h-full flex flex-col">
      <div className="label mb-5">DECISION RAIL</div>
      <ol className="list-none flex-1">
        {HERO_STAGES.map((s, i) => (
          <li key={s.id} className="relative pl-8 pb-6 last:pb-0">
            <span className="absolute left-0 top-0" aria-hidden="true">
              <StageNode stage={s.id} tone={s.iconTone ?? s.tone} size={22} iconSize={11} />
            </span>
            {i < HERO_STAGES.length - 1 && (
              <span className="absolute left-[10.5px] top-[24px] bottom-0 w-px bg-separator" aria-hidden="true" />
            )}
            <div className="label">{s.label}</div>
            <div className={`fin text-sm font-medium mt-0.5 ${s.tone === "recovered" ? "text-recovered" : "text-ink"}`}>
              {s.value}
            </div>
            <div className="text-[0.6875rem] text-ink-3">{s.sub}</div>
          </li>
        ))}
      </ol>
      <Link
        href="/demo"
        className="t-fast block mt-4 text-xs text-ink-2 hover:text-ink border-t border-separator pt-4"
      >
        Run the live demo →
      </Link>
    </div>
  );
}

const KPI_TREND = {
  opportunities: [8, 9, 10, 9, 11, 12, 12],
  actions: [7, 8, 8, 9, 9, 10, 10],
  ev: [22000, 24500, 21000, 26000, 25000, 28500, 27714],
  blocks: [1, 2, 1, 3, 2, 4, 3],
};

function KpiStrip() {
  const items = [
    { label: "OPPORTUNITIES", value: num(TODAY.opportunities), sub: "Active", spark: KPI_TREND.opportunities, tone: "recovered" as const },
    { label: "ACTIONS SELECTED", value: num(TODAY.actionsSelected), sub: "Today", spark: KPI_TREND.actions, tone: "muted" as const },
    { label: "PREDICTED NET EV", value: inr(TODAY.predictedNetEv), sub: "Model estimate", spark: KPI_TREND.ev, tone: "muted" as const },
    { label: "POLICY BLOCKS", value: num(TODAY.policyBlocks), sub: "Today", spark: KPI_TREND.blocks, tone: "blocked" as const },
    { label: "CAPACITY UTILIZATION", value: pct(TODAY.capacityUsed / TODAY.capacityTotal, 0), sub: `${TODAY.capacityUsed} / ${TODAY.capacityTotal} actions`, progress: TODAY.capacityUsed / TODAY.capacityTotal },
  ];
  return (
    <div className="border border-separator">
      <div className="grid grid-cols-2 md:grid-cols-5">
        {items.map((it, i) => (
          <div key={it.label} className={`p-5 ${i > 0 ? "border-t md:border-t-0 md:border-l border-separator" : ""}`}>
            <div className="fin text-3xl font-medium text-ink">{it.value}</div>
            <div className="label mt-2">{it.label}</div>
            <div className="text-[0.6875rem] text-ink-3 mt-0.5 mb-2">{it.sub}</div>
            {it.progress !== undefined ? (
              <ProgressBar value={it.progress} width={80} />
            ) : (
              <Sparkline points={it.spark!} tone={it.tone} />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function RecoveryComposition() {
  const executed = OPPORTUNITIES.filter((o) => o.execution);
  const total = executed.reduce((s, o) => s + o.amountInr, 0);
  const recovered = executed.reduce((s, o) => s + (o.recoveredInr ?? 0), 0);
  const pending = executed.filter((o) => o.outcome === "PENDING").reduce((s, o) => s + o.amountInr, 0);
  const notRecovered = total - recovered - pending;

  const segs = [
    { label: "RECOVERED", value: recovered, cls: "bg-recovered" },
    { label: "PENDING", value: pending, cls: "bg-pending" },
    { label: "NOT RECOVERED", value: Math.max(notRecovered, 0), cls: "bg-ink-3" },
  ];

  return (
    <div>
      <div className="label mb-4">RECOVERY COMPOSITION (TODAY)</div>
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
        <div className="text-xs text-ink-3 ml-auto">TOTAL ATTEMPTED <span className="fin text-ink-2">{inr(total)}</span></div>
      </div>
    </div>
  );
}

export default function OverviewPage() {
  const recentExec = OPPORTUNITIES.filter((o) => o.execution).slice(0, 5);
  const blocks = OPPORTUNITIES.filter((o) => o.outcome === "BLOCKED");

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
              <div className="label mb-2">RECOVERED TODAY</div>
              <div className="fin text-4xl font-medium text-ink">
                <CountUp value={TODAY.recoveredInr} format={(n) => inr(n)} />
              </div>
              <div className="flex items-center gap-2 mt-1.5">
                <span className="text-xs text-recovered">+28.7%</span>
                <span className="text-xs text-ink-3">vs yesterday</span>
              </div>
              <div className="text-[0.6875rem] text-recovered mt-1">VERIFIED RECOVERY</div>
            </div>
          </div>

          <HeroRail />
        </div>

        <MiniRail />
      </div>

      {/* ── KPI strip ───────────────────────────────────────── */}
      <KpiStrip />

      {/* ── Feed + executions + blocks ──────────────────────── */}
      <div className="grid lg:grid-cols-3 gap-8">
        <div>
          <Label>DECISION ACTIVITY</Label>
          <div className="mt-4">
            <LiveFeed limit={7} />
          </div>
          <Link href="/decisions" className="t-fast inline-block mt-4 text-xs text-ink-2 hover:text-ink">
            View all activity →
          </Link>
        </div>

        <div>
          <Label>RECENT EXECUTIONS</Label>
          <div className="mt-4">
            {recentExec.map((o) => (
              <Link
                key={o.id}
                href={`/execution/${o.id}`}
                className="t-fast grid grid-cols-[1fr_auto_auto] items-baseline gap-4 py-2.5 border-b border-separator/50 last:border-b-0 hover:bg-surface-2 -mx-2 px-2 rounded-sm"
              >
                <span className="min-w-0">
                  <span className="mono text-[0.6875rem] text-ink-2 block truncate">{o.execution!.paymentLinkId}</span>
                  <span className="mono text-[0.625rem] text-ink-3">{o.execution!.referenceId}</span>
                </span>
                <span className="fin text-xs text-ink">{inr(o.amountInr)}</span>
                <OutcomeBadge outcome={o.outcome} />
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
          <Link href="/decisions?filter=blocked" className="t-fast inline-block mt-4 text-xs text-ink-2 hover:text-ink">
            View all policy blocks →
          </Link>
        </div>
      </div>

      {/* ── Recovery composition ────────────────────────────── */}
      <div className="rule pt-8">
        <RecoveryComposition />
      </div>
    </div>
  );
}
