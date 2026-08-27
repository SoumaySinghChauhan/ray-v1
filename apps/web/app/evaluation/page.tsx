import Image from "next/image";
import {
  BENCHMARK,
  BENCHMARK_DELTAS,
  BENCHMARK_META,
  V1_NOT_PROVED,
  V1_PROVED,
  type StrategyBenchmark,
} from "@/lib/benchmark";
import { TODAY, OPPORTUNITIES } from "@/lib/demo";
import { inr, num, pct } from "@/lib/format";
import { Label, Section, KV, KpiCards } from "@/components/ui";
import { ComparisonBars } from "@/components/charts";
import { CheckCircle2, XCircle, ShieldCheck, Lock, Clock, FileX, BarChart3 } from "lucide-react";

const STRATEGIES: StrategyBenchmark[] = [BENCHMARK.baseline, BENCHMARK.modelA, BENCHMARK.modelB];

const FROZEN_BY_DESIGN = [
  { icon: Lock, label: "Test set (n=300)", sub: "Accessed once" },
  { icon: ShieldCheck, label: "Model artifacts", sub: "Frozen before evaluation" },
  { icon: Clock, label: "Evaluation run", sub: "Single, timestamped" },
  { icon: FileX, label: "No recomputation", sub: "Frontend renders only" },
];

/** Directionality-aware improvement check: lower is better for Brier/LogLoss, higher for AUC. */
function isBetter(metric: string, value: number, baseline: number): boolean {
  if (metric === "Brier" || metric === "Log loss") return value < baseline;
  if (metric === "ROC-AUC" || metric === "PR-AUC") return value > baseline;
  return false;
}

function IntervalBar({
  label,
  point,
  ci,
  domain,
}: {
  label: string;
  point: number;
  ci: [number, number];
  domain: [number, number];
}) {
  const [d0, d1] = domain;
  const span = d1 - d0;
  const left = ((ci[0] - d0) / span) * 100;
  const width = ((ci[1] - ci[0]) / span) * 100;
  const pt = ((point - d0) / span) * 100;
  return (
    <div className="grid grid-cols-[5.5rem_1fr_8rem] items-center gap-4">
      <span className="label">{label}</span>
      <div className="relative h-5">
        <div className="absolute top-1/2 left-0 right-0 h-px bg-separator" />
        <div className="absolute top-1/2 -translate-y-1/2 h-[3px] bg-ink-3" style={{ left: `${left}%`, width: `${width}%` }} />
        <div className="absolute top-1/2 -translate-y-1/2 w-[3px] h-3 bg-ink" style={{ left: `${pt}%` }} />
      </div>
      <span className="mono text-[0.625rem] text-ink-3 text-right">{inr(point)}</span>
    </div>
  );
}

function DeltaBar({
  label,
  point,
  ci,
  domain,
}: {
  label: string;
  point: number;
  ci: [number, number];
  domain: [number, number];
}) {
  const [d0, d1] = domain;
  const span = d1 - d0;
  const left = ((ci[0] - d0) / span) * 100;
  const width = ((ci[1] - ci[0]) / span) * 100;
  const pt = ((point - d0) / span) * 100;
  const zero = ((0 - d0) / span) * 100;
  return (
    <div className="grid grid-cols-[8rem_1fr_10rem] items-center gap-4">
      <span className="label">{label}</span>
      <div className="relative h-6">
        <div className="absolute top-1/2 left-0 right-0 h-px bg-separator" />
        <div className="absolute top-0 bottom-0 w-px bg-ink-3" style={{ left: `${zero}%` }} />
        <div className="absolute top-1/2 -translate-y-1/2 h-[3px] bg-ink-3" style={{ left: `${left}%`, width: `${width}%` }} />
        <div className="absolute top-1/2 -translate-y-1/2 w-[3px] h-3.5 bg-ink" style={{ left: `${pt}%` }} />
      </div>
      <span className="mono text-[0.625rem] text-ink-3 text-right">
        {inr(point, { sign: true })} · CI [{num(ci[0])}, {num(ci[1])}]
      </span>
    </div>
  );
}

