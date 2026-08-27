/**
 * Centralized API client for the RAY FastAPI backend.
 *
 * Every backend-connected page goes through here — no fetch() calls
 * scattered in components. The backend remains authoritative: this file
 * only sends requests and types responses, never recomputes ML/economic/
 * policy values.
 *
 * NEXT_PUBLIC_API_BASE_URL is a plain URL, not a secret — safe to expose.
 * No Razorpay keys or webhook secrets ever pass through this file.
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new ApiError(0, "Could not reach the RAY backend. Is the API server running?");
  }

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // response wasn't JSON; keep statusText
    }
    throw new ApiError(res.status, detail);
  }

  return res.json() as Promise<T>;
}

/* ------------------------------------------------------------------ */
/* Types — mirror the backend response shapes exactly                  */
/* ------------------------------------------------------------------ */

export interface ApiLastDecision {
  selected_action: string | null;
  policy_decision: "ALLOW" | "BLOCK" | null;
  policy_reason: string | null;
  evaluated_at: string | null;
  recovery_probability: number | null;
  incremental_ev: number | null;
  expected_value: number | null;
}

export interface ApiOpportunity {
  opportunity_id: string;
  merchant_id: string;
  customer_id: string;
  customer_name: string;
  amount: number;
  currency: string;
  failure_class: string | null;
  payment_method: string | null;
  failed_at: string | null;
  created_at: string | null;
  decision_made: boolean;
  selected_action: "create_payment_link" | "do_nothing" | null;
  recovered: boolean | null;
  last_decision: ApiLastDecision | null;
}

export interface ApiPolicyRule {
  rule_id: string;
  passed: boolean;
  reason: string | null;
}

export interface ApiPolicyResult {
  decision: "ALLOW" | "BLOCK";
  primary_reason: string | null;
  policy_version: string;
  rules: ApiPolicyRule[];
}

export interface ApiEvaluation {
  opportunity_id: string;
  model: { model_type: string; calibrated: boolean; feature_count: number; version: string };
  prediction: { recovery_probability: number; model_version: string };
  economics: { gross_ev: number; net_ev: number; do_nothing_ev: number; incremental_ev: number };
  optimizer: { recommended_action: "create_payment_link" | "do_nothing"; optimizer_version: string };
  policy: ApiPolicyResult | null;
}

export interface ApiExecutionResult {
  success: boolean;
  execution_id: string;
  state: string;
  payment_link_id: string | null;
  reference_id: string;
  short_url: string | null;
  error_message: string | null;
}

export interface ApiExecutionStatus {
  execution: {
    execution_id: string;
    state: string;
    payment_link_id: string | null;
    reference_id: string;
    short_url: string | null;
    created_at: string | null;
  } | null;
  webhook: {
    event_type: string;
    signature_verified: boolean;
    processing_status: string;
    received_at: string | null;
  } | null;
  outcome: {
    outcome_type: string;
    amount_recovered: number;
    razorpay_payment_id: string | null;
    observed_at: string | null;
  } | null;
}

export interface ApiAuditTrail {
  opportunity: ApiOpportunity;
  predictions: { recovery_probability: number; model_version: string; created_at: string | null }[];
  optimization_runs: {
    selected_action: string;
    expected_value: number;
    incremental_value: number;
    optimizer_version: string;
    created_at: string | null;
  }[];
  events: {
    timestamp: string | null;
    actor: string;
    event_type: string;
    decision: string | null;
    reason: string | null;
    policy_version: string | null;
    model_version: string | null;
    optimizer_version: string | null;
  }[];
  execution: ApiExecutionStatus["execution"];
  webhook: ApiExecutionStatus["webhook"];
  outcome: ApiExecutionStatus["outcome"];
}

/* ------------------------------------------------------------------ */
/* Calls                                                                */
/* ------------------------------------------------------------------ */

export const api = {
  listOpportunities: () =>
    request<{ merchant_id: string; opportunities: ApiOpportunity[] }>("/recovery/opportunities"),

  getOpportunity: (id: string) => request<ApiOpportunity>(`/recovery/opportunities/${id}`),

  evaluate: (opportunityId: string) =>
    request<ApiEvaluation>("/recovery/evaluate", {
      method: "POST",
      body: JSON.stringify({ opportunity_id: opportunityId }),
    }),

  execute: (opportunityId: string) =>
    request<ApiExecutionResult>("/recovery/execute", {
      method: "POST",
      body: JSON.stringify({ opportunity_id: opportunityId }),
    }),

  getStatus: (opportunityId: string) =>
    request<ApiExecutionStatus>(`/recovery/opportunities/${opportunityId}/status`),

  getAudit: (opportunityId: string) => request<ApiAuditTrail>(`/audit/opportunity/${opportunityId}`),

  listExecutions: () =>
    request<{ merchant_id: string; executions: ApiExecutionRow[] }>("/recovery/executions"),

  getConfig: () => request<ApiConfig>("/config"),
};

export interface ApiConfig {
  version: string;
  available_actions: string[];
  max_actions_per_day: number;
  autonomous_amount_limit: string;
}

export interface ApiExecutionRow {
  execution_id: string;
  opportunity_id: string;
  customer_name: string;
  state: string;
  payment_link_id: string | null;
  reference_id: string;
  short_url: string | null;
  amount: number;
  currency: string;
  created_at: string | null;
  webhook: ApiExecutionStatus["webhook"];
  outcome: ApiExecutionStatus["outcome"];
}
