"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import {
  Home,
  Target,
  GitBranch,
  Workflow,
  FileText,
  BarChart3,
  PlaySquare,
  ChevronDown,
} from "lucide-react";

interface NavItem {
  href: string;
  label: string;
  icon: typeof Home;
}

const OPERATIONS: NavItem[] = [
  { href: "/", label: "Overview", icon: Home },
  { href: "/opportunities", label: "Opportunities", icon: Target },
  { href: "/decisions", label: "Decisions", icon: GitBranch },
  { href: "/execution", label: "Execution", icon: Workflow },
];

const SYSTEM: NavItem[] = [
  { href: "/audit", label: "Audit", icon: FileText },
  { href: "/evaluation", label: "Evaluation", icon: BarChart3 },
];

const DEMO: NavItem[] = [{ href: "/demo", label: "Demo", icon: PlaySquare }];

const BREADCRUMB: Record<string, [string | null, string]> = {
  "/": [null, "OVERVIEW"],
  "/opportunities": ["OPERATIONS", "OPPORTUNITIES"],
  "/decisions": ["OPERATIONS", "DECISIONS"],
  "/execution": ["OPERATIONS", "EXECUTION"],
  "/audit": ["SYSTEM", "AUDIT"],
  "/evaluation": ["SYSTEM", "EVALUATION"],
  "/demo": ["DEMO", "LIVE DECISION"],
};

function fmtIST() {
  return new Intl.DateTimeFormat("en-IN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
    timeZone: "Asia/Kolkata",
  }).format(new Date());
}

function useISTClock() {
  const [time, setTime] = useState<string | null>(null);
  useEffect(() => {
    // Route the initial (client-only, SSR-unsafe) read through a timer callback
    // rather than calling setState synchronously in the effect body.
    const tick = () => setTime(fmtIST());
    const kickoff = setTimeout(tick, 0);
    const id = setInterval(tick, 1000);
    return () => {
      clearTimeout(kickoff);
      clearInterval(id);
    };
  }, []);
  return time;
}

function NavGroup({ label, items, pathname }: { label: string | null; items: NavItem[]; pathname: string }) {
  return (
    <div className="mb-5">
      {label && <div className="label px-2.5 mb-1.5">{label}</div>}
      <div className="flex flex-col gap-0.5">
        {items.map((item) => {
          const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={`t-fast relative flex items-center gap-2.5 px-2.5 py-1.5 text-[0.8125rem] rounded-sm ${
                active ? "text-ink bg-surface-3" : "text-ink-3 hover:text-ink-2 hover:bg-surface-2"
              }`}
            >
              {active && (
                <span className="absolute left-0 top-1 bottom-1 w-[2px] bg-ink rounded-full" aria-hidden="true" />
              )}
              <Icon size={15} strokeWidth={1.75} className={active ? "text-ink" : "text-ink-3"} />
              {item.label}
            </Link>
          );
        })}
      </div>
    </div>
  );
}

