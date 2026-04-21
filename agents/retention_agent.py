"""
INSURE.AI — Retention Agent
FastAPI endpoint: POST /agent/retention

ADR-002 Phase 2 changes:
- Pydantic field retention_event_id renamed to retention_id
- Backend fallback generator: if caller omits retention_id, generates
  RET-{customer_id}-{epoch_ms} so entity_id always carries a Business-Key
- CRITICAL BUG FIX: event_repo.log(entity_id=...) now uses retention_id
  (was customer_id, breaking joinability of audit trail to fact table)
- Encoding cleanup (Mojibake removed)
"""

import time
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
import anthropic
import json
import logging
from datetime import datetime

from db.database import db_session
from db.repositories import RetentionRepository, EventRepository

logger = logging.getLogger(__name__)

# ── MODELS ───────────────────────────────────────────────────────────────────

class RetentionInput(BaseModel):
    customer_id: str
    retention_id: Optional[str] = None
    trigger_type: str                # "login_anomaly", "portal_activity", "renewal_upcoming",
                                     # "competitor_signal", "support_contact", "payment_late", "manual"
    trigger_detail: Optional[str] = None
    customer_name: Optional[str] = None
    segment: Optional[str] = None
    customer_since_years: Optional[int] = None
    annual_premium: Optional[float] = None
    policy_count: Optional[int] = None
    policy_types: List[str] = []
    last_claim_months_ago: Optional[int] = None
    total_claims_ever: Optional[int] = None
    nps_score: Optional[int] = None
    renewal_due_days: Optional[int] = None
    portal_logins: Optional[int] = None
    contract_views: Optional[int] = None
    competitor_portal_visits: Optional[int] = None
    support_contacts: Optional[int] = None
    email_open_rate: Optional[float] = None
    customer_ltv: Optional[float] = None


class RetentionResult(BaseModel):
    customer_id: str
    retention_id: str
    churn_score: float
    churn_risk_level: str            # "low", "medium", "high", "critical"
    confidence: float
    recommended_route: str           # "automated_campaign", "call_task", "generate_offer", "no_action"
    offer_type: Optional[str]
    offer_value_suggestion: Optional[str]
    campaign_segment: Optional[str]
    priority_score: int
    flags: List[dict]
    reasoning: str
    suggested_next_steps: List[str]
    processed_at: str

# ── SYSTEM PROMPT ────────────────────────────────────────────────────────────

RETENTION_SYSTEM_PROMPT = """You are the Retention Agent for INSURE.AI, an intelligent insurance automation platform.

Your job is to analyze customer churn risk signals and produce a structured JSON retention recommendation.

CHURN SCORE CALCULATION:
Base churn score starts at 0.10. Adjust based on signals:

INCREASING churn risk:
- competitor_portal_visits >= 3 in 30 days: +0.25
- contract_views >= 4 in 30 days: +0.20
- renewal_due_days <= 60: +0.15
- support_contacts >= 2 in 30 days: +0.10
- payment_late trigger: +0.20
- nps_score < 0: +0.15
- nps_score < -30: +0.10 (additional)
- email_open_rate < 0.10: +0.08
- no claims ever (might be shopping around): +0.05

DECREASING churn risk:
- customer_since_years >= 10: -0.10
- customer_since_years >= 5: -0.05
- policy_count >= 3: -0.08
- nps_score > 50: -0.10
- last_claim settled favorably: -0.05 (use judgment)

CHURN RISK LEVELS:
- "critical": churn_score >= 0.80
- "high": churn_score 0.60-0.79
- "medium": churn_score 0.35-0.59
- "low": churn_score < 0.35

ROUTING RULES:
- "no_action": churn_score < 0.20, no renewal upcoming
- "automated_campaign": churn_score 0.20-0.45, standard segment
- "generate_offer": churn_score 0.35-0.70 OR renewal_due_days <= 90
- "call_task": churn_score >= 0.60 OR high LTV customer (annual_premium > CHF 5000) OR customer_since_years >= 8

OFFER TYPES:
- "loyalty_discount": customer_since_years >= 5, no recent issues
- "product_upgrade": missing coverage gaps exist, upsell opportunity
- "bundle_deal": policy_count < 3, can consolidate
- "premium_waiver": critical churn risk, high LTV, as last resort

PRIORITY SCORE (1-100):
priority_score = min(100, round(churn_score * 70 + (annual_premium / 500) + (1 / max(1, renewal_due_days or 365) * 500)))

Always respond with valid JSON only. No markdown, no preamble.

JSON Schema:
{
  "churn_score": 0.00,
  "churn_risk_level": "low|medium|high|critical",
  "confidence": 0.00,
  "recommended_route": "no_action|automated_campaign|generate_offer|call_task",
  "offer_type": null or "loyalty_discount|product_upgrade|bundle_deal|premium_waiver",
  "offer_value_suggestion": null or "e.g. 2 months premium-free",
  "campaign_segment": null or "e.g. private_55plus_renewal",
  "priority_score": 0,
  "flags": [
    {"severity": "danger|warn|info", "label": "...", "detail": "..."}
  ],
  "reasoning": "...",
  "suggested_next_steps": ["...", "..."]
}"""

