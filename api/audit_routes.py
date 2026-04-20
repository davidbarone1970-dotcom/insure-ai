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
    LeadRepository,
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
    entity_id: str              # business key: claim_id / retention_event_id / offer_trigger_id / lead_id
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
        - Idempotent: repeated calls for the same entity return the ORIGINAL review
          with already_reviewed=true (no duplicate audit event is written).
        - Returns 404 if the entity doesn't exist.
        """
        if req.entity_type not in ENTITY_TO_PIPELINE:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown entity_type: {req.entity_type}"
            )

        event_repo = EventRepository(session)

        try:
            if req.entity_type == "claim":
                result = await ClaimRepository(session).record_review(
                    claim_id=req.entity_id,
                    decision=req.decision,
                    reviewer_id=req.reviewer_id,
                    note=req.note,
                )
            elif req.entity_type == "retention":
                result = await RetentionRepository(session).record_review(
                    event_key=req.entity_id,
                    decision=req.decision,
                    reviewer_id=req.reviewer_id,
                    note=req.note,
                )
            elif req.entity_type == "offer":
                result = await OfferRepository(session).record_review(
                    offer_trigger_id=req.entity_id,
                    decision=req.decision,
                    reviewer_id=req.reviewer_id,
                    note=req.note,
                )
            elif req.entity_type == "lead":
                result = await LeadRepository(session).record_review(
                    lead_id=req.entity_id,
                    decision=req.decision,
                    reviewer_id=req.reviewer_id,
                    note=req.note,
                )
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown entity_type: {req.entity_type}"
                )
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

        # Audit event only on first successful review.
        if not result["was_already_reviewed"]:
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

        return {
            "reviewed": True,
            "already_reviewed": result["was_already_reviewed"],
            "decision": result["decision"],
            "reviewer_id": result["reviewer_id"],
            "reviewed_at": result["reviewed_at"].isoformat() if result["reviewed_at"] else None,
        }

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

    # ── QUEUE ENDPOINT (HITL dashboard queue) ────────────────────────────────
    @app.get("/api/v1/review/queue", tags=["Human Review"])
    async def get_review_queue(
        pipeline: Optional[str] = None,
        session: AsyncSession = Depends(db_session),
    ):
        """
        Returns all pending HITL items across all 4 pipelines, sorted globally
        by urgency (DESC) then queued_at (ASC).

        Optional ?pipeline= filter (values: claim, lead, retention, offer)
        restricts the result to a single pipeline.
        """
        # ── Helpers ──────────────────────────────────────────────────────────
        ENUM_RANK = {"critical": 3, "high": 2, "medium": 1, "low": 0}

        def enum_rank(value: Optional[str]) -> int:
            """Map priority/urgency enum string to numeric rank."""
            return ENUM_RANK.get((value or "").lower(), 0)

        def score_to_rank(score: Optional[float]) -> int:
            """Map a 0..1 score to urgency rank (higher score = more urgent)."""
            if score is None:
                return 0
            if score >= 0.8: return 3
            if score >= 0.6: return 2
            if score >= 0.4: return 1
            return 0

        RANK_TO_LABEL = {3: "critical", 2: "high", 1: "medium", 0: "low"}

        results = []

        # ── Claims ───────────────────────────────────────────────────────────
        if not pipeline or pipeline == "claim":
            claims = await ClaimRepository(session).list_pending_review(limit=50)
            for c in claims:
                rank = enum_rank(c.priority)
                results.append({
                    "entity_type": "claim",
                    "entity_id": c.claim_id,
                    "id": str(c.id),
                    "urgency": c.priority or "low",
                    "urgency_rank": rank,
                    "subtype": c.classification,
                    "confidence": float(c.confidence or 0),
                    "risk_score": float(c.fraud_score or 0),
                    "route": c.final_route,
                    "reasoning": c.agent_reasoning,
                    "flags": c.flags,
                    "queued_at": c.received_at.isoformat() if c.received_at else None,
                    "customer_id": c.customer_id,
                })

        # ── Retention ────────────────────────────────────────────────────────
        if not pipeline or pipeline == "retention":
            events = await RetentionRepository(session).list_pending_review(limit=50)
            for e in events:
                score = float(e.churn_score) if e.churn_score is not None else None
                rank = score_to_rank(score)
                results.append({
                    "entity_type": "retention",
                    "entity_id": e.retention_event_id,
                    "id": str(e.id),
                    "urgency": RANK_TO_LABEL[rank],
                    "urgency_rank": rank,
                    "subtype": e.trigger_type,
                    "confidence": float(e.confidence or 0) if hasattr(e, "confidence") else 0.0,
                    "risk_score": score or 0.0,
                    "route": e.final_route,
                    "reasoning": e.agent_reasoning if hasattr(e, "agent_reasoning") else None,
                    "flags": e.flags if hasattr(e, "flags") else None,
                    "queued_at": e.triggered_at.isoformat() if e.triggered_at else None,
                    "customer_id": e.customer_id,
                })

        # ── Offer ────────────────────────────────────────────────────────────
        if not pipeline or pipeline == "offer":
            offers = await OfferRepository(session).list_pending_review(limit=50)
            for o in offers:
                # Prefer explicit urgency string if present, else derive from score
                if o.urgency:
                    rank = enum_rank(o.urgency)
                else:
                    score = float(o.cross_sell_score) if o.cross_sell_score is not None else None
                    rank = score_to_rank(score)
                results.append({
                    "entity_type": "offer",
                    "entity_id": o.offer_trigger_id,
                    "id": str(o.id),
                    "urgency": RANK_TO_LABEL[rank],
                    "urgency_rank": rank,
                    "subtype": o.recommended_product if hasattr(o, "recommended_product") else None,
                    "confidence": float(o.confidence or 0) if hasattr(o, "confidence") else 0.0,
                    "risk_score": float(o.cross_sell_score or 0),
                    "route": o.final_route,
                    "reasoning": o.agent_reasoning if hasattr(o, "agent_reasoning") else None,
                    "flags": o.flags if hasattr(o, "flags") else None,
                    "queued_at": o.triggered_at.isoformat() if o.triggered_at else None,
                    "customer_id": o.customer_id,
                })

        # ── Lead ─────────────────────────────────────────────────────────────
        if not pipeline or pipeline == "lead":
            leads = await LeadRepository(session).list_pending_review(limit=50)
            for l in leads:
                rank = enum_rank(l.priority)
                results.append({
                    "entity_type": "lead",
                    "entity_id": l.lead_id,
                    "id": str(l.id),
                    "urgency": l.priority or "low",
                    "urgency_rank": rank,
                    "subtype": l.qualification if hasattr(l, "qualification") else None,
                    "confidence": float(l.confidence or 0),
                    "risk_score": float(l.lead_score or 0) / 100.0 if l.lead_score else 0.0,
                    "route": l.final_route,
                    "reasoning": l.agent_reasoning if hasattr(l, "agent_reasoning") else None,
                    "flags": l.flags if hasattr(l, "flags") else None,
                    "queued_at": l.received_at.isoformat() if l.received_at else None,
                    "customer_id": l.customer_id,
                })

        # ── Global sort: urgency DESC, queued_at ASC ─────────────────────────
        results.sort(key=lambda x: (
            -x["urgency_rank"],
            x["queued_at"] or "9999",  # null queued_at → treat as oldest
        ))

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

    @app.post("/api/v1/retention/{event_key}/outcome", tags=["Retention"])
    async def retention_outcome(
        event_key: str,
        outcome: str,
        action_taken: Optional[str] = None,
        session: AsyncSession = Depends(db_session),
    ):
        await RetentionRepository(session).record_outcome(event_key, outcome, action_taken)
        return {"updated": True}
