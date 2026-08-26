"use client";

import Link from "next/link";
import { OPPORTUNITIES, type Opportunity } from "@/lib/demo";
import { inr, pct } from "@/lib/format";

interface FeedEvent {
  time: string;
  text: string;
  detail?: string;
  tone: "neutral" | "recovered" | "pending" | "blocked";
  href: string;
}

function eventsFor(o: Opportunity): FeedEvent[] {
  const href = `/opportunities/${o.id}`;
  const events: FeedEvent[] = [
    {
      time: o.time,
      text: "Payment failed",
      detail: `${inr(o.amountInr)} · ${o.failureClass.replace(/_/g, " ").toLowerCase()}`,
      tone: "neutral",
      href,
    },
    {
      time: o.time,
      text: "RAY evaluated recovery",
      detail: `P(recovery) = ${pct(o.probability)}`,
      tone: "neutral",
      href,
    },
  ];

  if (o.action === "DO_NOTHING") {
    events.push({
      time: o.time,
      text: "Optimizer selected do-nothing",
      detail: "negative incremental EV",
      tone: "neutral",
      href,
    });
    return events;
  }

  events.push({
    time: o.time,
    text: "Optimizer selected Payment Link",
    detail: `incremental EV ${inr(o.incrementalEv, { sign: true })}`,
    tone: "neutral",
    href,
  });

  if (o.policy === "BLOCK") {
    events.push({
      time: o.time,
      text: "Policy BLOCK",
      detail: o.blockedRule,
      tone: "blocked",
      href,
    });
    return events;
  }

  events.push({ time: o.time, text: "Policy ALLOW", tone: "neutral", href });

  if (o.execution) {
    events.push({
      time: o.execution.createdAt,
      text: "Payment Link created",
      detail: o.execution.paymentLinkId,
      tone: "neutral",
      href,
    });
  }

  if (o.webhook) {
    events.push({
      time: o.webhook.receivedAt,
      text: `${o.webhook.event} received`,
      detail: "signature verified",
      tone: "neutral",
      href,
    });
  }

  if (o.outcome === "RECOVERED") {
    events.push({
      time: o.webhook?.receivedAt ?? o.time,
      text: "RECOVERED",
      detail: inr(o.recoveredInr ?? o.amountInr),
      tone: "recovered",
      href,
    });
  }

  return events;
}

const TONE: Record<FeedEvent["tone"], string> = {
  neutral: "text-ink",
  recovered: "text-recovered",
  pending: "text-pending",
  blocked: "text-blocked",
};

export function LiveFeed({ limit = 14 }: { limit?: number }) {
  const events = OPPORTUNITIES.slice(0, 5)
    .flatMap(eventsFor)
    .sort((a, b) => (a.time < b.time ? 1 : -1))
    .slice(0, limit);

  return (
    <div>
      {events.map((e, i) => (
        <Link
          key={i}
          href={e.href}
          className="t-fast grid grid-cols-[3.5rem_1fr_auto] items-baseline gap-4 py-2 border-b border-separator/50 last:border-b-0 hover:bg-surface-2 -mx-2 px-2 rounded-sm"
        >
          <span className="mono text-[0.625rem] text-ink-3">{e.time}</span>
          <span className={`text-xs ${TONE[e.tone]}`}>{e.text}</span>
          <span className="mono text-[0.625rem] text-ink-3 text-right">{e.detail}</span>
        </Link>
      ))}
    </div>
  );
}
