import Link from "next/link";
import { OPPORTUNITIES } from "@/lib/demo";
import { inr } from "@/lib/format";
import { Label, OutcomeBadge, TestModeTag } from "@/components/ui";

export default function ExecutionIndexPage() {
  const executed = OPPORTUNITIES.filter((o) => o.execution);

  return (
    <div className="space-y-8">
      <header className="flex items-start justify-between gap-6 flex-wrap">
        <div>
          <Label>OPERATIONS</Label>
          <h1 className="text-2xl font-medium tracking-tight mt-2">Execution</h1>
          <p className="text-sm text-ink-2 mt-2 max-w-lg">
            Payment Links created by RAY through Razorpay, and their verified
            outcomes.
          </p>
        </div>
        <TestModeTag />
      </header>

      <div className="overflow-x-auto -mx-5 px-5">
        <table className="w-full text-left min-w-[52rem]">
          <thead>
            <tr className="border-b border-separator">
              <th className="label py-3 pr-4 font-medium">STATUS</th>
              <th className="label py-3 pr-4 font-medium">EXECUTION</th>
              <th className="label py-3 pr-4 font-medium">PAYMENT LINK</th>
              <th className="label py-3 pr-4 font-medium">REFERENCE</th>
              <th className="label py-3 pr-4 font-medium">AMOUNT</th>
              <th className="label py-3 pr-4 font-medium">CREATED</th>
            </tr>
          </thead>
          <tbody>
            {executed.map((o) => (
              <tr key={o.id} className="t-fast border-b border-separator/40 hover:bg-surface-2">
                <td className="py-3 pr-4">
                  <OutcomeBadge outcome={o.outcome} />
                </td>
                <td className="py-3 pr-4">
                  <Link
                    href={`/execution/${o.id}`}
                    className="mono text-[0.6875rem] text-ink-2 hover:text-ink t-fast"
                  >
                    {o.execution!.executionId}
                  </Link>
                </td>
                <td className="py-3 pr-4 mono text-[0.6875rem] text-ink-3">
                  {o.execution!.paymentLinkId}
                </td>
                <td className="py-3 pr-4 mono text-[0.6875rem] text-ink-3">
                  {o.execution!.referenceId}
                </td>
                <td className="py-3 pr-4 fin text-xs text-ink">{inr(o.amountInr)}</td>
                <td className="py-3 pr-4 mono text-[0.625rem] text-ink-3">
                  {o.execution!.createdAt}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
