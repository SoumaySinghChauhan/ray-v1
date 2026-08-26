"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { OPPORTUNITIES, type Opportunity, type Outcome } from "@/lib/demo";
import { inr, pct } from "@/lib/format";
import { OutcomeBadge, PolicyBadge, Label } from "@/components/ui";
import { ProgressBar } from "@/components/charts";
import { TODAY } from "@/lib/demo";
import { num } from "@/lib/format";

type SortKey = "amount" | "probability" | "ev" | "time";

const FAILURE_FILTERS = [
  "ALL",
  "SOFT_DECLINE",
  "HARD_DECLINE",
  "GATEWAY_ERROR",
  "AUTHENTICATION_FAILURE",
] as const;

const OUTCOME_FILTERS: ("ALL" | Outcome)[] = [
  "ALL",
  "RECOVERED",
  "PENDING",
  "BLOCKED",
  "SKIPPED",
  "NOT_RECOVERED",
];

export default function OpportunitiesPage() {
  const [failure, setFailure] = useState<(typeof FAILURE_FILTERS)[number]>("ALL");
  const [outcome, setOutcome] = useState<"ALL" | Outcome>("ALL");
  const [sortKey, setSortKey] = useState<SortKey>("time");
  const [sortDesc, setSortDesc] = useState(true);

  const rows = useMemo(() => {
    let r = [...OPPORTUNITIES];
    if (failure !== "ALL") r = r.filter((o) => o.failureClass === failure);
    if (outcome !== "ALL") r = r.filter((o) => o.outcome === outcome);
    r.sort((a, b) => {
      const va = sortVal(a, sortKey);
      const vb = sortVal(b, sortKey);
      return sortDesc ? vb - va : va - vb;
    });
    return r;
  }, [failure, outcome, sortKey, sortDesc]);

  const toggleSort = (key: SortKey) => {
    if (key === sortKey) setSortDesc((v) => !v);
    else {
      setSortKey(key);
      setSortDesc(true);
    }
  };

  return (
    <div className="space-y-8">
      <header>
        <Label>OPERATIONS</Label>
        <h1 className="text-2xl font-medium tracking-tight mt-2">Opportunities</h1>
        <p className="text-sm text-ink-2 mt-2 max-w-lg">
          Every failed payment RAY has evaluated today — synthetic operational
          records, separate from the frozen benchmark.
        </p>
      </header>

      {/* KPI strip */}
      <div className="border border-separator grid grid-cols-2 md:grid-cols-5">
        {[
          { label: "ACTIVE", value: num(TODAY.opportunities), tone: "text-recovered" },
          { label: "ACTIONS SELECTED", value: num(TODAY.actionsSelected) },
          { label: "PREDICTED NET EV", value: inr(TODAY.predictedNetEv) },
          { label: "POLICY BLOCKS TODAY", value: num(TODAY.policyBlocks), tone: "text-blocked" },
          { label: "CAPACITY", value: `${TODAY.capacityUsed} / ${TODAY.capacityTotal}` },
        ].map((it, i) => (
          <div key={it.label} className={`p-5 ${i > 0 ? "border-t md:border-t-0 md:border-l border-separator" : ""}`}>
            <div className={`fin text-2xl font-medium ${it.tone ?? "text-ink"}`}>{it.value}</div>
            <div className="label mt-2">{it.label}</div>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-x-8 gap-y-4">
        <FilterGroup
          label="FAILURE"
          options={FAILURE_FILTERS}
          value={failure}
          onChange={(v) => setFailure(v as typeof failure)}
        />
        <FilterGroup
          label="OUTCOME"
          options={OUTCOME_FILTERS}
          value={outcome}
          onChange={(v) => setOutcome(v as typeof outcome)}
        />
      </div>

      {/* Table */}
      <div className="overflow-x-auto -mx-5 px-5">
        <table className="w-full text-left min-w-[64rem]">
          <thead>
            <tr className="border-b border-separator">
              <Th>STATUS</Th>
              <Th>CUSTOMER</Th>
              <Th sortable active={sortKey === "amount"} desc={sortDesc} onClick={() => toggleSort("amount")}>
                AMOUNT
              </Th>
              <Th>FAILURE</Th>
              <Th sortable active={sortKey === "probability"} desc={sortDesc} onClick={() => toggleSort("probability")}>
                P(RECOVERY)
              </Th>
              <Th>EXPECTED RECOVERY</Th>
              <Th sortable active={sortKey === "ev"} desc={sortDesc} onClick={() => toggleSort("ev")}>
                INCR. EV
              </Th>
              <Th>ACTION</Th>
              <Th>POLICY</Th>
              <Th>EXECUTION</Th>
              <Th sortable active={sortKey === "time"} desc={sortDesc} onClick={() => toggleSort("time")}>
                TIME
              </Th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr>
                <td colSpan={10} className="py-16 text-center text-sm text-ink-3">
                  No opportunities match the current filters.
                </td>
              </tr>
            )}
            {rows.map((o) => (
              <tr key={o.id} className="t-fast border-b border-separator/40 hover:bg-surface-2 group">
                <Td>
                  <OutcomeBadge outcome={o.outcome} />
                </Td>
                <Td>
                  <Link href={`/opportunities/${o.id}`} className="block group-hover:text-ink text-ink-2 t-fast">
                    <span className="text-xs">{o.customer}</span>
                    <span className="mono block text-[0.625rem] text-ink-3">{o.id}</span>
                  </Link>
                </Td>
                <Td>
                  <span className="fin text-xs text-ink">{inr(o.amountInr)}</span>
                </Td>
                <Td>
                  <span className="text-[0.6875rem] text-ink-2">
                    {o.failureClass.replace(/_/g, " ")}
                  </span>
                </Td>
                <Td>
                  <div className="flex items-center gap-2">
                    <ProgressBar value={o.probability} width={56} />
                    <span className="fin text-xs text-ink-2">{pct(o.probability)}</span>
                  </div>
                </Td>
                <Td>
                  <span className="fin text-xs text-ink-2">{inr(o.grossEv)}</span>
                </Td>
                <Td>
                  <span className={`fin text-xs ${o.incrementalEv > 0 ? "text-recovered" : "text-ink-3"}`}>
                    {inr(o.incrementalEv, { sign: true })}
                  </span>
                </Td>
                <Td>
                  <span className="mono text-[0.625rem] text-ink-2">
                    {o.action === "CREATE_PAYMENT_LINK" ? "payment_link" : "do_nothing"}
                  </span>
                </Td>
                <Td>
                  <PolicyBadge policy={o.policy} />
                </Td>
                <Td>
                  {o.execution ? (
                    <Link href={`/execution/${o.id}`} className="mono text-[0.625rem] text-ink-2 hover:text-ink t-fast">
                      {o.execution.executionId}
                    </Link>
                  ) : (
                    <span className="text-[0.625rem] text-ink-3">—</span>
                  )}
                </Td>
                <Td>
                  <span className="mono text-[0.625rem] text-ink-3">{o.time}</span>
                </Td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="text-[0.6875rem] text-ink-3">
        {rows.length} of {OPPORTUNITIES.length} opportunities · sorted by{" "}
        {sortKey.toUpperCase()} {sortDesc ? "descending" : "ascending"}
      </p>
    </div>
  );
}

function sortVal(o: Opportunity, key: SortKey): number {
  switch (key) {
    case "amount":
      return o.amountInr;
    case "probability":
      return o.probability;
    case "ev":
      return o.incrementalEv;
    case "time":
      return parseInt(o.time.replace(/:/g, ""), 10);
  }
}

function Th({
  children,
  sortable,
  active,
  desc,
  onClick,
}: {
  children: React.ReactNode;
  sortable?: boolean;
  active?: boolean;
  desc?: boolean;
  onClick?: () => void;
}) {
  if (!sortable)
    return <th className="label py-3 pr-4 font-medium">{children}</th>;
  return (
    <th className="py-3 pr-4">
      <button
        onClick={onClick}
        className={`label t-fast font-medium ${active ? "text-ink-2" : ""} hover:text-ink-2`}
      >
        {children}
        {active && <span className="ml-1">{desc ? "↓" : "↑"}</span>}
      </button>
    </th>
  );
}

function Td({ children }: { children: React.ReactNode }) {
  return <td className="py-3 pr-4 align-baseline">{children}</td>;
}

function FilterGroup({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: readonly string[];
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div>
      <div className="label mb-2">{label}</div>
      <div className="flex flex-wrap gap-1">
        {options.map((opt) => (
          <button
            key={opt}
            onClick={() => onChange(opt)}
            aria-pressed={value === opt}
            className={`t-fast px-2 py-1 text-[0.625rem] tracking-[0.1em] rounded-sm ${
              value === opt
                ? "bg-surface-3 text-ink"
                : "text-ink-3 hover:text-ink-2 hover:bg-surface-2"
            }`}
          >
            {opt.replace(/_/g, " ")}
          </button>
        ))}
      </div>
    </div>
  );
}
