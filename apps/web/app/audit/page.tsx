"use client";

import { useState } from "react";
import Link from "next/link";
import { OPPORTUNITIES, type Opportunity } from "@/lib/demo";
import { inr } from "@/lib/format";
import { KV, Label, OutcomeBadge } from "@/components/ui";

function AuditRow({ o }: { o: Opportunity }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border-b border-separator/50">
      <button
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="t-fast w-full grid grid-cols-[3.5rem_1fr_auto_auto] items-baseline gap-4 py-3 text-left hover:bg-surface-2 -mx-2 px-2 rounded-sm"
      >
        <span className="mono text-[0.625rem] text-ink-3">{o.time}</span>
        <span className="min-w-0">
          <span className="mono text-[0.6875rem] text-ink-2 block truncate">{o.id}</span>
          <span className="text-[0.625rem] text-ink-3">{o.customer}</span>
        </span>
        <span className="fin text-xs text-ink">{inr(o.amountInr)}</span>
        <OutcomeBadge outcome={o.outcome} />
      </button>

      <div className={`grid t-med ${open ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0"}`}>
        <div className="overflow-hidden">
          <div className="grid sm:grid-cols-2 gap-x-10 pb-5 pt-1 pl-2">
            <div className="border-l border-separator pl-4">
              <div className="label mb-2">IDENTITY</div>
              <KV k="Decision ID" v={`dec_${o.id.slice(4)}`} monoV />
              <KV k="Opportunity ID" v={o.id} monoV />
              <KV k="Customer ID" v={o.customerId} monoV />
              {o.execution && (
                <>
                  <KV k="Execution ID" v={o.execution.executionId} monoV />
                  <KV k="Payment Link" v={o.execution.paymentLinkId} monoV />
                </>
              )}
              {o.webhook && <KV k="Webhook payment" v={o.webhook.paymentId} monoV />}
            </div>
            <div className="border-l border-separator pl-4 mt-4 sm:mt-0">
              <div className="label mb-2">PROVENANCE</div>
              <KV k="Model version" v="model_a v1.0.0" monoV />
              <KV k="Optimizer version" v="v1.0.0" monoV />
              <KV k="Policy version" v="v1.0.0" monoV />
              <KV k="Decision time" v={o.time} monoV />
              {o.execution && <KV k="Executed" v={o.execution.createdAt} monoV />}
              {o.webhook && <KV k="Webhook received" v={o.webhook.receivedAt} monoV />}
              <div className="mt-3">
                <Link
                  href={`/decisions/${o.id}`}
                  className="t-fast text-[0.6875rem] text-ink-2 hover:text-ink border-b border-separator pb-0.5"
                >
                  Why did this happen? Open the trace →
                </Link>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function AuditPage() {
  return (
    <div className="space-y-8">
      <header>
        <Label>FORENSICS</Label>
        <h1 className="text-2xl font-medium tracking-tight mt-2">Audit</h1>
        <p className="text-sm text-ink-2 mt-2 max-w-lg">
          Every action is attributable: which model, which optimizer, which
          policy version, which execution, which webhook. Expand any record.
        </p>
      </header>

      <div>
        {OPPORTUNITIES.map((o) => (
          <AuditRow key={o.id} o={o} />
        ))}
      </div>
    </div>
  );
}
