"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Play, ArrowRight, CreditCard, Send, Radio, ShieldCheck, CheckCircle2, Info } from "lucide-react";
import { DEMO_SCENARIOS, type DemoScenario } from "@/lib/demo";
import { inr, pct } from "@/lib/format";
import { CountUp } from "@/components/CountUp";
import { PolicyRules } from "@/components/DecisionTrace";
import { StageNode } from "@/components/StageIcon";
import { Sparkline } from "@/components/charts";
import { KV, Label } from "@/components/ui";

const END_STEPS = [
  { icon: Send, label: "PAYMENT LINK SENT", sub: "Customer receives secure link" },
  { icon: CreditCard, label: "CUSTOMER PAYS", sub: "Completes payment via link" },
  { icon: Radio, label: "WEBHOOK RECEIVED", sub: "Razorpay sends payment event" },
  { icon: ShieldCheck, label: "SIGNATURE VERIFIED", sub: "Webhook signature cryptographically verified" },
  { icon: CheckCircle2, label: "RECOVERY RECORDED", sub: "Amount recorded and attributed" },
];

/**
 * Guided 30–60s interactive decision story.
 *
 * Phases:
 * 0 idle · 1 diagnosis · 2 prediction · 3 value · 4 optimizer ·
 * 5 policy (rules stream) · 6 policy verdict · 7 execution ·
 * 8 awaiting payment · 9 webhook · 10 recovered
 */

const PHASE_DELAYS: Record<number, number> = {
  1: 500,
  2: 800,
  3: 900,
  4: 800,
  5: 700,
  7: 800,
  8: 1400,
};

