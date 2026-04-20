"""
INSURE.AI — Repository Layer
All database read/write operations per pipeline.
Agents call these instead of raw SQL.
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select, update, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Claim, RetentionEvent, Offer, PipelineEvent, Lead


# ── HELPERS ───────────────────────────────────────────────────────────────────

def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── AUDIT EVENT REPOSITORY ────────────────────────────────────────────────────

class EventRepository:
    """Append-only audit log for all pipeline events."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def log(
        self,
        pipeline: str,
        entity_id: str,
        entity_type: str,
        event_type: str,
        payload: dict,
    ) -> PipelineEvent:
        event = PipelineEvent(
            pipeline=pipeline,
            entity_id=entity_id,
            entity_type=entity_type,
            event_type=event_type,
            payload=payload,
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def get_entity_history(self, entity_id: str) -> list[PipelineEvent]:
        result = await self.session.execute(
            select(PipelineEvent)
            .where(PipelineEvent.entity_id == entity_id)
            .order_by(PipelineEvent.created_at)
        )
        return list(result.scalars().all())


# ── CLAIMS REPOSITORY ─────────────────────────────────────────────────────────

class ClaimRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: dict) -> Claim:
        """Insert a new claim (after agent processing)."""
        claim = Claim(**data)
        self.session.add(claim)
        await self.session.flush()
        return claim

    async def get_by_claim_id(self, claim_id: str) -> Optional[Claim]:
        result = await self.session.execute(
            select(Claim).where(Claim.claim_id == claim_id)
        )
        return result.scalar_one_or_none()

    async def update_route(self, claim_id: str, final_route: str, override: bool, reason: Optional[str]) -> None:
        await self.session.execute(
            update(Claim)
            .where(Claim.claim_id == claim_id)
            .values(
                final_route=final_route,
                orchestrator_override=override,
                override_reason=reason,
                routed_at=utcnow(),
            )
        )

    async def record_review(
        self,
        claim_id: str,
        decision: str,
        reviewer_id: str,
        note: Optional[str] = None,
    ) -> None:
        await self.session.execute(
            update(Claim)
            .where(Claim.claim_id == claim_id)
            .values(
                review_decision=decision,
                reviewer_id=reviewer_id,
                reviewer_note=note,
                reviewed_at=utcnow(),
            )
        )

    async def list_pending_review(self, limit: int = 50) -> list[Claim]:
        result = await self.session.execute(
            select(Claim)
            .where(
                Claim.review_decision == 'pending',
                Claim.final_route.in_(['manual_review', 'escalation', 'siu_referral'])
            )
            .order_by(
                Claim.priority.desc(),
                Claim.received_at.asc()
            )
            .limit(limit)
        )
        return list(result.scalars().all())

    async def kpi_today(self) -> dict:
        today = utcnow().date()
        result = await self.session.execute(
            select(
                func.count().label("total"),
                func.count().filter(Claim.final_route == 'auto_process').label("auto"),
                func.count().filter(Claim.final_route == 'manual_review').label("manual"),
                func.count().filter(Claim.final_route == 'siu_referral').label("siu"),
                func.avg(Claim.confidence).label("avg_confidence"),
                func.avg(Claim.fraud_score).label("avg_fraud"),
            )
            .where(func.date(Claim.received_at) == today)
        )
        row = result.one()
        return {
            "total": row.total,
            "auto_processed": row.auto,
            "manual_review": row.manual,
            "siu_referral": row.siu,
            "avg_confidence": float(row.avg_confidence or 0),
            "avg_fraud_score": float(row.avg_fraud or 0),
            "automation_rate": row.auto / max(row.total, 1),
        }


# ── RETENTION REPOSITORY ──────────────────────────────────────────────────────

class RetentionRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: dict) -> RetentionEvent:
        event = RetentionEvent(**data)
        self.session.add(event)
        await self.session.flush()
        return event

    async def get_latest_for_customer(self, customer_id: str) -> Optional[RetentionEvent]:
        result = await self.session.execute(
            select(RetentionEvent)
            .where(RetentionEvent.customer_id == customer_id)
            .order_by(desc(RetentionEvent.triggered_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_history_for_customer(self, customer_id: str) -> list[RetentionEvent]:
        result = await self.session.execute(
            select(RetentionEvent)
            .where(RetentionEvent.customer_id == customer_id)
            .order_by(desc(RetentionEvent.triggered_at))
        )
        return list(result.scalars().all())

    async def record_outcome(
        self,
        event_key: str,
        outcome: str,
        action_taken: Optional[str] = None,
    ) -> None:
        await self.session.execute(
            update(RetentionEvent)
            .where(RetentionEvent.retention_event_id == event_key)
            .values(
                outcome=outcome,
                action_taken=action_taken,
                outcome_recorded_at=utcnow(),
            )
        )

    async def record_review(
        self,
        event_key: str,
        decision: str,
        reviewer_id: str,
        note: Optional[str] = None,
    ) -> None:
        await self.session.execute(
            update(RetentionEvent)
            .where(RetentionEvent.retention_event_id == event_key)
            .values(
                review_decision=decision,
                reviewer_id=reviewer_id,
                reviewer_note=note,
                reviewed_at=utcnow(),
            )
        )

    async def kpi_today(self) -> dict:
        today = utcnow().date()
        result = await self.session.execute(
            select(
                func.count().label("total"),
                func.count().filter(RetentionEvent.final_route == 'automated_campaign').label("campaigns"),
                func.count().filter(RetentionEvent.final_route == 'call_task').label("calls"),
                func.count().filter(RetentionEvent.final_route == 'generate_offer').label("offers"),
                func.count().filter(RetentionEvent.outcome == 'converted').label("converted"),
                func.avg(RetentionEvent.churn_score).label("avg_churn_score"),
            )
            .where(func.date(RetentionEvent.triggered_at) == today)
        )
        row = result.one()
        return {
            "total": row.total,
            "campaigns": row.campaigns,
            "call_tasks": row.calls,
            "offers_generated": row.offers,
            "converted": row.converted,
            "avg_churn_score": float(row.avg_churn_score or 0),
            "conversion_rate": row.converted / max(row.total, 1),
        }


# ── OFFER REPOSITORY ──────────────────────────────────────────────────────────

class OfferRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: dict) -> Offer:
        offer = Offer(**data)
        self.session.add(offer)
        await self.session.flush()
        return offer

    async def get_by_trigger_id(self, offer_trigger_id: str) -> Optional[Offer]:
        result = await self.session.execute(
            select(Offer).where(Offer.offer_trigger_id == offer_trigger_id)
        )
        return result.scalar_one_or_none()

    async def get_recent_for_customer(self, customer_id: str, days: int = 90) -> list[Offer]:
        from sqlalchemy import and_
        from datetime import timedelta
        cutoff = utcnow() - timedelta(days=days)
        result = await self.session.execute(
            select(Offer)
            .where(
                and_(
                    Offer.customer_id == customer_id,
                    Offer.triggered_at >= cutoff,
                )
            )
            .order_by(desc(Offer.triggered_at))
        )
        return list(result.scalars().all())

    async def record_acceptance(self, offer_trigger_id: str) -> None:
        await self.session.execute(
            update(Offer)
            .where(Offer.offer_trigger_id == offer_trigger_id)
            .values(offer_accepted_at=utcnow())
        )

    async def record_rejection(self, offer_trigger_id: str) -> None:
        await self.session.execute(
            update(Offer)
            .where(Offer.offer_trigger_id == offer_trigger_id)
            .values(offer_rejected_at=utcnow())
        )

    async def record_review(
        self,
        offer_trigger_id: str,
        decision: str,
        reviewer_id: str,
        note: Optional[str] = None,
    ) -> None:
        await self.session.execute(
            update(Offer)
            .where(Offer.offer_trigger_id == offer_trigger_id)
            .values(
                review_decision=decision,
                reviewer_id=reviewer_id,
                reviewer_note=note,
                reviewed_at=utcnow(),
            )
        )

    async def kpi_today(self) -> dict:
        today = utcnow().date()
        result = await self.session.execute(
            select(
                func.count().label("total"),
                func.count().filter(Offer.final_route == 'automated_offer').label("automated"),
                func.count().filter(Offer.final_route == 'sales_handoff').label("sales"),
                func.count().filter(Offer.final_route == 'nurturing_sequence').label("nurturing"),
                func.count().filter(Offer.offer_accepted_at.is_not(None)).label("accepted"),
                func.avg(Offer.cross_sell_score).label("avg_cross_sell"),
            )
            .where(func.date(Offer.triggered_at) == today)
        )
        row = result.one()
        return {
            "total": row.total,
            "automated": row.automated,
            "sales_handoff": row.sales,
            "nurturing": row.nurturing,
            "accepted": row.accepted,
            "avg_cross_sell_score": float(row.avg_cross_sell or 0),
            "acceptance_rate": row.accepted / max(row.total, 1),
        }
# ── LEAD REPOSITORY ────────────────────────────────────────────────────────
# Paste this class into db/repositories.py, after the OfferRepository class.
# Add Lead to the import at the top:
#   from db.models import Claim, RetentionEvent, Offer, PipelineEvent, Lead

class LeadRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: dict) -> Lead:
        """Insert a new lead after agent processing."""
        lead = Lead(**data)
        self.session.add(lead)
        await self.session.flush()
        return lead

    async def get_by_lead_id(self, lead_id: str) -> Optional[Lead]:
        result = await self.session.execute(
            select(Lead).where(Lead.lead_id == lead_id)
        )
        return result.scalar_one_or_none()

    async def get_history_for_customer(self, customer_id: str) -> list[Lead]:
        result = await self.session.execute(
            select(Lead)
            .where(Lead.customer_id == customer_id)
            .order_by(desc(Lead.received_at))
        )
        return list(result.scalars().all())

    async def update_route(
        self,
        lead_id: str,
        final_route: str,
        override: bool,
        reason: Optional[str],
    ) -> None:
        await self.session.execute(
            update(Lead)
            .where(Lead.lead_id == lead_id)
            .values(
                final_route=final_route,
                orchestrator_override=override,
                override_reason=reason,
                routed_at=utcnow(),
            )
        )

    async def record_review(
        self,
        lead_id: str,
        decision: str,
        reviewer_id: str,
        note: Optional[str] = None,
    ) -> None:
        await self.session.execute(
            update(Lead)
            .where(Lead.lead_id == lead_id)
            .values(
                review_decision=decision,
                reviewer_id=reviewer_id,
                reviewer_note=note,
                reviewed_at=utcnow(),
            )
        )

    async def record_conversion(
        self,
        lead_id: str,
        conversion_value: Optional[float] = None,
    ) -> None:
        await self.session.execute(
            update(Lead)
            .where(Lead.lead_id == lead_id)
            .values(
                converted=True,
                converted_at=utcnow(),
                conversion_value=conversion_value,
            )
        )

    async def list_pending_review(self, limit: int = 50) -> list[Lead]:
        """Borderline leads awaiting human routing decision."""
        result = await self.session.execute(
            select(Lead)
            .where(
                Lead.review_decision == 'pending',
                Lead.qualification == 'borderline',
                Lead.final_route.in_(['sales', 'nurturing']),
            )
            .order_by(
                Lead.priority.desc(),
                Lead.received_at.asc(),
            )
            .limit(limit)
        )
        return list(result.scalars().all())

    async def kpi_today(self) -> dict:
        today = utcnow().date()
        result = await self.session.execute(
            select(
                func.count().label("total"),
                func.count().filter(Lead.final_route == 'sales').label("sales"),
                func.count().filter(Lead.final_route == 'nurturing').label("nurturing"),
                func.count().filter(Lead.final_route == 'automation').label("automation"),
                func.count().filter(Lead.converted == True).label("converted"),
                func.avg(Lead.confidence).label("avg_confidence"),
                func.avg(Lead.lead_score).label("avg_score"),
            )
            .where(func.date(Lead.received_at) == today)
        )
        row = result.one()
        return {
            "total": row.total,
            "routed_sales": row.sales,
            "routed_nurturing": row.nurturing,
            "routed_automation": row.automation,
            "converted": row.converted,
            "avg_confidence": float(row.avg_confidence or 0),
            "avg_lead_score": float(row.avg_score or 0),
            "conversion_rate": row.converted / max(row.total, 1),
        }
