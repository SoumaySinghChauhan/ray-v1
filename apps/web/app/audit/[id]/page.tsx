"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api, ApiError, type ApiAuditTrail } from "@/lib/api";
import { Label } from "@/components/ui";
import { LoadingState, ErrorState } from "@/components/DataState";
import { AuditDetail } from "@/components/AuditDetail";

export default function AuditDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [trail, setTrail] = useState<ApiAuditTrail | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    setTrail(null);
    try {
      const res = await api.getAudit(id);
      setTrail(res);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load this audit record.");
    }
  }, [id]);

  useEffect(() => {
    const timer = setTimeout(load, 0);
    return () => clearTimeout(timer);
  }, [load]);

  return (
    <div className="space-y-8">
      <header className="flex items-start justify-between gap-6 flex-wrap">
        <div>
          <Label>AUDIT RECORD</Label>
        </div>
        <Link href="/audit" className="t-fast text-xs text-ink-2 hover:text-ink border-b border-separator pb-0.5">
          ← All audit records
        </Link>
      </header>

      {trail === null && !error && <LoadingState label="Loading audit trail from the RAY backend…" />}
      {error && <ErrorState message={error} onRetry={load} />}
      {trail && !error && <AuditDetail trail={trail} />}
    </div>
  );
}