export default function DemoPage() {
  const [scenario, setScenario] = useState<DemoScenario>(DEMO_SCENARIOS[0]);
  const [phase, setPhase] = useState(0);
  const [ruleCount, setRuleCount] = useState(0);
  const [execState, setExecState] = useState(0); // 0 pending 1 submitted 2 succeeded
  const [webhookState, setWebhookState] = useState(0); // 0 received 1 verifying 2 verified 3 processed
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

  const o = scenario.opportunity;
  const isBlock = scenario.storyline === "BLOCK";
  const isSkip = scenario.storyline === "SKIP";

  const clearTimers = useCallback(() => {
    timers.current.forEach(clearTimeout);
    timers.current = [];
  }, []);

  const later = useCallback((fn: () => void, ms: number) => {
    timers.current.push(setTimeout(fn, ms));
  }, []);

  const reset = useCallback(
    (s: DemoScenario) => {
      clearTimers();
      setScenario(s);
      setPhase(0);
      setRuleCount(0);
      setExecState(0);
      setWebhookState(0);
    },
    [clearTimers]
  );

  useEffect(() => () => clearTimers(), [clearTimers]);

  /* Phase advancement */
  useEffect(() => {
    if (phase === 0) return;

    // Skip storyline terminates after the optimizer
    if (isSkip && phase >= 4) return;

    if (phase === 5) {
      // Stream the seven rules; a blocked scenario stops at its failing rule
      const failIndex = isBlock
        ? ["VALID_ACTION_TYPE", "OPPORTUNITY_ACTIONABLE", "DO_NOT_CONTACT_CHECK", "DUPLICATE_ACTION_CHECK", "AUTONOMOUS_AMOUNT_LIMIT_CHECK", "MAX_CONTACTS_CHECK", "DAILY_CAPACITY_CHECK"].indexOf(o.blockedRule ?? "")
        : -1;
      const lastRule = failIndex >= 0 ? failIndex + 1 : 7;
      for (let i = 1; i <= lastRule; i++) {
        later(() => setRuleCount(i), i * 160);
      }
      later(() => setPhase(6), lastRule * 160 + 400);
      return;
    }

    if (phase === 6) {
      // Verdict shown; blocked scenarios end here
      if (isBlock) return;
      later(() => setPhase(7), PHASE_DELAYS[7]);
      return;
    }

    if (phase === 7) {
      // Execution state machine
      later(() => setExecState(1), 450);
      later(() => setExecState(2), 950);
      later(() => setPhase(8), PHASE_DELAYS[8]);
      return;
    }

    if (phase === 8) return; // awaiting user: SIMULATE PAYMENT

    if (phase === 9) {
      later(() => setWebhookState(1), 400);
      later(() => setWebhookState(2), 950);
      later(() => setWebhookState(3), 1400);
      later(() => setPhase(10), 1900);
      return;
    }

    if (phase < 5) {
      const next = phase + 1;
      later(() => setPhase(next), PHASE_DELAYS[next] ?? 700);
    }
  }, [phase, isBlock, isSkip, o.blockedRule, later]);

  const run = () => {
    clearTimers();
    setRuleCount(0);
    setExecState(0);
    setWebhookState(0);
    setPhase(0);
    later(() => setPhase(1), 80);
  };

  return (
    <div className="space-y-10">
      <header>
        <Label>LIVE DECISION DEMO</Label>
        <h1 className="text-2xl font-medium tracking-tight mt-2">
          Watch RAY decide
        </h1>
        <p className="text-sm text-ink-2 mt-2 max-w-lg">
          Deterministic synthetic scenarios. Each run walks the full decision
          rail — diagnosis to verified outcome.
        </p>
      </header>

      {/* Scenario selector */}
      <div className="flex flex-wrap gap-1.5">
        {DEMO_SCENARIOS.map((s) => (
          <button
            key={s.id}
            onClick={() => reset(s)}
            aria-pressed={scenario.id === s.id}
            className={`t-fast px-3 py-2 text-left rounded-sm ${
              scenario.id === s.id
                ? "bg-surface-3 text-ink"
                : "text-ink-3 hover:text-ink-2 hover:bg-surface-2"
            }`}
          >
            <span className="mono text-[0.625rem] block">SCENARIO {s.index}</span>
            <span className="text-xs">{s.title}</span>
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[18rem_minmax(0,1fr)_20rem] gap-10">
        {/* ── Scenario card + control ────────────────────────── */}
        <div className="space-y-6">
          <div className="border-t border-separator pt-5">
            <div className="label mb-4">SCENARIO {scenario.index}</div>
            <h2 className="text-lg font-medium tracking-tight">{scenario.title}</h2>

            <div className="mt-5 grid grid-cols-2 gap-x-4 gap-y-3 text-xs">
              <div>
                <div className="label mb-1">CUSTOMER</div>
                <div className="text-ink">{o.customer}</div>
              </div>
              <div>
                <div className="label mb-1">AMOUNT</div>
                <div className="fin text-ink">{inr(o.amountInr)}</div>
              </div>
              <div>
                <div className="label mb-1">FAILURE REASON</div>
                <div className="text-ink">{o.failureDetail}</div>
              </div>
              <div>
                <div className="label mb-1">TIME</div>
                <div className="mono text-ink-2">{o.time} IST</div>
              </div>
            </div>

            <div className="mt-6">
              <div className="label mb-1.5">ABOUT THIS SCENARIO</div>
              <p className="text-xs text-ink-2 leading-relaxed">{scenario.summary}</p>
            </div>

            <button
              onClick={run}
              className="t-fast mt-8 inline-flex items-center justify-center gap-2 px-8 py-3 bg-ink text-canvas text-xs font-medium tracking-[0.18em] hover:bg-ink-2 active:translate-y-px"
            >
              <Play size={13} strokeWidth={2} fill="currentColor" />
              {phase === 0 ? "RUN RAY" : "RUN AGAIN"}
            </button>
          </div>
        </div>

        {/* ── What RAY will decide ─────────────────────────────── */}
        <div className="space-y-8">
          <div>
            <div className="label mb-4">WHAT RAY WILL DECIDE</div>
            <div className="border border-separator grid grid-cols-2">
              <div className="p-5">
                <div className="label mb-2">RECOVERY PROBABILITY</div>
                <div className="fin text-3xl font-medium text-ink">
                  {phase >= 2 ? <CountUp value={o.probability} format={(n) => pct(n)} start duration={900} /> : "—"}
                </div>
                <div className="text-[0.6875rem] text-ink-3 mt-1 mb-3">Model estimate</div>
                <Sparkline points={[0.2, 0.32, 0.28, 0.41, 0.5, o.probability]} tone="muted" />
              </div>
              <div className="p-5 border-l border-separator">
                <div className="label mb-2">INCREMENTAL VALUE</div>
                <div className="fin text-3xl font-medium text-ink">
                  {phase >= 3 ? <CountUp value={o.incrementalEv} format={(n) => inr(n, { sign: true })} start duration={800} /> : "—"}
                </div>
                <div className="text-[0.6875rem] text-ink-3 mt-1 mb-3">Expected uplift</div>
                <Sparkline points={[0, o.incrementalEv * 0.3, o.incrementalEv * 0.55, o.incrementalEv * 0.8, o.incrementalEv]} tone={o.incrementalEv > 0 ? "recovered" : "blocked"} />
              </div>
            </div>

            <div className="border border-separator border-t-0 p-5 flex items-center justify-between gap-6 flex-wrap">
              <div>
                <div className="label mb-1.5">RECOMMENDED ACTION</div>
                <div className="text-sm font-medium text-ink">
                  {o.action === "CREATE_PAYMENT_LINK" ? "PAYMENT LINK" : "DO NOTHING"}
                </div>
                <div className="text-[0.6875rem] text-ink-3 mt-0.5">
                  {o.action === "CREATE_PAYMENT_LINK" ? "Best incremental EV" : o.actionReason}
                </div>
              </div>
              <div className="text-right">
                <div className="label mb-1.5">POLICY EXPECTATION</div>
                <div className={`text-sm font-medium ${isBlock ? "text-blocked" : "text-ink"}`}>
                  {isSkip ? "NOT EVALUATED" : isBlock ? "BLOCK" : "ALLOW"}
                </div>
                <div className="text-[0.6875rem] text-ink-3 mt-0.5">
                  {isSkip ? "no execution needed" : isBlock ? "1 rule failed" : "7 / 7 rules passed"}
                </div>
              </div>
            </div>
          </div>

          {!isSkip && (
            <div>
              <div className="label mb-4">HOW THIS SCENARIO ENDS</div>
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                {(isBlock ? END_STEPS.slice(0, 1) : END_STEPS).map((s, i, arr) => (
                  <div key={s.label} className="relative border border-separator p-3.5">
                    <s.icon size={16} strokeWidth={1.75} className="text-ink-3 mb-3" />
                    <div className="label leading-snug">{s.label}</div>
                    <div className="text-[0.625rem] text-ink-3 mt-1 leading-snug">{s.sub}</div>
                    {i < arr.length - 1 && (
                      <ArrowRight size={12} strokeWidth={1.75} className="hidden sm:block absolute -right-[1.55rem] top-1/2 -translate-y-1/2 text-ink-3" />
                    )}
                  </div>
                ))}
              </div>
              {isBlock && (
                <p className="text-xs text-ink-3 mt-3">
                  Policy authorization fails before execution — nothing downstream ever runs.
                </p>
              )}
            </div>
          )}

        </div>

        {/* ── Animated decision rail ─────────────────────────── */}
        <div className="min-h-[28rem]">
          <div className="flex items-center justify-between gap-3 mb-6">
            <div className="label">DECISION RAIL</div>
            <span
              className="inline-flex items-center gap-1.5 border px-2 py-0.5 text-[0.5625rem] tracking-[0.1em]"
              style={{ borderColor: "var(--pending)", color: "var(--pending)" }}
            >
              <span className="w-1 h-1 rounded-full bg-pending" />
              RAZORPAY TEST MODE
            </span>
          </div>
          <ol className="list-none space-y-0">
            <Stage stage="failed" active label="FAILED PAYMENT" time={o.time} iconTone="blocked">
              <span className="fin text-lg font-medium">{inr(o.amountInr)}</span>
              <span className="text-xs text-ink-3 block">
                {o.failureClass.replace(/_/g, " ").toLowerCase()}
              </span>
            </Stage>

            <Stage stage="diagnosis" active={phase >= 1} label="DIAGNOSIS">
              {o.diagnosis && (
                <>
                  <span className="fin text-lg font-medium">
                    {o.diagnosis.class.replace(/_/g, " ")}
                  </span>
                  <span className="text-xs text-ink-3 block">
                    confidence {o.diagnosis.confidence.toFixed(2)}
                  </span>
                </>
              )}
            </Stage>

            <Stage stage="prediction" active={phase >= 2} label="PREDICTION">
              <span className="fin text-lg font-medium">
                <CountUp value={o.probability} format={(n) => pct(n)} start={phase >= 2} duration={900} />
              </span>
              <span className="text-xs text-ink-3 block">P(recovery) · model estimate</span>
            </Stage>

            <Stage stage="value" active={phase >= 3} label="ECONOMIC VALUE">
              <div className="grid grid-cols-2 gap-x-8 gap-y-2">
                <div>
                  <span className="label block">EXPECTED RECOVERY</span>
                  <span className="fin text-lg font-medium">
                    <CountUp value={o.grossEv} format={(n) => inr(n)} start={phase >= 3} duration={800} />
                  </span>
                </div>
                <div>
                  <span className="label block">INCREMENTAL EV</span>
                  <span className="fin text-lg font-medium">
                    <CountUp
                      value={o.incrementalEv}
                      format={(n) => inr(n, { sign: true })}
                      start={phase >= 3}
                      duration={800}
                    />
                  </span>
                </div>
              </div>
            </Stage>

            <Stage stage="optimizer" active={phase >= 4} label="OPTIMIZER" isLast={isSkip}>
              <span className="fin text-lg font-medium">
                {o.action === "CREATE_PAYMENT_LINK" ? "PAYMENT LINK" : "DO NOTHING"}
              </span>
              <span className="text-xs text-ink-3 block">
                {o.action === "CREATE_PAYMENT_LINK"
                  ? "capacity-constrained selection"
                  : o.actionReason}
              </span>
              {isSkip && phase >= 4 && (
                <p className="text-xs text-ink-2 mt-3 anim-fade-up">
                  RAY spends nothing here. Scarce capacity is preserved for
                  opportunities with positive incremental value.
                </p>
              )}
            </Stage>

            {!isSkip && (
              <Stage
                stage="policy"
                active={phase >= 5}
                label="POLICY"
                tone={phase >= 6 && isBlock ? "blocked" : "neutral"}
                iconTone={phase >= 6 && isBlock ? "blocked" : "neutral"}
                isLast={isBlock}
              >
                <div className="max-w-sm">
                  <PolicyRules
                    visibleCount={ruleCount}
                    blockedRule={phase >= 5 ? o.blockedRule : undefined}
                    blockedReason={phase >= 6 ? o.blockedReason : undefined}
                  />
                </div>
                {phase >= 6 && (
                  <div className="mt-3 anim-settle">
                    <span
                      className={`text-lg font-medium tracking-[0.14em] ${
                        isBlock ? "text-blocked" : "text-ink"
                      }`}
                    >
                      {isBlock ? "BLOCK" : "ALLOW"}
                    </span>
                    {isBlock && (
                      <p className="text-xs text-ink-2 mt-2">
                        The optimizer chose to act. Policy refused
                        authorization. Nothing was executed.
                      </p>
                    )}
                  </div>
                )}
              </Stage>
            )}

            {!isSkip && !isBlock && (
              <>
                <Stage stage="execution" active={phase >= 7} label="EXECUTION">
                  <div className="flex items-center gap-3 text-xs tracking-[0.14em] font-medium">
                    <span className={execState >= 0 && phase >= 7 ? "text-ink" : "text-ink-3"}>PENDING</span>
                    <span className="w-6 h-px bg-separator" />
                    <span className={execState >= 1 ? "text-ink" : "text-ink-3"}>SUBMITTED</span>
                    <span className="w-6 h-px bg-separator" />
                    <span className={execState >= 2 ? "text-ink" : "text-ink-3"}>SUCCEEDED</span>
                  </div>
                  {execState >= 2 && o.execution && (
                    <div className="border-l border-separator pl-4 mt-3 anim-fade-up">
                      <KV k="Payment Link" v={o.execution.paymentLinkId} monoV />
                      <KV k="Reference" v={o.execution.referenceId} monoV />
                      <KV k="Short URL" v={o.execution.shortUrl} monoV />
                    </div>
                  )}
                </Stage>

                <Stage
                  stage="webhook"
                  active={phase >= 8}
                  label={phase >= 9 ? "WEBHOOK" : "AWAITING PAYMENT"}
                  tone={phase === 8 ? "pending" : "neutral"}
                  iconTone={phase === 8 ? "pending" : "neutral"}
                >
                  {phase === 8 && (
                    <div className="anim-fade-up">
                      <span className="text-pending text-sm font-medium tracking-[0.14em]">
                        PENDING
                      </span>
                      <p className="text-xs text-ink-3 mt-1 mb-4">
                        The payment link is live. In test mode, simulate the
                        customer paying it.
                      </p>
                      <button
                        onClick={() => setPhase(9)}
                        className="t-fast px-6 py-2.5 border border-separator text-xs font-medium tracking-[0.18em] text-ink hover:bg-surface-3"
                      >
                        SIMULATE PAYMENT
                      </button>
                    </div>
                  )}
                  {phase >= 9 && (
                    <div>
                      <div className="flex items-center gap-3 text-xs tracking-[0.14em] font-medium flex-wrap">
                        <span className="text-ink">RECEIVED</span>
                        <span className="w-5 h-px bg-separator" />
                        <span className={webhookState >= 1 ? "text-ink" : "text-ink-3"}>VERIFYING</span>
                        <span className="w-5 h-px bg-separator" />
                        <span className={webhookState >= 2 ? "text-ink" : "text-ink-3"}>VERIFIED</span>
                        <span className="w-5 h-px bg-separator" />
                        <span className={webhookState >= 3 ? "text-ink" : "text-ink-3"}>PROCESSED</span>
                      </div>
                      {webhookState >= 2 && o.webhook && (
                        <div className="border-l border-separator pl-4 mt-3 anim-fade-up">
                          <KV k="Event" v={o.webhook.event} monoV />
                          <KV k="Signature" v="VERIFIED" monoV />
                        </div>
                      )}
                    </div>
                  )}
                </Stage>

                <Stage stage="outcome" active={phase >= 10} label="RECOVERED" tone="recovered" iconTone="recovered" isLast>
                  {phase >= 10 && (
                    <div className="anim-confirm inline-block pr-6">
                      <span className="fin text-3xl font-medium text-recovered">
                        <CountUp
                          value={o.recoveredInr ?? o.amountInr}
                          format={(n) => inr(n)}
                          start={phase >= 10}
                          duration={700}
                        />
                      </span>
                      <span className="text-xs text-ink-3 block mt-1">VERIFIED RECOVERY</span>
                    </div>
                  )}
                </Stage>
              </>
            )}
          </ol>
        </div>
      </div>

      <div className="border-t border-separator pt-5 flex items-center justify-between gap-6 flex-wrap">
        <div className="flex items-center gap-2.5 text-[0.6875rem] text-ink-3">
          <Info size={14} strokeWidth={1.75} className="shrink-0" />
          All scenarios are deterministic and use synthetic data. No live payments are executed.
        </div>
        <a
          href="#top"
          className="t-fast inline-flex items-center gap-2 border border-separator px-4 py-2 text-[0.6875rem] tracking-[0.08em] text-ink-2 hover:text-ink hover:bg-surface-2"
        >
          VIEW ALL SCENARIOS
          <ArrowRight size={12} strokeWidth={1.75} />
        </a>
      </div>
    </div>
  );
}

function Stage({
  stage,
  active,
  label,
  time,
  tone = "neutral",
  iconTone,
  isLast = false,
  children,
}: {
  stage: import("@/components/StageIcon").StageId;
  active: boolean;
  label: string;
  time?: string;
  tone?: "neutral" | "recovered" | "pending" | "blocked";
  iconTone?: "neutral" | "recovered" | "pending" | "blocked";
  isLast?: boolean;
  children: React.ReactNode;
}) {
  return (
    <li className={`relative pl-11 t-slow ${active ? "opacity-100" : "opacity-30"}`}>
      <span className="absolute left-0 top-0" aria-hidden="true">
        <StageNode stage={stage} tone={iconTone ?? (active ? tone : "neutral")} size={30} iconSize={14} />
      </span>
      {!isLast && (
        <span className="absolute left-[14.5px] top-[34px] bottom-[-6px] w-px bg-separator" aria-hidden="true" />
      )}
      <div className="pb-8 pt-1">
        <div className="flex items-baseline justify-between gap-4">
          <span className="label">{label}</span>
          {time && <span className="mono text-[0.625rem] text-ink-3">{time}</span>}
        </div>
        <div className={`mt-1 ${active ? "anim-fade-up" : "invisible"}`}>{children}</div>
      </div>
    </li>
  );
}