export default function EvaluationPage() {
  const ciDomain: [number, number] = [100000, 250000];
  const deltaDomain: [number, number] = [-16000, 16000];
  const attempted = OPPORTUNITIES.filter((o) => o.execution).reduce((s, o) => s + o.amountInr, 0);

  return (
    <div className="space-y-10">
      <header className="flex items-start justify-between gap-8 flex-wrap">
        <div className="max-w-xl">
          <Label>SYSTEM</Label>
          <h1 className="text-3xl font-medium tracking-tight mt-3">Final frozen benchmark</h1>
          <p className="text-sm text-ink-2 mt-3 leading-relaxed">
            Synthetic V1 benchmark · n = {BENCHMARK_META.testSize} · evaluated once on{" "}
            {BENCHMARK_META.evaluationDate}. Model artifacts were frozen before evaluation; the test set was
            accessed exactly once and no value on this page is recomputed by the frontend.
          </p>
        </div>
        <div className="flex-1 min-w-[20rem]">
          <KpiCards
            items={[
              { label: "TEST OPPORTUNITIES", sub: "Frozen test set", value: num(BENCHMARK_META.testSize) },
              { label: "FROZEN RUN", sub: "No re-evaluation", value: "1" },
              { label: "TOTAL ATTEMPTED", sub: "Operational amounts", value: inr(attempted) },
              { label: "BOOTSTRAP UNCERTAINTY", sub: "1,000 resamples", value: "95% CI" },
            ]}
          />
        </div>
      </header>

      <div className="mono text-[0.625rem] text-ink-3 space-x-6">
        <span>dataset v{BENCHMARK_META.datasetVersion}</span>
        <span>model_a {BENCHMARK_META.modelAHash}</span>
        <span>model_b {BENCHMARK_META.modelBHash}</span>
        <span>baseline {BENCHMARK_META.baselineHash}</span>
      </div>

      {/* Headline finding */}
      <div className="border-l-2 border-recovered pl-6 py-4 flex items-start gap-4">
        <span className="shrink-0 w-8 h-8 flex items-center justify-center border border-separator text-ink-3">
          <BarChart3 size={15} strokeWidth={1.75} />
        </span>
        <div>
          <p className="text-lg text-ink leading-relaxed max-w-2xl">
            Predictive improvements did not produce statistically significant economic gains in V1.
          </p>
          <p className="text-xs text-ink-3 mt-2">
            Every bootstrap confidence interval for realized-recovery deltas contains zero (
            {BENCHMARK_META.bootstrapIterations} iterations, case-level resampling).
          </p>
        </div>
      </div>

      {/* Designations */}
      <div className="grid sm:grid-cols-2 gap-8 max-w-2xl">
        <div className="border-t border-separator pt-4">
          <div className="text-sm font-medium">MODEL A</div>
          <div className="label mt-1">RECOMMENDED V1 DEFAULT</div>
          <p className="text-xs text-ink-3 mt-2 leading-relaxed">
            Observable features only. Best calibration-to-complexity ratio; no LLM dependency.
          </p>
        </div>
        <div className="border-t border-separator pt-4">
          <div className="text-sm font-medium">MODEL B</div>
          <div className="label mt-1">EXPERIMENTAL LLM-ENRICHED</div>
          <p className="text-xs text-ink-3 mt-2 leading-relaxed">
            Adds LLM diagnosis features. Marginal metric gains that did not carry to economic outcomes.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_16rem] gap-10">
        <div className="space-y-12">
          {/* Metric table */}
          <Section title="MODEL COMPARISON — TEST SET (N = 300)">
            <div className="overflow-x-auto -mx-5 px-5">
              <table className="w-full text-left min-w-[36rem]">
                <thead>
                  <tr className="border-b border-separator">
                    <th className="label py-3 pr-4 font-medium">METRIC</th>
                    <th className="label py-3 pr-4 font-medium text-right">BASELINE</th>
                    <th className="label py-3 pr-4 font-medium text-right">
                      MODEL A
                      <span className="block text-[0.5625rem] text-ink-3 font-normal normal-case tracking-normal">recommended</span>
                    </th>
                    <th className="label py-3 pr-4 font-medium text-right">
                      MODEL B
                      <span className="block text-[0.5625rem] text-ink-3 font-normal normal-case tracking-normal">experimental</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {(
                    [
                      ["ROC-AUC", (s: StrategyBenchmark) => s.rocAuc.toFixed(4)],
                      ["PR-AUC", (s: StrategyBenchmark) => s.prAuc.toFixed(4)],
                      ["Brier", (s: StrategyBenchmark) => s.brier.toFixed(4)],
                      ["Log loss", (s: StrategyBenchmark) => s.logLoss.toFixed(4)],
                      ["Actions selected", (s: StrategyBenchmark) => num(s.actionsSelected)],
                      ["Recovery rate", (s: StrategyBenchmark) => pct(s.recoveryRate)],
                      ["Recovered INR", (s: StrategyBenchmark) => inr(s.recoveredInr)],
                      ["INR / action", (s: StrategyBenchmark) => inr(s.inrPerAction)],
                      ["Predicted net EV", (s: StrategyBenchmark) => inr(s.predictedNetEv)],
                    ] as [string, (s: StrategyBenchmark) => string][]
                  ).map(([metric, fn]) => (
                    <tr key={metric} className="border-b border-separator/40">
                      <td className="py-2.5 pr-4 text-xs text-ink-2">{metric}</td>
                      <td className="py-2.5 pr-4 mono text-xs text-ink text-right">{fn(BENCHMARK.baseline)}</td>
                      {[BENCHMARK.modelA, BENCHMARK.modelB].map((s) => {
                        const better = isBetter(metric, parseFloat(fn(s)), parseFloat(fn(BENCHMARK.baseline)));
                        return (
                          <td
                            key={s.name}
                            className={`py-2.5 pr-4 mono text-xs text-right ${better ? "text-recovered" : "text-ink"}`}
                          >
                            {fn(s)}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="text-[0.6875rem] text-ink-3 mt-4">
              Predicted net EV is a MODEL ESTIMATE. Recovered INR is the VERIFIED outcome against frozen test
              labels. The two are deliberately reported apart — they must never be conflated.
            </p>
          </Section>

          {/* Bootstrap intervals */}
          <Section title="BOOTSTRAP UNCERTAINTY — REALIZED RECOVERED INR">
            <div className="space-y-3">
              {STRATEGIES.map((s) => (
                <IntervalBar key={s.name} label={s.name.toUpperCase()} point={s.recoveredInr} ci={s.bootstrapCi95} domain={ciDomain} />
              ))}
            </div>
            <p className="text-[0.6875rem] text-ink-3 mt-4">
              95% percentile intervals · {BENCHMARK_META.bootstrapIterations} case-level bootstrap resamples · seed{" "}
              {BENCHMARK_META.bootstrapSeed}.
            </p>

            <div className="mt-10 space-y-3">
              <div className="label-2 mb-4">DELTA VS BASELINE</div>
              <DeltaBar
                label="MODEL A − BASE"
                point={BENCHMARK_DELTAS.modelAVsBaseline.pointEstimate}
                ci={BENCHMARK_DELTAS.modelAVsBaseline.ci95}
                domain={deltaDomain}
              />
              <DeltaBar
                label="MODEL B − BASE"
                point={BENCHMARK_DELTAS.modelBVsBaseline.pointEstimate}
                ci={BENCHMARK_DELTAS.modelBVsBaseline.ci95}
                domain={deltaDomain}
              />
              <p className="text-[0.6875rem] text-ink-3 pt-2">
                Both intervals cross the zero line: no statistically significant difference in realized recovery
                at n = 300.
              </p>
            </div>
          </Section>

          {/* Calibration + predicted vs realized */}
          <div className="grid md:grid-cols-2 gap-8">
            <Section title="CALIBRATION (RELIABILITY)">
              <div className="border border-separator p-2">
                <Image
                  src="/evaluation/final-test-calibration.png"
                  alt="Calibration reliability curves for Baseline, Model A, and Model B against perfect calibration, computed once on the frozen 300-case test set."
                  width={1000}
                  height={400}
                  className="w-full h-auto"
                />
              </div>
              <p className="text-[0.6875rem] text-ink-3 mt-3">
                Frozen artifact from the single evaluation run — rendered verbatim, not recomputed.
              </p>
            </Section>

            <Section title="PREDICTED VS REALIZED RECOVERY">
              <p className="text-[0.6875rem] text-ink-3 mb-4">Model estimate (predicted) vs verified outcome (realized).</p>
              <ComparisonBars
                rows={STRATEGIES.map((s) => ({ label: s.name.toUpperCase(), predicted: s.predictedNetEv, realized: s.recoveredInr }))}
                maxValue={Math.max(...STRATEGIES.map((s) => Math.max(s.predictedNetEv, s.recoveredInr))) * 1.1}
              />
              <div className="flex items-center gap-6 mt-4 text-[0.6875rem]">
                <span className="flex items-center gap-1.5 text-ink-2">
                  <span className="inline-block w-2.5 h-2.5 border border-ink-3" /> Predicted net EV (estimate)
                </span>
                <span className="flex items-center gap-1.5 text-ink-2">
                  <span className="inline-block w-2.5 h-2.5 bg-recovered" /> Realized recovered INR (verified)
                </span>
              </div>
            </Section>
          </div>

          <Section title="ECONOMIC SUMMARY">
            <div className="grid sm:grid-cols-2 gap-x-12 max-w-xl">
              <div>
                <KV k="Total attempted (INR)" v={inr(attempted)} monoV />
                <KV k="Total recovered (INR)" v={inr(TODAY.recoveredInr)} monoV />
                <KV k="Overall recovery rate" v={pct(TODAY.recoveredInr / attempted)} monoV />
              </div>
              <div>
                <KV k="Avg INR recovered / action" v={inr(TODAY.recoveredInr / Math.max(TODAY.capacityUsed, 1))} monoV />
                <KV k="Capacity utilization" v={pct(TODAY.capacityUsed / TODAY.capacityTotal, 0)} monoV />
                <KV k="Policy blocks" v={num(TODAY.policyBlocks)} monoV />
              </div>
            </div>
          </Section>
        </div>

        {/* Right rail: proved / not proved / frozen by design */}
        <div className="space-y-10">
          <div>
            <div className="label mb-3">WHAT V1 PROVED</div>
            <ul className="space-y-2">
              {V1_PROVED.map((item) => (
                <li key={item} className="flex items-start gap-2 text-xs text-ink-2">
                  <CheckCircle2 size={13} strokeWidth={1.75} className="text-ink-3 shrink-0 mt-0.5" />
                  {item}
                </li>
              ))}
            </ul>
          </div>
          <div>
            <div className="label mb-3">WHAT V1 DID NOT PROVE</div>
            <ul className="space-y-2">
              {V1_NOT_PROVED.map((item) => (
                <li key={item} className="flex items-start gap-2 text-xs text-ink-2">
                  <XCircle size={13} strokeWidth={1.75} className="text-ink-3 shrink-0 mt-0.5" />
                  {item}
                </li>
              ))}
            </ul>
            <p className="text-[0.6875rem] text-ink-3 mt-4">Synthetic benchmark — not production performance.</p>
          </div>
          <div>
            <div className="label mb-3">FROZEN BY DESIGN</div>
            <ul className="space-y-3">
              {FROZEN_BY_DESIGN.map((f) => (
                <li key={f.label} className="flex items-start gap-2.5">
                  <f.icon size={14} strokeWidth={1.75} className="text-ink-3 shrink-0 mt-0.5" />
                  <span>
                    <span className="block text-xs text-ink">{f.label}</span>
                    <span className="block text-[0.6875rem] text-ink-3">{f.sub}</span>
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>

      <p className="text-[0.6875rem] text-ink-3 border-t border-separator pt-5">
        Calibration estimates at n = 300 are descriptive and limited by sample size. This page renders the frozen
        evaluation artifacts verbatim; the benchmark is architecturally separate from the operational surfaces of
        this product.
      </p>
    </div>
  );
}
