/** Indian-grouped INR formatting: 654210 -> ₹6,54,210 */
export function inr(value: number, opts?: { sign?: boolean; decimals?: number }): string {
  const sign = opts?.sign && value > 0 ? "+" : value < 0 ? "−" : "";
  const abs = Math.abs(value);
  const formatted = abs.toLocaleString("en-IN", {
    maximumFractionDigits: opts?.decimals ?? 0,
    minimumFractionDigits: opts?.decimals ?? 0,
  });
  return `${sign}₹${formatted}`;
}

export function pct(value: number, decimals = 1): string {
  return `${(value * 100).toFixed(decimals)}%`;
}

export function num(value: number, decimals = 0): string {
  return value.toLocaleString("en-IN", {
    maximumFractionDigits: decimals,
    minimumFractionDigits: decimals,
  });
}
