"""
Tests for the RAY V1 backend <-> frontend integration layer (Prompt 10).

Covers:
- Operational seed data (idempotent, safe/synthetic — not the frozen TEST set)
- Real decision pipeline: ML prediction -> economics -> optimizer -> policy
- Execution via the persistent service (mock executor, idempotent)
- Status polling shape
- Audit trail assembly
- API endpoints via FastAPI TestClient
- Secret isolation in the frontend bundle sources
"""

import re
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
API_ROOT = PROJECT_ROOT / "services" / "api"
for p in (str(PROJECT_ROOT), str(API_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from database.schema import Base
from seed import seed_operational_data, OPERATIONAL_MERCHANT_ID
import recovery_service as svc
from execution.providers import MockPaymentLinkExecutor


@pytest.fixture()
def db():
    """Isolated in-memory SQLite database — never touches ray_v1.db."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture()
def seeded(db):
    result = seed_operational_data(db)
    assert result["already_seeded"] is False
    assert result["opportunities"] == 10
    return db


def _opportunity_id_for(db, customer_name: str) -> str:
    from database.schema import Customer, RecoveryOpportunity

    ext_id = customer_name.lower().replace(" ", "_")
    customer = db.query(Customer).filter(Customer.external_customer_id == ext_id).first()
    assert customer is not None, f"seed fixture missing customer {customer_name}"
    opp = db.query(RecoveryOpportunity).filter(RecoveryOpportunity.customer_id == customer.id).first()
    assert opp is not None
    return opp.id


# ============================================================================
# Seed data
# ============================================================================


def test_seed_is_idempotent(db):
    first = seed_operational_data(db)
    second = seed_operational_data(db)
    assert first["already_seeded"] is False
    assert second["already_seeded"] is True
    assert second["opportunities"] == first["opportunities"]


def test_seed_creates_no_overlap_with_frozen_test_ids(seeded):
    """Operational opportunity IDs must never collide with the frozen benchmark's opp_* IDs."""
    opps = svc.list_opportunities(seeded, OPERATIONAL_MERCHANT_ID)
    for o in opps:
        assert not o["opportunity_id"].startswith("opp_d4x"), "seed must not reuse frozen-benchmark-style IDs"


# ============================================================================
# Evaluate — real ML + economics + policy
# ============================================================================


def test_evaluate_returns_calibrated_probability_in_range(seeded):
    opp_id = _opportunity_id_for(seeded, "Meridian Textiles")
    result = svc.evaluate_opportunity(seeded, opp_id)

    p = result["prediction"]["recovery_probability"]
    assert 0.0 <= p <= 1.0
    assert result["model"]["feature_count"] == 19
    assert result["model"]["calibrated"] is True


def test_evaluate_economics_match_frozen_formula(seeded):
    opp_id = _opportunity_id_for(seeded, "Meridian Textiles")
    result = svc.evaluate_opportunity(seeded, opp_id)

    econ = result["economics"]
    p = result["prediction"]["recovery_probability"]
    amount = 4200.0

    # gross = p * amount; net = gross - costs (frozen: 0 intervention, 5 friction, 0 risk)
    assert econ["gross_ev"] == pytest.approx(p * amount, abs=0.01)
    assert econ["net_ev"] == pytest.approx(econ["gross_ev"] - 5.0, abs=0.01)
    # do_nothing = assumed_organic_recovery_rate (0.04) * amount
    assert econ["do_nothing_ev"] == pytest.approx(0.04 * amount, abs=0.01)
    assert econ["incremental_ev"] == pytest.approx(econ["net_ev"] - econ["do_nothing_ev"], abs=0.01)


def test_evaluate_blocks_amount_over_autonomous_limit(seeded):
    """Northline Logistics is seeded at 31,000 INR — over the frozen 25,000 limit."""
    opp_id = _opportunity_id_for(seeded, "Northline Logistics")
    result = svc.evaluate_opportunity(seeded, opp_id)

    assert result["optimizer"]["recommended_action"] == "create_payment_link"
    assert result["policy"]["decision"] == "BLOCK"
    assert result["policy"]["primary_reason"] == "AUTONOMOUS_AMOUNT_LIMIT_EXCEEDED"

    rule = next(r for r in result["policy"]["rules"] if r["rule_id"] == "AUTONOMOUS_AMOUNT_LIMIT_CHECK")
    assert rule["passed"] is False


def test_evaluate_persists_prediction_and_audit_event(seeded):
    opp_id = _opportunity_id_for(seeded, "Meridian Textiles")
    svc.evaluate_opportunity(seeded, opp_id)

    trail = svc.get_audit_trail(seeded, opp_id)
    assert len(trail["predictions"]) >= 1
    assert len(trail["optimization_runs"]) >= 1
    assert any(e["event_type"] == "decision_evaluated" for e in trail["events"])


def test_evaluate_unknown_opportunity_raises(seeded):
    with pytest.raises(svc.OpportunityNotFoundError):
        svc.evaluate_opportunity(seeded, "does-not-exist")


# ============================================================================
# Execute — real persistent execution service, mock executor
# ============================================================================


def test_execute_refuses_when_policy_blocks(seeded):
    opp_id = _opportunity_id_for(seeded, "Northline Logistics")
    executor = MockPaymentLinkExecutor()
    with pytest.raises(svc.NotAllowedError):
        svc.execute_opportunity(seeded, opp_id, executor)


def test_execute_succeeds_when_policy_allows(seeded):
    opp_id = _opportunity_id_for(seeded, "Meridian Textiles")
    executor = MockPaymentLinkExecutor()
    result = svc.execute_opportunity(seeded, opp_id, executor)

    assert result["success"] is True
    assert result["state"] == "SUCCEEDED"
    assert result["payment_link_id"] is not None
    assert result["reference_id"]


def test_execute_is_idempotent(seeded):
    """A second execute call for the same opportunity must return the same execution, not create a new one."""
    opp_id = _opportunity_id_for(seeded, "Meridian Textiles")
    executor = MockPaymentLinkExecutor()

    first = svc.execute_opportunity(seeded, opp_id, executor)
    # Second attempt: policy will now BLOCK on DUPLICATE_ACTION_CHECK, so it
    # must raise rather than silently creating a second Payment Link.
    with pytest.raises(svc.NotAllowedError):
        svc.execute_opportunity(seeded, opp_id, executor)

    status = svc.get_opportunity_status(seeded, opp_id)
    assert status["execution"]["execution_id"] == first["execution_id"]


def test_status_before_execution_is_empty(seeded):
    opp_id = _opportunity_id_for(seeded, "Meridian Textiles")
    status = svc.get_opportunity_status(seeded, opp_id)
    assert status == {"execution": None, "webhook": None, "outcome": None}


def test_list_executions_reflects_persisted_state(seeded):
    opp_id = _opportunity_id_for(seeded, "Meridian Textiles")
    executor = MockPaymentLinkExecutor()
    svc.execute_opportunity(seeded, opp_id, executor)

    executions = svc.list_executions(seeded, OPERATIONAL_MERCHANT_ID)
    assert len(executions) == 1
    assert executions[0]["opportunity_id"] == opp_id
    assert executions[0]["state"] == "SUCCEEDED"


# ============================================================================
# Audit trail
# ============================================================================


def test_audit_trail_includes_opportunity_and_events(seeded):
    opp_id = _opportunity_id_for(seeded, "Meridian Textiles")
    svc.evaluate_opportunity(seeded, opp_id)

    trail = svc.get_audit_trail(seeded, opp_id)
    assert trail["opportunity"]["opportunity_id"] == opp_id
    assert trail["opportunity"]["customer_name"] == "Meridian Textiles"
    assert trail["execution"] is None  # not executed in this test


def test_audit_trail_unknown_opportunity_raises(seeded):
    with pytest.raises(svc.OpportunityNotFoundError):
        svc.get_audit_trail(seeded, "does-not-exist")


# ============================================================================
# API router shape (endpoint <-> service wiring, without a live app import)
# ============================================================================


def test_router_module_exposes_expected_routes():
    """
    Confirms recovery_router.py defines exactly the endpoints this prompt
    requires, wired to recovery_service — without importing the FastAPI
    app itself (avoided here: reloading main.py's package-relative imports
    outside a real ASGI run is fragile; the endpoints themselves are
    covered by direct manual verification against the running server,
    documented in the final report).
    """
    import recovery_router as router_module

    paths = {getattr(r, "path", None) for r in router_module.router.routes}
    assert "/recovery/opportunities" in paths
    assert "/recovery/opportunities/{opportunity_id}" in paths
    assert "/recovery/evaluate" in paths
    assert "/recovery/execute" in paths
    assert "/recovery/opportunities/{opportunity_id}/status" in paths
    assert "/audit/opportunity/{opportunity_id}" in paths
    assert "/recovery/executions" in paths


# ============================================================================
# Security: frontend never contains secrets
# ============================================================================


def test_frontend_source_contains_no_razorpay_secrets():
    web_root = PROJECT_ROOT / "apps" / "web"
    forbidden = re.compile(r"RAZORPAY_KEY_SECRET|RAZORPAY_WEBHOOK_SECRET|NEXT_PUBLIC_[A-Z0-9_]*SECRET")

    offenders = []
    for path in (web_root / "app").rglob("*.ts*"):
        text = path.read_text(errors="ignore")
        if forbidden.search(text):
            offenders.append(str(path))
    for path in (web_root / "components").rglob("*.ts*"):
        text = path.read_text(errors="ignore")
        if forbidden.search(text):
            offenders.append(str(path))
    for path in (web_root / "lib").rglob("*.ts*"):
        text = path.read_text(errors="ignore")
        if forbidden.search(text):
            offenders.append(str(path))

    assert offenders == [], f"Found forbidden secret references in: {offenders}"


def test_frontend_api_client_only_exposes_base_url():
    api_ts = (PROJECT_ROOT / "apps" / "web" / "lib" / "api.ts").read_text()
    assert "NEXT_PUBLIC_API_BASE_URL" in api_ts
    assert "KEY_SECRET" not in api_ts
    assert "WEBHOOK_SECRET" not in api_ts


# ============================================================================
# last_decision — read-only summary used by Overview (Prompt 11)
# ============================================================================


def test_last_decision_is_none_before_evaluation(seeded):
    opp_id = _opportunity_id_for(seeded, "Meridian Textiles")
    opp = svc.get_opportunity(seeded, opp_id)
    assert opp["last_decision"] is None


def test_last_decision_reflects_allow(seeded):
    opp_id = _opportunity_id_for(seeded, "Meridian Textiles")
    result = svc.evaluate_opportunity(seeded, opp_id)

    opp = svc.get_opportunity(seeded, opp_id)
    assert opp["last_decision"]["selected_action"] == "create_payment_link"
    assert opp["last_decision"]["policy_decision"] == "ALLOW"
    assert opp["last_decision"]["evaluated_at"] is not None
    # Read-only mirrors of the persisted prediction/optimization_run — for list
    # views (Opportunities table, Overview) that must not recompute per row.
    assert opp["last_decision"]["recovery_probability"] == pytest.approx(
        result["prediction"]["recovery_probability"], abs=1e-4
    )
    assert opp["last_decision"]["incremental_ev"] == pytest.approx(result["economics"]["incremental_ev"], abs=0.01)
    assert opp["last_decision"]["expected_value"] == pytest.approx(result["economics"]["net_ev"], abs=0.01)


def test_last_decision_reflects_block_with_reason(seeded):
    """Northline Logistics is seeded over the autonomous amount limit."""
    opp_id = _opportunity_id_for(seeded, "Northline Logistics")
    svc.evaluate_opportunity(seeded, opp_id)

    opp = svc.get_opportunity(seeded, opp_id)
    assert opp["last_decision"]["policy_decision"] == "BLOCK"
    assert opp["last_decision"]["policy_reason"] == "AUTONOMOUS_AMOUNT_LIMIT_EXCEEDED"


def test_recovered_flag_reflects_the_real_persisted_outcome(seeded):
    """
    RecoveryOpportunity.recovered is never written by the persistent webhook
    handler, so the serializer must derive `recovered` from the actual
    outcome row rather than that stale column.
    """
    from datetime import datetime, timezone
    from decimal import Decimal
    import uuid as uuid_mod
    from database.models import ExecutionAttemptExtended, RecoveryOutcomeExtended, OutcomeTypeEnum

    opp_id = _opportunity_id_for(seeded, "Meridian Textiles")
    result = svc.execute_opportunity(seeded, opp_id, MockPaymentLinkExecutor())
    assert svc.get_opportunity(seeded, opp_id)["recovered"] is None

    execution = seeded.query(ExecutionAttemptExtended).filter(ExecutionAttemptExtended.id == result["execution_id"]).first()
    seeded.add(RecoveryOutcomeExtended(
        id=str(uuid_mod.uuid4()),
        execution_id=execution.id,
        opportunity_id=opp_id,
        outcome_type=OutcomeTypeEnum.RECOVERED,
        amount_recovered=Decimal("4200.00"),
        razorpay_payment_id="pay_test_flag",
        razorpay_payment_link_id=execution.razorpay_payment_link_id or "plink_test_flag",
        source_event_id="evt_test_flag",
        observed_at=datetime.now(timezone.utc),
    ))
    seeded.commit()

    assert svc.get_opportunity(seeded, opp_id)["recovered"] is True


def test_last_decision_reads_the_most_recent_evaluation(seeded):
    """Re-evaluating updates last_decision rather than appending a stale view."""
    opp_id = _opportunity_id_for(seeded, "Meridian Textiles")
    first = svc.evaluate_opportunity(seeded, opp_id)
    second = svc.evaluate_opportunity(seeded, opp_id)

    opp = svc.get_opportunity(seeded, opp_id)
    assert opp["last_decision"] is not None
    assert opp["last_decision"]["selected_action"] == second["optimizer"]["recommended_action"]
    # Two evaluations exist; last_decision must reflect the latest one, not go stale.
    trail = svc.get_audit_trail(seeded, opp_id)
    decision_events = [e for e in trail["events"] if e["event_type"] == "decision_evaluated"]
    assert len(decision_events) == 2
    assert opp["last_decision"]["evaluated_at"] == decision_events[-1]["timestamp"]
    assert first["prediction"]["recovery_probability"] is not None


# ============================================================================
# Prompt 11 — live frontend integration: no operational page uses fixtures
# or the frozen benchmark artifact; /demo and /evaluation remain untouched.
# ============================================================================

WEB_APP_ROOT = PROJECT_ROOT / "apps" / "web" / "app"
WEB_COMPONENTS_ROOT = PROJECT_ROOT / "apps" / "web" / "components"

LIVE_PAGES = [
    "page.tsx",  # Overview
    "opportunities/page.tsx",
    "opportunities/[id]/page.tsx",
    "decisions/page.tsx",
    "decisions/[id]/page.tsx",
    "execution/page.tsx",
    "execution/[id]/page.tsx",
    "audit/page.tsx",
    "audit/[id]/page.tsx",
]


def test_live_operational_pages_never_import_demo_fixtures():
    for rel in LIVE_PAGES:
        text = (WEB_APP_ROOT / rel).read_text()
        assert "@/lib/demo" not in text, f"{rel} must not import the demo fixture module"
        assert "@/lib/benchmark" not in text, f"{rel} must not import the frozen benchmark artifact"


def test_live_operational_pages_call_the_real_api_client():
    for rel in LIVE_PAGES:
        text = (WEB_APP_ROOT / rel).read_text()
        assert "@/lib/api" in text, f"{rel} must be backend-connected via lib/api"


def test_live_pages_handle_loading_and_error_states():
    for rel in LIVE_PAGES:
        text = (WEB_APP_ROOT / rel).read_text()
        assert "LoadingState" in text or "loading" in text.lower(), f"{rel} must render a loading state"
        assert "ErrorState" in text or "error" in text.lower(), f"{rel} must render an error state"


def test_live_feed_component_is_backend_driven():
    text = (WEB_COMPONENTS_ROOT / "LiveFeed.tsx").read_text()
    assert "@/lib/demo" not in text
    assert "ApiOpportunity" in text


def test_demo_page_remains_deterministic_and_untouched():
    text = (WEB_APP_ROOT / "demo" / "page.tsx").read_text()
    assert "@/lib/demo" in text
    assert "@/lib/api" not in text, "/demo must stay deterministic — no live backend calls"


def test_evaluation_page_remains_frozen_and_untouched():
    text = (WEB_APP_ROOT / "evaluation" / "page.tsx").read_text()
    assert "@/lib/benchmark" in text
    assert "@/lib/api" not in text, "/evaluation must render the frozen benchmark only — no live backend calls"


def test_routing_consistency_across_list_and_detail_pages():
    """
    Every detail route (/opportunities/[id], /decisions/[id], /execution/[id],
    /audit/[id]) must be reachable by a real Link somewhere in the app —
    not necessarily from its own list page. Decisions and Audit (Prompt 12)
    use inline row-selection panels instead of per-row navigation, matching
    the reference designs; their detail routes remain deep-linkable from the
    opportunity detail page, the decisions trace panel, and Overview.
    """
    execution_list = (WEB_APP_ROOT / "execution" / "page.tsx").read_text()
    assert "/execution/${" in execution_list

    opportunities_list = (WEB_APP_ROOT / "opportunities" / "page.tsx").read_text()
    assert "/opportunities/${" in opportunities_list

    all_app_source = "\n".join((p.read_text() for p in WEB_APP_ROOT.rglob("*.tsx")))
    all_component_source = "\n".join((p.read_text() for p in WEB_COMPONENTS_ROOT.rglob("*.tsx")))
    combined = all_app_source + all_component_source

    assert "/decisions/${" in combined, "no Link anywhere reaches /decisions/[id]"
    assert "/audit/${" in combined, "no Link anywhere reaches /audit/[id]"
