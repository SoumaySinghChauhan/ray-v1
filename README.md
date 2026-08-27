# RAY — Revenue Recovery Orchestrator

**RAY** is an AI-native revenue recovery decision system built for the Razorpay AI Buildathon. It turns a failed payment into a bounded decision problem: predict the odds of recovery, weigh the economics, let a deterministic policy authorize (or refuse) the action, execute safely in Razorpay Test Mode, and verify the outcome via signed webhooks — with every step attributable.

## 1. What RAY does

For every failed payment, RAY decides between exactly two actions — `create_payment_link` or `do_nothing` — using:

```
Failed payment
  → ML prediction (recovery probability)
  → Economic value (frozen formula)
  → Optimizer (best action by incremental EV)
  → Policy engine (authorization gate — 7 rules)
  → Execution (Razorpay Test Mode Payment Link)
  → Webhook (signature-verified outcome)
  → Recovery (persisted, attributable)
```

No component may bypass the one before it. The optimizer never executes anything — it only recommends. The policy engine is the sole authority to authorize execution.

## 2. Core architecture

```
apps/web/          Next.js frontend (operational UI, deterministic demo, frozen evaluation)
services/api/       FastAPI backend (recovery pipeline, webhooks, persistence)
ml/                 Frozen ML models + feature engineering
optimizer/           Economic action selection (frozen formula)
policy/              Deterministic authorization engine (7 rules)
services/api/execution/   Razorpay Test Mode execution + persistent state
simulator/          Synthetic world generator (training/eval data only)
evaluation/          Frozen benchmark protocol and baselines
config/              Versioned configuration (economics, limits, model/policy versions)
tests/               Unit + integration tests (isolated from the operational database)
docs/                Architecture, engineering contract, demo materials
```

Backend and frontend are connected through one centralized API client (`apps/web/lib/api.ts`) — the frontend never recomputes ML, economics, optimizer, or policy decisions. It only requests, displays, and polls.

## 3. Decision pipeline

`services/api/recovery_service.py` orchestrates the real pipeline for one operational opportunity — it doesn't reimplement any stage, it calls the real modules:

1. **Features** are built live from actual database history (payment counts, historical recovery rate, amount ratios) — never from the frozen TEST parquet.
2. **Prediction** — the frozen, calibrated Model A logistic regression.
3. **Economics** — `gross_ev = p × amount`; `net_ev = gross_ev − costs`; `incremental_ev = net_ev − do_nothing_ev`. Config-driven, frozen formula.
4. **Optimizer** selects `create_payment_link` when `incremental_ev > 0`, otherwise `do_nothing`.
5. **Policy** re-evaluates fresh on every execution attempt — it never trusts a client-held decision.
6. **Execution** goes through `PersistentExecutionService`, idempotent by a deterministic reference ID.
7. **Webhook** verification is HMAC-SHA256, constant-time compare.
8. **Outcome** is persisted and immediately queryable by the frontend.

## 4. ML models

Two calibrated models were trained and frozen before the single evaluation run:

- **Model A** (`ml/models/v1.0.0/model_a_calibrated.pkl`) — observable features only, logistic regression. **Recommended V1 default.**
- **Model B** — adds LLM-diagnosis-derived features. Experimental; marginal metric gains that did not carry to economic outcomes.

Both are frozen artifacts loaded read-only at inference time; nothing about them is retrained or adjusted by the operational system.

## 5. Optimizer

`optimizer/core.py` — pure economic action selection under a frozen formula and a capacity constraint (`max_actions_per_day`). It never touches Razorpay and never authorizes execution; it only ranks and recommends.

## 6. Policy engine

`policy/engine.py::DeterministicPolicyEngine` — the single authorization gate, evaluated in this fixed order, short-circuiting on the first failure:

1. `VALID_ACTION_TYPE`
2. `OPPORTUNITY_ACTIONABLE`
3. `DO_NOT_CONTACT_CHECK`
4. `DUPLICATE_ACTION_CHECK`
5. `AUTONOMOUS_AMOUNT_LIMIT_CHECK`
6. `MAX_CONTACTS_CHECK`
7. `DAILY_CAPACITY_CHECK`

Because the engine short-circuits, a BLOCK response only contains rules up to and including the failure — the frontend renders the remaining rules as `NOT REACHED` rather than hiding them (`apps/web/lib/policyRules.ts`).

## 7. Razorpay Test Mode

All execution runs through the real `razorpay` Python SDK against **Test Mode only**. There is no live-mode toggle anywhere in this system. `execute_opportunity()` re-runs the full decision pipeline server-side before creating anything — a stale or spoofed client-side decision can never trigger execution. Idempotency keys are deterministic (SHA-256 of merchant/opportunity/action/policy-version), so a duplicate execution attempt is rejected by Razorpay itself if the local record was ever lost.