function TestModePill() {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="t-fast flex items-center gap-2 border border-separator px-3 py-1.5 text-[0.6875rem] tracking-[0.1em] text-ink hover:bg-surface-2 rounded-sm"
      >
        RAZORPAY TEST MODE
        <ChevronDown size={13} strokeWidth={2} className={`t-fast text-ink-3 ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="anim-fade-up absolute right-0 top-full mt-2 w-64 border border-separator bg-surface-2 p-3 text-xs text-ink-2 leading-relaxed z-20">
          All executions run in Razorpay Test Mode. No live payments are created or captured. There is no live-mode toggle in this product.
        </div>
      )}
    </div>
  );
}

function TopBar({ pathname }: { pathname: string }) {
  const crumb = BREADCRUMB[pathname] ?? BREADCRUMB[Object.keys(BREADCRUMB).find((k) => pathname.startsWith(k) && k !== "/") ?? "/"];
  const [group, page] = crumb;
  return (
    <div className="flex items-center justify-between px-5 lg:px-10 h-14 border-b border-separator shrink-0">
      <div className="label-2 tracking-[0.14em]">
        {group ? `${group} / ${page}` : page}
      </div>
      <div className="flex items-center gap-4">
        <span className="hidden sm:flex items-center gap-2 text-[0.6875rem] tracking-[0.1em] text-ink-2">
          <span className="w-1.5 h-1.5 rounded-full bg-recovered anim-live" />
          SYSTEM OPERATIONAL
        </span>
        <TestModePill />
      </div>
    </div>
  );
}

export function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const clock = useISTClock();

  return (
    <div className="min-h-screen flex flex-col lg:flex-row">
      {/* Left rail */}
      <aside className="lg:w-56 shrink-0 lg:h-screen lg:sticky lg:top-0 flex flex-col border-b lg:border-b-0 lg:border-r border-separator bg-surface-1">
        <div className="px-5 py-5 flex items-center gap-2.5 shrink-0">
          <Image src="/brand/ray-mark.png" alt="" width={30} height={30} priority className="rounded-[6px]" />
          <div>
            <div className="text-sm font-semibold tracking-[0.18em] leading-none">RAY</div>
            <div className="text-[0.5625rem] tracking-[0.12em] text-ink-3 leading-tight mt-1">
              REVENUE RECOVERY
              <br />
              ORCHESTRATOR
            </div>
          </div>
        </div>

        <div className="rule mx-5" />

        <div className="relative min-w-0 flex-1 lg:flex lg:flex-col">
          <nav
            className="flex lg:flex-col lg:flex-1 gap-0.5 px-3 py-4 overflow-x-auto lg:overflow-visible"
            aria-label="Primary"
          >
            <div className="hidden lg:block lg:contents">
              <NavGroup label={null} items={OPERATIONS} pathname={pathname} />
              <NavGroup label="SYSTEM" items={SYSTEM} pathname={pathname} />
              <NavGroup label="DEMO" items={DEMO} pathname={pathname} />
            </div>
            {/* Mobile: flat scrollable row, icons hidden for density */}
            <div className="flex lg:hidden gap-0.5">
              {[...OPERATIONS, ...SYSTEM, ...DEMO].map((item) => {
                const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    aria-current={active ? "page" : undefined}
                    className={`t-fast whitespace-nowrap px-2.5 py-1.5 text-xs rounded-sm ${
                      active ? "text-ink bg-surface-3" : "text-ink-3 hover:text-ink-2 hover:bg-surface-2"
                    }`}
                  >
                    {item.label}
                  </Link>
                );
              })}
            </div>
          </nav>
          <div
            className="lg:hidden pointer-events-none absolute right-0 top-0 bottom-0 w-8"
            style={{ background: "linear-gradient(to right, transparent, var(--surface-1))" }}
            aria-hidden="true"
          />
        </div>

        {/* System status footer */}
        <div className="hidden lg:block px-5 py-5 space-y-3.5 shrink-0">
          <div className="rule pt-3.5">
            <div className="label mb-1.5">SYSTEM</div>
            <div className="flex items-center gap-1.5 text-xs text-ink-2">
              <span className="w-1.5 h-1.5 rounded-full bg-recovered anim-live" />
              6 / 6 OPERATIONAL
            </div>
          </div>
          <div>
            <div className="label mb-1.5">ENVIRONMENT</div>
            <div className="text-xs" style={{ color: "var(--test-mode)" }}>
              RAZORPAY TEST MODE
            </div>
          </div>
          <div>
            <div className="label mb-1.5">VERSION</div>
            <div className="text-xs text-ink-2">v1.0.0</div>
          </div>
          <div className="flex items-center gap-1.5 text-[0.6875rem] mono text-ink-3">
            <span className="w-1.5 h-1.5 rounded-full bg-recovered anim-live shrink-0" />
            {clock ? `${clock} IST` : " "}
          </div>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 min-w-0 flex flex-col">
        <TopBar pathname={pathname} />
        <main className="flex-1 min-w-0">
          <div className="max-w-[1400px] mx-auto px-5 lg:px-10 py-8 lg:py-10">{children}</div>
        </main>
      </div>
    </div>
  );
}
