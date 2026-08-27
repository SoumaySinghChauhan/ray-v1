/**
 * Frozen V1 economic configuration — display-only mirror of config/v1_config.py.
 * The backend remains authoritative. The frontend never re-implements decision
 * logic; these constants exist only so demo narration matches system reality.
 */
export const ECONOMICS = {
  assumedOrganicRecoveryRate: 0.04,
  interventionCostInr: 0,
  frictionCostInr: 5,
  riskPenaltyInr: 0,
  maxActionsPerDay: 10,
  maxContactsPerCustomerPerDay: 1,
  autonomousAmountLimitInr: 25000,
} as const;

/** Display-only EV breakdown mirroring optimizer/core.py output shape. */
export function evBreakdown(amountInr: number, probability: number) {
  const gross = probability * amountInr;
  const net =
    gross -
    ECONOMICS.interventionCostInr -
    ECONOMICS.frictionCostInr -
    ECONOMICS.riskPenaltyInr;
  const doNothing = ECONOMICS.assumedOrganicRecoveryRate * amountInr;
  return {
    grossEv: gross,
    netEv: net,
    doNothingEv: doNothing,
    incrementalEv: net - doNothing,
  };
}
