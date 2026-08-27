"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ExternalLink } from "lucide-react";
import { api, ApiError, type ApiOpportunity, type ApiExecutionStatus } from "@/lib/api";
import { inr } from "@/lib/format";
import { KV, Label, Section, TestModeTag } from "@/components/ui";
import { LoadingState, ErrorState, EmptyState } from "@/components/DataState";

const POLL_INTERVAL_MS = 4000;
const POLL_MAX_ATTEMPTS = 30; // ~2 minutes, then stop hammering the backend

function terminalOutcome(status: ApiExecutionStatus | null): boolean {
  const t = status?.outcome?.outcome_type;
  return t === "RECOVERED" || t === "EXPIRED" || t === "CANCELLED" || t === "PARTIALLY_RECOVERED";
}

function StateStep({
  label,
  reached,
  tone = "neutral",
  isLast = false,
}: {
  label: string;
  reached: boolean;
  tone?: "neutral" | "recovered" | "pending" | "blocked";
  isLast?: boolean;
}) {
  const toneCls =
    tone === "recovered"
      ? "text-recovered"
      : tone === "pending"
        ? "text-pending"
        : tone === "blocked"
          ? "text-blocked"
          : reached
            ? "text-ink"
            : "text-ink-3";
  return (
    <div className="flex items-center gap-3">
      <span className={`text-xs tracking-[0.14em] font-medium whitespace-nowrap ${toneCls}`}>{label}</span>
      {!isLast && <span className="w-8 h-px bg-separator shrink-0" />}
    </div>
  );
}

