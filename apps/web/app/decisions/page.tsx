import Link from "next/link";
import { OPPORTUNITIES } from "@/lib/demo";
import { inr, pct } from "@/lib/format";
import { Label, OutcomeBadge, PolicyBadge } from "@/components/ui";

export default function DecisionsPage() {
  return (
    <div className="space-y-8">
      <header>
        <Label>OPERATIONS</Label>
        <h1 className="text-2xl font-medium tracking-tight mt-2">Decisions</h1>
        <p className="text-sm text-ink-2 mt-2 max-w-lg">
          Every decision RAY reached today, with its full reasoning trace.
        </p>
      </header>

      <div>
        {OPPORTUNITIES.map((o) => (
          <Link
            key={o.id}
            href={`/decisions/${o.id}`}
            className="t-fast grid grid-cols-[auto_1fr_auto_auto_auto] items-baseline gap-4 lg:gap-8 py-3.5 border-b border-separator/50 hover:bg-surface-2 -mx-2 px-2 rounded-sm"
          >
            <span className="mono text-[0.625rem] text-ink-3 w-14">{o.time}</span>
            <span className="min-w-0">
              <span className="text-xs text-ink block truncate">
                {o.action === "CREATE_PAYMENT_LINK" ? "Payment Link" : "Do nothing"} ·{" "}
                {o.customer}
              </span>
              <span className="mono text-[0.625rem] text-ink-3">
                P = {pct(o.probability)} · EV {inr(o.incrementalEv, { sign: true })}
              </span>
            </span>
            <span className="fin text-xs text-ink hidden sm:block">{inr(o.amountInr)}</span>
            <PolicyBadge policy={o.policy} />
            <OutcomeBadge outcome={o.outcome} />
          </Link>
        ))}
      </div>
    </div>
  );
}
