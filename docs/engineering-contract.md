# RAY Engineering Contract

## Core Principles

### 1. Frozen Product Contract

The V1 product specification is FROZEN.

Do NOT:
- Expand action space beyond `create_payment_link` and `do_nothing`
- Add revenue surfaces beyond payment failures
- Add communication channels beyond Payment Links
- Implement features from V2+ roadmap

### 2. Strict Typing

Use type annotations everywhere:
- Python: strict mypy compliance
- TypeScript: strict mode enabled
- Pydantic models for all data validation
- SQLAlchemy with typed models

### 3. Small, Modular Functions

Functions should:
- Do one thing
- Be testable in isolation
- Have clear input/output contracts
- Avoid hidden state

Avoid:
- Functions over 50 lines
- Deep nesting
- Global mutable state

### 4. Separation of Concerns

Domain logic MUST be separate from:
- HTTP handling
- Database access
- UI rendering
- External API calls

Example:

```python
# GOOD
def calculate_incremental_value(
    payment_link_ev: Decimal,
    organic_ev: Decimal
) -> Decimal:
    return payment_link_ev - organic_ev

# BAD
def calculate_incremental_value(opportunity_id: str) -> Decimal:
    # Mixes business logic with database access
    opportunity = db.query(Opportunity).get(opportunity_id)
    # ... calculations mixed with data access
```

### 5. No Hidden Global State

Avoid:
- Module-level mutable variables
- Implicit configuration
- Thread-local state
- Singleton mutations

Use:
- Explicit dependency injection
- Immutable configuration
- Pure functions where possible

### 6. Explicit Over Implicit

Prefer:
```python
def make_decision(
    opportunity: RecoveryOpportunity,
    predictions: dict[ActionType, float],
    config: RecoveryConfig
) -> ActionType:
    # All inputs explicit
```

Not:
```python
def make_decision(opportunity_id: str) -> ActionType:
    # Implicitly fetches data, config
```

### 7. Import Boundaries

**CRITICAL**: Production code MUST NOT import evaluation code.

```python
# FORBIDDEN in production modules
from simulator.ground_truth import get_true_recovery_probability
from evaluation.benchmark import get_test_labels

# ALLOWED in production
from config import get_config
from action_registry import validate_action_type
```

Test code MAY import production code.

Evaluation code MAY import production code for benchmarking.

But never the reverse.

### 8. Error Handling

Use appropriate error types:
- `ValueError` for validation errors
- `RuntimeError` for unexpected state
- Custom exceptions for domain errors

Example:
```python
class PolicyBlockedError(Exception):
    """Action blocked by policy engine."""
    pass

class InvalidActionTypeError(ValueError):
    """Unknown action type."""
    pass
```

Always provide context:
```python
raise ValueError(
    f"Recovery probability {prob} must be between 0 and 1"
)
```

### 9. Logging

Use structured logging:
```python
logger.info(
    "action_selected",
    opportunity_id=opportunity.id,
    action=selected_action,
    expected_value=float(ev),
)
```

Not:
```python
print(f"Selected {selected_action} for {opportunity.id}")
```

### 10. Testing Strategy

#### Unit Tests
Test individual functions in isolation.

Example:
```python
def test_calculate_payment_link_ev():
    recovery_prob = 0.3
    amount = Decimal("1000")
    cost = Decimal("10")
    
    ev = calculate_payment_link_ev(recovery_prob, amount, cost)
    
    assert ev == Decimal("290")  # 0.3 * 1000 - 10
```

#### Integration Tests
Test complete decision pipeline.

Example:
```python
def test_decision_pipeline_end_to_end():
    # Create opportunity
    # Run LLM diagnosis
    # Run ML prediction
    # Run optimizer
    # Run policy check
    # Verify decision chain
```

#### Adversarial Tests
Test security boundaries.

Examples:
- LLM trying to access ground truth
- Policy bypass attempts
- Duplicate execution
- Invalid action types

### 11. Documentation Standards

