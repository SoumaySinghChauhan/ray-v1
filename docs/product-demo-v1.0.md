# RAY V1.0 — Product & Demo Documentation

**Frontend**: Next.js App Router (`apps/web/`)
**Status**: Production build passing · lint clean · backend untouched
**Icons**: `lucide-react` — one consistent thin-line icon system throughout
**Brand assets**: `Ray_Images/Logo.png` (wordmark) and `Ray_Images/Favicon.png`
(mark) are the source files; processed copies live in `apps/web/app/icon.png`,
`apps/web/app/apple-icon.png` (Next.js auto-favicon convention) and
`apps/web/public/brand/`.

---

## 1. Product Workflow

The interface tells one story, end to end:

```
FAILED PAYMENT → DIAGNOSIS → PREDICTION → EXPECTED VALUE
→ OPTIMIZATION → POLICY → EXECUTION → WEBHOOK → RECOVERY
```

The signature interaction is the **Decision Trace**: open any opportunity and
see why RAY acted (or refused), what the model predicted, what the optimizer
chose, what policy authorized, what executed, what the webhook verified, and
what actually happened.

Architectural message repeated across the product:
**OPTIMIZER CHOOSES. POLICY AUTHORIZES.**

---

## 2. Routes

| Route | Purpose |
|---|---|
| `/` | Command center — horizontal icon Decision Rail, KPI strip with sparklines, decision activity / recent executions / policy blocks, recovery composition bar |
| `/opportunities` | Premium data table — KPI strip, filters, progress-bar probability column, sort |
| `/opportunities/[id]` | Split decision terminal — observable facts left, RAY decision right, full icon trace below |
| `/decisions` | Decision log — KPI strip, filter tabs, click a row to open the slide-over trace panel |
| `/decisions/[id]` | Decision Trace focus view + policy evaluation + provenance |
| `/execution` | Execution ledger — KPI strip with sparklines, execution flow state machine, execution-outcomes donut, Test Mode guardrails |
| `/execution/[id]` | Execution + recovery state machines with identifiers |
| `/audit` | Forensic three-column audit — record list, icon trace detail, provenance/links/checksums/notes |
| `/evaluation` | Frozen V1 benchmark presentation (display-only) |
| `/demo` | Guided 30–60s interactive decision story — scenario picker, "what RAY will decide", icon Decision Rail |

### Signature components

- **`DecisionPanel`** (`components/DecisionPanel.tsx`) — the slide-over used
  from `/decisions`: TRACE / POLICY (7) / PROVENANCE tabs over the same icon
  trace used everywhere else.
- **`StageNode` / `StageIcon.tsx`** — the one icon-node system shared by the
  Overview hero rail, the mini Decision Rail, `DecisionTrace`, the Demo rail,
  and the Audit trace. Nine stage icons (failed → diagnosis → prediction →
  value → optimizer → policy → execution → webhook → outcome); the failed-payment
  icon is always rendered in the blocked-red tone as an alert signal
  independent of the eventual outcome — the headline text next to it stays
  neutral.
- **`charts.tsx`** — hand-rolled SVG primitives (`Sparkline`, `ProgressBar`,
  `Donut`, `ComparisonBars`). No charting library; the data is small, real,
  and mostly frozen, so a dependency wasn't warranted.

---

## 3. Design System

### Color — ~95% monochrome, ~5% semantic

| Token | Value | Role |
|---|---|---|
| `--canvas` | `#050505` | Level 0 — canvas |
| `--surface-1` | `#0B0B0B` | Level 1 — structural surface |
| `--surface-2` | `#111111` | Level 2 — elevated surface |
| `--surface-3` | `#161616` | Level 3 — focused interaction |
| `--separator` | `#242424` | Structural separators |
| `--ink` | `#F5F5F5` | Primary text |
| `--ink-2` | `#929292` | Secondary text |
| `--ink-3` | `#5C5C5C` | Muted text |
| `--recovered` | `#35C759` | Verified recovery only |
| `--pending` | `#F5B942` | Awaiting states only |
| `--blocked` | `#FF453A` | Blocks and failures only |
| `--test-mode` | `#5A83C3` | Environment/safety indicator only — the sidebar's `ENVIRONMENT` value, nowhere else |

The `--test-mode` steel blue is a deliberate, singular exception to the
monochrome-plus-operational-semantics rule: it exists solely to make the
environment/safety indicator legible and distinct from ordinary muted text —
it never appears on financial data, charts, or decorative elements.

