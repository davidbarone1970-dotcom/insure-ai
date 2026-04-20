"""
INSURE.AI — Claims Assessment Agent
FastAPI endpoint: POST /agent/claims
"""

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
import anthropic
import json
import logging
from datetime import datetime

from db.database import db_session
from db.repositories import ClaimRepository, EventRepository

logger = logging.getLogger(__name__)

# ── MODELS ────────────────────────────────────────────────────────────────

class ClaimInput(BaseModel):
    claim_id: str
    customer_id: str
    policy_id: str
    claim_type: str                  # "fire", "water", "theft", "accident", "fraud_suspected"
    claim_amount: float
    currency: str = "CHF"
    description: str
    submission_channel: str          # "web", "phone", "broker", "email"
    attachments: List[str] = []
    customer_since_years: Optional[int] = None
    previous_claims_count: Optional[int] = None
    previous_claims_total: Optional[float] = None
    policy_type: Optional[str] = None
    policy_annual_premium: Optional[float] = None
    policy_coverage_limit: Optional[float] = None
    customer_ltv: Optional[float] = None

class ClaimResult(BaseModel):
    claim_id: str
    classification: str              # "standard", "complex", "fraud_suspected", "catastrophic"
    priority: str                    # "low", "medium", "high", "critical"
    confidence: float
    recommended_route: str           # "auto_process", "manual_review", "escalation", "siu_referral"
    fraud_score: float
    estimated_payout: Optional[float]
    flags: List[dict]
    reasoning: str
    suggested_next_steps: List[str]
    processed_at: str

# ── SYSTEM PROMPT ─────────────────────────────────────────────────────────

CLAIMS_SYSTEM_PROMPT = """You are the Claims Assessment Agent for INSURE.AI, an intelligent insurance automation platform.

Your job is to analyze incoming insurance claims and produce a structured JSON assessment.

CLASSIFICATION RULES:
- "standard": Clear-cut claim, within normal parameters, no anomalies
- "complex": Coverage ambiguity, high value, or requires specialist input
- "fraud_suspected": Statistical anomalies, inconsistencies, or behavioral red flags
- "catastrophic": Large-scale event, major property loss, or life-affecting claim

PRIORITY RULES:
- "critical": Fraud suspected OR claim > CHF 100k OR life/health impact
- "high": Claim > CHF 50k OR multiple red flags OR repeat claimant (3+ in 24 months)
- "medium": Claim CHF 10k–50k OR coverage ambiguity OR missing documentation
- "low": Routine claim < CHF 10k, clean history, full documentation

ROUTING RULES:
- "auto_process": Standard + low/medium priority, confidence > 0.85, no fraud signal
- "manual_review": Complex OR confidence 0.65–0.85 OR coverage disputes
- "escalation": High/critical priority, major claims needing senior adjuster
- "siu_referral": Fraud score > 0.75 → Special Investigations Unit

FRAUD INDICATORS (increase fraud_score):
- Multiple claims within 18 months (each +0.15)
- Claim value > 120% of insured asset market value (+0.30)
- New policy < 12 months old with large claim (+0.20)
- Claim filed shortly after premium increase (+0.15)
- Inconsistent or vague description (+0.10)
- No supporting documentation (+0.10)

Always respond with valid JSON only. No markdown, no preamble.

JSON Schema:
{
  "classification": "standard|complex|fraud_suspected|catastrophic",
  "priority": "low|medium|high|critical",
  "confidence": 0.00,
  "recommended_route": "auto_process|manual_review|escalation|siu_referral",
  "fraud_score": 0.00,
  "estimated_payout": null or number,
  "flags": [
    {"severity": "danger|warn|info", "label": "...", "detail": "..."}
  ],
  "reasoning": "...",
  "suggested_next_steps": ["...", "..."]
}"""

# ── AGENT LOGIC ───────────────────────────────────────────────────────────

client = anthropic.Anthropic()

