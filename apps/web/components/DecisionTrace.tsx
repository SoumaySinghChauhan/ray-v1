"use client";

import { useState } from "react";
import type { Opportunity } from "@/lib/demo";
import { POLICY_RULES } from "@/lib/demo";
import { inr, pct } from "@/lib/format";
import { KV } from "./ui";

type StageTone = "neutral" | "recovered" | "pending" | "blocked";

export interface TraceStage {
  id: string;
  label: string;
  headline: string;
  sub?: string;
  time?: string;
  tone: StageTone;
  details?: { k: string; v: string; mono?: boolean }[];
}

/** Derive the decision trace rail from a decision record. Pure presentation. */
export function deriveStages(o: Opportunity): TraceStage[] {
  const stages: TraceStage[] = [
    {
      id: "failed",
      label: "FAILED PAYMENT",
      headline: inr(o.amountInr),
      sub: o.failureClass.replace(/_/g, " "),
      time: o.time,
      tone: "neutral",
      details: [
        { k: "Opportunity", v: o.id, mono: true },
        { k: "Customer", v: o.customerId, mono: true },
        { k: "Failure detail", v: o.failureDetail },
      ],
    },
  ];

  if (o.diagnosis) {
    stages.push({
      id: "diagnosis",
      label: "DIAGNOSIS",
      headline: o.diagnosis.class.replace(/_/g, " "),
      sub: `confidence ${o.diagnosis.confidence.toFixed(2)}`,
      tone: "neutral",
      details: [
        { k: "Diagnostic class", v: o.diagnosis.class, mono: true },
        { k: "Confidence", v: o.diagnosis.confidence.toFixed(2), mono: true },
        { k: "Summary", v: o.diagnosis.summary },
      ],
    });
  }

  stages.push({
    id: "prediction",
    label: "PREDICTION",
    headline: pct(o.probability),
    sub: "P(recovery) · model estimate",
    tone: "neutral",
    details: [
      { k: "Model", v: "Model A v1.0.0", mono: true },
      { k: "Type", v: "Logistic regression · calibrated" },
      { k: "Features", v: "19 observable", mono: true },
      { k: "Probability", v: o.probability.toFixed(3), mono: true },
    ],
  });

  stages.push({
    id: "value",
    label: "ECONOMIC VALUE",
    headline: inr(o.incrementalEv, { sign: true }),
    sub: "incremental EV vs do-nothing",
    tone: "neutral",
    details: [
      { k: "Expected recovery", v: inr(o.grossEv), mono: true },
      { k: "Payment-link net EV", v: inr(o.netEv), mono: true },
      { k: "Do-nothing EV", v: inr(o.doNothingEv), mono: true },
      { k: "Incremental EV", v: inr(o.incrementalEv, { sign: true }), mono: true },
    ],
  });

  if (o.action === "DO_NOTHING") {
    stages.push({
      id: "optimizer",
      label: "OPTIMIZER",
      headline: "DO NOTHING",
      sub: o.actionReason,
      tone: "neutral",
      details: [
        { k: "Selected action", v: "do_nothing", mono: true },
        { k: "Reason", v: o.actionReason ?? "Negative incremental EV" },
      ],
    });
    return stages;
  }

  stages.push({
    id: "optimizer",
    label: "OPTIMIZER",
    headline: "PAYMENT LINK",
    sub: "capacity-constrained selection",
    tone: "neutral",
    details: [
      { k: "Selected action", v: "create_payment_link", mono: true },
      { k: "Daily capacity", v: "10 / day", mono: true },
      { k: "Ranking basis", v: "Incremental EV, descending" },
    ],
  });

  if (o.policy === "BLOCK") {
    stages.push({
      id: "policy",
      label: "POLICY",
      headline: "BLOCK",
      sub: o.blockedReason,
      tone: "blocked",
      details: [
        { k: "Rules evaluated", v: "7", mono: true },
        { k: "Failing rule", v: o.blockedRule ?? "—", mono: true },
        { k: "Reason", v: o.blockedReason ?? "—" },
        { k: "Policy version", v: "v1.0.0", mono: true },
      ],
    });
    return stages;
  }

  stages.push({
    id: "policy",
    label: "POLICY",
    headline: "ALLOW",
    sub: "7 rules evaluated · 0 failed",
    tone: "neutral",
    details: [
      { k: "Rules evaluated", v: "7", mono: true },
      { k: "Failed rules", v: "0", mono: true },
      { k: "Policy version", v: "v1.0.0", mono: true },
    ],
  });

  if (o.execution) {
    stages.push({
      id: "execution",
      label: "EXECUTION",
      headline: o.execution.status === "SUCCEEDED" ? "CREATED" : "PENDING",
      sub: o.execution.paymentLinkId,
      time: o.execution.createdAt,
      tone: "neutral",
      details: [
        { k: "Execution ID", v: o.execution.executionId, mono: true },
        { k: "Payment Link", v: o.execution.paymentLinkId, mono: true },
        { k: "Reference", v: o.execution.referenceId, mono: true },
        { k: "Mode", v: "RAZORPAY TEST MODE" },
      ],
    });
  }

  if (o.webhook) {
    stages.push({
      id: "webhook",
      label: "WEBHOOK",
      headline: "VERIFIED",
      sub: o.webhook.event,
      time: o.webhook.receivedAt,
      tone: "neutral",
      details: [
        { k: "Event", v: o.webhook.event, mono: true },
        { k: "Signature", v: "VERIFIED", mono: true },
        { k: "Payment ID", v: o.webhook.paymentId, mono: true },
      ],
    });
  }

  if (o.outcome === "RECOVERED") {
    stages.push({
      id: "outcome",
      label: "RECOVERED",
      headline: inr(o.recoveredInr ?? o.amountInr),
      sub: "verified recovery",
      tone: "recovered",
      details: [
        { k: "Outcome", v: "RECOVERED", mono: true },
        { k: "Amount", v: inr(o.recoveredInr ?? o.amountInr), mono: true },
      ],
    });
  } else if (o.outcome === "PENDING") {
    stages.push({
      id: "outcome",
      label: "AWAITING PAYMENT",
      headline: "PENDING",
      sub: "payment link active",
      tone: "pending",
    });
  } else if (o.outcome === "NOT_RECOVERED") {
    stages.push({
      id: "outcome",
      label: "OUTCOME",
      headline: "NOT RECOVERED",
      sub: "link expired unpaid",
      tone: "neutral",
    });
  }

  return stages;
}