## 8. Webhook verification

`payment_link.paid` (and related) events are verified with HMAC-SHA256 over the raw request body using `hmac.compare_digest` (constant-time). Verified events are persisted, matched to their execution by payment-link ID or reference ID, and produce exactly one recovery outcome — duplicate webhook deliveries are detected and ignored.

## 9. Persistence

SQLite by default (`ray_v1.db`, overridable via `DATABASE_URL`). Execution attempts, webhook events, and recovery outcomes are all durable — `PersistentExecutionService` and `PersistentWebhookHandler` survive process restarts (see `tests/integration/test_restart_safety.py`). Tests never touch the operational database: `tests/conftest.py` points every test run at an isolated, ephemeral SQLite file, and `services/api/database/session.py` fails fast if a test process ever resolves to the real `ray_v1.db` (see `docs/testing.md`).

## 10. Frontend

Next.js + TypeScript + Tailwind, dark-first monochrome design with semantic color reserved for state (recovered / pending / blocked). Three distinct data boundaries, enforced and tested:

- **Operational** (`/`, `/opportunities`, `/decisions`, `/execution`, `/audit`, and their `[id]` detail routes) — 100% live backend data.
- **Demo** (`/demo`) — deterministic, synthetic, zero backend calls. Reliable without any credentials.
- **Evaluation** (`/evaluation`) — renders the frozen benchmark artifact verbatim. No recomputation, no live calls.

## 11. Demo instructions

```bash
bash script.sh          # starts the frontend at http://localhost:3000
```

Open `/demo`, pick a scenario, click **RUN RAY**. All five scenarios are deterministic and require no backend or Razorpay credentials:

1. Soft decline → ALLOW → recovered
2. Hard decline → optimizer skips (negative incremental EV, not a policy block)
3. Amount over ₹25,000 → policy BLOCK
4. Contact limit reached → policy BLOCK
5. Duplicate execution → policy BLOCK

See `docs/buildathon-demo-guide.md` for the full walkthrough script.

## 12. Evaluation methodology

One frozen run, one time, on a 300-case synthetic TEST split, evaluated 2026-08-26 (`apps/web/lib/benchmark.ts`, transcribed verbatim from `reports/final-test-evaluation-v1.0.json`):

| | Baseline | Model A (recommended) | Model B (experimental) |
|---|---|---|---|
| ROC-AUC | 0.6297 | 0.6588 | 0.6696 |
| Recovered INR | ₹1,71,943 | ₹1,71,616 | ₹1,70,139 |
| Δ vs baseline (95% CI) | — | −₹327 [−13,607, 12,210] | −₹1,803 [−14,990, 11,743] |

**Both confidence intervals cross zero** — predictive improvements did not produce statistically significant economic gains in V1 at n=300. Model A is the recommended default: best calibration-to-complexity ratio, no LLM dependency. The test set was accessed exactly once; model artifacts were frozen before evaluation; nothing on `/evaluation` is recomputed by the frontend.

## 13. Synthetic-data disclaimer

**This is a synthetic demonstration system.** All benchmark data is generated by `simulator/`. Recovery rates, customer behavior, and the economic results above are not claims about real Razorpay merchant behavior — they demonstrate that the full decision-and-execution pipeline works end-to-end under a controlled, honest evaluation protocol, not that the model would outperform in production.

## 14. Local setup

### Prerequisites
- Python 3.14+
- Node.js 22+
- A Razorpay **Test Mode** key pair + webhook secret (optional — the demo works without any credentials)

### Backend

```bash
cd services/api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Optional: real Razorpay Test Mode execution
cp ../../.env.example ../../.env   # if present — set RAZORPAY_MODE=test and your Test Mode keys

cd ../..
python scripts/seed_operational_data.py   # idempotent — seeds safe synthetic operational data
python -m uvicorn services.api.main:app --reload
```

### Frontend

```bash
bash script.sh
# or: cd apps/web && npm install && npm run dev
```

### Tests

```bash
pytest tests/ -v      # isolated from the operational database — see docs/testing.md
```

## Documentation

- [Architecture](docs/architecture.md)
- [Engineering Contract](docs/engineering-contract.md)
- [Evaluation Protocol](docs/evaluation-protocol.md)
- [Testing / Database Isolation](docs/testing.md)
- [Buildathon Demo Guide](docs/buildathon-demo-guide.md)
- [Buildathon Pitch Outline](docs/buildathon-pitch-outline.md)

## Built for

Razorpay AI Buildathon 2026
