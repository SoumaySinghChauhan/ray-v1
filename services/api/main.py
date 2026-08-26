"""
RAY V1 API Server

FastAPI backend for revenue recovery orchestration.
"""

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn
from datetime import datetime

# Local imports (to be implemented)
from .action_registry import ActionType, list_available_actions, validate_action_type
from .types import FailureClass, PolicyDecision
from config.v1_config import get_config


# ============================================================================
# Application Setup
# ============================================================================

app = FastAPI(
    title="RAY - Revenue Recovery Orchestrator",
    description="AI-native revenue recovery decision system",
    version="1.0.0",
)

# CORS middleware for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js default
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Request/Response Models
# ============================================================================

class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    timestamp: datetime
    version: str


class ConfigResponse(BaseModel):
    """Configuration information response."""
    version: str
    available_actions: list[str]
    max_actions_per_day: int
    autonomous_amount_limit: str


# ============================================================================
# Routes
# ============================================================================

@app.get("/", response_model=HealthResponse)
async def root():
    """Root endpoint."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow(),
        version="1.0.0"
    )


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow(),
        version="1.0.0"
    )


@app.get("/config", response_model=ConfigResponse)
async def get_system_config():
    """Get system configuration."""
    config = get_config()
    return ConfigResponse(
        version=config.versions.optimizer_version,
        available_actions=[action.value for action in list_available_actions()],
        max_actions_per_day=config.recovery.max_actions_per_day,
        autonomous_amount_limit=str(config.recovery.autonomous_amount_limit),
    )


@app.get("/config/verify")
async def verify_config():
    """
    Verify sensitive configuration is loaded without revealing values.

    Returns presence/absence of sensitive config values.
    NEVER returns actual secret values.
    """
    config = get_config()

    return {
        "razorpay": {
            "mode": config.razorpay.mode,
            "key_id_present": bool(config.razorpay.key_id),
            "key_secret_present": bool(config.razorpay.key_secret),
            "webhook_secret_present": bool(config.razorpay.webhook_secret),
        },
        "dotenv_loaded": True,
    }


# ============================================================================
# Webhook Endpoints (Scaffolded)
# ============================================================================

@app.post("/webhooks/razorpay")
async def razorpay_webhook(request: Request):
    """
    Razorpay webhook receiver.

    Verifies signature and processes Payment Link events.
    Uses persistent database-backed services for restart safety.
    """
    import sys
    import os
    sys.path.insert(0, '/Users/soumaysinghchauhan/Ray')

    # Get raw body BEFORE parsing
    raw_body = await request.body()

    # Get signature header
    signature = request.headers.get("X-Razorpay-Signature", "")

    # Get webhook secret
    webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")

    if not webhook_secret:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "Webhook secret not configured"}
        )

    # Parse JSON payload
    try:
        payload = await request.json()
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": f"Invalid JSON payload: {str(e)}"}
        )

    # Initialize persistent services with database
    from database.session import SessionLocal
    from execution.service_persistent import PersistentExecutionService
    from execution.webhooks_persistent import PersistentWebhookHandler
    from execution.providers import MockPaymentLinkExecutor

    # Create database session
    db = SessionLocal()

    try:
        # Create persistent execution service
        executor = MockPaymentLinkExecutor()
        execution_service = PersistentExecutionService(executor, db)

        # Create persistent webhook handler
        handler = PersistentWebhookHandler(execution_service, webhook_secret, db)

        # Process webhook
        result = handler.process_webhook(
            raw_body=raw_body,
            signature=signature,
            payload=payload,
        )

        # Return response
        if result.get("success"):
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=result
            )
        else:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=result
            )

    finally:
        db.close()


# ============================================================================
# Recovery Decision Endpoints (Scaffolded)
# ============================================================================

@app.post("/recovery/evaluate")
async def evaluate_recovery_opportunity():
    """
    Evaluate a recovery opportunity and make decision.

    This is the main decision pipeline entry point.
    Implementation deferred to later prompt.
    """
    return JSONResponse(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        content={"detail": "Recovery evaluation not yet implemented"}
    )


# ============================================================================
# Audit Endpoints (Scaffolded)
# ============================================================================

@app.get("/audit/opportunity/{opportunity_id}")
async def get_opportunity_audit(opportunity_id: str):
    """
    Retrieve complete audit trail for an opportunity.
    Implementation deferred to later prompt.
    """
    return JSONResponse(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        content={"detail": "Audit retrieval not yet implemented"}
    )


# ============================================================================
# Error Handlers
# ============================================================================

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """Handle validation errors."""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc)}
    )


# ============================================================================
# Development Server
# ============================================================================

if __name__ == "__main__":
    config = get_config()
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