def build_claim_prompt(claim: ClaimInput) -> str:
    parts = [
        f"CLAIM ID: {claim.claim_id}",
        f"Customer ID: {claim.customer_id} | Policy: {claim.policy_id}",
        f"Type: {claim.claim_type} | Amount: {claim.currency} {claim.claim_amount:,.0f}",
        f"Channel: {claim.submission_channel}",
        f"Description: {claim.description}",
        f"Attachments: {len(claim.attachments)} documents",
    ]
    if claim.customer_since_years is not None:
        parts.append(f"Customer since: {claim.customer_since_years} years")
    if claim.previous_claims_count is not None:
        parts.append(
            f"Previous claims: {claim.previous_claims_count} "
            f"(total CHF {claim.previous_claims_total or 0:,.0f})"
        )
    if claim.policy_type:
        parts.append(f"Policy type: {claim.policy_type}")
    if claim.policy_coverage_limit:
        parts.append(f"Coverage limit: CHF {claim.policy_coverage_limit:,.0f}")
    if claim.policy_annual_premium:
        parts.append(f"Annual premium: CHF {claim.policy_annual_premium:,.0f}")
    if claim.customer_ltv:
        parts.append(f"Customer LTV: CHF {claim.customer_ltv:,.0f}")
    return "\n".join(parts)


async def run_claims_agent(claim: ClaimInput) -> ClaimResult:
    prompt = build_claim_prompt(claim)

    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1024,
        system=CLAIMS_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = message.content[0].text.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        import re
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            data = json.loads(match.group())
        else:
            raise ValueError(f"Agent returned non-JSON: {raw[:200]}")

    return ClaimResult(
        claim_id=claim.claim_id,
        classification=data["classification"],
        priority=data["priority"],
        confidence=data["confidence"],
        recommended_route=data["recommended_route"],
        fraud_score=data["fraud_score"],
        estimated_payout=data.get("estimated_payout"),
        flags=data.get("flags", []),
        reasoning=data["reasoning"],
        suggested_next_steps=data.get("suggested_next_steps", []),
        processed_at=datetime.utcnow().isoformat() + "Z"
    )

# ── FASTAPI ROUTES ────────────────────────────────────────────────────────

def register_routes(app: FastAPI):

    @app.post("/agent/claims", response_model=ClaimResult, tags=["Agents"])
    async def assess_claim(
        claim: ClaimInput,
        session: AsyncSession = Depends(db_session),
    ):
        """
        Claims Assessment Agent.
        Receives enriched claim data, returns classification + routing decision.
        Persists result to DB.
        """
        try:
            result = await run_claims_agent(claim)

            # ── Persist to DB ──────────────────────────────────────────
            claim_repo = ClaimRepository(session)
            event_repo = EventRepository(session)

            await claim_repo.create({
                "claim_id":              claim.claim_id,
                "customer_id":           claim.customer_id,
                "policy_id":             claim.policy_id,
                "claim_type":            claim.claim_type,
                "claim_amount":          claim.claim_amount,
                "currency":              claim.currency,
                "description":           claim.description,
                "submission_channel":    claim.submission_channel,
                "classification":        result.classification,
                "priority":              result.priority,
                "confidence":            result.confidence,
                "fraud_score":           result.fraud_score,
                "estimated_payout":      result.estimated_payout,
                "agent_reasoning":       result.reasoning,
                "flags":                 result.flags,
                "recommended_route":     result.recommended_route,
                "final_route":           result.recommended_route,
                "agent_processed_at":    datetime.utcnow(),
                "routed_at": datetime.utcnow(),
                "customer_snapshot": {
                    "customer_since_years":   claim.customer_since_years,
                    "previous_claims_count":  claim.previous_claims_count,
                    "previous_claims_total":  claim.previous_claims_total,
                    "policy_type":            claim.policy_type,
                    "policy_annual_premium":  claim.policy_annual_premium,
                    "policy_coverage_limit":  claim.policy_coverage_limit,
                    "customer_ltv":           claim.customer_ltv,
                },
            })

            await event_repo.log(
                pipeline=    "claims",
                entity_id=   claim.claim_id,
                entity_type= "claim",
                event_type=  "agent_processed",
                payload={
                    "classification": result.classification,
                    "route":          result.recommended_route,
                    "priority":       result.priority,
                    "confidence":     result.confidence,
                    "fraud_score":    result.fraud_score,
                },
            )

            logger.info(
                f"[Claims] {claim.claim_id} → {result.recommended_route} "
                f"(confidence={result.confidence:.2f}, fraud={result.fraud_score:.2f})"
            )
            return result

        except Exception as e:
            logger.error(f"[Claims] Error processing {claim.claim_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/agent/claims/health", tags=["Health"])
    async def claims_health():
        return {"agent": "claims", "status": "ok"}
