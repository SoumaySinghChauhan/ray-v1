# RAY — Buildathon Demo Guide

## Pre-demo checklist

- [ ] Backend running: `python -m uvicorn services.api.main:app --reload` (from repo root, with `services/api/.venv` active) — confirm `curl http://localhost:8000/health` returns `200`.
- [ ] Frontend running: `bash script.sh` (or `cd apps/web && npm run dev`) — confirm `http://localhost:3000` loads.
- [ ] Database available: `ray_v1.db` present at the repo root with seeded operational data. If empty, run `python scripts/seed_operational_data.py` once (idempotent).
- [ ] Razorpay Test Mode confirmed: `curl http://localhost:8000/config/verify` shows `"mode": "test"` and all three `_present` flags `true`. Never mode `"live"`.
- [ ] Existing operational record available: `curl http://localhost:8000/recovery/opportunities/c0d90f2984c07386b62a3380/status` shows a `SUCCEEDED` execution, a verified webhook, and a `RECOVERED` outcome for **Meridian Textiles**, ₹4,200. This is the record to show live — do not create a new Payment Link during the demo.
- [ ] Browser open to `http://localhost:3000` with `/` (Overview) loaded, both a dark-mode and light-mode pass rehearsed.

## Demo script (live product)

1. **Open Overview** (`/`) — the decision rail at top shows the most recent real decision end-to-end; the KPI strip shows live operational counts (opportunities, decisions, policy blocks, capacity).
2. **Open an opportunity** — click through to Meridian Textiles (or any decided opportunity) at `/opportunities/[id]`.
3. **Show the prediction** — recovery probability, labeled "model estimate," sourced from the frozen Model A.
4. **Show the economic value** — expected recovery, incremental EV vs. do-nothing, computed once by the backend and only rendered by the frontend.
5. **Show the optimizer** — the recommended action (`create_payment_link`) and why (positive incremental EV).
6. **Show the seven policy rules** — all passing for Meridian Textiles (ALLOW). Point out that policy re-evaluates fresh on every request; a stale client-held decision can never authorize execution.
7. **Show the Decision Trace** — the full rail: failed payment → prediction → economic value → optimizer → policy → execution → webhook → recovered.
8. **Show execution** — `/execution/[id]`: execution ID, Payment Link ID, reference ID, state `SUCCEEDED`, Razorpay Test Mode tag.
9. **Show the webhook** — signature verified, event `payment_link.paid`, processing status `PROCESSED`.
10. **Show recovery** — outcome `RECOVERED`, ₹4,200, attributed and persisted.
11. **Open Evaluation** (`/evaluation`) — the frozen benchmark artifact.
12. **Explain the V1 finding** — "predictive improvements did not produce statistically significant economic gains at n=300 — every bootstrap CI for realized-recovery deltas contains zero." Model A is the recommended default: the simplest model that survived the full evaluation, not the model with marginally better offline metrics.

## Blocked scenarios (via `/demo`)

All five run without any backend or Razorpay dependency — safe to demo even if the network is down.

1. **Soft decline** → ALLOW → recovered (the full happy path, animated end to end)
2. **Hard decline** → optimizer selects do-nothing (negative incremental EV — RAY spends nothing; this is an economic skip, not a policy block)
3. **Amount over ₹25,000** → policy BLOCK on `AUTONOMOUS_AMOUNT_LIMIT_CHECK`
4. **Contact limit reached** → policy BLOCK on `MAX_CONTACTS_CHECK`
5. **Duplicate execution** → policy BLOCK on `DUPLICATE_ACTION_CHECK` (idempotency)

For each blocked/skipped scenario, the UI states which rule failed and why — never a bare "blocked" with no reason.

## Fallback plan

If live Razorpay Test Mode checkout cannot be shown (no network, credentials unavailable, time pressure):

- Fall back to the **existing operational record** (Meridian Textiles) — its execution, webhook, and outcome are already persisted and load instantly with no external calls.
- If even that's not reachable (backend down), fall back fully to `/demo` — deterministic, reproducible, no dependencies.
- State plainly: *"The payment execution layer is running in Razorpay Test Mode; the demo environment uses deterministic state transitions for reproducibility."*
- Do not improvise claims about production behavior, live payments, or uplift the evaluation didn't establish.

## Do not, during the demo

- Do not click **CREATE PAYMENT LINK** on an already-executed opportunity (policy will correctly BLOCK it on `DUPLICATE_ACTION_CHECK` — a good thing to show once, deliberately, but not by accident).
- Do not run `pytest tests/` (full suite) live during the demo unless intentionally showing test isolation — it's safe (isolated DB), but it's not demo content.
- Do not toggle any environment variable live — there is no live-mode switch to show, by design.
