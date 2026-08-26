"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

const NAV = [
  { href: "/", label: "Overview" },
  { href: "/opportunities", label: "Opportunities" },
  { href: "/decisions", label: "Decisions" },
  { href: "/execution", label: "Execution" },
  { href: "/audit", label: "Audit" },
  { href: "/evaluation", label: "Evaluation" },
  { href: "/demo", label: "Demo" },
];

function RayMark() {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
      {/* Geometric mark: three converging recovery rays */}
      <path d="M3 17L10 3" stroke="#f5f5f5" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M10 17L13 8" stroke="#929292" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M16 17L17 12" stroke="#5c5c5c" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

export function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="min-h-screen flex flex-col lg:flex-row">
      {/* Left rail */}
      <aside className="lg:w-52 shrink-0 lg:h-screen lg:sticky lg:top-0 flex lg:flex-col border-b lg:border-b-0 lg:border-r border-separator bg-surface-1">
        <div className="px-5 py-5 flex items-center gap-2.5">
          <RayMark />
          <span className="text-sm font-semibold tracking-[0.22em]">RAY</span>
        </div>

        <div className="relative min-w-0 lg:contents">
          <nav className="flex lg:flex-col gap-0.5 px-3 pb-3 lg:pb-0 overflow-x-auto lg:overflow-visible" aria-label="Primary">
            {NAV.map((item) => {
              const active =
                item.href === "/"
                  ? pathname === "/"
                  : pathname.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={`t-fast whitespace-nowrap px-2.5 py-1.5 text-xs rounded-sm ${
                    active
                      ? "text-ink bg-surface-3"
                      : "text-ink-3 hover:text-ink-2 hover:bg-surface-2"
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
          {/* Scroll affordance — hints the nav overflows on narrow viewports */}
          <div
            className="lg:hidden pointer-events-none absolute right-0 top-0 bottom-3 w-8"
            style={{ background: "linear-gradient(to right, transparent, var(--surface-1))" }}
            aria-hidden="true"
          />
        </div>

        {/* System status footer */}
        <div className="hidden lg:block mt-auto px-5 py-5 space-y-3">
          <div>
            <div className="label mb-1">SYSTEM</div>
            <div className="flex items-center gap-1.5 text-xs text-ink-2">
              <span className="w-1 h-1 rounded-full bg-recovered anim-live" />
              6 / 6 OPERATIONAL
            </div>
          </div>
          <div>
            <div className="label mb-1">ENVIRONMENT</div>
            <div className="text-xs text-ink-2">TEST MODE</div>
          </div>
          <div>
            <div className="label mb-1">VERSIONS</div>
            <div className="mono text-[0.625rem] text-ink-3 leading-relaxed">
              model a v1.0.0
              <br />
              policy v1.0.0
              <br />
              optimizer v1.0.0
            </div>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 min-w-0">
        <div className="max-w-6xl mx-auto px-5 lg:px-10 py-8 lg:py-12">{children}</div>
      </main>
    </div>
  );
}
