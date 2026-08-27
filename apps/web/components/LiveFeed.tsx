"use client";

import Link from "next/link";
import { CheckCircle2 } from "lucide-react";
import type { ApiOpportunity } from "@/lib/api";
import { inr } from "@/lib/format";

type Dot = "gray" | "white" | "amber" | "green" | "red" | "check";

interface FeedEvent {
  rawTime: string;
  text: string;
  detail?: string;
  tone: "neutral" | "recovered" | "pending" | "blocked";
  dot: Dot;
  href: string;
}

function eventFor(o: ApiOpportunity): FeedEvent {
  const href = `/opportunities/${o.opportunity_id}`;
  const rawTime = o.last_decision?.evaluated_at ?? o.created_at ?? o.failed_at ?? "";

  if (!o.decision_made) {
    return { rawTime, text: "Payment failed — awaiting decision", detail: inr(o.amount), tone: "neutral", dot: "red", href };
  }
  if (o.recovered) {
    return { rawTime, text: "RECOVERED", detail: inr(o.amount), tone: "recovered", dot: "check", href };
  }
  if (o.last_decision?.selected_action === "do_nothing") {
    return { rawTime, text: "Optimizer selected do-nothing", detail: "negative incremental EV", tone: "neutral", dot: "gray", href };
  }
  if (o.last_decision?.policy_decision === "BLOCK") {
    return { rawTime, text: "Policy BLOCK", detail: o.last_decision.policy_reason ?? undefined, tone: "blocked", dot: "red", href };
  }
  if (o.last_decision?.policy_decision === "ALLOW") {
    return { rawTime, text: "Policy ALLOW — Payment Link authorized", detail: inr(o.amount), tone: "neutral", dot: "amber", href };
  }
  return { rawTime, text: "RAY evaluated recovery", detail: inr(o.amount), tone: "neutral", dot: "gray", href };
}

const TONE: Record<FeedEvent["tone"], string> = {
  neutral: "text-ink",
  recovered: "text-recovered",
  pending: "text-pending",
  blocked: "text-blocked",
};

const DOT_CLS: Record<Exclude<Dot, "check">, string> = {
  gray: "bg-ink-3",
  white: "bg-ink border border-ink",
  amber: "bg-pending",
  green: "bg-recovered",
  red: "bg-blocked",
};

function EventDot({ dot }: { dot: Dot }) {
  if (dot === "check") {
    return <CheckCircle2 size={14} strokeWidth={2} className="text-recovered shrink-0" />;
  }
  return <span className={`inline-block w-1.5 h-1.5 rounded-full shrink-0 ${DOT_CLS[dot]}`} />;
}

/** Live decision-activity feed — one row per operational opportunity, driven by the RAY backend. */
export function LiveFeed({ opportunities, limit = 14 }: { opportunities: ApiOpportunity[]; limit?: number }) {
  const events = opportunities
    .map(eventFor)
    .sort((a, b) => (a.rawTime < b.rawTime ? 1 : -1))
    .slice(0, limit);

  if (events.length === 0) {
    return <p className="text-xs text-ink-3 py-6">No decision activity yet.</p>;
  }

  return (
    <div>
      {events.map((e, i) => (
        <Link
          key={i}
          href={e.href}
          className="t-fast grid grid-cols-[3.5rem_auto_1fr_auto] items-center gap-3 py-2 border-b border-separator/50 last:border-b-0 hover:bg-surface-2 -mx-2 px-2 rounded-sm"
        >
          <span className="mono text-[0.625rem] text-ink-3">{e.rawTime ? new Date(e.rawTime).toLocaleTimeString() : "—"}</span>
          <EventDot dot={e.dot} />
          <span className={`text-xs ${TONE[e.tone]}`}>{e.text}</span>
          <span className="mono text-[0.625rem] text-ink-3 text-right truncate">{e.detail}</span>
        </Link>
      ))}
    </div>
  );
}