const TONE_TEXT: Record<StageTone, string> = {
  neutral: "text-ink",
  recovered: "text-recovered",
  pending: "text-pending",
  blocked: "text-blocked",
};

const TONE_NODE: Record<StageTone, string> = {
  neutral: "border-ink-3 bg-canvas",
  recovered: "border-recovered bg-canvas",
  pending: "border-pending bg-canvas",
  blocked: "border-blocked bg-canvas",
};

function StageRow({
  stage,
  isLast,
  animate,
}: {
  stage: TraceStage;
  isLast: boolean;
  animate: boolean;
}) {
  const [open, setOpen] = useState(false);
  const hasDetails = (stage.details?.length ?? 0) > 0;

  return (
    <li className={`relative pl-8 ${animate ? "anim-fade-up" : ""}`}>
      {/* rail node */}
      <span
        className={`absolute left-0 top-1 w-2.5 h-2.5 rounded-full border ${TONE_NODE[stage.tone]}`}
        aria-hidden="true"
      />
      {/* rail line */}
      {!isLast && (
        <span
          className={`absolute left-[4.5px] top-4 bottom-[-4px] w-px bg-separator ${animate ? "anim-line" : ""}`}
          aria-hidden="true"
        />
      )}

      <div className="pb-7">
        <div className="flex items-baseline justify-between gap-4">
          <span className="label">{stage.label}</span>
          {stage.time && <span className="mono text-[0.625rem] text-ink-3">{stage.time}</span>}
        </div>
        <div className={`fin text-lg font-medium mt-1 ${TONE_TEXT[stage.tone]} ${stage.tone === "recovered" && animate ? "anim-confirm" : ""}`}>
          {stage.headline}
        </div>
        {stage.sub && <div className="text-xs text-ink-3 mt-0.5">{stage.sub}</div>}

        {hasDetails && (
          <div className="mt-2">
            <button
              onClick={() => setOpen((v) => !v)}
              aria-expanded={open}
              className="t-fast text-[0.625rem] tracking-[0.14em] text-ink-3 hover:text-ink-2"
            >
              {open ? "− DETAILS" : "+ DETAILS"}
            </button>
            <div
              className={`grid t-med ${open ? "grid-rows-[1fr] opacity-100 mt-2" : "grid-rows-[0fr] opacity-0"}`}
            >
              <div className="overflow-hidden">
                <div className="border-l border-separator pl-4">
                  {stage.details!.map((d) => (
                    <KV key={d.k} k={d.k} v={d.v} monoV={d.mono} />
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </li>
  );
}

/**
 * The signature RAY experience: one opportunity, the full decision rail.
 * `visible` limits how many stages render (for sequential activation);
 * omit for the complete static trace.
 */
export function DecisionTrace({
  opportunity,
  visible,
  animate = false,
}: {
  opportunity: Opportunity;
  visible?: number;
  animate?: boolean;
}) {
  const stages = deriveStages(opportunity);
  const shown = visible === undefined ? stages : stages.slice(0, visible);

  return (
    <ol className="list-none">
      {shown.map((s, i) => (
        <StageRow
          key={s.id}
          stage={s}
          isLast={i === shown.length - 1}
          animate={animate && i === shown.length - 1}
        />
      ))}
    </ol>
  );
}

/** Seven-rule policy evaluation panel. Only the first failing rule is colored. */
export function PolicyRules({
  blockedRule,
  blockedReason,
  compact = false,
  visibleCount,
}: {
  blockedRule?: string;
  blockedReason?: string;
  compact?: boolean;
  visibleCount?: number;
}) {
  const rules = visibleCount === undefined ? POLICY_RULES : POLICY_RULES.slice(0, visibleCount);
  const failIndex = blockedRule ? POLICY_RULES.indexOf(blockedRule as (typeof POLICY_RULES)[number]) : -1;
  return (
    <div className={compact ? "space-y-1" : "space-y-1.5"}>
      {rules.map((rule, i) => {
        const isBlocked = rule === blockedRule;
        const afterBlock = failIndex >= 0 && i > failIndex;
        return (
          <div key={rule} className="anim-fade">
            <div className="flex items-center justify-between gap-4">
              <span className={`mono text-[0.6875rem] ${isBlocked ? "text-blocked" : afterBlock ? "text-ink-3" : "text-ink-2"}`}>
                {rule}
              </span>
              <span className={`mono text-[0.6875rem] ${isBlocked ? "text-blocked" : afterBlock ? "text-ink-3" : "text-ink-2"}`}>
                {isBlocked ? "✕ BLOCK" : afterBlock ? "· NOT REACHED" : "✓ PASS"}
              </span>
            </div>
            {isBlocked && blockedReason && (
              <div className="text-xs text-ink-3 mt-1 mb-1 pl-0">{blockedReason}</div>
            )}
          </div>
        );
      })}
    </div>
  );
}