Every module should have:
```python
"""
Module purpose.

Responsibilities:
- What it does
- What it doesn't do

Authority:
- What it can access
- What it cannot access

Prohibited:
- What it must never do
"""
```

Every non-trivial function should document:
- Purpose
- Parameters
- Return value
- Raises (if applicable)

Do NOT document obvious code.

### 12. Git Practices

#### Commits
- Small, logical commits
- Clear commit messages
- One conceptual change per commit

Good:
```
Add policy engine authorization checks

Implements daily capacity check, do-not-contact check,
and autonomous amount limit validation.
```

Bad:
```
Updates
```

#### Branches
- `main`: production-ready code
- `develop/*`: development work
- `eval/*`: evaluation experiments

#### Never Commit
- `.env` files
- API keys
- Credentials
- Large generated datasets
- ML model binaries (use Git LFS if needed)

### 13. Configuration Changes

When changing configuration defaults:

1. Document reason in `docs/decisions.md`
2. Update `config/v1_config.py`
3. Update `.env.example` if environment variable
4. Update `README.md` if user-facing
5. Increment appropriate version number

### 14. Database Migrations

Use Alembic for schema changes:

```bash
alembic revision --autogenerate -m "Add column X to table Y"
alembic upgrade head
```

Never:
- Manually modify schema in production
- Skip migrations
- Edit old migration files

### 15. Dependency Management

Python:
- Pin exact versions in `requirements.txt`
- Document why each dependency exists

Node.js:
- Use `package-lock.json`
- Keep dependencies minimal

### 16. Performance Guidelines

V1 prioritizes correctness over performance.

Do NOT prematurely optimize.

Do NOT add:
- Caching without measurement
- Async processing without necessity
- Distributed systems without scale proof

Do:
- Write clear, correct code first
- Measure if performance is a concern
- Optimize with data

### 17. Review Checklist

Before submitting code:

- [ ] Type annotations present
- [ ] Tests written and passing
- [ ] No production imports of evaluation code
- [ ] No secrets in code
- [ ] Error handling appropriate
- [ ] Logging structured
- [ ] Documentation updated
- [ ] Configuration changes documented

### 18. Prohibited Patterns

#### Global State
```python
# BAD
current_config = {}

def update_config(key, value):
    current_config[key] = value
```

#### Hidden Coupling
```python
# BAD
def make_decision(opportunity_id):
    # Implicitly depends on database connection,
    # configuration, model state, etc.
    pass
```

#### Mixing Concerns
```python
# BAD
def evaluate_and_execute(opportunity_id):
    # Mixes decision logic with execution
    # Cannot test decision without side effects
    pass
```

#### God Objects
```python
# BAD
class RAYSystem:
    def handle_webhook(self): ...
    def diagnose(self): ...
    def predict(self): ...
    def optimize(self): ...
    def execute(self): ...
    # Everything in one class
```

### 19. Maintenance Principles

#### When Adding Features
1. Check if it violates frozen V1 scope
2. If yes: defer to V2
3. If no: document design decision
4. Implement with tests
5. Update documentation

#### When Fixing Bugs
1. Write test that reproduces bug
2. Fix bug
3. Verify test passes
4. Check for similar bugs elsewhere

#### When Refactoring
1. Ensure tests exist and pass
2. Refactor incrementally
3. Run tests after each change
4. Do not change behavior

### 20. Code Review Standards

Reviewers should verify:
- Frozen contract not violated
- Import boundaries respected
- Type annotations present
- Tests adequate
- Error handling appropriate
- Documentation updated
- No secrets committed
- Performance reasonable for V1 scale

## Summary

The engineering contract exists to maintain:
- **Scientific integrity** of the benchmark
- **Architectural clarity** of the system
- **Maintainability** of the codebase
- **Reproducibility** of results

When in doubt, prefer:
- Explicit over implicit
- Simple over clever
- Correct over fast
- Typed over dynamic
- Tested over assumed
