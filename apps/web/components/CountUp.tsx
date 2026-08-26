"use client";

import { useEffect, useRef, useState, useSyncExternalStore } from "react";

function subscribeReducedMotion(callback: () => void) {
  const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
  mq.addEventListener("change", callback);
  return () => mq.removeEventListener("change", callback);
}

function usePrefersReducedMotion(): boolean {
  return useSyncExternalStore(
    subscribeReducedMotion,
    () => window.matchMedia("(prefers-reduced-motion: reduce)").matches,
    () => false
  );
}

/**
 * Controlled number resolution — a value settles into place rather than
 * appearing instantly. Respects prefers-reduced-motion (renders final value).
 */
export function CountUp({
  value,
  format,
  duration = 700,
  start = true,
}: {
  value: number;
  format: (n: number) => string;
  duration?: number;
  start?: boolean;
}) {
  const reduced = usePrefersReducedMotion();
  const [display, setDisplay] = useState(0);
  const raf = useRef<number | null>(null);

  useEffect(() => {
    // All state updates flow through rAF callbacks (external system → React).
    if (!start) {
      raf.current = requestAnimationFrame(() => setDisplay(0));
      return () => {
        if (raf.current !== null) cancelAnimationFrame(raf.current);
      };
    }
    if (reduced) {
      raf.current = requestAnimationFrame(() => setDisplay(value));
      return () => {
        if (raf.current !== null) cancelAnimationFrame(raf.current);
      };
    }
    const t0 = performance.now();
    const tick = (t: number) => {
      const p = Math.min((t - t0) / duration, 1);
      // refined ease-out (cubic)
      const eased = 1 - Math.pow(1 - p, 3);
      setDisplay(value * eased);
      if (p < 1) raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => {
      if (raf.current !== null) cancelAnimationFrame(raf.current);
    };
  }, [value, duration, start, reduced]);

  return <span className="fin">{format(display)}</span>;
}
