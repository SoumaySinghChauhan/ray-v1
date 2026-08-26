/**
 * Minimal hand-rolled SVG chart primitives.
 * No charting library — data is small, real, and frozen; a dependency isn't warranted.
 */

/** Tiny inline trend line for KPI strips. Texture, not analysis. */
export function Sparkline({
  points,
  tone = "muted",
  width = 84,
  height = 24,
}: {
  points: number[];
  tone?: "muted" | "recovered" | "blocked";
  width?: number;
  height?: number;
}) {
  if (points.length < 2) return null;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const span = max - min || 1;
  const step = width / (points.length - 1);
  const coords = points.map((p, i) => {
    const x = i * step;
    const y = height - ((p - min) / span) * (height - 4) - 2;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const stroke = tone === "recovered" ? "var(--recovered)" : tone === "blocked" ? "var(--blocked)" : "var(--ink-3)";
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden="true">
      <polyline points={coords.join(" ")} fill="none" stroke={stroke} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/** Horizontal capacity/progress bar for table cells and KPI cards. */
export function ProgressBar({
  value,
  max = 1,
  width = 64,
  tone = "ink",
}: {
  value: number;
  max?: number;
  width?: number;
  tone?: "ink" | "recovered";
}) {
  const pct = Math.max(0, Math.min(1, value / max));
  const fill = tone === "recovered" ? "var(--recovered)" : "var(--ink-2)";
  return (
    <span className="inline-block align-middle" style={{ width }}>
      <span className="block h-[3px] rounded-full bg-separator overflow-hidden">
        <span className="block h-full rounded-full" style={{ width: `${pct * 100}%`, background: fill }} />
      </span>
    </span>
  );
}

/** Restrained donut — used once, for execution channel mix. Slices are NOT operational-state colors. */
export function Donut({
  slices,
  size = 108,
  thickness = 16,
}: {
  slices: { label: string; value: number; color: string }[];
  size?: number;
  thickness?: number;
}) {
  const total = slices.reduce((s, x) => s + x.value, 0) || 1;
  const r = (size - thickness) / 2;
  const c = 2 * Math.PI * r;

  const dashes = slices.map((s) => (s.value / total) * c);
  const offsets = dashes.reduce<number[]>((acc, dash, i) => {
    acc.push(i === 0 ? 0 : acc[i - 1] + dashes[i - 1]);
    return acc;
  }, []);

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
      <g transform={`rotate(-90 ${size / 2} ${size / 2})`}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--separator)" strokeWidth={thickness} />
        {slices.map((s, i) => (
          <circle
            key={i}
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke={s.color}
            strokeWidth={thickness}
            strokeDasharray={`${dashes[i]} ${c - dashes[i]}`}
            strokeDashoffset={-offsets[i]}
            strokeLinecap="butt"
          />
        ))}
      </g>
    </svg>
  );
}

/** Grouped predicted-vs-realized bars, driven by real frozen numbers only. */
export function ComparisonBars({
  rows,
  maxValue,
}: {
  rows: { label: string; predicted: number; realized: number }[];
  maxValue: number;
}) {
  const H = 120;
  return (
    <div className="flex items-end justify-around gap-8" style={{ height: H + 24 }}>
      {rows.map((r) => {
        const predH = (r.predicted / maxValue) * H;
        const realH = (r.realized / maxValue) * H;
        return (
          <div key={r.label} className="flex flex-col items-center gap-2">
            <div className="relative flex items-end" style={{ height: H, width: 34 }}>
              <div
                className="absolute left-0 bottom-0 w-full border border-ink-3"
                style={{ height: Math.max(predH, 1) }}
                aria-hidden="true"
              />
              <div
                className="absolute left-0 bottom-0 w-full bg-recovered"
                style={{ height: Math.max(realH, 1) }}
                aria-hidden="true"
              />
            </div>
            <span className="label">{r.label}</span>
          </div>
        );
      })}
    </div>
  );
}
