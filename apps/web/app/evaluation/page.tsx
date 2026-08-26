import {
  BENCHMARK,
  BENCHMARK_DELTAS,
  BENCHMARK_META,
  V1_NOT_PROVED,
  V1_PROVED,
  type StrategyBenchmark,
} from "@/lib/benchmark";
import { inr, num, pct } from "@/lib/format";
import { Label, Section } from "@/components/ui";

const STRATEGIES: StrategyBenchmark[] = [
  BENCHMARK.baseline,
  BENCHMARK.modelA,
  BENCHMARK.modelB,
];

/* Monochrome bootstrap interval bar. Domain spans all CIs. */
function IntervalBar({
  label,
  point,
  ci,
  domain,
  highlight = false,
}: {
  label: string;
  point: number;
  ci: [number, number];
  domain: [number, number];
  highlight?: boolean;
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
        <div
          className={`absolute top-1/2 -translate-y-1/2 h-[3px] ${highlight ? "bg-ink-2" : "bg-ink-3"}`}
          style={{ left: `${left}%`, width: `${width}%` }}
        />
        <div
          className="absolute top-1/2 -translate-y-1/2 w-[3px] h-3 bg-ink"
          style={{ left: `${pt}%` }}
        />
      </div>
      <span className="mono text-[0.625rem] text-ink-3 text-right">
        {inr(point)}
      </span>
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
        <div
          className="absolute top-1/2 -translate-y-1/2 h-[3px] bg-ink-3"
          style={{ left: `${left}%`, width: `${width}%` }}
        />
        <div
          className="absolute top-1/2 -translate-y-1/2 w-[3px] h-3.5 bg-ink"
          style={{ left: `${pt}%` }}
        />
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

  return (
    <div className="space-y-12">
      <header>
        <Label>RAY V1</Label>
        <h1 className="text-3xl font-medium tracking-tight mt-3">
          Final frozen benchmark
        </h1>
        <p className="text-sm text-ink-2 mt-3 max-w-xl leading-relaxed">
          Synthetic V1 benchmark · n = {BENCHMARK_META.testSize} · evaluated
          once on {BENCHMARK_META.evaluationDate}. Model artifacts were frozen
          before evaluation; the test set was accessed exactly once and no
          value on this page is recomputed by the frontend.
        </p>
        <div className="mono text-[0.625rem] text-ink-3 mt-4 space-x-6">
          <span>dataset v{BENCHMARK_META.datasetVersion}</span>
          <span>model_a {BENCHMARK_META.modelAHash}</span>
          <span>model_b {BENCHMARK_META.modelBHash}</span>
          <span>baseline {BENCHMARK_META.baselineHash}</span>
        </div>
      </header>

      {/* Headline finding */}
      <div className="border-l-2 border-ink-3 pl-6 py-1 max-w-2xl">
        <p className="text-lg text-ink leading-relaxed">
          Predictive improvements did not produce statistically significant
          economic gains in V1.
        </p>
        <p className="text-xs text-ink-3 mt-2">
          Every bootstrap confidence interval for realized-recovery deltas
          contains zero ({BENCHMARK_META.bootstrapIterations} iterations,
          case-level resampling).
        </p>
      </div>

      {/* Designations */}
      <div className="grid sm:grid-cols-2 gap-8 max-w-2xl">
        <div className="border-t border-separator pt-4">
          <div className="text-sm font-medium">MODEL A</div>
          <div className="label mt-1">RECOMMENDED V1 DEFAULT</div>
          <p className="text-xs text-ink-3 mt-2 leading-relaxed">
            Observable features only. Best calibration-to-complexity ratio; no
            LLM dependency.
          </p>
        </div>
        <div className="border-t border-separator pt-4">
          <div className="text-sm font-medium">MODEL B</div>
          <div className="label mt-1">EXPERIMENTAL LLM-ENRICHED</div>
          <p className="text-xs text-ink-3 mt-2 leading-relaxed">
            Adds LLM diagnosis features. Marginal metric gains that did not
            carry to economic outcomes.
          </p>
        </div>
      </div>

      {/* Metric table */}
      <Section title="MODEL COMPARISON — TEST SET (N = 300)">
        <div className="overflow-x-auto -mx-5 px-5">
          <table className="w-full text-left min-w-[44rem] max-w-3xl">
            <thead>
              <tr className="border-b border-separator">
                <th className="label py-3 pr-4 font-medium">METRIC</th>
                {STRATEGIES.map((s) => (
                  <th key={s.name} className="label py-3 pr-4 font-medium text-right">
                    {s.name.toUpperCase()}
                  </th>
                ))}
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
                  [
                    "Predicted net EV",
                    (s: StrategyBenchmark) => inr(s.predictedNetEv),
                  ],
                ] as [string, (s: StrategyBenchmark) => string][]
              ).map(([metric, fn]) => (
                <tr key={metric} className="border-b border-separator/40">
                  <td className="py-2.5 pr-4 text-xs text-ink-2">{metric}</td>
                  {STRATEGIES.map((s) => (
                    <td key={s.name} className="py-2.5 pr-4 mono text-xs text-ink text-right">
                      {fn(s)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-[0.6875rem] text-ink-3 mt-4 max-w-2xl">
          Predicted net EV is a MODEL ESTIMATE. Recovered INR is the VERIFIED
          outcome against frozen test labels. The two are deliberately reported
          apart — they must never be conflated.
        </p>
      </Section>

      {/* Bootstrap intervals */}
      <Section title="BOOTSTRAP UNCERTAINTY — REALIZED RECOVERED INR">
        <div className="space-y-3 max-w-3xl">
          {STRATEGIES.map((s) => (
            <IntervalBar
              key={s.name}
              label={s.name.toUpperCase()}
              point={s.recoveredInr}
              ci={s.bootstrapCi95}
              domain={ciDomain}
            />
          ))}
        </div>
        <p className="text-[0.6875rem] text-ink-3 mt-4">
          95% percentile intervals · {BENCHMARK_META.bootstrapIterations}{" "}
          case-level bootstrap resamples · seed {BENCHMARK_META.bootstrapSeed}.
        </p>

        <div className="mt-10 space-y-3 max-w-3xl">
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
            Both intervals cross the zero line: no statistically significant
            difference in realized recovery at n = 300.
          </p>
        </div>
      </Section>

      {/* Proved / not proved */}
      <div className="grid sm:grid-cols-2 gap-10 max-w-3xl">
        <Section title="WHAT V1 PROVED">
          <ul className="space-y-2">
            {V1_PROVED.map((item) => (
              <li key={item} className="flex items-baseline gap-3 text-xs text-ink-2">
                <span className="text-ink-3">✓</span>
                {item}
              </li>
            ))}
          </ul>
        </Section>
        <Section title="WHAT V1 DID NOT PROVE">
          <ul className="space-y-2">
            {V1_NOT_PROVED.map((item) => (
              <li key={item} className="flex items-baseline gap-3 text-xs text-ink-2">
                <span className="text-ink-3">×</span>
                {item}
              </li>
            ))}
          </ul>
          <p className="text-[0.6875rem] text-ink-3 mt-5">
            Synthetic benchmark — not production performance.
          </p>
        </Section>
      </div>

      <p className="text-[0.6875rem] text-ink-3 border-t border-separator pt-5 max-w-2xl">
        Calibration estimates at n = 300 are descriptive and limited by sample
        size. This page renders the frozen evaluation artifacts verbatim; the
        benchmark is architecturally separate from the operational surfaces of
        this product.
      </p>
    </div>
  );
}
