import Link from "next/link";
import { notFound } from "next/navigation";
import { getOpportunity, OPPORTUNITIES } from "@/lib/demo";
import { ECONOMICS } from "@/lib/economics";
import { inr, pct } from "@/lib/format";
import { DecisionTrace, PolicyRules } from "@/components/DecisionTrace";
import { KV, Label, OutcomeBadge, Section, TestModeTag } from "@/components/ui";

export function generateStaticParams() {
  return OPPORTUNITIES.map((o) => ({ id: o.id }));
}

export default async function OpportunityDetailPage(
  props: PageProps<"/opportunities/[id]">
) {
  const { id } = await props.params;
  const o = getOpportunity(id);
  if (!o) notFound();

  const capacityUsed = OPPORTUNITIES.filter((x) => x.execution).length;

  return (
    <div className="space-y-10">
      <header className="flex items-start justify-between gap-6 flex-wrap">
        <div>
          <div className="flex items-center gap-3">
            <Label>RECOVERY OPPORTUNITY</Label>
            <OutcomeBadge outcome={o.outcome} />
          </div>
          <h1 className="fin text-4xl lg:text-5xl font-medium tracking-tight mt-3">
            {inr(o.amountInr)}
          </h1>
          <div className="text-sm text-ink-2 mt-2">
            {o.failureClass.replace(/_/g, " ")} · {o.customer}
          </div>
        </div>
        <div className="text-right space-y-1">
          <div className="mono text-xs text-ink-3">{o.id}</div>
          <div className="mono text-xs text-ink-3">{o.time}</div>
        </div>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)] gap-10 lg:gap-14">
        {/* ── LEFT: observable facts ─────────────────────────── */}
        <div className="space-y-8">
          <Section title="PAYMENT">
            <KV k="Amount" v={inr(o.amountInr)} monoV />
            <KV k="Failure class" v={o.failureClass.replace(/_/g, " ")} />
            <KV k="Failure detail" v={o.failureDetail} />
            <KV k="Failed at" v={o.time} monoV />
          </Section>

          <Section title="CUSTOMER">
            <KV k="Name" v={o.customer} />
            <KV k="Customer ID" v={o.customerId} monoV />
          </Section>

          <Section title="HISTORY">
            <KV k="Payments" v={o.history.payments} monoV />
            <KV k="Successful" v={o.history.successes} monoV />
            <KV k="Past recoveries" v={o.history.recoveries} monoV />
            <KV k="Historical recovery rate" v={pct(o.history.recoveryRate)} monoV />
          </Section>

          {o.diagnosis && (
            <Section title="DIAGNOSIS">
              <KV k="Class" v={o.diagnosis.class} monoV />
              <KV k="Confidence" v={o.diagnosis.confidence.toFixed(2)} monoV />
              <p className="text-xs text-ink-2 leading-relaxed mt-3">
                {o.diagnosis.summary}
              </p>
            </Section>
          )}
        </div>

        {/* ── RIGHT: the RAY decision ────────────────────────── */}
        <div className="space-y-8">
          <Section title="RAY DECISION">
            <div className="grid grid-cols-2 gap-x-8 gap-y-6 mb-2">
              <div>
                <div className="label mb-1.5">PROBABILITY</div>
                <div className="fin text-3xl font-medium">{pct(o.probability)}</div>
                <div className="text-[0.6875rem] text-ink-3 mt-1">MODEL ESTIMATE</div>
              </div>
              <div>
                <div className="label mb-1.5">EXPECTED RECOVERY</div>
                <div className="fin text-3xl font-medium text-ink-2">{inr(o.grossEv)}</div>
                <div className="text-[0.6875rem] text-ink-3 mt-1">MODEL ESTIMATE</div>
              </div>
            </div>

            <div className="border-l border-separator pl-4 mt-6">
              <KV k="Payment-link net EV" v={inr(o.netEv)} monoV />
              <KV k="Do-nothing EV" v={inr(o.doNothingEv)} monoV />
              <KV k="Incremental EV" v={inr(o.incrementalEv, { sign: true })} monoV />
              <KV k="Capacity" v={`${capacityUsed} / ${ECONOMICS.maxActionsPerDay}`} monoV />
            </div>
          </Section>

          <Section title="POLICY">
            {o.policy === "NOT_EVALUATED" ? (
              <p className="text-xs text-ink-3">
                Not evaluated — the optimizer selected do-nothing, so no
                execution authorization was required.
              </p>
            ) : (
              <>
                <PolicyRules blockedRule={o.blockedRule} blockedReason={o.blockedReason} />
                <div className="mt-5 flex items-center justify-between">
                  <span className="label">RESULT</span>
                  <span
                    className={`text-sm font-medium tracking-[0.14em] ${
                      o.policy === "ALLOW" ? "text-ink" : "text-blocked"
                    }`}
                  >
                    {o.policy}
                  </span>
                </div>
                <p className="text-[0.6875rem] text-ink-3 mt-4">
                  OPTIMIZER CHOOSES. POLICY AUTHORIZES.
                </p>
              </>
            )}
          </Section>

          {o.execution && (
            <Section title="EXECUTION" action={<TestModeTag />}>
              <KV k="Status" v={o.execution.status} monoV />
              <KV k="Execution ID" v={o.execution.executionId} monoV />
              <KV k="Payment Link" v={o.execution.paymentLinkId} monoV />
              <KV k="Reference" v={o.execution.referenceId} monoV />
              <div className="mt-4">
                <Link
                  href={`/execution/${o.id}`}
                  className="t-fast text-xs text-ink-2 hover:text-ink border-b border-separator pb-0.5"
                >
                  Open execution record →
                </Link>
              </div>
            </Section>
          )}
        </div>
      </div>

      {/* ── Full decision trace ──────────────────────────────── */}
      <Section title="DECISION TRACE">
        <div className="max-w-lg">
          <DecisionTrace opportunity={o} />
        </div>
        <Link
          href={`/decisions/${o.id}`}
          className="t-fast text-xs text-ink-2 hover:text-ink border-b border-separator pb-0.5"
        >
          Open full decision record →
        </Link>
      </Section>
    </div>
  );
}
