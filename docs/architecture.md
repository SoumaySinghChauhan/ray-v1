# RAY Architecture

## Overview

RAY (Revenue Recovery Orchestrator) follows a strict layered architecture with clear separation of concerns.

## Core Principle

**No component may bypass its authority boundary.**

The decision hierarchy is:

```
Payment Failure Event
    ↓
LLM Diagnosis
    ↓
ML Prediction
    ↓
Economic Optimizer
    ↓
Policy Engine (AUTHORIZATION GATE)
    ↓
Execution Layer
    ↓
Outcome Observation
    ↓
Audit Trail
```

## Component Responsibilities

### 1. Event Ingestion

**Location**: `services/api/webhooks/`

**Responsibilities**:
- Receive Razorpay webhooks
- Verify webhook signatures
- Deduplicate events
- Create/update payment records
- Create recovery opportunities

**Authority**: Read-only payment verification, opportunity creation

**Prohibited**: Cannot execute financial actions

### 2. LLM Diagnosis

**Location**: `ai/diagnosis/`

**Responsibilities**:
- Classify failure into structured schema
- Provide confidence score
- Generate human-readable explanation
- Extract reason codes

**Authority**: Diagnosis only

**Prohibited**:
- Cannot access simulator ground truth
- Cannot execute actions
- Cannot override policy
- Cannot access hidden variables

**Important**: For benchmark evaluation, LLM diagnosis is run OFFLINE and cached.

### 3. ML Prediction

**Location**: `ml/`

**Responsibilities**:
- Predict P(recovery | opportunity, action)
- One prediction per action type
- Use only observable features
- Return calibrated probabilities

**Authority**: Prediction only

**Prohibited**:
- Cannot access simulator ground truth
- Cannot access future outcomes during training
- Cannot access hidden latent variables
- Cannot execute actions

### 4. Optimizer

**Location**: `optimizer/`

**Responsibilities**:
- Calculate expected value for each action
- Compare incremental value vs do_nothing
- Apply daily capacity constraints
- Select economically optimal action

**Authority**: Economic recommendation

**Prohibited**:
- Cannot access simulator ground truth
- Cannot override policy blocks
- Cannot execute actions directly

**Key Calculation**:

```python
EV(payment_link) = P_ML(recovery) × amount - costs
EV(do_nothing) = assumed_organic_rate × amount
incremental_EV = EV(payment_link) - EV(do_nothing)
```

### 5. Policy Engine

**Location**: `policy/`

**Responsibilities**:
- Apply deterministic authorization rules
- Return ALLOW or BLOCK
- Check:
  - Daily capacity limits
  - Per-customer contact limits
  - Do-not-contact list
  - Autonomous amount limits
  - Duplicate execution prevention
  - Valid action type

**Authority**: AUTHORIZATION GATE - final decision authority

**Prohibited**:
- Cannot be overridden by LLM
- Cannot be bypassed by optimizer

**Important**: Policy blocks are FINAL. No downstream override.

### 6. Execution Layer

**Location**: `integrations/razorpay/`

**Responsibilities**:
- Execute ONLY policy-approved actions
- Create Razorpay Payment Links
- Handle execution errors
- Return execution result
- Maintain idempotency

**Authority**: Execution only

**Prohibited**:
- Cannot execute without policy approval
- Cannot retry policy-blocked actions
- Cannot modify merchant policies

### 7. Outcome Engine

**Location**: `evaluation/`

**Responsibilities**:
- Observe actual recovery results
- Determine attribution window
- Record outcome independently of prediction

**Authority**: Observation only

**Prohibited**:
- Cannot access during decision-making
- Cannot influence action selection

**Important**: Ground truth comes from simulator OR real Razorpay data, NEVER from ML predictions.

### 8. Audit System

**Location**: `audit/`

**Responsibilities**:
- Record complete decision chain
- Log actor, timestamp, reason for each decision
- Enable reconstruction of what happened and why
- Track versions of all components

**Authority**: Read-only logging

**Prohibited**:
- Cannot modify decisions
- Cannot block execution

## Data Flow

