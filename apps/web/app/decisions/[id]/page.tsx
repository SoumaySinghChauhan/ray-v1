import Link from "next/link";
import { notFound } from "next/navigation";
import { getOpportunity, OPPORTUNITIES } from "@/lib/demo";
import { inr } from "@/lib/format";
import { DecisionTrace, PolicyRules } from "@/components/DecisionTrace";
import { Label, OutcomeBadge, Section, KV } from "@/components/ui";

export function generateStaticParams() {
  return OPPORTUNITIES.map((o) => ({ id: o.id }));
}

export default async function DecisionDetailPage(props: PageProps<"/decisions/[id]">) {
  const { id } = await props.params;
  const o = getOpportunity(id);
  if (!o) notFound();

  return (
    <div className="space-y-10">
      <header className="flex items-start justify-between gap-6 flex-wrap">
        <div>
          <div className="flex items-center gap-3">
            <Label>DECISION RECORD</Label>
            <OutcomeBadge outcome={o.outcome} />
          </div>
          <h1 className="text-2xl font-medium tracking-tight mt-3">
            {o.customer} · <span className="fin">{inr(o.amountInr)}</span>
          </h1>
          <div className="mono text-xs text-ink-3 mt-2">{o.id}</div>
        </div>
        <Link
          href={`/opportunities/${o.id}`}
          className="t-fast text-xs text-ink-2 hover:text-ink border-b border-separator pb-0.5"
        >
          Open opportunity →
        </Link>
      </header>

      <div className="grid lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)] gap-10 lg:gap-14">
        <Section title="DECISION TRACE">
          <div className="max-w-lg">
            <DecisionTrace opportunity={o} />
          </div>
        </Section>

        <div className="space-y-8">
          {o.policy !== "NOT_EVALUATED" && (
            <Section title="POLICY EVALUATION">
              <PolicyRules blockedRule={o.blockedRule} blockedReason={o.blockedReason} />
              <p className="text-[0.6875rem] text-ink-3 mt-5">
                OPTIMIZER CHOOSES. POLICY AUTHORIZES.
              </p>
            </Section>
          )}

          <Section title="PROVENANCE">
            <KV k="Model" v="Model A v1.0.0" monoV />
            <KV k="Optimizer" v="v1.0.0" monoV />
            <KV k="Policy" v="v1.0.0" monoV />
            <KV k="Decision time" v={o.time} monoV />
          </Section>
        </div>
      </div>
    </div>
  );
}
