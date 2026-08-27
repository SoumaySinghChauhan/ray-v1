import type { ApiPolicyRule } from "@/lib/api";

/**
 * The seven deterministic policy rules, in the fixed evaluation order used
 * by policy/engine.py::DeterministicPolicyEngine.evaluate_action(). The
 * engine short-circuits on the first failing rule, so a BLOCK response's
 * `rules` array only contains entries up to and including the failure —
 * rules after it were never reached and never evaluated. This is frozen
 * policy semantics, not a frontend gap: this file only fills in the display
 * for what the engine deliberately never ran.
 */
export const POLICY_RULE_ORDER = [
  "VALID_ACTION_TYPE",
  "OPPORTUNITY_ACTIONABLE",
  "DO_NOT_CONTACT_CHECK",
  "DUPLICATE_ACTION_CHECK",
  "AUTONOMOUS_AMOUNT_LIMIT_CHECK",
  "MAX_CONTACTS_CHECK",
  "DAILY_CAPACITY_CHECK",
] as const;

export const POLICY_RULE_LABELS: Record<string, string> = Object.fromEntries(
  POLICY_RULE_ORDER.map((id) => [id, id])
);

export interface DisplayRule {
  rule_id: string;
  passed: boolean;
  reason: string | null;
  reached: boolean;
}

/**
 * Merges the engine's returned rules with the full canonical rule order so
 * the UI can render every rule slot — including ones the engine never
 * reached because an earlier rule already blocked the action.
 */
export function withUnreachedRules(rules: ApiPolicyRule[]): DisplayRule[] {
  const byId = new Map(rules.map((r) => [r.rule_id, r]));
  return POLICY_RULE_ORDER.map((id) => {
    const r = byId.get(id);
    if (r) return { rule_id: r.rule_id, passed: r.passed, reason: r.reason, reached: true };
    return { rule_id: id, passed: false, reason: null, reached: false };
  });
}