# ── HELPERS ──────────────────────────────────────────────────────────────────

def generate_retention_id(customer_id: str) -> str:
    """
    Backend fallback: synthesize a Business-Key when caller omits retention_id.
    Pattern: RET-{customer_id}-{epoch_ms}
    Example: RET-CUST-9001-1745234567890
    """
    return f"RET-{customer_id}-{int(time.time() * 1000)}"

# ── AGENT LOGIC ──────────────────────────────────────────────────────────────

client = anthropic.Anthropic()

def build_retention_prompt(data: RetentionInput) -> str:
    parts = [
        f"CUSTOMER ID: {data.customer_id}",
        f"Trigger: {data.trigger_type}" + (f" — {data.trigger_detail}" if data.trigger_detail else ""),
    ]
    if data.customer_name:
        parts.append(f"Name: {data.customer_name} | Segment: {data.segment or 'unknown'}")
    if data.customer_since_years is not None:
        parts.append(f"Customer since: {data.customer_since_years} years")
    if data.annual_premium is not None:
        parts.append(f"Annual premium: CHF {data.annual_premium:,.0f}")
    if data.customer_ltv is not None:
        parts.append(f"Estimated LTV: CHF {data.customer_ltv:,.0f}")
    if data.policy_types:
        parts.append(f"Policies ({data.policy_count}): {', '.join(data.policy_types)}")
    if data.renewal_due_days is not None:
        parts.append(f"Renewal due in: {data.renewal_due_days} days")
    if data.nps_score is not None:
        parts.append(f"NPS score: {data.nps_score}")
    if data.total_claims_ever is not None:
        parts.append(f"Total claims: {data.total_claims_ever}" +
                     (f" | Last: {data.last_claim_months_ago} months ago" if data.last_claim_months_ago else ""))
    parts.append("\nBEHAVIORAL SIGNALS (last 30 days):")
    if data.portal_logins is not None:
        parts.append(f"  Portal logins: {data.portal_logins}")
    if data.contract_views is not None:
        parts.append(f"  Contract views: {data.contract_views}")
    if data.competitor_portal_visits is not None:
        parts.append(f"  Competitor portal visits: {data.competitor_portal_visits}")
    if data.support_contacts is not None:
        parts.append(f"  Support contacts: {data.support_contacts}")
    if data.email_open_rate is not None:
        parts.append(f"  Email open rate: {data.email_open_rate:.0%}")
    return "\n".join(parts)


