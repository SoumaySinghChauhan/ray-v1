import Link from "next/link";
import { ExternalLink } from "lucide-react";
import { type ApiAuditTrail } from "@/lib/api";
import { inr } from "@/lib/format";
import { KV } from "@/components/ui";
import { StageNode } from "@/components/StageIcon";

export function AuditDetail({ trail }: { trail: ApiAuditTrail }) {
  const o = trail.opportunity;
  const prediction = trail.predictions[0];
  const run = trail.optimization_runs[0];
  // trail.events is ordered oldest→newest; take the LAST matching decision so
  // this aligns with predictions[0]/optimization_runs[0], which are already
  // most-recent-first from the backend.
  const policyEvent = [...trail.events]
    .reverse()
    .find((e) => e.event_type === "decision_evaluated" && (e.reason === "ALLOW" || e.reason === "BLOCK"));

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_16rem] gap-10">
      <div className="min-w-0">
        <div className="flex items-center gap-2.5 mb-3">
          {policyEvent && (
            <span className={`text-[0.625rem] tracking-[0.1em] font-medium px-2 py-0.5 border ${policyEvent.reason === "ALLOW" ? "border-separator text-ink" : "border-blocked text-blocked"}`}>
              {policyEvent.reason === "ALLOW" ? "ALLOWED" : "BLOCKED"}
            </span>
          )}
          {trail.outcome?.outcome_type === "RECOVERED" && (
            <span className="text-[0.625rem] tracking-[0.1em] font-medium text-recovered flex items-center gap-1.5">
              <span className="w-1 h-1 rounded-full bg-recovered" />
              RECOVERED
            </span>
          )}
        </div>
        <h2 className="text-xl font-medium tracking-tight">{o.customer_name}</h2>
        <div className="fin text-2xl font-medium text-ink mt-2">{inr(o.amount)}</div>
        <div className="mono text-[0.6875rem] text-ink-3 mt-1">{o.opportunity_id}</div>

        <div className="label mt-8 mb-4">DECISION TRACE</div>
        <ol className="list-none max-w-lg">
          <AuditRow stage="failed" tone="blocked" label="FAILED PAYMENT" value={inr(o.amount)} sub={(o.failure_class ?? "unknown").replace(/_/g, " ")} />
          {prediction && (
            <AuditRow stage="prediction" label="PREDICTION" value={`${(prediction.recovery_probability * 100).toFixed(1)}%`} sub={`model v${prediction.model_version}`} />
          )}
          {run && (
            <AuditRow
              stage="value"
              label="ECONOMIC VALUE"
              value={`${run.incremental_value >= 0 ? "+" : ""}${inr(run.incremental_value)}`}
              sub="incremental EV vs do-nothing"
            />
          )}
          {run && <AuditRow stage="optimizer" label="OPTIMIZER" value={run.selected_action.toUpperCase()} sub={`optimizer v${run.optimizer_version}`} />}
          {policyEvent && (
            <AuditRow
              stage="policy"
              tone={policyEvent.reason === "ALLOW" ? "neutral" : "blocked"}
              label="POLICY"
              value={policyEvent.reason ?? ""}
              sub={`policy v${policyEvent.policy_version}`}
            />
          )}
          {trail.execution && <AuditRow stage="execution" label="EXECUTION" value={trail.execution.state} sub={trail.execution.payment_link_id ?? ""} />}
          {trail.webhook && <AuditRow stage="webhook" label="WEBHOOK" value="VERIFIED" sub={trail.webhook.event_type} />}
          {trail.outcome && (
            <AuditRow stage="outcome" tone="recovered" label="OUTCOME" value={inr(trail.outcome.amount_recovered)} sub="verified recovery" isLast />
          )}
        </ol>

        <div className="mt-8 pt-6 border-t border-separator">
          <div className="label mb-3">EVENT LOG</div>
          {trail.events.length === 0 ? (
            <p className="text-xs text-ink-3">No events recorded yet.</p>
          ) : (
            <div className="max-w-lg">
              {trail.events.map((e, i) => (
                <KV key={i} k={e.event_type} v={e.timestamp ? new Date(e.timestamp).toLocaleTimeString() : "—"} monoV />
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="space-y-8">
        <div>
          <div className="label mb-3">PROVENANCE</div>
          <KV k="Model" v={prediction ? `Model A v${prediction.model_version}` : "—"} monoV />
          <KV k="Optimizer" v={run ? `optimizer_v${run.optimizer_version}` : "—"} monoV />
          <KV k="Policy" v={policyEvent ? `policy_v${policyEvent.policy_version}` : "—"} monoV />
          <KV k="Execution Service" v="execution_v1.0.0" monoV />
          <KV k="Webhook Verifier" v="webhook_v1.0.0" monoV />
          <KV k="Environment" v="Razorpay Test Mode" />
        </div>

        <div>
          <div className="label mb-3">RELATED LINKS</div>
          <RelatedLink href={`/opportunities/${o.opportunity_id}`} label="Opportunity" id={o.opportunity_id} />
          <RelatedLink href={`/decisions/${o.opportunity_id}`} label="Decision" id={o.opportunity_id} />
          {trail.execution && (
            <RelatedLink href={`/execution/${o.opportunity_id}`} label="Execution" id={trail.execution.execution_id} />
          )}
        </div>
      </div>
    </div>
  );
}

function RelatedLink({ href, label, id }: { href: string; label: string; id: string }) {
  return (
    <Link href={href} className="t-fast flex items-center justify-between gap-2 py-1.5 group">
      <span className="text-xs text-ink-2 group-hover:text-ink">{label}</span>
      <span className="flex items-center gap-1 mono text-[0.625rem] text-ink-3 group-hover:text-ink-2 truncate max-w-[8rem]">
        {id.slice(0, 12)}…
        <ExternalLink size={10} strokeWidth={1.75} className="shrink-0" />
      </span>
    </Link>
  );
}

function AuditRow({
  stage,
  label,
  value,
  sub,
  tone = "neutral",
  isLast = false,
}: {
  stage: string;
  label: string;
  value: string;
  sub?: string;
  tone?: "neutral" | "recovered" | "blocked";
  isLast?: boolean;
}) {
  return (
    <li className="relative pl-11">
      <span className="absolute left-0 top-0" aria-hidden="true">
        <StageNode stage={stage} tone={tone} size={28} iconSize={13} />
      </span>
      {!isLast && <span className="absolute left-[13.5px] top-[32px] bottom-[-6px] w-px bg-separator" aria-hidden="true" />}
      <div className="pb-6 pt-0.5">
        <div className="label">{label}</div>
        <div className={`text-sm font-medium mt-0.5 ${tone === "recovered" ? "text-recovered" : tone === "blocked" ? "text-blocked" : "text-ink"}`}>
          {value}
        </div>
        {sub && <div className="text-xs text-ink-3 mt-0.5">{sub}</div>}
      </div>
    </li>
  );
}
