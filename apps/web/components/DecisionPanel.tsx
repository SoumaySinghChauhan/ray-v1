"use client";

import { useState } from "react";
import { X } from "lucide-react";
import type { Opportunity } from "@/lib/demo";
import { DecisionTrace, PolicyRules } from "./DecisionTrace";
import { OutcomeBadge, KV } from "./ui";
import { inr } from "@/lib/format";

type Tab = "trace" | "policy" | "provenance";

/** Slide-over decision detail — TRACE / POLICY / PROVENANCE tabs, used from list pages. */
export function DecisionPanel({ opportunity, onClose }: { opportunity: Opportunity; onClose: () => void }) {
  const [tab, setTab] = useState<Tab>("trace");
  const o = opportunity;

  return (
    <div className="fixed inset-0 z-30 flex justify-end" role="dialog" aria-modal="true" aria-label="Decision trace">
      <button
        className="absolute inset-0 bg-black/60 anim-fade"
        onClick={onClose}
        aria-label="Close decision trace"
      />
      <div className="anim-fade-up relative w-full max-w-md h-full bg-surface-1 border-l border-separator overflow-y-auto">
        <div className="sticky top-0 bg-surface-1 border-b border-separator px-6 py-4 flex items-center justify-between z-10">
          <div className="label-2">DECISION TRACE</div>
          <button onClick={onClose} className="t-fast text-ink-3 hover:text-ink" aria-label="Close">
            <X size={18} strokeWidth={1.75} />
          </button>
        </div>

        <div className="px-6 pt-5">
          <OutcomeBadge outcome={o.outcome} />
          <h3 className="text-xl font-medium tracking-tight mt-2">{o.customer}</h3>
          <div className="fin text-lg text-ink-2 mt-0.5">{inr(o.amountInr)}</div>
          <div className="mono text-[0.6875rem] text-ink-3 mt-1">{o.id}</div>
        </div>

        <div className="flex gap-1 px-6 mt-5 border-b border-separator">
          {(["trace", "policy", "provenance"] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              aria-current={tab === t ? "page" : undefined}
              className={`t-fast px-3 py-2.5 text-xs tracking-[0.08em] border-b -mb-px ${
                tab === t ? "text-ink border-ink" : "text-ink-3 border-transparent hover:text-ink-2"
              }`}
            >
              {t === "trace" ? "TRACE" : t === "policy" ? "POLICY (7)" : "PROVENANCE"}
            </button>
          ))}
        </div>

        <div className="px-6 py-6">
          {tab === "trace" && (
            <DecisionTrace opportunity={o} />
          )}

          {tab === "policy" && (
            <>
              {o.policy === "NOT_EVALUATED" ? (
                <p className="text-xs text-ink-3">
                  Not evaluated — the optimizer selected do-nothing, so no execution authorization was required.
                </p>
              ) : (
                <>
                  <PolicyRules blockedRule={o.blockedRule} blockedReason={o.blockedReason} />
                  <p className="text-[0.6875rem] text-ink-3 mt-5">OPTIMIZER CHOOSES. POLICY AUTHORIZES.</p>
                </>
              )}
            </>
          )}

          {tab === "provenance" && (
            <div>
              <KV k="Model" v="Model A v1.0.0" monoV />
              <KV k="Optimizer" v="v1.0.0" monoV />
              <KV k="Policy" v="v1.0.0" monoV />
              <KV k="Policy ruleset" v="rules_v1.0.0" monoV />
              {o.execution && <KV k="Execution service" v="execution_v1.0.0" monoV />}
              {o.webhook && <KV k="Webhook verifier" v="webhook_v1.0.0" monoV />}
              <KV k="Environment" v="Razorpay Test Mode" />
              <KV k="Decision time" v={o.time} monoV />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