### Runtime Decision Flow

```
1. Razorpay webhook arrives
2. Event verified and deduplicated
3. Payment state fetched
4. Recovery opportunity created
5. LLM diagnoses failure (if live mode)
6. ML predicts recovery probability per action
7. Optimizer selects economically optimal action
8. Policy engine authorizes or blocks
9. If ALLOW: execute action
10. If BLOCK: record block reason, stop
11. Audit trail records complete chain
12. Later: outcome observed and recorded
```

### Offline Benchmark Flow

```
1. Simulator generates synthetic world
2. LLM diagnosis run ONCE on all opportunities → cached
3. Dataset created with cached diagnoses
4. Train/validation/test split (by customer)
5. ML model trained on train set
6. Hyperparameters selected on validation set
7. Baseline threshold selected on validation set
8. FREEZE all decisions
9. For each test opportunity:
   a. Load cached LLM diagnosis
   b. ML predicts recovery probability
   c. Optimizer selects action
   d. Policy authorizes
   e. Simulator determines outcome
   f. Audit records decision chain
10. Aggregate metrics with bootstrap confidence intervals
```

## Isolation Rules

### Production vs Evaluation

**Production code** (`services/api/`, `policy/`, `optimizer/`, `integrations/`):
- MUST NOT import from `simulator/ground_truth/`
- MUST NOT import from `evaluation/benchmark/`
- MUST NOT access hidden simulator variables

**Evaluation code** (`evaluation/`, `simulator/`):
- MAY import production code for testing
- MUST maintain ground truth separation
- MUST NOT expose hidden variables to production modules

### Testing Isolation

Unit tests verify individual component behavior.

Integration tests verify end-to-end decision pipeline.

Adversarial tests verify:
- LLM cannot access ground truth
- Policy blocks are enforced
- Idempotency is maintained
- Duplicate webhooks are handled
- Stale state is detected

## Technology Stack

### Backend
- **Language**: Python 3.14+
- **Framework**: FastAPI
- **Database**: PostgreSQL with SQLAlchemy
- **Validation**: Pydantic v2

### Frontend
- **Framework**: Next.js 16 with App Router
- **Language**: TypeScript
- **Styling**: Tailwind CSS

### ML
- **Training**: scikit-learn, LightGBM, XGBoost
- **Evaluation**: Bootstrap resampling (1000 iterations)

### LLM
- **Providers**: Anthropic Claude, OpenAI
- **Abstraction**: Provider-agnostic interface

### Integration
- **Razorpay**: Official SDK

## Configuration Management

All configuration is typed and validated via `config/v1_config.py`.

Environment variables are loaded from `.env` (never committed).

Configuration changes must be documented in `docs/decisions.md`.

## Database Schema

See `services/api/database/schema.py` for complete schema.

Key entities:
- **Merchant**: Merchant account
- **Customer**: Customer identity
- **Payment**: Transaction record
- **WebhookEvent**: Incoming events
- **RecoveryOpportunity**: Decision unit
- **ActionPrediction**: ML prediction
- **OptimizationRun**: Economic decision
- **MerchantPolicy**: Authorization rules
- **ExecutionAttempt**: Action execution
- **RecoveryOutcome**: Actual result
- **AuditEvent**: Decision trail
- **EvaluationRun**: Benchmark result

## Versioning

Every component is versioned:

```python
simulation_version: str
dataset_version: str
diagnosis_prompt_version: str
diagnosis_model_version: str
model_version: str
optimizer_version: str
policy_version: str
evaluation_protocol_version: str
```

Benchmark results must record all versions.

## Security

- Webhook signatures verified before processing
- API keys stored in environment variables only
- Never commit secrets to Git
- Idempotency keys prevent duplicate execution
- Policy engine is final authorization gate

## Scalability Notes (V1)

V1 is intentionally simple:
- Monolithic application
- Synchronous decision pipeline
- PostgreSQL for all persistence
- No Redis/Celery/Kafka

Future versions may introduce:
- Async job processing
- Caching layer
- Distributed coordination

But V1 prioritizes correctness over scale.
