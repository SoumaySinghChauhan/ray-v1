"""
RAY V1 API Server

FastAPI backend for revenue recovery orchestration.
"""

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Setup Python path for imports
from pathlib import Path
import os
import sys

_file_path = Path(__file__).resolve()
_project_root = _file_path.parent.parent.parent  # Ray root
_api_root = _file_path.parent  # services/api

# Add to path if not already present
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
if str(_api_root) not in sys.path:
    sys.path.insert(0, str(_api_root))

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn
from datetime import datetime

# Local imports (to be implemented)
from .action_registry import ActionType, list_available_actions, validate_action_type
from .types import FailureClass, PolicyDecision
from .recovery_router import router as recovery_router
from config.v1_config import get_config


# ============================================================================
# Application Setup
# ============================================================================

app = FastAPI(
    title="RAY - Revenue Recovery Orchestrator",
    description="AI-native revenue recovery decision system",
    version="1.0.0",
)

# CORS: local dev origin plus any deployed frontend origins from ALLOWED_ORIGINS
# (comma-separated, e.g. "https://web-mu-ashy.vercel.app"). No wildcard — the
# frontend sends credentials, and CORS forbids combining "*" with credentials.
_default_origins = ["http://localhost:3000"]
_extra_origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_default_origins + _extra_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(recovery_router)


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

    SECURITY: Verifies signature BEFORE parsing JSON.
    Uses persistent database-backed services for restart safety.
    """
    import os
    import json

    # Step 1: Get raw body BEFORE any parsing
    raw_body = await request.body()

    # Step 2: Get signature header
    signature = request.headers.get("X-Razorpay-Signature", "")

    # Step 3: Get webhook secret
    webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")

    # Step 4: Reject if webhook secret not configured
    if not webhook_secret:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "Webhook secret not configured"}
        )

    # Step 5: Reject if signature missing
    if not signature:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"error": "Missing signature"}
        )

    # Step 6: VERIFY SIGNATURE BEFORE PARSING JSON
    from execution.providers import verify_webhook_signature

    signature_valid = verify_webhook_signature(
        payload_body=raw_body,
        signature=signature,
        secret=webhook_secret,
    )

    # Step 7: Reject invalid signature BEFORE parsing JSON
    if not signature_valid:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"error": "Invalid signature"}
        )

    # Step 8: ONLY AFTER signature verification, parse JSON
    try:
        payload = json.loads(raw_body)
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": f"Invalid JSON payload: {str(e)}"}
        )

    # Step 9: Initialize persistent services with database
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

        # Process webhook (signature already verified)
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
# Recovery Decision & Audit Endpoints
#
# Real implementations live in recovery_router.py / recovery_service.py,
# mounted above via app.include_router(recovery_router). Kept out of this
# file so the orchestration logic isn't scattered across main.py.
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
