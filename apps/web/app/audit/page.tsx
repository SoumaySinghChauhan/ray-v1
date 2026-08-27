"use client";

import { useCallback, useEffect, useState } from "react";
import { Search } from "lucide-react";
import { api, ApiError, type ApiOpportunity, type ApiAuditTrail } from "@/lib/api";
import { inr, num } from "@/lib/format";
import { Label, KpiCards } from "@/components/ui";
import { LoadingState, ErrorState, EmptyState } from "@/components/DataState";
import { AuditDetail } from "@/components/AuditDetail";

export default function AuditPage() {
  const [opportunities, setOpportunities] = useState<ApiOpportunity[] | null>(null);
  const [listError, setListError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [trail, setTrail] = useState<ApiAuditTrail | null>(null);
  const [trailError, setTrailError] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  const loadList = useCallback(async () => {
    setListError(null);
    setOpportunities(null);
    try {
      const res = await api.listOpportunities();
      setOpportunities(res.opportunities);
      const decided = res.opportunities.find((o) => o.decision_made);
      if (decided) setSelectedId(decided.opportunity_id);
    } catch (e) {
      setListError(e instanceof ApiError ? e.message : "Failed to load audit records.");
    }
  }, []);

  useEffect(() => {
    const id = setTimeout(loadList, 0);
    return () => clearTimeout(id);
  }, [loadList]);

  const loadTrail = useCallback(async (id: string) => {
    setTrailError(null);
    setTrail(null);
    try {
      const res = await api.getAudit(id);
      setTrail(res);
    } catch (e) {
      setTrailError(e instanceof ApiError ? e.message : "Failed to load this record's audit trail.");
    }
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    const id = setTimeout(() => loadTrail(selectedId), 0);
    return () => clearTimeout(id);
  }, [selectedId, loadTrail]);

  const records = (opportunities ?? []).filter((o) => {
    const q = query.trim().toLowerCase();
    if (!q) return true;
    return o.customer_name.toLowerCase().includes(q) || o.opportunity_id.toLowerCase().includes(q);
  });

  const decided = (opportunities ?? []).filter((o) => o.decision_made);
  const today = decided.length;

  return (
    <div className="space-y-8">
      <header>
        <Label>SYSTEM</Label>
        <h1 className="text-2xl font-medium tracking-tight mt-2">Audit</h1>
        <p className="text-sm text-ink-2 mt-2 max-w-lg">
          Every action is attributable. Select any record to reconstruct the full reasoning and execution path.
        </p>
      </header>

      {opportunities === null && !listError && <LoadingState label="Loading audit records from the RAY backend…" />}
      {listError && <ErrorState message={listError} onRetry={loadList} />}

      {opportunities !== null && !listError && (
        <>
          <KpiCards
            items={[
              { label: "TOTAL RECORDS", value: num(opportunities.length), sub: "All time" },
              { label: "DECIDED", value: num(today), sub: "With a trace" },
              { label: "RECOVERED", value: inr(decided.filter((o) => o.recovered).reduce((s, o) => s + o.amount, 0)), sub: "Verified", tone: "recovered" },
            ]}
          />

          <div className="relative max-w-md">
            <Search size={14} strokeWidth={1.75} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-3" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search by customer or opportunity ID..."
              className="w-full bg-surface-2 border border-separator rounded-sm pl-9 pr-3 py-2 text-xs text-ink placeholder:text-ink-3 focus-visible:outline-1 focus-visible:outline-ink-2"
            />
          </div>

          {records.length === 0 ? (
            <EmptyState message="No records match your search." />
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-[16rem_minmax(0,1fr)] gap-8">
              <div>
                <div className="label mb-3">AUDIT RECORDS</div>
                <div className="max-h-[42rem] overflow-y-auto pr-1">
                  {records.map((o) => (
                    <button
                      key={o.opportunity_id}
                      onClick={() => setSelectedId(o.opportunity_id)}
                      aria-current={selectedId === o.opportunity_id ? "true" : undefined}
                      className={`t-fast w-full text-left px-3 py-2.5 border-l-2 mb-0.5 ${
                        selectedId === o.opportunity_id ? "border-l-recovered bg-surface-2" : "border-l-transparent hover:bg-surface-2"
                      }`}
                    >
                      <div className="flex items-baseline justify-between gap-2">
                        <span className="text-xs text-ink">{o.customer_name}</span>
                        <span className="fin text-[0.6875rem] text-ink-2">{inr(o.amount)}</span>
                      </div>
                      <div className="flex items-center justify-between gap-2 mt-1">
                        <span className="mono text-[0.625rem] text-ink-3 truncate">{o.opportunity_id.slice(0, 16)}…</span>
                        <span className={`text-[0.625rem] tracking-[0.1em] ${o.decision_made ? "text-ink-2" : "text-ink-3"}`}>
                          {o.decision_made ? "DECIDED" : "PENDING"}
                        </span>
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              <div className="min-w-0 border-t lg:border-t-0 lg:border-l border-separator pt-6 lg:pt-0 lg:pl-8">
                {!selectedId && <EmptyState message="Select a record to reconstruct its full reasoning path." />}
                {selectedId && trailError && <ErrorState message={trailError} onRetry={() => loadTrail(selectedId)} />}
                {selectedId && !trailError && !trail && <LoadingState label="Loading audit trail…" />}
                {selectedId && !trailError && trail && <AuditDetail trail={trail} />}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
