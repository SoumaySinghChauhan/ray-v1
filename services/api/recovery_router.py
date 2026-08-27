"""
Recovery API router for RAY V1.

Thin HTTP layer over recovery_service — no business logic lives here.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database.session import SessionLocal
import recovery_service as svc
from seed import OPERATIONAL_MERCHANT_ID

router = APIRouter()


class OpportunityRef(BaseModel):
    opportunity_id: str


@router.get("/recovery/opportunities")
async def list_opportunities(merchant_id: str = OPERATIONAL_MERCHANT_ID):
    db = SessionLocal()
    try:
        return {"merchant_id": merchant_id, "opportunities": svc.list_opportunities(db, merchant_id)}
    finally:
        db.close()


@router.get("/recovery/opportunities/{opportunity_id}")
async def get_opportunity(opportunity_id: str):
    db = SessionLocal()
    try:
        return svc.get_opportunity(db, opportunity_id)
    except svc.OpportunityNotFoundError:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    finally:
        db.close()


@router.post("/recovery/evaluate")
async def evaluate_recovery_opportunity(body: OpportunityRef):
    db = SessionLocal()
    try:
        return svc.evaluate_opportunity(db, body.opportunity_id)
    except svc.OpportunityNotFoundError:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    finally:
        db.close()


@router.post("/recovery/execute")
async def execute_recovery_opportunity(body: OpportunityRef):
    db = SessionLocal()
    try:
        executor = svc.default_executor()
        return svc.execute_opportunity(db, body.opportunity_id, executor)
    except svc.OpportunityNotFoundError:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    except svc.NotAllowedError as e:
        raise HTTPException(status_code=403, detail=str(e))
    finally:
        db.close()


@router.get("/recovery/executions")
async def list_executions(merchant_id: str = OPERATIONAL_MERCHANT_ID):
    db = SessionLocal()
    try:
        return {"merchant_id": merchant_id, "executions": svc.list_executions(db, merchant_id)}
    finally:
        db.close()


@router.get("/recovery/opportunities/{opportunity_id}/status")
async def get_opportunity_status(opportunity_id: str):
    db = SessionLocal()
    try:
        # Ensure the opportunity exists (404 rather than a silently empty status)
        svc.get_opportunity(db, opportunity_id)
        return svc.get_opportunity_status(db, opportunity_id)
    except svc.OpportunityNotFoundError:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    finally:
        db.close()


@router.get("/audit/opportunity/{opportunity_id}")
async def get_opportunity_audit(opportunity_id: str):
    db = SessionLocal()
    try:
        return svc.get_audit_trail(db, opportunity_id)
    except svc.OpportunityNotFoundError:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    finally:
        db.close()
