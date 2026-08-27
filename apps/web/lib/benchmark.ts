/**
 * FROZEN V1 BENCHMARK — transcribed verbatim from
 * reports/final-test-evaluation-v1.0.json (Prompt 8, evaluated once).
 *
 * DO NOT recalculate, adjust, or re-derive any value here.
 * These numbers are the single frozen final evaluation of TEST v1.0
 * (n = 300 synthetic opportunities, evaluated exactly once).
 */

export const BENCHMARK_META = {
  datasetVersion: "1.0.0",
  diagnosisVersion: "local_v1",
  testSize: 300,
  bootstrapIterations: 1000,
  bootstrapSeed: 44,
  evaluatedOnce: true,
  evaluationDate: "2026-08-26",
  modelAHash: "442cb669300b7f18",
  modelBHash: "438cfbad547e1ecc",
  baselineHash: "7480f27e347dc430",
} as const;

export interface StrategyBenchmark {
  name: string;
  designation: string;
  rocAuc: number;
  prAuc: number;
  brier: number;
  logLoss: number;
  actionsSelected: number;
  actionRate: number;
  recoveryCount: number;
  recoveryRate: number;
  recoveredInr: number;
  inrPerAction: number;
  predictedNetEv: number;
  bootstrapCi95: [number, number];
}

export const BENCHMARK: Record<"baseline" | "modelA" | "modelB", StrategyBenchmark> = {
  baseline: {
    name: "Baseline",
    designation: "HISTORICAL RECOVERY RATE",
    rocAuc: 0.6297,
    prAuc: 0.2989,
    brier: 0.1913,
    logLoss: 1.3526,
    actionsSelected: 100,
    actionRate: 0.333,
    recoveryCount: 30,
    recoveryRate: 0.3,
    recoveredInr: 171942.55,
    inrPerAction: 1719.43,
    predictedNetEv: 222421.74,
    bootstrapCi95: [109150.65, 244211.55],
  },
  modelA: {
    name: "Model A",
    designation: "RECOMMENDED V1 DEFAULT",
    rocAuc: 0.6588,
    prAuc: 0.2734,
    brier: 0.154,
    logLoss: 0.4797,
    actionsSelected: 100,
    actionRate: 0.333,
    recoveryCount: 29,
    recoveryRate: 0.29,
    recoveredInr: 171615.61,
    inrPerAction: 1716.16,
    predictedNetEv: 90791.56,
    bootstrapCi95: [108362.08, 241917.88],
  },
  modelB: {
    name: "Model B",
    designation: "EXPERIMENTAL LLM-ENRICHED",
    rocAuc: 0.6696,
    prAuc: 0.2772,
    brier: 0.1537,
    logLoss: 0.4793,
    actionsSelected: 100,
    actionRate: 0.333,
    recoveryCount: 28,
    recoveryRate: 0.28,
    recoveredInr: 170139.4,
    inrPerAction: 1701.39,
    predictedNetEv: 98373.53,
    bootstrapCi95: [107484.42, 240433.62],
  },
};

/** Bootstrap deltas vs baseline (realized recovered INR). CI contains zero. */
export const BENCHMARK_DELTAS = {
  modelAVsBaseline: {
    pointEstimate: -326.94,
    ci95: [-13606.82, 12209.71] as [number, number],
  },
  modelBVsBaseline: {
    pointEstimate: -1803.15,
    ci95: [-14990.43, 11742.63] as [number, number],
  },
} as const;

export const V1_PROVED = [
  "End-to-end decision orchestration",
  "Model calibration workflow",
  "Capacity-constrained optimization",
  "Deterministic policy authorization",
  "Safe Razorpay execution",
  "Signed webhook verification",
  "Persistent outcomes",
] as const;

export const V1_NOT_PROVED = [
  "Real-world recovery uplift",
  "Production generalization",
  "Production economics",
] as const;
