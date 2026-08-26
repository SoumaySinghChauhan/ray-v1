import Link from "next/link";
import { notFound } from "next/navigation";
import { getOpportunity, OPPORTUNITIES } from "@/lib/demo";
import { inr } from "@/lib/format";
import { KV, Label, OutcomeBadge, Section, TestModeTag } from "@/components/ui";

export function generateStaticParams() {
  return OPPORTUNITIES.filter((o) => o.execution).map((o) => ({ id: o.id }));
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
      <span
        className={`text-xs tracking-[0.14em] font-medium whitespace-nowrap ${toneCls}`}
      >
        {label}
      </span>
      {!isLast && <span className="w-8 h-px bg-separator shrink-0" />}
    </div>
  );
}

export default async function ExecutionDetailPage(props: PageProps<"/execution/[id]">) {
  const { id } = await props.params;
  const o = getOpportunity(id);
  if (!o || !o.execution) notFound();
  const ex = o.execution;

  const recovered = o.outcome === "RECOVERED";
  const pending = o.outcome === "PENDING";

  return (
    <div className="space-y-10">
      <header className="flex items-start justify-between gap-6 flex-wrap">
        <div>
          <div className="flex items-center gap-3">
            <Label>EXECUTION RECORD</Label>
            <OutcomeBadge outcome={o.outcome} />
          </div>
          <h1 className="fin text-4xl font-medium tracking-tight mt-3">
            {inr(o.amountInr)}
          </h1>
          <div className="mono text-xs text-ink-3 mt-2">{ex.executionId}</div>
        </div>
        <TestModeTag />
      </header>

      {/* Execution state machine */}
      <Section title="EXECUTION STATE">
        <div className="flex items-center gap-3 flex-wrap">
          <StateStep label="PENDING" reached />
          <StateStep label="SUBMITTED" reached />
          <StateStep label="SUCCEEDED" reached isLast />
        </div>
        <div className="border-l border-separator pl-4 mt-6 max-w-md">
          <KV k="Execution ID" v={ex.executionId} monoV />
          <KV k="Payment Link ID" v={ex.paymentLinkId} monoV />
          <KV k="Reference ID" v={ex.referenceId} monoV />
          <KV k="Short URL" v={ex.shortUrl} monoV />
          <KV k="Created" v={ex.createdAt} monoV />
          <KV k="Mode" v="RAZORPAY TEST MODE" />
          <KV k="Idempotency" v="ENFORCED — one execution per action" />
        </div>
      </Section>

      {/* Webhook / recovery state machine */}
      <Section title="RECOVERY STATE">
        <div className="flex items-center gap-3 flex-wrap">
          <StateStep label="AWAITING PAYMENT" reached tone={pending ? "pending" : "neutral"} />
          <StateStep label="PAYMENT RECEIVED" reached={!!o.webhook} />
          <StateStep label="WEBHOOK VERIFIED" reached={!!o.webhook} />
          <StateStep
            label={recovered ? "RECOVERY RECORDED" : "OUTCOME RECORDED"}
            reached={!!o.webhook}
            tone={recovered ? "recovered" : "neutral"}
            isLast
          />
        </div>

        {o.webhook ? (
          <div className="border-l border-separator pl-4 mt-6 max-w-md">
            <KV k="Webhook event" v={o.webhook.event} monoV />
            <KV k="Signature" v="VERIFIED" monoV />
            <KV k="Payment ID" v={o.webhook.paymentId} monoV />
            <KV k="Received" v={o.webhook.receivedAt} monoV />
            <KV
              k="Outcome"
              v={
                recovered ? (
                  <span className="text-recovered">RECOVERED · {inr(o.recoveredInr ?? o.amountInr)}</span>
                ) : (
                  "NOT RECOVERED"
                )
              }
            />
          </div>
        ) : (
          <p className="text-xs text-ink-3 mt-6">
            No webhook received yet. The payment link is active; RAY records
            the outcome only after signature-verified confirmation.
          </p>
        )}
      </Section>

      <div className="flex gap-6">
        <Link
          href={`/opportunities/${o.id}`}
          className="t-fast text-xs text-ink-2 hover:text-ink border-b border-separator pb-0.5"
        >
          Open opportunity →
        </Link>
        <Link
          href={`/decisions/${o.id}`}
          className="t-fast text-xs text-ink-2 hover:text-ink border-b border-separator pb-0.5"
        >
          Open decision trace →
        </Link>
      </div>
    </div>
  );
}