async def run_retention_agent(data: RetentionInput, retention_id: str) -> RetentionResult:
    prompt = build_retention_prompt(data)

    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1024,
        system=RETENTION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = message.content[0].text.strip()

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        import re
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            parsed = json.loads(match.group())
        else:
            raise ValueError(f"Agent returned non-JSON: {raw[:200]}")

    return RetentionResult(
        customer_id=data.customer_id,
        retention_id=retention_id,
        churn_score=parsed["churn_score"],
        churn_risk_level=parsed["churn_risk_level"],
        confidence=parsed["confidence"],
        recommended_route=parsed["recommended_route"],
        offer_type=parsed.get("offer_type"),
        offer_value_suggestion=parsed.get("offer_value_suggestion"),
        campaign_segment=parsed.get("campaign_segment"),
        priority_score=parsed.get("priority_score", 50),
        flags=parsed.get("flags", []),
        reasoning=parsed["reasoning"],
        suggested_next_steps=parsed.get("suggested_next_steps", []),
        processed_at=datetime.utcnow().isoformat() + "Z"
    )

# ── FASTAPI ROUTES ───────────────────────────────────────────────────────────

def register_routes(app: FastAPI):

    @app.post("/agent/retention", response_model=RetentionResult, tags=["Agents"])
    async def assess_retention(
        data: RetentionInput,
        session: AsyncSession = Depends(db_session),
    ):
        """
        Retention Agent.
        Computes churn score and recommends retention action.
        Persists result to DB.
        """
        # ADR-002: Generate Business-Key if caller didn't supply one.
        # Guarantees entity_id in pipeline_events is always joinable to retentions.
        retention_id = data.retention_id or generate_retention_id(data.customer_id)

        try:
            result = await run_retention_agent(data, retention_id)

            # ── Persist to DB ──────────────────────────────────────────────
            retention_repo = RetentionRepository(session)
            event_repo     = EventRepository(session)

            await retention_repo.create({
                "retention_id":           retention_id,
                "customer_id":            data.customer_id,
                "trigger_type":           data.trigger_type,
                "trigger_detail":         data.trigger_detail,
                "churn_score":            result.churn_score,
                "churn_risk_level":       result.churn_risk_level,
                "confidence":             result.confidence,
                "offer_type":             result.offer_type,
                "offer_value_suggestion": result.offer_value_suggestion,
                "campaign_segment":       result.campaign_segment,
                "priority_score":         result.priority_score,
                "agent_reasoning":        result.reasoning,
                "flags":                  result.flags,
                "recommended_route":      result.recommended_route,
                "final_route":            result.recommended_route,
                "agent_processed_at":     datetime.utcnow(),
                "routed_at":              datetime.utcnow(),
                "customer_snapshot": {
                    "customer_name":          data.customer_name,
                    "segment":                data.segment,
                    "customer_since_years":   data.customer_since_years,
                    "annual_premium":         data.annual_premium,
                    "policy_count":           data.policy_count,
                    "policy_types":           data.policy_types,
                    "customer_ltv":           data.customer_ltv,
                    "renewal_due_days":       data.renewal_due_days,
                    "nps_score":              data.nps_score,
                },
            })

            # ADR-002 D5: entity_id MUST be the Business-Key (retention_id),
            # never customer_id. This is the bug fix that motivated ADR-002.
            await event_repo.log(
                pipeline=    "retention",
                entity_id=   retention_id,
                entity_type= "retention",
                event_type=  "agent_processed",
                payload={
                    "retention_id":     retention_id,
                    "customer_id":      data.customer_id,
                    "churn_score":      result.churn_score,
                    "churn_risk_level": result.churn_risk_level,
                    "route":            result.recommended_route,
                    "confidence":       result.confidence,
                },
            )

            logger.info(
                f"[Retention] {retention_id} ({data.customer_id}) -> "
                f"churn={result.churn_score:.2f} ({result.churn_risk_level}) "
                f"-> {result.recommended_route}"
            )
            return result

        except Exception as e:
            logger.error(f"[Retention] Error processing {retention_id} ({data.customer_id}): {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/agent/retention/health", tags=["Health"])
    async def retention_health():
        return {"agent": "retention", "status": "ok"}
