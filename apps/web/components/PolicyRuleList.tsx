import type { ApiPolicyRule } from "@/lib/api";
import { withUnreachedRules } from "@/lib/policyRules";

/**
 * Renders all seven policy rules in fixed evaluation order. The policy
 * engine short-circuits on the first failing rule, so `rules` (from the
 * backend) only contains entries up to and including that failure — this
 * component fills in the remaining slots as NOT REACHED rather than
 * silently omitting them, and gives the first failing rule the strongest
 * visual emphasis.
 */
export function PolicyRuleList({ rules, dense = false }: { rules: ApiPolicyRule[]; dense?: boolean }) {
  const display = withUnreachedRules(rules);
  const firstFailureIndex = display.findIndex((r) => r.reached && !r.passed);

  return (
    <div className={dense ? "space-y-1.5" : "space-y-2"}>
      {display.map((r, i) => {
        const isFirstFailure = i === firstFailureIndex;
        const idCls = !r.reached ? "text-ink-3" : r.passed ? "text-ink-2" : "text-blocked";
        const statusCls = !r.reached ? "text-ink-3" : r.passed ? "text-ink-2" : "text-blocked";
        return (
          <div
            key={r.rule_id}
            className={`flex items-center justify-between gap-4 ${
              isFirstFailure ? "px-2.5 py-1.5 -mx-2.5 bg-blocked/10 border-l-2 border-blocked" : ""
            }`}
          >
            <span className={`mono text-[0.6875rem] ${idCls} ${isFirstFailure ? "font-medium" : ""} ${!r.reached ? "opacity-50" : ""}`}>
              {r.rule_id}
            </span>
            <span className={`mono text-[0.6875rem] ${statusCls} ${isFirstFailure ? "font-medium" : ""} ${!r.reached ? "opacity-50" : ""}`}>
              {!r.reached ? "NOT REACHED" : r.passed ? "✓ PASS" : "✕ BLOCK"}
            </span>
          </div>
        );
      })}
    </div>
  );
}
