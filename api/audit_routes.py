"""
INSURE.AI — Audit, KPI & Review API Routes
Replaces the mock AUDIT_BASE_URL with real PostgreSQL writes.
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import db_session
from db.repositories import (
    ClaimRepository,
    RetentionRepository,
    OfferRepository,
    EventRepository,
)


# ── ENUM MAPPING ──────────────────────────────────────────────────────────────
# DB enum `pipeline_type` has values: lead, claims, retention, offer
# (intentionally mixed singular/plural — absorbed here so UI/API stay clean).
# Keys are the HITL entity_type values used in the UI + review API.

ENTITY_TO_PIPELINE = {
    "claim":     "claims",
    "retention": "retention",
    "offer":     "offer",
    "lead":      "lead",
}


# ── REQUEST / RESPONSE MODELS ────────────────────────────────────────────────

class AuditLogRequest(BaseModel):
    pipeline: str
    entity_id: str
    entity_type: str = "unknown"
    event_type: str = "pipeline_event"
    payload: dict = {}


class ReviewRequest(BaseModel):
    entity_type: str            # "claim" | "retention" | "offer" | "lead"
    entity_id: str              # claim_id / UUID for retention / offer_trigger_id / lead_id
    decision: str               # "approved" | "rejected" | "escalated" | "info_requested"
    reviewer_id: str
    note: Optional[str] = None


class KpiResponse(BaseModel):
    date: str
    claims: dict
    retention: dict
    offers: dict


# ── ROUTE REGISTRATION ────────────────────────────────────────────────────────

def register_routes(app: FastAPI):

    # ── AUDIT LOG (called by n8n "Audit Log" nodes) ────────────────────────

    @app.post("/api/v1/audit/log", tags=["Audit"])
    async def audit_log(
        req: AuditLogRequest,
        session: AsyncSession = Depends(db_session),
    ):
        """
        Generic audit log endpoint — called by all n8n pipelines.
        Normalizes pipeline value in case caller uses singular form
        (e.g. 'claim' instead of 'claims').
        """
        repo = EventRepository(session)
        pipeline = ENTITY_TO_PIPELINE.get(req.pipeline, req.pipeline)

        event = await repo.log(
            pipeline=pipeline,
            entity_id=req.entity_id,
            entity_type=req.entity_type,
            event_type=req.event_type,
            payload=req.payload,
        )
        return {"logged": True, "event_id": str(event.id)}


    # ── PIPELINE WRITE ENDPOINTS (called by agents after processing) ──────

    @app.post("/api/v1/claims", tags=["Claims"])
    async def store_claim(
        data: dict,
        session: AsyncSession = Depends(db_session),
    ):
        repo = ClaimRepository(session)
        existing = await repo.get_by_claim_id(data.get("claim_id", ""))
        if existing:
            raise HTTPException(status_code=409, detail="Claim already exists")
        claim = await repo.create(data)
        return {"id": str(claim.id), "claim_id": claim.claim_id}


    @app.post("/api/v1/retention", tags=["Retention"])
    async def store_retention_event(
        data: dict,
        session: AsyncSession = Depends(db_session),
    ):
        repo = RetentionRepository(session)
        event = await repo.create(data)
        return {"id": str(event.id)}


    @app.post("/api/v1/offers", tags=["Offers"])
    async def store_offer(
        data: dict,
        session: AsyncSession = Depends(db_session),
    ):
        repo = OfferRepository(session)
        existing = await repo.get_by_trigger_id(data.get("offer_trigger_id", ""))
        if existing:
            raise HTTPException(status_code=409, detail="Offer trigger already exists")
        offer = await repo.create(data)
        return {"id": str(offer.id), "offer_trigger_id": offer.offer_trigger_id}


    # ── HITL REVIEW (called by HITL dashboard) ─────────────────────────────

    @app.post("/api/v1/review", tags=["Human Review"])
    async def submit_review(
        req: ReviewRequest,
        session: AsyncSession = Depends(db_session),
    ):
        """
        Submit a human review decision for any entity type.
        Updates the relevant table and appends to audit log.
        """
        # Validate entity_type upfront (prevents KeyError later in mapping)
        if req.entity_type not in ENTITY_TO_PIPELINE:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown entity_type: {req.entity_type}"
            )

        event_repo = EventRepository(session)

        if req.entity_type == "claim":
            repo = ClaimRepository(session)
            await repo.record_review(
                claim_id=req.entity_id,
                decision=req.decision,
                reviewer_id=req.reviewer_id,
                note=req.note,
            )

        elif req.entity_type == "retention":
            # For retention, entity_id is the UUID of the retention_event row
            repo = RetentionRepository(session)
            try:
                uid = UUID(req.entity_id)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="entity_id must be a UUID for retention"
                )
            await repo.record_review(
                event_id=uid,
                decision=req.decision,
                reviewer_id=req.reviewer_id,
                note=req.note,
            )

        elif req.entity_type == "offer":
            repo = OfferRepository(session)
            await repo.record_review(
                offer_trigger_id=req.entity_id,
                decision=req.decision,
                reviewer_id=req.reviewer_id,
                note=req.note,
            )

        else:
            # Should not be reachable due to upfront validation,
            # but kept as defense-in-depth.
            raise HTTPException(
                status_code=400,
                detail=f"Unknown entity_type: {req.entity_type}"
            )

        # Append audit event (use mapped pipeline value to satisfy DB enum)
        await event_repo.log(
            pipeline=ENTITY_TO_PIPELINE[req.entity_type],
            entity_id=req.entity_id,
            entity_type=req.entity_type,
            event_type="human_review",
            payload={
                "decision": req.decision,
                "reviewer_id": req.reviewer_id,
                "note": req.note,
            },
        )

        return {"reviewed": True, "decision": req.decision}


    # ── KPI ENDPOINT (called by dashboard) ────────────────────────────────

    @app.get("/api/v1/kpi/today", response_model=KpiResponse, tags=["KPI"])
    async def kpi_today(session: AsyncSession = Depends(db_session)):
        """Returns today's KPIs for all three pipelines."""
        claims_kpi    = await ClaimRepository(session).kpi_today()
        retention_kpi = await RetentionRepository(session).kpi_today()
        offers_kpi    = await OfferRepository(session).kpi_today()

        return KpiResponse(
            date=datetime.now(timezone.utc).date().isoformat(),
            claims=claims_kpi,
            retention=retention_kpi,
            offers=offers_kpi,
        )


    # ── QUEUE ENDPOINT (HITL dashboard queue) ─────────────────────────────

    @app.get("/api/v1/review/queue", tags=["Human Review"])
    async def get_review_queue(
        pipeline: Optional[str] = None,
        session: AsyncSession = Depends(db_session),
    ):
        """Returns all pending HITL items, optionally filtered by pipeline."""
        results = []

        if not pipeline or pipeline == "claim":
            claims = await ClaimRepository(session).list_pending_review(limit=50)
            for c in claims:
                results.append({
                    "entity_type": "claim",
                    "entity_id": c.claim_id,
                    "id": str(c.id),
                    "urgency": c.priority,
                    "subtype": c.classification,
                    "confidence": float(c.confidence or 0),
                    "risk_score": float(c.fraud_score or 0),
                    "route": c.final_route,
                    "reasoning": c.agent_reasoning,
                    "flags": c.flags,
                    "queued_at": c.received_at.isoformat() if c.received_at else None,
                    "customer_id": c.customer_id,
                })

        # TODO: Extend queue to cover retention + offer pipelines.
        # The HITL UI expects all four pipeline types — currently only claims
        # are surfaced. Add analogous blocks once RetentionRepository and
        # OfferRepository expose a list_pending_review() method.

        return {"queue": results, "total": len(results)}


    # ── OUTCOME UPDATES ────────────────────────────────────────────────────

    @app.post("/api/v1/offers/{offer_trigger_id}/accepted", tags=["Offers"])
    async def offer_accepted(
        offer_trigger_id: str,
        session: AsyncSession = Depends(db_session),
    ):
        await OfferRepository(session).record_acceptance(offer_trigger_id)
        return {"updated": True}

    @app.post("/api/v1/offers/{offer_trigger_id}/rejected", tags=["Offers"])
    async def offer_rejected(
        offer_trigger_id: str,
        session: AsyncSession = Depends(db_session),
    ):
        await OfferRepository(session).record_rejection(offer_trigger_id)
        return {"updated": True}

    @app.post("/api/v1/retention/{event_id}/outcome", tags=["Retention"])
    async def retention_outcome(
        event_id: str,
        outcome: str,
        action_taken: Optional[str] = None,
        session: AsyncSession = Depends(db_session),
    ):
        try:
            uid = UUID(event_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid UUID")
        await RetentionRepository(session).record_outcome(uid, outcome, action_taken)
        return {"updated": True}