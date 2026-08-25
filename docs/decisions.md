# RAY Decision Log

## Purpose

This document records all significant design decisions, configuration changes, and architectural choices made during RAY development.

## Format

Each entry should include:
- **Date**: When the decision was made
- **Decision**: What was decided
- **Rationale**: Why it was decided
- **Alternatives Considered**: What else was considered
- **Impact**: What systems/components are affected
- **Version**: What version number changed (if applicable)

---

## Decision Log

### 2026-08-25: Initial Repository Structure

**Decision**: Use modular monolith with clear directory separation

**Rationale**:
- V1 prioritizes correctness over scale
- Separation of concerns more important than distributed architecture
- Easier to maintain experimental integrity
- Lower operational complexity

**Alternatives Considered**:
- Microservices architecture (rejected: premature for V1 scale)
- Single flat directory (rejected: poor separation of concerns)

**Impact**: All components

---

### 2026-08-25: V1 Action Space

**Decision**: Exactly TWO actions - `create_payment_link` and `do_nothing`

**Rationale**:
- Frozen V1 specification
- Simplifies evaluation
- Clear baseline comparison
- Sufficient to demonstrate economic optimization

**Alternatives Considered**:
- Email/SMS actions (deferred to V1.5+)
- Retry payment directly (not permitted by Razorpay API model)
- Multiple recovery workflows (deferred to V2)

**Impact**: Action registry, optimizer, policy engine, execution layer

---

### 2026-08-25: Customer-Level Data Split

**Decision**: Split by customer (not by opportunity)

**Rationale**:
- V1 has exactly one opportunity per customer (1,000 opportunities, 1,000 customers)
- Prevents information leakage
- Mirrors real-world deployment (new customers in test)

**Alternatives Considered**:
- Random opportunity split (rejected: could leak customer patterns)
- Time-based split (deferred: requires temporal simulation complexity)

**Impact**: Dataset generation, evaluation protocol

---

### 2026-08-25: Offline LLM Diagnosis Caching

**Decision**: Run LLM diagnosis once offline, cache results, use cached results in benchmark

**Rationale**:
- Reproducibility: same diagnosis every benchmark run
- Cost control: no repeated expensive LLM calls
- Performance: benchmark runs quickly
- Scientific rigor: removes diagnosis variance from evaluation

**Alternatives Considered**:
- Live LLM calls during benchmark (rejected: non-reproducible, expensive)
- No LLM diagnosis (rejected: wanted to demonstrate LLM integration)

**Impact**: Dataset generation, benchmark execution, cost

**Version**: `diagnosis_prompt_version = "1.0.0"`, `diagnosis_model_version = "claude-3-5-sonnet-20241022"`

---

### 2026-08-25: Baseline Definition

**Decision**: Baseline = historical recovery rate per customer, cold-start fallback = validation mean

**Rationale**:
- Simple, interpretable baseline
- Uses same information available to RAY
- Historical rate is reasonable proxy for payment-link success
- Better than random or constant baseline

**Alternatives Considered**:
- Constant 4% baseline (rejected: ignores customer heterogeneity)
- Use organic recovery rate (rejected: baseline is for payment-link action)
- ML model baseline (considered for V1.5)

**Impact**: Baseline implementation, evaluation metrics

---

### 2026-08-25: RAY Organic Recovery Assumption

**Decision**: RAY assumes `organic_recovery_rate = 0.04` (4%)

**Rationale**:
- Configurable business assumption
- Visible to RAY for economic comparison
- Not simulator ground truth
- Conservative estimate encourages action when incremental value is positive

**Alternatives Considered**:
- Customer-specific organic rate (rejected: not observable)
- Learn from data (deferred to V2)

**Impact**: Optimizer economic calculations

**Version**: `config.recovery.assumed_organic_recovery_rate = 0.04`

---

### 2026-08-25: Daily Capacity Constraint

**Decision**: `max_actions_per_day = 10`, simulated over 10 days

**Rationale**:
- Tests constrained optimization, not unlimited batch selection
- Mirrors real-world operational limits
- Forces prioritization of high-value opportunities
- 10 days × 10 actions = 100 total actions for 300 test opportunities

**Alternatives Considered**:
- No capacity limit (rejected: unrealistic, trivial optimization)
- Customer-level limits only (rejected: wanted global budget constraint)

**Impact**: Optimizer, policy engine, evaluation protocol

**Version**: `config.recovery.max_actions_per_day = 10`, `config.simulator.simulation_days = 10`

---

### 2026-08-25: Bootstrap Confidence Intervals

**Decision**: 1,000 bootstrap iterations, 95% confidence level

**Rationale**:
- Standard statistical practice
- Quantifies uncertainty
- 1,000 iterations balances accuracy and computation time
- 95% CI is conventional threshold

**Alternatives Considered**:
- Parametric confidence intervals (rejected: may not hold for complex metrics)
- 10,000 iterations (rejected: diminishing returns, slower)

**Impact**: Evaluation metrics, reporting

**Version**: `config.evaluation.bootstrap_iterations = 1000`

---

### 2026-08-25: Python 3.14+ Requirement

**Decision**: Require Python 3.14 or newer

**Rationale**:
- Modern type system features
- Performance improvements
- Latest library compatibility
- Development machine has 3.14.6

**Alternatives Considered**:
- Python 3.10+ (rejected: wanted latest features)
- Python 3.9 (rejected: older type system)

**Impact**: Development environment, deployment

---

### 2026-08-25: PostgreSQL Without Redis/Celery

**Decision**: PostgreSQL only, no Redis or Celery in V1

**Rationale**:
- V1 is synchronous, no async job queue needed
- Simpler operations
- Sufficient for benchmark scale (1,500 customers)
- Can add later if production scale requires

**Alternatives Considered**:
- Redis for caching (deferred: no measured need yet)
- Celery for background jobs (deferred: no async execution in V1)

**Impact**: Architecture, dependencies, operations

---

### 2026-08-25: Idempotency Key Strategy

**Decision**: `idempotency_key = hash(merchant_id + opportunity_id + action_type + policy_version)`

**Rationale**:
- Prevents duplicate execution from duplicate webhooks
- Deterministic: same opportunity + same action = same key
- Includes policy version: allows policy changes to trigger new execution
- Database constraint enforces uniqueness

**Alternatives Considered**:
- Random UUID (rejected: not deterministic, can't detect duplicates)
- Opportunity ID only (rejected: doesn't distinguish action types)

**Impact**: Execution layer, database schema

---

### 2026-08-25: No V2 Features in V1 Codebase

**Decision**: Do not implement placeholders for V2 features

**Rationale**:
- V1 scope is frozen
- Unused code adds maintenance burden
- Premature abstraction is harmful
- V2 requirements may change

**Alternatives Considered**:
- Add "extensibility hooks" (rejected: YAGNI)
- Design for V2 (rejected: violates frozen contract)

**Impact**: Codebase simplicity, maintenance

---

## Template for Future Decisions

### YYYY-MM-DD: [Decision Title]

**Decision**: [What was decided]

**Rationale**: [Why]

**Alternatives Considered**: [What else was considered]

**Impact**: [Affected components]

**Version**: [If version number changed]

---

## Review Process

Before making a significant decision:

1. Check if it violates frozen V1 contract
2. Document in this file
3. Update affected configuration/code
4. Update version numbers if applicable
5. Update README/docs if user-facing

This log is append-only. Do not edit past decisions.

If a decision was wrong, add a new entry that supersedes it.
