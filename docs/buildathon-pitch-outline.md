# RAY — Five-Minute Presentation Story

## 0:00 – 0:30 — The problem

Failed payments are lost revenue that nobody owns. A merchant's payment fails — insufficient funds, a gateway timeout, an abandoned 3DS challenge — and by default, nothing happens. No diagnosis, no retry, no accountability. Revenue leaks silently.

## 0:30 – 1:15 — The RAY idea

RAY turns recovery into a bounded decision problem, not a blast campaign. For every failed payment, RAY asks: *is this worth recovering, and if so, how?* It doesn't retry everything — it decides, economically and safely, action by action.

## 1:15 – 2:15 — How RAY thinks

Four stages, strict separation of authority:

- **Prediction** — a calibrated model estimates recovery probability from observable signals only.
- **Economics** — expected recovery, cost, and incremental value versus doing nothing at all.
- **Optimizer** — picks the action with the best incremental EV, under a daily capacity constraint.
- **Policy** — the only component allowed to authorize execution. Seven deterministic rules, re-evaluated fresh every time, never trusting a stale decision.

The optimizer recommends. Policy authorizes. Nothing executes without both.

## 2:15 – 3:15 — Live Decision Trace

*(Show a real operational opportunity, not a mock.)*

Walk the Decision Trace top to bottom: failed payment → prediction → economic value → optimizer → policy → execution → webhook → recovered. Every stage carries a timestamp, a version, and a real backend-computed value — the frontend never recomputes anything, it only renders what the backend decided.

## 3:15 – 4:00 — Execution + webhook

RAY creates the Payment Link through the real Razorpay API, in **Test Mode only** — no live-mode switch exists in this system. The customer completes payment; Razorpay sends a signed `payment_link.paid` webhook; RAY verifies the HMAC signature, persists the event, and records the recovery outcome — durable across restarts, attributable end to end.

## 4:00 – 4:40 — Evaluation

*(Show `/evaluation`.)*

One frozen benchmark, evaluated exactly once on 300 held-out synthetic cases. Two models trained, calibrated, and compared against a historical-rate baseline with 1,000-iteration bootstrap confidence intervals. Every interval for realized-recovery deltas crosses zero — the predictive improvements did not translate into statistically significant economic gains at this sample size.

## 4:40 – 5:00 — Key insight

RAY chose the simplest model that survived the full evaluation — not the one with marginally better offline metrics. Model B added LLM-derived features and improved ROC-AUC slightly; it did not improve verified recovered revenue. That honest result, reported rather than hidden, is what V1 actually proved: a working, safe, attributable decision pipeline — not a production revenue-uplift claim. We are not claiming production uplift; we are showing that when we ran the full pipeline honestly, the extra complexity didn't pay for itself, and we said so.