Rules enforced in components:

- No persistent brand accent. No gradients, glow, or colored charts.
- **Predicted values** render in silver/graphite, labeled `MODEL ESTIMATE`.
- **Realized values** render in off-white/emerald, labeled `VERIFIED RECOVERY`.
- In a blocked policy evaluation, only the **first failing rule** is colored;
  passing rules stay neutral, unreached rules are muted.
- One-shot `anim-confirm` glow exists solely for the semantic transition to
  RECOVERED — subtle, localized, ~900ms, never persistent.

### Typography

- **Geist Sans** — UI and editorial; **Geist Mono** — IDs, timestamps,
  references, rule names.
- Tiny uppercase labels (`.label`, 10px, 0.14em tracking) over large tabular
  financial numerals (`.fin`, `font-variant-numeric: tabular-nums`).
- Indian-grouped INR formatting: `₹6,54,210` (`lib/format.ts`).

### Material hierarchy

Hierarchy comes from typography, spacing, alignment, surface depth
(4 levels), separators, semantic color, and motion — not borders/shadows.
Cards are avoided; sections are separated by 1px structural rules.

---

## 4. Motion System

| Class | Duration | Use |
|---|---|---|
| `.t-fast` | 150ms | hovers, buttons, rows |
| `.t-med` | 240ms | expand/collapse |
| `.t-slow` | 400ms | stage activation |
| `.anim-fade-up` | 280ms | content entrance |
| `.anim-settle` | 450ms | verdicts settling |
| `.anim-line` | 500ms | trace rail growth |
| `.anim-confirm` | 900ms one-shot | RECOVERED transition only |

Easing: `cubic-bezier(0.22, 1, 0.36, 1)` (refined ease-out). No bounce,
particles, or parallax.

**Number resolution**: `CountUp` (rAF-driven cubic ease-out) animates
probability, EV, and recovered amounts from 0 to final value.

**Reduced motion**: `prefers-reduced-motion` collapses all animation to ≤1ms
via a global media query; `CountUp` renders the final value immediately
(via `useSyncExternalStore` media-query subscription).

### Demo animation choreography (`/demo`)

1. `RUN RAY` → stages activate sequentially (500–900ms apart)
2. Prediction resolves 0% → final via CountUp
3. Economic values resolve via CountUp
4. Seven policy rules stream at 160ms intervals; a blocked scenario stops at
   the first failing rule
5. Execution state machine: PENDING → SUBMITTED → SUCCEEDED, then IDs reveal
6. `SIMULATE PAYMENT` (explicit user action) → webhook rail:
   RECEIVED → VERIFYING → VERIFIED → PROCESSED
7. RECOVERED settles with the one-shot confirmation

---

## 5. Demo Scenarios (deterministic)

| # | Scenario | Path |
|---|---|---|
| 01 | Soft decline | ALLOW → executed → webhook verified → **RECOVERED ₹4,200** |
| 02 | Hard decline | negative incremental EV → optimizer selects **do-nothing** |
| 03 | ₹31,000 over autonomous limit | `AUTONOMOUS_AMOUNT_LIMIT_CHECK` → **BLOCK** |
| 04 | Customer already contacted today | `MAX_CONTACTS_CHECK` → **BLOCK** |
| 05 | Duplicate execution | `DUPLICATE_ACTION_CHECK` → **BLOCK** |

Every blocked scenario explains *why* inline. Expected demo duration:
30–60 seconds per scenario.

---

## 6. Data Architecture & Safety

- **Operational surfaces** (`/`, `/opportunities`, `/decisions`, `/execution`,
  `/audit`, `/demo`) use `lib/demo.ts`: deterministic **synthetic** records.
  No frozen TEST benchmark rows, no test labels, no hidden simulator
  variables anywhere in the frontend.
- **Benchmark surface** (`/evaluation`) renders `lib/benchmark.ts` — values
  transcribed verbatim from `reports/final-test-evaluation-v1.0.json`.
  Nothing is recalculated client-side. Operations and benchmark are
  architecturally and visually separate.
- `lib/economics.ts` mirrors the frozen `config/v1_config.py` constants for
  display narration only; the backend remains authoritative and no optimizer,
  policy, ML, or Razorpay logic is duplicated in the frontend.