export default function ExecutionDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [opportunity, setOpportunity] = useState<ApiOpportunity | null>(null);
  const [status, setStatus] = useState<ApiExecutionStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pollAttempts = useRef(0);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [opp, statusResult] = await Promise.all([api.getOpportunity(id), api.getStatus(id)]);
      setOpportunity(opp);
      setStatus(statusResult);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load this execution.");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    const timer = setTimeout(load, 0);
    return () => clearTimeout(timer);
  }, [load]);

  // Poll for webhook/outcome updates while the execution hasn't reached a terminal state.
  useEffect(() => {
    if (!status?.execution || terminalOutcome(status)) return;

    const tick = async () => {
      pollAttempts.current += 1;
      try {
        const next = await api.getStatus(id);
        setStatus(next);
        if (!terminalOutcome(next) && pollAttempts.current < POLL_MAX_ATTEMPTS) {
          pollRef.current = setTimeout(tick, POLL_INTERVAL_MS);
        }
      } catch {
        if (pollAttempts.current < POLL_MAX_ATTEMPTS) {
          pollRef.current = setTimeout(tick, POLL_INTERVAL_MS);
        }
      }
    };

    pollRef.current = setTimeout(tick, POLL_INTERVAL_MS);
    return () => {
      if (pollRef.current) clearTimeout(pollRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, status?.execution?.execution_id]);

  if (loading) return <LoadingState label="Loading execution record from the RAY backend…" />;
  if (error || !opportunity) return <ErrorState message={error ?? "Execution not found."} onRetry={load} />;

  if (!status?.execution) {
    return (
      <div className="space-y-8">
        <header>
          <Label>EXECUTION RECORD</Label>
          <h1 className="text-2xl font-medium tracking-tight mt-2">{opportunity.customer_name}</h1>
        </header>
        <EmptyState message="No execution has been created for this opportunity yet." />
        <Link href={`/opportunities/${id}`} className="t-fast text-xs text-ink-2 hover:text-ink border-b border-separator pb-0.5">
          Open opportunity →
        </Link>
      </div>
    );
  }

  const ex = status.execution;
  const recovered = status.outcome?.outcome_type === "RECOVERED";
  const pending = !status.outcome;

  return (
    <div className="space-y-10">
      <header className="flex items-start justify-between gap-6 flex-wrap">
        <div>
          <Label>EXECUTION RECORD</Label>
          <h1 className="fin text-4xl font-medium tracking-tight mt-3">{inr(opportunity.amount)}</h1>
          <div className="mono text-xs text-ink-3 mt-2">{ex.execution_id}</div>
        </div>
        <TestModeTag />
      </header>

      {/* Execution state machine */}
      <Section title="EXECUTION STATE">
        <div className="flex items-center gap-3 flex-wrap">
          <StateStep label="PENDING" reached />
          <StateStep label="SUBMITTED" reached={ex.state !== "PENDING"} />
          <StateStep
            label={ex.state === "FAILED" ? "FAILED" : "SUCCEEDED"}
            reached={ex.state === "SUCCEEDED" || ex.state === "FAILED"}
            tone={ex.state === "FAILED" ? "blocked" : "neutral"}
            isLast
          />
        </div>
        <div className="border-l border-separator pl-4 mt-6 max-w-md">
          <KV k="Execution ID" v={ex.execution_id} monoV />
          <KV k="Payment Link ID" v={ex.payment_link_id ?? "—"} monoV />
          <KV k="Reference ID" v={ex.reference_id} monoV />
          <KV k="Short URL" v={ex.short_url ?? "—"} monoV />
          <KV k="Created" v={ex.created_at ? new Date(ex.created_at).toLocaleString() : "—"} monoV />
          <KV k="Mode" v="RAZORPAY TEST MODE" />
          <KV k="Idempotency" v="ENFORCED — one execution per action" />
          {ex.short_url && (
            <div className="mt-4">
              <a
                href={ex.short_url}
                target="_blank"
                rel="noreferrer"
                className="t-fast inline-flex items-center gap-1.5 text-xs text-ink-2 hover:text-ink border-b border-separator pb-0.5"
              >
                OPEN PAYMENT LINK
                <ExternalLink size={12} strokeWidth={1.75} />
              </a>
            </div>
          )}
        </div>
      </Section>

      {/* Webhook / recovery state machine */}
      <Section title="RECOVERY STATE">
        <div className="flex items-center gap-3 flex-wrap">
          <StateStep label="AWAITING PAYMENT" reached tone={pending ? "pending" : "neutral"} />
          <StateStep label="PAYMENT RECEIVED" reached={!!status.webhook} />
          <StateStep label="WEBHOOK VERIFIED" reached={!!status.webhook} />
          <StateStep
            label={recovered ? "RECOVERY RECORDED" : "OUTCOME RECORDED"}
            reached={!!status.outcome}
            tone={recovered ? "recovered" : "neutral"}
            isLast
          />
        </div>

        {status.webhook ? (
          <div className="border-l border-separator pl-4 mt-6 max-w-md">
            <KV k="Webhook event" v={status.webhook.event_type} monoV />
            <KV k="Signature" v={status.webhook.signature_verified ? "VERIFIED" : "UNVERIFIED"} monoV />
            <KV k="Received" v={status.webhook.received_at ? new Date(status.webhook.received_at).toLocaleString() : "—"} monoV />
            <KV
              k="Outcome"
              v={
                status.outcome ? (
                  <span className="text-recovered">RECOVERED · {inr(status.outcome.amount_recovered)}</span>
                ) : (
                  "AWAITING OUTCOME"
                )
              }
            />
          </div>
        ) : (
          <p className="text-xs text-ink-3 mt-6">
            No webhook received yet. The payment link is active; RAY records the outcome only after
            signature-verified confirmation. This page checks for updates automatically.
          </p>
        )}
      </Section>

      <div className="flex gap-6">
        <Link href={`/opportunities/${id}`} className="t-fast text-xs text-ink-2 hover:text-ink border-b border-separator pb-0.5">
          Open opportunity →
        </Link>
        <Link href={`/decisions/${id}`} className="t-fast text-xs text-ink-2 hover:text-ink border-b border-separator pb-0.5">
          Open decision trace →
        </Link>
      </div>
    </div>
  );
}