- Policy rule names match `policy/types.py::RuleId` exactly.
- The Execution page's "Execution Outcomes" donut shows RECOVERED / PENDING /
  NOT RECOVERED — not a multi-channel breakdown. The backend's
  `action_registry.py` registers exactly one action type
  (`CREATE_PAYMENT_LINK`); a "Payment Link / UPI Intent / Card Retry" channel
  mix would misrepresent a capability the system doesn't have, so the donut
  was scoped to what's real instead.

### Test Mode safety

- `RAZORPAY TEST MODE` tag is displayed on every execution surface.
- No live-mode toggle exists anywhere.
- Nothing executes on page load; the demo requires explicit `RUN RAY` and
  `SIMULATE PAYMENT` confirmation clicks. No Razorpay calls are made by the
  frontend at all.

### Secrets

- Zero environment variables in the frontend; zero `NEXT_PUBLIC_*` usage.
- Audit: `grep -rn "NEXT_PUBLIC\|RAZORPAY\|secret" app components lib` → clean.

---

## 7. Backend Integration

Current FastAPI surface (`services/api/main.py`): `/health`, `/config`,
`/webhooks/razorpay` (live), `/recovery/evaluate` and `/audit/opportunity/*`
(501 scaffolds). The V1 frontend ships fully static against deterministic
demo data, so **no new backend endpoints were added** and no experiment
semantics were touched. When the scaffolded endpoints land, the data layer
(`lib/demo.ts`) is the single seam to swap for live fetches.

---

## 8. Component Architecture

```
apps/web/
├── app/
│   ├── layout.tsx          # root layout + fonts + Shell
│   ├── globals.css         # design tokens + motion system
│   ├── icon.png            # app favicon (from Ray_Images/Favicon.png)
│   ├── apple-icon.png       # apple touch icon
│   ├── page.tsx            # Overview
│   ├── opportunities/      # table + [id] detail
│   ├── decisions/          # log + [id] trace view
│   ├── execution/          # ledger + [id] state machines
│   ├── audit/, evaluation/, demo/
├── components/
│   ├── Shell.tsx           # grouped nav w/ icons, breadcrumb top bar, IST clock
│   ├── DecisionTrace.tsx   # signature icon trace rail + PolicyRules
│   ├── DecisionPanel.tsx   # slide-over trace panel (Decisions list)
│   ├── StageIcon.tsx       # StageNode — the one icon-node system, reused everywhere
│   ├── charts.tsx          # Sparkline, ProgressBar, Donut, ComparisonBars (hand-rolled SVG)
│   ├── CountUp.tsx         # rAF number resolution, reduced-motion aware
│   ├── LiveFeed.tsx        # operational activity feed
│   └── ui.tsx              # Label, Section, Figure, KV, badges, TestModeTag
├── public/brand/
│   ├── ray-mark.png        # sidebar icon (from Favicon.png)
│   └── ray-logo-lockup.png # full wordmark lockup (from Logo.png)
├── public/evaluation/
│   └── final-test-calibration.png  # frozen calibration chart, copied verbatim
└── lib/
    ├── demo.ts             # deterministic synthetic operational data
    ├── benchmark.ts        # frozen V1 benchmark (verbatim transcription)
    ├── economics.ts        # display mirror of frozen economic config
    └── format.ts           # INR (Indian grouping), percent, number
```

Brand: the supplied RAY mark (`Ray_Images/Favicon.png`) is used directly as
the sidebar icon and the app favicon/apple-touch-icon — not redrawn. The full
glow wordmark lockup (`Ray_Images/Logo.png`) is kept in `public/brand/` for
future large-format brand placements; the sidebar itself pairs the small mark
with the app's own tracked `RAY` / `REVENUE RECOVERY ORCHESTRATOR` type
treatment, matching the reference sidebar exactly.

---

## 9. Accessibility

- Semantic HTML (`table`, `ol` rails, `nav` with `aria-label`)
- `aria-current` on active nav, `aria-expanded` on expandables,
  `aria-pressed` on filter toggles
- Visible `:focus-visible` outlines; keyboard-reachable rows and controls
- `prefers-reduced-motion` respected globally
- Contrast: primary text #F5F5F5 on #050505

---

## 10. Setup

```bash
cd apps/web
npm install
npm run dev        # http://localhost:3000
npm run build      # production build (all routes prerender)
npm run lint       # eslint — clean
```

Backend tests remain green: `pytest tests/ -v` → 265 passed.
